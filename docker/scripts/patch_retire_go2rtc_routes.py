#!/usr/bin/env python3
"""Retire every go2rtc-proxied nginx location and replace `/live/mse/api/ws`'s
function with a route to G2's own fMP4-over-WebSocket listener (corvette
issue #12, N2).

D-6 fully replaces go2rtc -- not only its live-view role -- so every location
in the donor's nginx.conf that proxies to the `go2rtc` upstream is
permanently dead once F1 (this repo, go2rtc's s6-overlay startup disabled)
and K1 (corvette, the manifest cutover) land: `/live/mse/api/ws`,
`/live/webrtc/api/ws`, `/live/webrtc/webrtc.html`, `/api/go2rtc/api`, and
`/api/go2rtc/webrtc`. Confirmed directly against
`tests/nginx-parity/vendor/nginx.conf` (corvette): exactly these five proxy
to `go2rtc`, and no others do -- `/live/jsmpeg/` proxies to Frigate's own
`jsmpeg` upstream and is untouched by this script.

Four of the five have no replacement: nothing in this deployment still needs
a WebRTC signalling path or a go2rtc version/candidate passthrough once
go2rtc itself is gone. The fifth, `/live/mse/api/ws`, is different -- the
grid tile's live view (corvette's `crates/corvette-ui/src/live_view.rs`,
item U1) depends on a working replacement existing, so this script also adds
`location /live/mse/ws/`, proxying to G2 (`corvette-media-bridge`'s
fMP4-over-WebSocket packager, `crates/corvette-media-bridge/src/
ws_repackager.rs`), a sibling container in this pod (K1) reachable at
127.0.0.1 the same way jsmpeg and G3's HLS listener already are (port 8555,
`crates/corvette-media-bridge/src/config.rs`'s `fmp4_ws_bind_addr`). The
trailing slash on both this location and its `proxy_pass` is nginx's own
standard prefix-stripping convention (matching `/live/hls/`'s own precedent,
N1): G2's own per-camera path convention is the request path with its
leading slash trimmed (`ws_repackager::handle_connection`), so once nginx
strips the `/live/mse/ws/` prefix, G2 receives exactly the camera name it
already expects. `crates/corvette-ui/src/live_view.rs`'s own
`MEDIA_BRIDGE_WS_PATH_PREFIX` constant names this exact prefix and depends on
this script adding it.

Chained AFTER `patch_pkg_location.py` and `patch_live_hls_location.py` (N1)
in the Dockerfile -- this script's own `EXPECTED_MD5` is the md5 of the
donor's nginx.conf with both of those patches already applied, not the
pristine donor's, because the anchor text this script matches (the comment
immediately preceding `/live/mse/api/ws`) sits right after N1's own inserted
`/live/hls/` block.

Fails loudly, before touching anything, if the input does not match the
expected post-N1 md5 -- the same donor-drift guard shape
`patch_pkg_location.py`/`patch_live_hls_location.py` established.

Takes an optional path argument naming the file to patch, defaulting to the
real location inside the image, so the guard and the substitution can be
exercised against a fixture copy without writing to a container filesystem.
"""

import hashlib
import sys
from pathlib import Path

DEFAULT_TARGET = Path("/usr/local/nginx/conf/nginx.conf")

