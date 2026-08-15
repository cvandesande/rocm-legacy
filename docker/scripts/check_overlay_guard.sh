#!/usr/bin/env bash
# Corvette issue #2 (D2), INV-2 enforcement: "overlay, never replace".
#
# Greps every file under docker/ for these forbidden shapes:
#
#   1. Any `rm` invocation naming a path under /opt/frigate/web -- deleting
#      even a single file there (login.html, an /assets/ entry, ...) breaks
#      something D2's overlay promised would keep working. Corvette's own
#      index.html is expected to *land* there via the overlay COPY, which is
#      a copy, not an rm; nothing in this build should ever need to rm
#      anything under that directory.
#   2. Any `mv` invocation whose source is under /opt/frigate/web and whose
#      destination is not -- i.e. moving content out of the served directory.
#      This is the same violation as (1) by a different verb: INV-2's own
#      text (and the comment above the overlay COPY in Dockerfile.py313) say
#      "never delete, move, or replace". A same-directory rename such as
#      `mv /opt/frigate/web/foo.tmp /opt/frigate/web/foo` is *not* a
#      violation -- nothing leaves the overlay -- so this check only flags an
#      `mv` instruction that mentions /opt/frigate/web exactly once (the
#      source). One mentioning it twice (source and destination both under
#      it) is a rename-in-place and is allowed.
#   3. Any `find` invocation combining a path under /opt/frigate/web with
#      `-delete` on the same instruction -- the batch-delete equivalent of
#      (1), same reasoning.
#   4. A COPY (or ADD) instruction whose destination is the bare directory
#      /opt/frigate/web with no trailing slash. This repo's convention for
#      "merge into an existing directory" is a trailing slash on both sides
#      of the instruction -- see docker/Dockerfile.py313's
#      `COPY --from=corvette-ui /site/ /opt/frigate/web/`. A destination
#      without the trailing slash reads as "replace this path", which is
#      exactly what INV-2 forbids.
#
# Run this from anywhere; it always scans docker/Dockerfile* relative to
# this script, not the caller's cwd. Deliberately scoped to the Dockerfiles
# themselves (where RUN/COPY/ADD instructions actually live) rather than all
# of docker/ recursively -- a repo-wide text grep for "rm" and
# "/opt/frigate/web" would also match this script's own prose above.
# Exits non-zero and prints every offending line if any shape is found in
# any Dockerfile.
set -euo pipefail

docker_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fail=0

echo "check_overlay_guard: scanning $docker_dir/Dockerfile* for INV-2 violations"

if matches=$(grep -nE '\brm\b[[:space:]]+[^|;&]*/opt/frigate/web' "$docker_dir"/Dockerfile*); then
    echo "check_overlay_guard: forbidden deletion under /opt/frigate/web (INV-2):" >&2
    echo "$matches" >&2
    fail=1
fi

mv_matches=""
if mv_candidates=$(grep -nE '\bmv\b[[:space:]]+.*/opt/frigate/web' "$docker_dir"/Dockerfile*); then
    while IFS= read -r candidate; do
        [ -n "$candidate" ] || continue
        content="${candidate#*:*:}"
        # A rename-in-place mentions /opt/frigate/web twice (source and
        # destination both under it); only flag instructions that mention it
        # once, meaning the destination lands outside the overlay.
        occurrences=$(grep -o '/opt/frigate/web' <<<"$content" | wc -l)
        if [ "$occurrences" -lt 2 ]; then
            mv_matches="${mv_matches}${candidate}
"
        fi
    done <<<"$mv_candidates"
fi
if [ -n "$mv_matches" ]; then
    echo "check_overlay_guard: forbidden move out of /opt/frigate/web (INV-2):" >&2
    printf '%s' "$mv_matches" >&2
    fail=1
fi

if matches=$(grep -nE '\bfind\b.*-delete\b' "$docker_dir"/Dockerfile* | grep -E '/opt/frigate/web'); then
    echo "check_overlay_guard: forbidden find -delete under /opt/frigate/web (INV-2):" >&2
    echo "$matches" >&2
    fail=1
fi

if matches=$(grep -nE '^[[:space:]]*(COPY|ADD)\b.*[[:space:]]/opt/frigate/web[[:space:]]*(#.*)?$' "$docker_dir"/Dockerfile*); then
    echo "check_overlay_guard: COPY/ADD destination /opt/frigate/web has no trailing slash -- replace form, not overlay (INV-2):" >&2
    echo "$matches" >&2
    fail=1
fi

if [ "$fail" -ne 0 ]; then
    exit 1
fi

echo "check_overlay_guard: OK -- no rm/mv/find-delete of /opt/frigate/web content, no non-overlay COPY/ADD destination"
