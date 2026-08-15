#!/usr/bin/env python3
"""Add a `/pkg/` nginx location for the Leptos UI bundle (Corvette issue #2, D1).

The donor's `location /` sets `Cache-Control: no-store` on everything under it
and is the SPA fallback (`try_files $uri $uri.html $uri/ /index.html;`), which
nested locations do not inherit. Left unpatched, a missing file under `/pkg/`
silently returns `index.html` at HTTP 200 instead of a 404, and every
multi-megabyte wasm/JS chunk is re-transferred on every load. Giving `/pkg/`
its own nested location, the same way the donor already does for `/assets/`,
`/fonts/` and `/locales/`, fixes both: nested locations do not inherit
try_files, so a miss is a real 404, and `add_header Cache-Control "no-cache"`
(no `expires`, no positive `max-age`) means the browser revalidates every
load instead of skipping the cache outright -- see
`.agents/issue-2/PLAN-ui-replacement.md` D1 in the `corvette` repo for the
full rationale, including why `no-cache` and not `no-store` or a positive
freshness lifetime.

Fails loudly, before touching anything, if the donor's nginx.conf does not
match the md5 recorded from Frigate v0.17.2 (3d4dd3ac4) -- this is
`FRIGATE_IMAGE` naming a floating tag, not a digest (serving R-8), made loud
instead of silent. The recorded value is the same one carried in
`corvette`'s `tests/nginx-parity/vendor/PROVENANCE`; the two are meant to be
re-vendored together if the donor ever changes.

Takes an optional path argument naming the file to patch, defaulting to the
real location inside the image, so the guard and the substitution can be
exercised against a fixture copy without writing to a container filesystem.
"""

import hashlib
import sys
from pathlib import Path

DEFAULT_TARGET = Path("/usr/local/nginx/conf/nginx.conf")

# docker/Dockerfile.py313:70 copies /usr/local/nginx wholesale from
# ${FRIGATE_IMAGE} (currently the tag 0.17.2, not a digest). This is the md5
# of docker/main/rootfs/usr/local/nginx/conf/nginx.conf at 3d4dd3ac4, recorded
# by `corvette`'s serving-contract research (RESEARCH-serving-contract.md F-2)
# and re-checked in tests/nginx-parity/vendor/PROVENANCE.
EXPECTED_MD5 = "ab5dc3e90e54616dc30c7cdc8fac4048"

OLD = """            location /locales/ {
                access_log off;
                add_header Cache-Control "public";
            }

            location ~ ^/.*-([A-Za-z0-9]+)\\.webmanifest$ {
"""

# No `expires` directive (so no positive freshness lifetime -- INV-5), no
# `try_files` (nested locations do not inherit it, which is the point), no
# addition to `sub_filter_types` (`.wasm` must stay untouched by sub_filter,
# serving F-8). `add_header Cache-Control "no-cache"` on this level replaces
# the parent `location /`'s `no-store`, the same way `/assets/`, `/fonts/`
# and `/locales/` already override it -- add_header does not merge across
# levels, it is replaced outright by any add_header on the current level.
NEW = """            location /locales/ {
                access_log off;
                add_header Cache-Control "public";
            }

            location /pkg/ {
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
        print("patch_pkg_location: already applied")
        return 0

    if actual_md5 != EXPECTED_MD5:
        print(
            f"patch_pkg_location: {target} is md5 {actual_md5}, but the donor "
            f"nginx.conf pinned from Frigate 3d4dd3ac4 (v0.17.2) is "
            f"{EXPECTED_MD5} -- FRIGATE_IMAGE has drifted from the revision "
            "this patch was written against. Re-verify the /pkg/ insertion "
            "point by hand, update EXPECTED_MD5 here and "
            "tests/nginx-parity/vendor/PROVENANCE in corvette together, "
            "then retry.",
            file=sys.stderr,
        )
        return 1

    if OLD not in source:
        # Unreachable if the md5 check above passed -- md5 is whole-file
        # identity, so a match implies OLD is present. Kept as an explicit,
        # named failure rather than a silent no-op if that invariant is ever
        # wrong (e.g. an md5 collision, or this script edited out of step
        # with EXPECTED_MD5).
        print(
            "patch_pkg_location: nginx.conf's md5 matched but the /locales/ "
            "block this patch anchors on was not found verbatim -- the file "
            "and the recorded md5 disagree with each other",
            file=sys.stderr,
        )
        return 1

    target.write_text(source.replace(OLD, NEW), encoding="utf-8")
    print("patch_pkg_location: /pkg/ location inserted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
