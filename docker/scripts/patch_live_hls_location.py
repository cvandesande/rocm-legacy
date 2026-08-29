#!/usr/bin/env python3
"""Add a `/live/hls/` nginx location proxying to G3's HLS/LL-HLS packager
(corvette issue #12, N1, resolving OPEN-2).

D-6 fully replaces go2rtc, including its own HLS-adjacent role, so the
expanded-view fallback this deployment's UI reaches for when its primary
transport is unavailable now needs a real, non-go2rtc backend. Item G3
(`corvette-media-bridge`, `crates/corvette-media-bridge/src/hls.rs`) is that
backend: a small per-camera HLS/LL-HLS packager reading the same in-process
frame stream every other role in that crate already reads from, run as a
sibling container in this pod (issue #12 item K1). Its own module doc names
the exact contract this patch proxies to: `GET /<camera name>/playlist.m3u8`,
`GET /<camera name>/init.mp4`, and `GET /<camera name>/segment-<sequence>.m4s`,
served on `127.0.0.1:8556` (`crates/corvette-media-bridge/src/config.rs`'s
`hls_bind_addr`, reachable at `127.0.0.1` the same way `jsmpeg` and `go2rtc`
already are here -- every container in this pod shares one network namespace,
confirmed directly against `corvette`'s own K1 manifest draft, which declares
this pod's other same-purpose sibling ports, e.g. the `rtsp` containerPort,
the same way). The trailing slash on both this location and its `proxy_pass`
is nginx's own standard prefix-stripping convention (matching the donor's own
`/live/jsmpeg/` block immediately above the insertion point), so G3's listener
is handed exactly its own path convention with the `/live/hls/` prefix already
removed -- it never needs to know that prefix exists.

Chained AFTER `patch_pkg_location.py` in the Dockerfile (this script's own
`EXPECTED_MD5` is the md5 of the donor's nginx.conf with that patch already
applied, not the pristine donor's) -- both patches touch disjoint regions of
the same file (the `/pkg/` insertion is nested inside `location /`, far from
the `upstream`/`location /live/*` block this patch touches), so ordering
between them is not itself load-bearing, but the guard below only recognizes
the one order this Dockerfile actually runs.

Fails loudly, before touching anything, if the input does not match the
expected post-`/pkg/`-patch md5 -- the same donor-drift guard shape
`patch_pkg_location.py` established (issue #2, D1), extended here for this
item's own hunk rather than folded into that script, so each patch keeps its
own anchor text and its own recorded md5.

Takes an optional path argument naming the file to patch, defaulting to the
real location inside the image, so the guard and the substitution can be
exercised against a fixture copy without writing to a container filesystem.
"""

import hashlib
import sys
from pathlib import Path

DEFAULT_TARGET = Path("/usr/local/nginx/conf/nginx.conf")

# md5 of docker/main/rootfs/usr/local/nginx/conf/nginx.conf at 3d4dd3ac4
# (Frigate v0.17.2, the same revision tests/nginx-parity/vendor/PROVENANCE and
# patch_pkg_location.py's own EXPECTED_MD5 are pinned to, in corvette), AFTER
# patch_pkg_location.py's own /pkg/ location has already been inserted -- this
# script runs second in the Dockerfile, against that script's own output, not
# against the pristine donor file. Recorded by applying patch_pkg_location.py
# to a scratch copy of the pristine donor and hashing the result.
EXPECTED_MD5 = "99c599fe0c13ff3efd6a5a35d49042a1"

OLD_UPSTREAM = """    upstream jsmpeg {
        server 127.0.0.1:8082;
        keepalive 1024;
    }

    include go2rtc_upstream.conf;
"""

