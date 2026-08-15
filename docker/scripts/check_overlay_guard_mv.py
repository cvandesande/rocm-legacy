#!/usr/bin/env python3
"""INV-2 `mv`-out-of-overlay detector, used by check_overlay_guard.sh (D2).

Third review-fix cycle. The first two cycles tried to judge an `mv`
instruction by *counting* how many times the literal string
`/opt/frigate/web` appeared among its tokens (2 occurrences = a
same-directory rename = safe, fewer = a move-out = violation), first with a
bare substring count and then with a boundary-aware per-token count. Both
were defeated by the same root problem: real `mv` supports multiple
sources with a single trailing destination --

    mv SOURCE1 SOURCE2... DIRECTORY
    mv -t DIRECTORY SOURCE1 SOURCE2...

-- so occurrence-counting cannot tell "two sources, both leaving the
overlay" (a violation) apart from "one source and one destination, both
under the overlay" (a safe rename): both mention the path twice. E.g.

    RUN mv /opt/frigate/web/login.html /opt/frigate/web/robots.txt /tmp/

moves two files OUT of the overlay into /tmp/, but a naive count sees two
tokens under /opt/frigate/web and waves it through.

This module fixes that by actually parsing the `mv` invocation's arguments
into (sources, destination) per real `mv` semantics, then checking: is any
source under /opt/frigate/web while the destination is not? That -- and
only that -- is the violation condition INV-2 cares about. It is not a
full shell parser (this is a static Dockerfile linter, not a shell
interpreter) but it does handle: multiple bare/quoted path arguments,
`-t DIR` / `-tDIR` / `--target-directory=DIR` (which supply the
destination as a flag rather than a trailing argument, so there is no
trailing-destination argument at all in that form), other flags
interspersed among the paths (-f, -i, -v, -n, -u, -b, -T, ...), bundled
short-option clusters where -t's value is attached to a run of other
short flags (`-vft/tmp` meaning `-v -f -t /tmp` -- an early draft of this
script got this wrong and was empirically confirmed, during this same fix
cycle's own adversarial testing, to wave through a real move-out written
this way; see check_overlay_guard_mv.py's git history / the D2 evidence
log for the repro), and multiple `mv` invocations chained onto one
Dockerfile RUN line with &&, ||, ;, or |.

One residual, deliberately-unhandled edge case: mv also has a second
value-taking short option, -S (backup suffix), and a *cluster containing
both* in a specific order -- -S's value swallowing a literal "t" meant as
a plain character of the suffix, e.g. `-Wt` where W is some other
value-taking option -- is resolved correctly (first value-taking option
in the cluster wins, per real getopt bundling), but this script does not
attempt to model every GNU short option's arity, only -t and -S (mv's
only two that take a value). If a future mv gains a third value-taking
short option, a cluster ordering could in principle re-open this gap;
noted here rather than silently assumed away.

Called as: check_overlay_guard_mv.py DOCKERFILE [DOCKERFILE...]
Prints one `path:lineno:content` line per violation found (grep -n style,
so check_overlay_guard.sh can echo them the same way it echoes its other
checks' matches) and always exits 0 on a normal run -- "no output" *is*
"no violations" here, there is no separate use of the exit code to signal
that, so a failure to open/read an input file is the only nonzero exit.
"""

import re
import shlex
import sys

OVERLAY_DIR = "/opt/frigate/web"

# Same path-boundary logic as check_overlay_guard.sh's own `boundary`
# regex for the rm/find checks: a path is "under" OVERLAY_DIR only if it
# equals it exactly (mod a trailing slash) or continues past it with a
# '/'. This is what keeps a same-prefixed sibling such as
# /opt/frigate/web-backup from being misjudged as "under"
# /opt/frigate/web just because it shares that string as a prefix.


def is_under_overlay(path: str) -> bool:
    path = path.rstrip("/")
    return path == OVERLAY_DIR or path.startswith(OVERLAY_DIR + "/")


# Tokens made up entirely of shell control-operator characters: these are
# what separate one subcommand from the next on a Dockerfile RUN line
# (&&, ||, ;, a bare &, a bare |, ( ) for subshells/grouping). Isolating
# subcommands this way keeps an `mv` invocation's argument parsing from
# accidentally swallowing tokens that belong to a *different* command
# chained onto the same RUN line.
_OPERATOR_RE = re.compile(r"^[;&|()<>]+$")