# md5 of docker/main/rootfs/usr/local/nginx/conf/nginx.conf at 3d4dd3ac4
# (Frigate v0.17.2, the same revision tests/nginx-parity/vendor/PROVENANCE,
# patch_pkg_location.py's own EXPECTED_MD5, and patch_live_hls_location.py's
# own EXPECTED_MD5 are pinned to, in corvette), AFTER both
# patch_pkg_location.py's /pkg/ location AND patch_live_hls_location.py's
# /live/hls/ location have already been inserted -- this script runs third in
# the Dockerfile, against that chained output, not against the pristine donor
# file. Recorded by applying both prior scripts, in order, to a scratch copy
# of the pristine donor and hashing the result. Re-recorded after
# patch_live_hls_location.py stopped giving corvette_hls its own `keepalive`
# line (see that script's own doc for why: G3's HLS listener never supports
# keep-alive, and nginx pooling connections to it anyway caused live 503s).
# Re-recorded again after patch_live_hls_location.py added explicit
# `Connection: close`/empty `Upgrade` headers to its own /live/hls/ location
# (see that script's own doc's fourth-incident section: the keepalive
# removal alone traded the 503s for a worse 20-30 second stall).
# Re-recorded a third time after patch_live_hls_location.py restored
# `keepalive 1024;` on `corvette_hls` (same doc): removing it had been the
# actual regression, not the fix -- corvette_hls was the only upstream in
# this whole file without one.
EXPECTED_MD5 = "8961358cf897c66450268570e2964ac3"

OLD_UPSTREAM = """    upstream corvette_hls {
        server 127.0.0.1:8556;
        keepalive 1024;
    }

    include go2rtc_upstream.conf;
"""

# Declared alongside `corvette_hls` (N1), the same fixed-port, non-user-
# configurable style -- G2's fMP4-over-WebSocket port has no user-facing
# configuration point either, so it belongs with `corvette_hls`'s style, not
# go2rtc's own Frigate-templated include. `include go2rtc_upstream.conf;` is
# left in place even though nothing proxies to it anymore after this script
# runs: it is a static file the donor image already ships (unconditionally,
# not rendered from user config), an unreferenced nginx `upstream` block is
# not an error, and removing it is not something this item's Do steps ask
# for -- go2rtc's own removal from this image is F1's item, not this one's.
#
# `corvette_fmp4_ws` carries its own `keepalive 1024;` for the same reason
# `corvette_hls` now does (see `upstream corvette_hls`'s own doc in
# patch_live_hls_location.py): G2's WebSocket listener holds one long-lived
# connection per viewer for as long as the tile stays mounted
# (`ws_repackager.rs`), nothing like G3's one-request-then-close HLS server,
# so nginx pooling idle keep-alive connections to it was never in question --
# `corvette_hls`'s own "don't reuse a connection to a backend that closes it"
# guarantee comes from its `/live/hls/` location's explicit `Connection:
# close` header instead, not from omitting `keepalive` at the upstream level.
NEW_UPSTREAM = """    upstream corvette_hls {
        server 127.0.0.1:8556;
        keepalive 1024;
    }

    upstream corvette_fmp4_ws {
        server 127.0.0.1:8555;
        keepalive 1024;
    }

    include go2rtc_upstream.conf;
"""

# The full contiguous run of all five go2rtc-proxied locations, immediately
# following N1's own /live/hls/ insertion -- every one of Premise's five
# confirmed hits, and nothing else, so this replace can neither miss one nor
# accidentally reach past them into the unrelated /api/*.(jpg|...) block that
# follows.
OLD_LOCATION = """        # frigate lovelace card uses this path
        location /live/mse/api/ws {
            include auth_request.conf;
            limit_except GET {
                deny  all;
            }
            proxy_pass http://go2rtc/api/ws;
            include proxy.conf;
        }

        location /live/webrtc/api/ws {
            include auth_request.conf;
            limit_except GET {
                deny  all;
            }
            proxy_pass http://go2rtc/api/ws;
            include proxy.conf;
        }

        # pass through go2rtc player
        location /live/webrtc/webrtc.html {
            include auth_request.conf;
            limit_except GET {
                deny  all;
            }
            proxy_pass http://go2rtc/webrtc.html;
            include proxy.conf;
        }

        # frontend uses this to fetch the version
        location /api/go2rtc/api {
            include auth_request.conf;
            limit_except GET {
                deny  all;
            }
            proxy_pass http://go2rtc/api;
            include proxy.conf;
        }

        # integration uses this to add webrtc candidate
        location /api/go2rtc/webrtc {
            include auth_request.conf;
            limit_except POST {
                deny  all;
            }
            proxy_pass http://go2rtc/api/webrtc;
            include proxy.conf;
        }
"""

