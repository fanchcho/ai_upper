"""Tests for tools/ci_tail.py, the CI failure-text publisher.

The publisher exists because GitHub truncates a check-run annotation message
from the *front* at 4096 characters. Three consecutive workflow runs
(43578841766, 43580099288, 43581355558) reported ``build.py (exit 1)`` whose
message contained nothing but ``cl.exe`` command lines -- the last 80 lines of
build.log verbatim, which on Windows overflow the budget before the compiler's
diagnostic is reached. These tests pin the properties that made that happen,
so the publisher cannot silently regress into "it prints something".
"""

import sys
from pathlib import Path

TOOLS = Path(__file__).parents[2] / "tools"
VALIDATION_WORKFLOW = Path(__file__).parents[2] / ".github" / "workflows" / "validate.yml"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import ci_tail  # noqa: E402


def _cl_line(index: int) -> str:
    """A build line shaped like the ones that consumed the whole budget."""
    return (
        '"C:\\Program Files\\Microsoft Visual Studio\\18\\Enterprise\\VC\\Tools\\MSVC'
        '\\14.51.36231\\bin\\HostX64\\x64\\cl.exe" /c /nologo /O2 /W3 /GL /DNDEBUG /MD '
        + " ".join('-IC:\\Program Files\\Windows Kits\\10\\include\\10.0.26100.0\\part%d' % i for i in range(6))
        + " /TcD:\\a\\ai_upper\\ai_upper\\build\\merged\\windows-x86_64\\mvvm\\%04d_x.c" % index
    )


def test_diagnostic_survives_a_tail_of_long_compiler_command_lines():
    """The regression the publisher was written for.

    A verbatim tail is longer than GitHub's 4096-character cap, and the cap
    keeps the beginning -- so the error at the end disappears. The diagnostic
    has to be picked out of the log instead.
    """
    lines = [_cl_line(i) for i in range(40)]
    lines.append("0059_mvvm_webui_assembly.c")
    error = (
        "D:\\a\\ai_upper\\ai_upper\\build\\merged\\windows-x86_64\\mvvm\\0059_mvvm_webui_assembly.c(12): "
        'fatal error C1083: Cannot open include file: "Python.h": No such file or directory'
    )
    lines.append(error)
    lines.append("error: command 'cl.exe' failed with exit code 2")

    found = ci_tail.diagnostic_lines(lines)

    assert found, "no diagnostic picked out of a log that contains a fatal error"
    assert any("C1083" in line for line in found), found
    assert any("cl.exe' failed with exit code 2" in line for line in found), found
    # Each emitted annotation is its own message, so it must fit on its own.
    for line in found:
        assert len(ci_tail.escape_command_message(line)) <= ci_tail.MESSAGE_BUDGET


def test_fallback_tail_is_accumulated_from_the_end():
    """When nothing matches a diagnostic pattern, keep the *end* of the log.

    Building the message from the end is the property that makes truncation
    harmless: whatever fits is the part where the failure is.
    """
    lines = ["noise %d" % i for i in range(5000)]
    lines.append("the actual last word")

    message = ci_tail.tail_message(lines)

    assert "the actual last word" in message
    assert len(message) <= ci_tail.MESSAGE_BUDGET
    # Nothing from the beginning of the log can be in a budget-sized tail.
    assert "noise 0" not in message


def test_single_line_longer_than_the_budget_keeps_its_end():
    """A compiler can put the diagnostic at the end of one enormous line."""
    line = "X" * 20000 + " fatal error C1083: Cannot open include file"

    message = ci_tail.tail_message([line])

    assert len(message) <= ci_tail.MESSAGE_BUDGET
    assert "C1083" in message


def test_the_failing_stage_is_reported(capsys, tmp_path):
    """Which stage died is the first thing a reader needs.

    The stage banner does not look like an error, so a diagnostic-only emitter
    drops it and the annotation says ``fatal error C1083`` without saying that
    the build was at [3/6]. The stage has to ride along.
    """
    log = tmp_path / "build.log"
    log.write_text(
        "\n".join(
            [
                "[1/6] Runtime + SDK",
                "[2/6] Third-party dependencies",
                "[3/6] Target launcher",
                _cl_line(0),
                'fatal error C1083: Cannot open include file: "Python.h"',
            ]
        ),
        encoding="utf-8",
    )
    rc = tmp_path / "build.exitcode"
    rc.write_text("1\n", encoding="utf-8")

    ci_tail.main(
        [
            "--log",
            str(log),
            "--title",
            "build.py (exit 1)",
            "--exit-code-file",
            str(rc),
            "--label",
            "build.log",
        ]
    )

    out = capsys.readouterr().out
    assert "[3/6] Target launcher" in out
    assert "C1083" in out
    # Stage first: the title may repeat, the stage is what narrows the cause.
    assert out.index("[3/6]") < out.index("C1083")


def test_escaping_order_does_not_double_the_percent():
    """``%`` has to be escaped before line breaks become ``%0A``.

    The reverse order rewrites the ``%`` of ``%0A`` into ``%250A``, which the
    runner then renders literally.
    """
    escaped = ci_tail.escape_command_message("100% done\r\nnext")

    assert escaped == "100%25 done%0D%0Anext"


