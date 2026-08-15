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
#   2. Any `mv` invocation with at least one source under /opt/frigate/web
#      whose destination is not -- i.e. moving content out of the served
#      directory. This is the same violation as (1) by a different verb:
#      INV-2's own text (and the comment above the overlay COPY in
#      Dockerfile.py313) say "never delete, move, or replace". A
#      same-directory rename such as `mv /opt/frigate/web/foo.tmp
#      /opt/frigate/web/foo` is *not* a violation -- nothing leaves the
#      overlay. Real `mv` syntax supports multiple sources with one
#      trailing destination directory (`mv SRC1 SRC2... DIR`) and a
#      `-t DIR` / `--target-directory=DIR` form (`mv -t DIR SRC1 SRC2...`)
#      where the destination is a flag value, not a trailing argument --
#      so this check actually parses each `mv` invocation's arguments into
#      (sources, destination) per those semantics (see
#      check_overlay_guard_mv.py) rather than counting how many times
#      /opt/frigate/web is mentioned; a prior version of this guard tried
#      occurrence-counting and was defeated by exactly this multi-source
#      shape (two sources leaving the overlay for the same place count the
#      same as one source and one destination both staying inside it).
#      Both the source and destination checks are path-boundary-aware, so
#      a sibling directory that merely starts with the same string (e.g.
#      /opt/frigate/web-backup) is never miscounted as "under"
#      /opt/frigate/web.
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

# Path-boundary suffix for grep -E matches of the literal string
# /opt/frigate/web: require the next character to be something other than
# alnum/underscore/dot/hyphen (i.e. not another path-continuing character),
# or end of line. Without this, a bare substring match of "/opt/frigate/web"
# also matches as a *prefix* of an unrelated sibling directory name such as
# /opt/frigate/web-backup or /opt/frigate/webapp -- which both under-flags
# (an mv into such a sibling reads as "mentions the path twice" and gets
# waved through as an allowed same-directory rename, even though the
# content actually left the overlay) and over-flags (an rm/find -delete
# confined entirely to such a sibling gets reported as an INV-2 violation
# it isn't).
boundary='([^[:alnum:]_.-]|$)'

echo "check_overlay_guard: scanning $docker_dir/Dockerfile* for INV-2 violations"

if matches=$(grep -nE "\\brm\\b[[:space:]]+[^|;&]*/opt/frigate/web${boundary}" "$docker_dir"/Dockerfile*); then
    echo "check_overlay_guard: forbidden deletion under /opt/frigate/web (INV-2):" >&2
    echo "$matches" >&2
    fail=1
fi

# The actual "does this mv move something out of /opt/frigate/web"
# judgment requires parsing mv's own argument syntax (which argument is
# the destination vs. which are sources -- see the header comment above
# and check_overlay_guard_mv.py's module docstring for why occurrence
# counting can't do this correctly), so it's delegated to a small Python
# script rather than reimplemented in bash.
mv_matches="$(python3 "$docker_dir"/scripts/check_overlay_guard_mv.py "$docker_dir"/Dockerfile*)"
if [ -n "$mv_matches" ]; then
    echo "check_overlay_guard: forbidden move out of /opt/frigate/web (INV-2):" >&2
    echo "$mv_matches" >&2
    fail=1
fi

if matches=$(grep -nE '\bfind\b.*-delete\b' "$docker_dir"/Dockerfile* | grep -E "/opt/frigate/web${boundary}"); then
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