def split_subcommands(line: str):
    """Tokenize a shell line and split it into a list of subcommand
    token-lists on unquoted control operators. Returns [] if the line
    can't be safely tokenized (e.g. unbalanced quotes) -- callers should
    treat that as "nothing to check here" rather than guessing.
    """
    try:
        lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return []

    commands = []
    current = []
    for tok in tokens:
        if _OPERATOR_RE.match(tok):
            if current:
                commands.append(current)
                current = []
        else:
            current.append(tok)
    if current:
        commands.append(current)
    return commands


def mv_violation(args) -> bool:
    """`args` is the mv invocation's argument tokens (everything after the
    leading `mv` token itself). Returns True iff this invocation moves
    something out of /opt/frigate/web: at least one source argument is
    under it and the destination argument is not.
    """
    target_dir = None
    paths = []
    i = 0
    n = len(args)
    while i < n:
        tok = args[i]
        if tok == "--":
            paths.extend(args[i + 1 :])
            break
        if tok == "--target-directory":
            i += 1
            if i < n:
                target_dir = args[i]
            i += 1
            continue
        if tok.startswith("--target-directory="):
            target_dir = tok.split("=", 1)[1]
            i += 1
            continue
        if tok.startswith("--"):
            # Any other GNU long option (--force, --interactive,
            # --verbose, --backup, --no-target-directory, ...): none of
            # these change which remaining argument is the destination.
            i += 1
            continue
        if tok.startswith("-") and tok != "-":
            # A POSIX-style short-option cluster: -f, -v, -fv, -t, -tDIR,
            # or (GNU getopt bundling) several boolean flags followed by a
            # value-taking one whose value is the *rest of the same
            # token*, e.g. -vft/tmp meaning -v -f -t /tmp. mv has two
            # short options that consume a value this way: -t (target
            # directory, what we care about) and -S (backup suffix, value
            # irrelevant here but it still *consumes* the value so a
            # literal "t" appearing inside a -S suffix must not be
            # mistaken for -t). Scan left to right for the first
            # value-taking option in the cluster; whichever is hit first
            # is the one whose value is "everything remaining in this
            # token, or the next token if none remains" -- real clusters
            # never have a flag after a value-taking one, since the rest
            # of the token is already consumed as that flag's value.
            cluster = tok[1:]
            for pos, c in enumerate(cluster):
                if c not in ("t", "S"):
                    continue
                rest = cluster[pos + 1 :]
                if c == "t":
                    if rest:
                        target_dir = rest
                        i += 1
                    else:
                        i += 1
                        if i < n:
                            target_dir = args[i]
                            i += 1
                else:  # c == "S": backup suffix, value doesn't matter here
                    i += 1
                    if not rest and i < n:
                        i += 1
                break
            else:
                i += 1
            continue
        paths.append(tok)
        i += 1

    if target_dir is not None:
        # mv -t DIR SOURCE...  /  mv --target-directory=DIR SOURCE...
        # Every non-option argument is a source; there is no trailing
        # destination argument in this form at all.
        dest = target_dir
        sources = paths
    else:
        # mv SOURCE... DIRECTORY  (subsumes the plain 2-arg SOURCE DEST
        # case: with exactly one preceding path, "sources" is that one
        # path). The last non-option argument is always the destination.
        if len(paths) < 2:
            # Can't identify a source/dest split (e.g. `mv` with zero or
            # one bare path argument) -- nothing to judge, don't flag.
            return False
        dest = paths[-1]
        sources = paths[:-1]

    return any(is_under_overlay(s) for s in sources) and not is_under_overlay(dest)


def find_violations(path: str):
    violations = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            # Coarse pre-filter so we don't tokenize every line of every
            # Dockerfile: a line that doesn't even contain the substring
            # "mv" can't contain an mv invocation.
            if "mv" not in line:
                continue
            for command in split_subcommands(line):
                if not command:
                    continue
                # `mv` need not be command[0]: a Dockerfile RUN line is
                # "RUN <shell command>", so the subcommand token list here
                # is typically ['RUN', 'mv', ...] (or, after a chained
                # '&&'/';'/'|', possibly just ['mv', ...], or prefixed by
                # something like 'sudo'/'exec'/'nice -n5'). Rather than
                # trying to enumerate every possible prefix word, look for
                # an `mv` token anywhere in the subcommand and treat
                # whatever follows it as that invocation's arguments.
                for idx, tok in enumerate(command):
                    if tok != "mv" and not tok.endswith("/mv"):
                        continue
                    if mv_violation(command[idx + 1 :]):
                        violations.append(f"{path}:{lineno}:{line.rstrip(chr(10))}")
                        break
    return violations


def main() -> int:
    if len(sys.argv) < 2:
        return 0

    all_violations = []
    for path in sys.argv[1:]:
        all_violations.extend(find_violations(path))

    for v in all_violations:
        print(v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
