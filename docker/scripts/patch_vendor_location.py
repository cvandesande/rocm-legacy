#!/usr/bin/env python3
"""Add a `/vendor/` nginx location for U2's vendored `@moq/watch`/`hls.js`
bundles (Corvette issue #12, U2).

U2's expanded live view (`crates/corvette-ui/src/expanded_view.rs`) loads
`/vendor/moq-watch.bundle.js` and `/vendor/hls.min.js` as plain `<script>`
tags. `scripts/build_site.sh` (corvette) stages `target/site/vendor/` -- the
`assets-dir` cargo-leptos already copies from
`crates/corvette-ui/public/vendor/` -- into the publish tree alongside
`pkg/`, so both files reach `/opt/frigate/web/vendor/` on disk the same way
`/opt/frigate/web/pkg/` does. Without a nested `location /vendor/` here,
though, the donor's `location /` SPA fallback (`try_files $uri $uri.html
$uri/ /index.html;`) serves `index.html` at HTTP 200 for both files instead
of a 404 -- the exact same failure mode `patch_pkg_location.py`'s own doc
describes for `/pkg/`, and the reason U2's HLS fallback never actually loads
`hls.js` in production: the browser receives an HTML document with a
`text/html` content type where a script was expected, which fails silently
(a classic MIME-type script-load rejection) rather than raising anything
`expanded_view.rs`'s own bounded-timeout logic can see or react to.

Mirrors `patch_pkg_location.py` exactly (`Cache-Control: no-cache`, no
`expires`): neither vendored file's name is content-hashed, so a browser
must revalidate on every load rather than caching indefinitely.

Runs AFTER `patch_pkg_location.py` (D1), `patch_live_hls_location.py` (N1)
and `patch_retire_go2rtc_routes.py` (N2) in the Dockerfile -- this script's
own `EXPECTED_MD5` is the md5 of nginx.conf with all three already applied,
read directly from the built `frigate-vulkan:py313-20260829` image, not
computed by hand. Deliberately last and independent of the other three's own
`EXPECTED_MD5` constants: inserting here, after everything else, means none
of D1/N1/N2's own already-reviewed `EXPECTED_MD5` values need to change to
account for this patch.

Takes an optional path argument naming the file to patch, defaulting to the
real location inside the image, so the guard and the substitution can be
exercised against a fixture copy without writing to a container filesystem.
"""

import hashlib
import sys
from pathlib import Path

DEFAULT_TARGET = Path("/usr/local/nginx/conf/nginx.conf")

# md5 of /usr/local/nginx/conf/nginx.conf inside the frigate-vulkan:py313
# image immediately after patch_pkg_location.py, patch_live_hls_location.py
# and patch_retire_go2rtc_routes.py have all run, read directly from a real
# build carrying all three -- not computed by hand, not the donor's own
# pristine md5 any of those three scripts checks against. Re-recorded after
# patch_live_hls_location.py stopped giving corvette_hls its own `keepalive`
# line (see that script's own doc): its output, and everything chained after
# it, changed by those removed bytes.
#
# Re-recorded again after patch_live_hls_location.py added explicit
# `Connection: close`/empty `Upgrade` headers to its own /live/hls/ location
# (fourth-incident fix, same doc).
EXPECTED_MD5 = "4e3d133f5ceb44377e63a07efdecfded"

OLD = """            location /pkg/ {
                add_header Cache-Control "no-cache";
            }

            location ~ ^/.*-([A-Za-z0-9]+)\\.webmanifest$ {
"""

# Same rationale as patch_pkg_location.py's own /pkg/ location: no
# `expires` (INV-5's no-positive-freshness-lifetime rule), no `try_files`
# (the point of a nested location), `Cache-Control: no-cache` (not
# `no-store` -- lets the browser revalidate rather than refetch outright).
NEW = """            location /pkg/ {
                add_header Cache-Control "no-cache";
            }

            location /vendor/ {
                add_header Cache-Control "no-cache";
            }

            location ~ ^/.*-([A-Za-z0-9]+)\\.webmanifest$ {
"""


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGET
    raw = target.read_bytes()
    actual_md5 = hashlib.md5(raw).hexdigest()

    source = raw.decode("utf-8")
    if NEW in source:
        print("patch_vendor_location: already applied")
        return 0

    if actual_md5 != EXPECTED_MD5:
        print(
            f"patch_vendor_location: {target} is md5 {actual_md5}, but the "
            f"expected post-D1/N1/N2 nginx.conf is {EXPECTED_MD5} -- either "
            "FRIGATE_IMAGE has drifted, or one of patch_pkg_location.py/"
            "patch_live_hls_location.py/patch_retire_go2rtc_routes.py "
            "changed. Re-verify the /vendor/ insertion point by hand and "
            "update EXPECTED_MD5 here, then retry.",
            file=sys.stderr,
        )
        return 1

    if OLD not in source:
        # Unreachable if the md5 check above passed -- md5 is whole-file
        # identity, so a match implies OLD is present. Kept as an explicit,
        # named failure rather than a silent no-op if that invariant is ever
        # wrong, matching patch_pkg_location.py's own precedent.
        print(
            "patch_vendor_location: nginx.conf's md5 matched but the /pkg/ "
            "block this patch anchors on was not found verbatim -- the file "
            "and the recorded md5 disagree with each other",
            file=sys.stderr,
        )
        return 1

    target.write_text(source.replace(OLD, NEW), encoding="utf-8")
    print("patch_vendor_location: /vendor/ location inserted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