# Declared as its own named upstream, matching `jsmpeg`'s own precedent
# immediately above (a fixed, non-user-configurable port declared directly in
# this static file) rather than go2rtc's pattern (a separate
# Frigate-templated include, because go2rtc's own API port is user
# configurable) -- G3's HLS port has no such user-facing configuration point,
# so it belongs with jsmpeg's style, not go2rtc's.
#
# Carries `keepalive 1024;`, the same as every other upstream this donor
# nginx.conf declares (`jsmpeg` above, plus `frigate_api`/`mqtt_ws`/
# `corvette_fmp4_ws` elsewhere in this file) -- this file has no precedent
# anywhere for a `keepalive`-less upstream proxied under `proxy.conf`'s own
# unconditional `Connection: Upgrade` header (see `proxy.conf`'s own doc, or
# this script's own history), and `corvette_hls` genuinely tried being the
# first: G3's own HLS listener (crates/corvette-media-bridge/src/hls.rs,
# "Named simplifications") reads exactly one request per TCP connection and
# always closes afterward, so an earlier revision of this script omitted
# `keepalive` here entirely, reasoning that a keepalive pool against a
# backend that always closes its connection would eventually hand out a dead
# socket. That reasoning was correct about the failure mode (503s were
# confirmed live under hls.js's own retry pattern) but wrong about the fix:
# removing `keepalive` here -- the one upstream in this entire file without
# it -- traded the intermittent 503s for something worse, confirmed live and
# repeatedly: authenticated requests through the real deployment's own
# external ingress stalled 3-30 seconds (variable, not a fixed timeout)
# before failing, while the same backend answered in under 1ms whenever it
# was reached by a path that bypassed real session auth (direct, loopback,
# or the in-cluster Service) -- ruling out G3 itself, and pointing at
# something in nginx's own handling of a `keepalive`-less upstream under
# this donor's blanket Upgrade-forcing specifically, still unproven at the
# packet level but the one variable that reliably flips the symptom on and
# off. `keepalive` is restored here to match every sibling upstream's own
# shape; the actual "don't reuse a connection to a backend that always
# closes it" fix now lives where it belongs -- the `/live/hls/` location's
# own explicit `Connection: close`/empty `Upgrade` headers below, added
# alongside this change, which tell nginx per request not to pool this
# connection regardless of what the upstream group allows.
NEW_UPSTREAM = """    upstream jsmpeg {
        server 127.0.0.1:8082;
        keepalive 1024;
    }

    upstream corvette_hls {
        server 127.0.0.1:8556;
        keepalive 1024;
    }

    include go2rtc_upstream.conf;
"""

OLD_LOCATION = """        location /live/jsmpeg/ {
            include auth_request.conf;
            proxy_pass http://jsmpeg/;
            include proxy.conf;
        }

        # frigate lovelace card uses this path
        location /live/mse/api/ws {
"""

