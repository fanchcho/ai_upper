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
from ai_upper.localization import tr

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


def diagnostic_lines(lines, limit=8, continuation_limit=40):
    """Return the last ``limit`` distinct diagnostics, each with its detail.

    A diagnostic is often a header plus indented detail: build.py prints
    ``ERROR: RuntimeError: Unresolved native dependencies:`` and then one
    ``  <file>: <library>`` line per unresolved dependency. Emitting the header
    alone names the class of failure and withholds the only part that says
    which library. The indented continuation lines are carried with it.
    """
    patterns = [re.compile(p, re.IGNORECASE) for p in DIAGNOSTIC_PATTERNS]
    picked = []
    seen = set()
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        index += 1
        if not stripped or stripped in seen:
            continue
        if not any(pattern.search(stripped) for pattern in patterns):
            continue
        seen.add(stripped)
        block = [stripped]
        while index < len(lines) and len(block) <= continuation_limit:
            follow = lines[index]
            # Detail belongs to the diagnostic above it; the next unindented
            # line is a new statement and ends the block.
            if not follow.strip() or not follow[:1].isspace():
                break
            block.append(follow.rstrip())
            index += 1
        picked.append(_fit_block(block))
    return picked[-limit:]


def _fit_block(block):
    """Join a diagnostic with its detail, keeping the block inside the budget.

    The header comes first and GitHub keeps the front of an over-long message,
    so the header would survive a truncation -- but the detail is the part
    worth reading, and a second annotation is not needed for it.
    """
    kept = [block[0]]
    for line in block[1:]:
        if len(escape_command_message("\n".join(kept + [line]))) > MESSAGE_BUDGET:
            break
        kept.append(line)
    return "\n".join(kept)


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
    raw = "\n".join(chosen)
    if len(escape_command_message(raw)) > budget:
        # A single line longer than the budget still has to be reported: keep
        # its tail, which is where a compiler puts the diagnostic. The suffix
        # is measured on the ESCAPED form, one character at a time: escaping a
        # slice and then cutting it can leave half a sequence ("%0") behind.
        kept = []
        size = 0
        for char in reversed(raw):
            width = 3 if char in "%\r\n" else 1
            if size + width > budget:
                break
            kept.append(char)
            size += width
        raw = "".join(reversed(kept))
    return escape_command_message(raw)


def emit(level, title, message):
    print("::%s title=%s::%s" % (level, title, message))


def main(argv=None):
    from ai_upper.localization import configure_cli
    configure_cli(argv)
    parser = argparse.ArgumentParser(description=tr('cli.550fb411462d'))
    parser.add_argument("--log", required=True, help=tr('legacy.39c18e099daf'))
    parser.add_argument("--title", required=True, help=tr('legacy.1ade049df091'))
    parser.add_argument(
        "--exit-code-file",
        help=tr('legacy.4681048c9e29'),
    )
    parser.add_argument(
        "--label",
        default="log",
        help=tr('legacy.b3928325349a'),
    )
    parser.add_argument(
        "--level",
        choices=("error", "warning", "notice"),
        default=None,
        help=tr('legacy.fa8e373674f7'),
    )
    parser.add_argument("--lang", choices=("zh-CN", "en"), help=tr('cli.d7fa6622c296'))
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
        # already red and a second, wrong failure only hides the real one. The
        # missing log is still an error unless the caller downgraded the
        # annotation to a notice.
        emit(
            args.level or "error",
            args.title,
            escape_command_message(
                tr('cli.3464dbfca280') % args.label
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
        # The join is inside a workflow *command value*: a raw newline ends the
        # command there, so the runner keeps the stage and silently drops the
        # tail. That is how the macOS jobs in run 44023896272 reported 26 bytes
        # ("[6/6] Target runtime smoke") while run.log held the real failure.
        stage_text = escape_command_message(stage) + "%0A"
        # Both halves share the annotation budget GitHub keeps; a tail sized as
        # if it had the whole budget would push the stage's detail out.
        if len(stage_text) + len(message) > MESSAGE_BUDGET:
            message = tail_message(lines, budget=max(1, MESSAGE_BUDGET - len(stage_text)))
        message = stage_text + message
    emit(level, args.title, message)
    return 0


def last_non_empty(lines):
    for line in reversed(lines):
        if line.strip():
            return line.strip()
    return "(empty log)"


if __name__ == "__main__":
    sys.exit(main())