# Only `/live/mse/api/ws` gets a replacement -- the other four (WebRTC
# signalling, the go2rtc version/candidate passthrough) have no successor
# anywhere in this plan; nothing left in this deployment calls them.
# `limit_except GET` and `include auth_request.conf;` match every other
# proxied /live/* location's own convention in this file.
NEW_LOCATION = """        # corvette issue #12 (N2): replaces /live/mse/api/ws's function.
        # G2's fMP4-over-WebSocket packager, a sibling container in this pod
        # (K1), reachable at 127.0.0.1 the same way jsmpeg and G3's HLS
        # listener already are. Trailing slash on both sides strips this
        # prefix before proxying, so G2's own listener sees exactly its own
        # per-camera path convention (the request path, trimmed of its
        # leading slash, names the camera) -- see corvette's own
        # crates/corvette-media-bridge/src/ws_repackager.rs module doc and
        # crates/corvette-ui/src/live_view.rs's own
        # MEDIA_BRIDGE_WS_PATH_PREFIX, which names this exact prefix.
        location /live/mse/ws/ {
            include auth_request.conf;
            limit_except GET {
                deny  all;
            }
            proxy_pass http://corvette_fmp4_ws/;
            include proxy.conf;
        }
"""


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGET
    raw = target.read_bytes()
    actual_md5 = hashlib.md5(raw).hexdigest()

    source = raw.decode("utf-8")
    if NEW_UPSTREAM in source and NEW_LOCATION in source:
        print("patch_retire_go2rtc_routes: already applied")
        return 0

    if actual_md5 != EXPECTED_MD5:
        print(
            f"patch_retire_go2rtc_routes: {target} is md5 {actual_md5}, but "
            "the expected input (donor nginx.conf from Frigate "
            "3d4dd3ac4/v0.17.2, with patch_pkg_location.py's /pkg/ location "
            "and patch_live_hls_location.py's /live/hls/ location already "
            f"applied) is {EXPECTED_MD5} -- either FRIGATE_IMAGE has drifted "
            "from the revision this patch was written against, or this "
            "script no longer runs immediately after patch_live_hls_location.py "
            "in the Dockerfile. Re-verify all three insertion points by hand, "
            "update EXPECTED_MD5 here (and patch_pkg_location.py's own "
            "EXPECTED_MD5, patch_live_hls_location.py's own EXPECTED_MD5, "
            "plus tests/nginx-parity/vendor/PROVENANCE in corvette, if the "
            "donor itself changed) together, then retry.",
            file=sys.stderr,
        )
        return 1

    if OLD_UPSTREAM not in source or OLD_LOCATION not in source:
        # Unreachable if the md5 check above passed -- md5 is whole-file
        # identity, so a match implies both OLD anchors are present. Kept as
        # an explicit, named failure rather than a silent no-op if that
        # invariant is ever wrong, matching patch_pkg_location.py's and
        # patch_live_hls_location.py's own precedent for this exact
        # situation.
        print(
            "patch_retire_go2rtc_routes: nginx.conf's md5 matched but one of "
            "this patch's own anchor blocks (the corvette_hls upstream "
            "group, or the five go2rtc-proxied locations) was not found "
            "verbatim -- the file and the recorded md5 disagree with each "
            "other",
            file=sys.stderr,
        )
        return 1

    source = source.replace(OLD_UPSTREAM, NEW_UPSTREAM)
    source = source.replace(OLD_LOCATION, NEW_LOCATION)
    target.write_text(source, encoding="utf-8")
    print(
        "patch_retire_go2rtc_routes: five go2rtc-proxied locations removed, "
        "/live/mse/ws/ inserted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
