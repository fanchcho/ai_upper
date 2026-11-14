"""Turn the tail of a CI log into check-run annotations that survive GitHub's cap.

GitHub truncates a check-run annotation message at 4096 characters, and it
keeps the *beginning* of the message. The previous publishers handed it the
last N lines of the log verbatim -- and on Windows a handful of ``cl.exe``
command lines is already longer than 4096 characters, so the only thing left
readable was the compiler invocation itself and the actual diagnostic was cut
off. Three runs in a row (43578841766, 43580099288, 43581355558) therefore
reported ``build.py (exit 1)`` with a message that never contained the error.

So the message is assembled differently:

* diagnostic lines are pulled out of the whole log and annotated one by one,
  which is what a failure actually needs to be diagnosed from; and
* the fallback tail is accumulated *backwards* from the end of the log, so the
  part that fits is the part where the failure is.

The escape used by the workflow-command format expands the text (``%`` becomes
``%25``), so the budget is measured on the escaped form, not the raw one.

Python 3.8 is the oldest interpreter that runs this repository's CI matrix, so
nothing newer than that is used here.
"""

import argparse
import re
import sys

# GitHub keeps roughly this many characters of an annotation message. Stay
# meaningfully below it: the escaped form can grow and the title shares the
# budget in some clients.
MESSAGE_BUDGET = 3500

# Lines worth surfacing on their own. Each pattern matches the shape of a real
# diagnostic printed by a compiler, the linker, MSBuild, pip or Python -- the
# point is to pick the error out of the noise of build chatter.
DIAGNOSTIC_PATTERNS = [
    r"error [A-Z]+[0-9]+",              # MSVC C1083 / LNK2019 / MSB8041
    r"command line error",              # cl.exe D8021 and friends
    r"fatal error",
    r"\bLNK[0-9]{4}\b",
    r"Traceback \(most recent call last\)",
    r"^\s*File \".*\", line [0-9]+",
    r"\b(?:ModuleNotFoundError|ImportError|SyntaxError|TypeError|"
    r"RuntimeError|ValueError|AssertionError|CalledProcessError|"
    r"FileNotFoundError|KeyError|AttributeError)\b",
    r"^\s*E\s+\w",                       # pytest's long-traceback lines
    r"^\s*(?:FAILED|ERROR)\s+\S",
    r"^\s*>\s",                          # assertion context in a traceback
    r"^\s*assert\s",
    r"nmake(?:\.exe)?:.*(?:error|fatal)",
    r"failed with exit (?:code|status)",
]

# build.py announces the stage it is in. Which stage failed is the first thing
# anyone reading a red build wants, and the stage line itself never looks like
# an error, so it is carried as context rather than matched as a diagnostic.
STAGE_PATTERN = re.compile(r"^\[\d/\d\]\s+\S")


def escape_command_message(text):
    """Escape a message for the ``::error`` workflow-command format.

    Order matters: ``%`` has to be escaped before the line breaks are, or the
    ``%`` introduced by ``%0A`` would be doubled.
    """
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def read_log_lines(path):
    """Read ``path`` as text, or return ``None`` when there is no log at all."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read().splitlines()
    except (IOError, OSError):
        return None


def diagnostic_lines(lines, limit=8):
    """Return the last ``limit`` distinct lines that look like diagnostics."""
    patterns = [re.compile(p, re.IGNORECASE) for p in DIAGNOSTIC_PATTERNS]
    picked = []
    seen = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped in seen:
            continue
        if any(pattern.search(stripped) for pattern in patterns):
            picked.append(stripped)
            seen.add(stripped)
    return picked[-limit:]


def last_stage(lines):
    """The last ``[n/6]`` stage banner build.py printed, if any."""
    for line in reversed(lines):
        if STAGE_PATTERN.match(line.strip()):
            return line.strip()
    return None


def tail_message(lines, budget=MESSAGE_BUDGET):
    """Build a message from the END of the log that fits inside ``budget``.

    Accumulating backwards is the whole point: if the message is going to be
    cut, it must be cut at the *start* of the log, not at the end where the
    failure is.
    """
    chosen = []
    for line in reversed(lines):
        candidate = "\n".join([line] + chosen)
        if chosen and len(escape_command_message(candidate)) > budget:
            break
        chosen.insert(0, line)
    # A single line longer than the budget still has to be reported: keep its
    # tail, which is where a compiler puts the diagnostic.
    message = escape_command_message("\n".join(chosen))
    if len(message) > budget:
        message = message[-budget:]
    return message


def emit(level, title, message):
    print("::%s title=%s::%s" % (level, title, message))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", required=True, help="path to the log file")
    parser.add_argument("--title", required=True, help="annotation title")
    parser.add_argument(
        "--exit-code-file",
        help="file holding the step's exit code; exit 0 downgrades to a notice",
    )
    parser.add_argument(
        "--label",
        default="log",
        help="what to call the log when it is missing (e.g. 'build.log')",
    )
    parser.add_argument(
        "--level",
        choices=("error", "warning", "notice"),
        default=None,
        help="force the annotation level instead of deriving it from the exit code",
    )
    args = parser.parse_args(argv)

    exit_code = None
    if args.exit_code_file:
        try:
            with open(args.exit_code_file, "r", encoding="utf-8", errors="replace") as handle:
                exit_code = handle.read().strip()
        except (IOError, OSError):
            exit_code = None

    lines = read_log_lines(args.log)
    if lines is None:
        # Never invent an exit code for a step that did not run: the job is
        # already red and a second, wrong failure only hides the real one.
        emit(
            "error",
            args.title,
            escape_command_message(
                "%s was not created: the step failed before it could write one." % args.label
            ),
        )
        return 0

    if exit_code == "0" or args.level == "notice":
        emit("notice", args.title, escape_command_message(last_non_empty(lines)))
        return 0

    level = args.level or "error"
    stage = last_stage(lines)
    found = diagnostic_lines(lines)
    if found:
        # One annotation per diagnostic, so a long path or a wide command line
        # in one of them cannot push the others past the budget.
        if stage:
            emit(level, args.title, escape_command_message(stage))
        for line in found:
            emit(level, args.title, escape_command_message(line))
        return 0

    # No line looked like a diagnostic (an interrupted toolchain, a crash
    # without a message). Fall back to the true tail, end-first. The stage goes
    # in front of it when there is one: the tail may start mid-command line.
    message = tail_message(lines)
    if stage:
        message = escape_command_message(stage) + "\n" + message
    emit(level, args.title, message)
    return 0


def last_non_empty(lines):
    for line in reversed(lines):
        if line.strip():
            return line.strip()
    return "(empty log)"


if __name__ == "__main__":
    sys.exit(main())