def test_missing_log_says_so_and_does_not_invent_an_exit_code(capsys, tmp_path):
    """A step that never ran must not file a fabricated failure.

    On windows-arm64 a unit test failure meant the build never started; the
    publisher nevertheless reported ``build.py (exit 255) (no build.log)``,
    pointing at a build nobody attempted.
    """
    code = ci_tail.main(
        [
            "--log",
            str(tmp_path / "absent.log"),
            "--title",
            "build.py (exit 1)",
            "--label",
            "build.log",
        ]
    )

    assert code == 0
    out = capsys.readouterr().out
    assert "::error title=build.py (exit 1)::" in out
    assert "build.log was not created" in out
    assert "255" not in out


def test_successful_step_emits_a_notice_without_diagnostics(capsys, tmp_path):
    log = tmp_path / "run.log"
    log.write_text("building\nerror text in a message body is fine\nQML OK size=1280x820\n", encoding="utf-8")
    rc = tmp_path / "run.exitcode"
    rc.write_text("0\n", encoding="utf-8")

    code = ci_tail.main(
        [
            "--log",
            str(log),
            "--title",
            "run.log (build.py --run exit 0)",
            "--exit-code-file",
            str(rc),
            "--level",
            "notice",
        ]
    )

    assert code == 0
    out = capsys.readouterr().out
    assert out.startswith("::notice title=run.log (build.py --run exit 0)::")
    assert "::error" not in out


def test_workflow_publishers_delegate_to_ci_tail():
    """The inline emitters are what got truncated; they must not come back.

    A test on the function alone would pass while the workflow still printed a
    raw tail, because the workflow is what runs in CI.
    """
    text = VALIDATION_WORKFLOW.read_text(encoding="utf-8")

    assert text.count("tools/ci_tail.py") >= 3
    # The removed inline emitters built their message from a raw line slice.
    assert "splitlines()[-80:]" not in text
    assert "splitlines()[-60:]" not in text


def test_no_publisher_invents_an_exit_code_for_a_step_that_never_ran():
    """Both log publishers, not just the build one, must check first.

    The build publisher was fixed in ee6c219, but the unit-test publisher kept
    ``cat app/pytest.exitcode 2>/dev/null || echo 255``. That is the same bug:
    a job that goes red before pytest runs gets a fabricated
    "pytest (exit 255)" annotation pointing at tests nobody executed.
    """
    text = VALIDATION_WORKFLOW.read_text(encoding="utf-8")
    assert "|| echo 255" not in text

    start = text.index("- name: Publish unit test log")
    publish = text[start : text.index("- name: Upload unit test log", start)]
    assert "if [ -f app/pytest.exitcode ]" in publish
    assert "Not run: an earlier step in this job failed." in publish
    not_run = publish.index("Not run: an earlier step")
    early_exit = publish.index("exit 0", not_run)
    emitter = publish.index("tools/ci_tail.py")
    assert not_run < early_exit < emitter


def test_ci_tail_runs_on_the_oldest_ci_interpreter():
    """The Build Tool job runs Python 3.8; the tool must be importable there.

    Compiling the source catches syntax the 3.8 grammar rejects without needing
    a 3.8 interpreter on this machine.
    """
    source = (TOOLS / "ci_tail.py").read_text(encoding="utf-8")
    compile(source, "ci_tail.py", "exec")
    # No f-string ``=`` specifier, no ``match`` statement: the usual ways a
    # 3.9+/3.10+ construct slips into a file the 3.8 job imports.
    assert "=}" not in source
    assert not any(line.strip().startswith("match ") for line in source.splitlines())


def test_a_diagnostic_keeps_the_detail_indented_under_it(capsys, tmp_path):
    """The header names the failure class; the indented lines name the library.

    ``ERROR: RuntimeError: Unresolved native dependencies:`` under an
    ``[4/6]`` stage is all a header-only picker reported for the windows-x86_64
    build, and the six files it could not resolve -- the actual cause -- were
    in the indented lines below it.
    """
    log = tmp_path / "build.log"
    log.write_text(
        "\n".join(
            [
                "[4/6] Package + native dependency closure",
                "ERROR: RuntimeError: Unresolved native dependencies:",
                "  site-packages/PySide6/plugins/sqldrivers/qsqlmysql.dll: libmysql.dll",
                "  site-packages/PySide6/plugins/sqldrivers/qsqlpsql.dll: libpq.dll",
                ">>> closing",
            ]
        ),
        encoding="utf-8",
    )
    rc = tmp_path / "build.exitcode"
    rc.write_text("1\n", encoding="utf-8")

    ci_tail.main(
        [
            "--log",
            str(log),
            "--title",
            "build.py (exit 1)",
            "--exit-code-file",
            str(rc),
            "--label",
            "build.log",
        ]
    )

    out = capsys.readouterr().out
    assert "libmysql.dll" in out
    assert "libpq.dll" in out
    # The detail rides with its header, not as a separate annotation.
    assert out.count("=>") == 0
    assert "::error title=build.py (exit 1)::ERROR: RuntimeError" in out


def test_an_unindented_line_ends_the_detail_block():
    """Detail collection must stop before swallowing the next statement."""
    lines = [
        "ERROR: RuntimeError: Unresolved native dependencies:",
        "  a.dll: b.dll",
        "and now something else entirely",
        "Traceback (most recent call last):",
    ]

    found = ci_tail.diagnostic_lines(lines)

    assert found == [
        "ERROR: RuntimeError: Unresolved native dependencies:\n  a.dll: b.dll",
        "Traceback (most recent call last):",
    ]
