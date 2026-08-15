#!/usr/bin/env python3
"""Fail the build unless CORVETTE_UI_IMAGE is pinned by digest.

Corvette issue #2 (D2), INV-4: "digest, not tag" -- every reference to the
Leptos UI artifact in a consuming build file must carry `@sha256:<64 hex>`.
A bare `repo:tag` reference is not caught by the `FROM ${CORVETTE_UI_IMAGE}`
line on its own: `docker.io/cvandesande/corvette-ui:20260815` is a real,
resolvable tag as of this writing, so the pull would simply succeed against
whatever that tag happens to point to at build time -- silently defeating
the whole point of pinning to a specific, reviewed push. This script is the
explicit check that catches it instead.

Reads CORVETTE_UI_IMAGE from the environment (docker/Dockerfile.py313 passes
the build ARG down via `RUN CORVETTE_UI_IMAGE="${CORVETTE_UI_IMAGE}" ...`)
rather than from argv, so it can run as a plain `RUN` step with no shell
quoting surprises around the `@` and `:` characters a real reference
contains.
"""

import os
import re
import sys

# Exactly one `@sha256:` followed by 64 lowercase hex chars, anchored, with
# at least one non-`@` character before it (the repo:tag or bare repo part).
# No placeholder, example, or hand-typed digest may ever satisfy this by
# accident -- the only thing that matches is a real, syntactically complete
# digest reference.
PATTERN = re.compile(r"^[^@]+@sha256:[0-9a-f]{64}$")


def main() -> int:
    image = os.environ.get("CORVETTE_UI_IMAGE", "")

    if not image:
        print(
            "check_corvette_ui_image: CORVETTE_UI_IMAGE is empty -- INV-4 "
            "requires a digest-pinned reference "
            "(docker.io/cvandesande/corvette-ui:<tag>@sha256:<64 hex>), "
            "got nothing at all",
            file=sys.stderr,
        )
        return 1

    if not PATTERN.match(image):
        print(
            f"check_corvette_ui_image: CORVETTE_UI_IMAGE={image!r} is not "
            "pinned by digest (INV-4). Every reference to the Corvette UI "
            "artifact must carry @sha256:<64 hex>, copied verbatim from a "
            "real push -- a bare repo:tag reference, even one that resolves "
            "today, floats onto whatever that tag points to later and is "
            "rejected here on purpose.",
            file=sys.stderr,
        )
        return 1

    print(f"check_corvette_ui_image: {image} is digest-pinned, OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