# Grouped immediately after /live/jsmpeg/ -- the other non-go2rtc-backed
# /live/* route -- rather than among the three go2rtc-backed ones below,
# since this location shares nothing with go2rtc (D-6 removes it entirely;
# see corvette issue #12 item N2). `limit_except GET` matches the
# `/live/mse/api/ws` and `/live/webrtc/*` blocks' own convention (this
# listener, like those, only ever needs to answer GET); `/live/jsmpeg/`
# itself omits it, but that is that route's own upstream's own concern, not a
# reason to omit it here. `include auth_request.conf;` matches every other
# proxied location in this file -- this route carries no exception from the
# deployment's own auth gate.
#
# The two `proxy_set_header` lines after `include proxy.conf;` override that
# shared file's own unconditional `proxy_set_header Connection "Upgrade";
# proxy_set_header Upgrade $http_upgrade;` -- forced on every proxied
# location in this donor nginx.conf, not just real Upgrade requests, and not
# gated behind the `map $http_upgrade $connection_upgrade` pattern a correct
# WebSocket-proxying config uses. G3 never performs a real protocol upgrade,
# so forcing nginx to consider one is never correct here; these two lines
# tell it, per request, that this is a plain non-upgradeable exchange.
#
# This alone was tried first, paired with removing `keepalive` from
# `corvette_hls` entirely (this file's own earlier history). That combination
# did fix the original 503s but traded them for something worse -- confirmed
# directly, twice, against a live redeploy of exactly that combination, not
# assumed: every authenticated request through the real deployment's own
# external ingress stalled 3-30 seconds (variable, not a fixed protocol
# timeout) before failing, while the same backend answered in under 1ms
# whenever a request reached it by any path that bypassed real session auth
# (direct, loopback, or the in-cluster Service) -- ruling out G3 itself, CPU
# starvation, and local port exhaustion in turn, and ruling out slow auth in
# general too (`/live/mse/ws/` and `/api/config`, both gated by the exact
# same `auth_request.conf`, answered in well under 50ms through the same real
# session in the same browser tab, moments apart). `corvette_hls` turned out
# to be the only upstream in this entire nginx.conf without `keepalive`
# (`upstream corvette_hls`'s own doc, above); every sibling upstream that
# shares this same Upgrade-forcing `proxy.conf` keeps one. That upstream
# declaration has now been restored to match its siblings; the actual
# "don't reuse a connection to a backend that always closes it" fix lives
# here instead, in these two explicit headers, which work regardless of
# whether the upstream group itself is configured to pool connections.
NEW_LOCATION = """        location /live/jsmpeg/ {
            include auth_request.conf;
            proxy_pass http://jsmpeg/;
            include proxy.conf;
        }

        # corvette issue #12 (N1): G3's HLS/LL-HLS packager, a sibling
        # container in this pod (K1), reachable at 127.0.0.1 the same way
        # jsmpeg and go2rtc already are. Trailing slash on both sides strips
        # this prefix before proxying, so G3's own listener sees exactly its
        # own path convention (/<camera name>/playlist.m3u8, /init.mp4,
        # /segment-<sequence>.m4s) -- see corvette's own
        # crates/corvette-media-bridge/src/hls.rs module doc.
        location /live/hls/ {
            include auth_request.conf;
            limit_except GET {
                deny  all;
            }
            proxy_pass http://corvette_hls/;
            include proxy.conf;
            proxy_set_header Connection "close";
            proxy_set_header Upgrade "";
        }

        # frigate lovelace card uses this path
        location /live/mse/api/ws {
"""


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGET
    raw = target.read_bytes()
    actual_md5 = hashlib.md5(raw).hexdigest()

    source = raw.decode("utf-8")
    if NEW_UPSTREAM in source and NEW_LOCATION in source:
        print("patch_live_hls_location: already applied")
        return 0

    if actual_md5 != EXPECTED_MD5:
        print(
            f"patch_live_hls_location: {target} is md5 {actual_md5}, but the "
            f"expected input (donor nginx.conf from Frigate 3d4dd3ac4/v0.17.2, "
            "with patch_pkg_location.py's /pkg/ location already applied) is "
            f"{EXPECTED_MD5} -- either FRIGATE_IMAGE has drifted from the "
            "revision this patch was written against, or this script no "
            "longer runs immediately after patch_pkg_location.py in the "
            "Dockerfile. Re-verify both insertion points by hand, update "
            "EXPECTED_MD5 here (and patch_pkg_location.py's own EXPECTED_MD5 "
            "plus tests/nginx-parity/vendor/PROVENANCE in corvette, if the "
            "donor itself changed) together, then retry.",
            file=sys.stderr,
        )
        return 1

    if OLD_UPSTREAM not in source or OLD_LOCATION not in source:
        # Unreachable if the md5 check above passed -- md5 is whole-file
        # identity, so a match implies both OLD anchors are present. Kept as
        # an explicit, named failure rather than a silent no-op if that
        # invariant is ever wrong, matching patch_pkg_location.py's own
        # precedent for this exact situation.
        print(
            "patch_live_hls_location: nginx.conf's md5 matched but one of "
            "this patch's own anchor blocks (the jsmpeg upstream, or the "
            "/live/jsmpeg/ location) was not found verbatim -- the file and "
            "the recorded md5 disagree with each other",
            file=sys.stderr,
        )
        return 1

    source = source.replace(OLD_UPSTREAM, NEW_UPSTREAM)
    source = source.replace(OLD_LOCATION, NEW_LOCATION)
    target.write_text(source, encoding="utf-8")
    print("patch_live_hls_location: /live/hls/ location inserted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
