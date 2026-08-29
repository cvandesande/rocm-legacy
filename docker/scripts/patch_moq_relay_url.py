#!/usr/bin/env python3
"""Inject the MoQ relay's public URL into the served page shell (Corvette
issue #12, V3).

`crates/corvette-ui/src/expanded_view.rs`'s `mount_moq` (corvette repo) reads
a `window.__corvetteMoqRelayUrl` global to know where to dial the MoQ relay
for the expanded live view -- its own doc comment: "a `window` global a
deployment sets via a small inline `<script>` in the served page shell...
An unset value degrades to the HLS fallback immediately". Nothing in this
repo or corvette's own build ever set it, so the expanded view always fell
straight through to the HLS fallback, regardless of whether the relay was
actually reachable (issue #12, V1's own real-iPhone check surfaced this).

Unlike this directory's `patch_pkg_location.py`/`patch_vendor_location.py`/
etc., which patch a *donor* nginx.conf this repo does not own the shape of,
`index.html` here is Corvette's own file
(`crates/corvette-ui/public/app.html`), copied in whole by the
`COPY --from=corvette-ui /site/ /opt/frigate/web/` step immediately before
this one runs. There is no third-party drift to guard against with an
`EXPECTED_MD5`-style check the way the nginx patches need -- `</head>` is
anchored on because it is present in any well-formed HTML document, not
because this exact file's byte content was independently verified.

Reads `CORVETTE_MOQ_RELAY_URL` from the environment (this Dockerfile's own
`ARG` of the same name, passed down via `RUN CORVETTE_MOQ_RELAY_URL=... `,
matching `check_corvette_ui_image.py`'s own env-not-argv convention). Empty
(the default) is a deliberate no-op, not an error: a deployment that has not
set up external MoQ/QUIC exposure yet -- or a `docker build` with no
`--build-arg` at all -- gets exactly today's behavior (HLS fallback always),
not a build failure over a feature it may not want yet.

Takes an optional path argument naming the file to patch, defaulting to the
real location inside the image, so the guard and the substitution can be
exercised against a fixture copy without writing to a container filesystem.
"""

import json
import os
import sys
from pathlib import Path

DEFAULT_TARGET = Path("/opt/frigate/web/index.html")

ANCHOR = "</head>"


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGET
    relay_url = os.environ.get("CORVETTE_MOQ_RELAY_URL", "")

    if not relay_url:
        print(
            "patch_moq_relay_url: CORVETTE_MOQ_RELAY_URL is empty -- leaving "
            f"{target} untouched, the expanded live view will always use its "
            "HLS fallback"
        )
        return 0

    raw = target.read_text(encoding="utf-8")
    marker = "__corvetteMoqRelayUrl"
    if marker in raw:
        print(f"patch_moq_relay_url: {marker} is already set in {target}, leaving it alone")
        return 0

    if ANCHOR not in raw:
        print(
            f"patch_moq_relay_url: no {ANCHOR!r} found in {target} -- this "
            "file's own shape has changed enough that the insertion point "
            "below is no longer safe to assume; re-verify by hand",
            file=sys.stderr,
        )
        return 1

    script_tag = f"<script>window.{marker}={json.dumps(relay_url)};</script>\n  {ANCHOR}"
    target.write_text(raw.replace(ANCHOR, script_tag, 1), encoding="utf-8")
    print(f"patch_moq_relay_url: set {marker} to {relay_url!r} in {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
