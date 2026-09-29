import json
import os
import shutil
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import mutation
import pytest
from conftest import SOURCE, commit, init
from gate_config import Group

PRICE = """\
def discount(total: float, member: bool) -> float:
    if total >= 100 and member:
        return total * 0.9
    return total


class Basket:
    def label(self, total: float) -> str:
        if total >= 50:
            raise ValueError("too large for a small basket")
        return "small order"
"""


def project(root: Path, tests: list[str]) -> None:
    init(root)
    checks = [{"name": "tests", "role": "tests", "command": tests}]
    package = {"path": ".", "language": "python", "sources": ["src"], "checks": checks}
    config = {"packages": [{"name": "shop", **package}], "shared": list[str]()}
    (root / "hard-eng.gates.json").write_text(json.dumps(config))
    (root / "src/shop").mkdir(parents=True)
    (root / "src/shop/__init__.py").write_text("")
    (root / "src/shop/price.py").write_text(PRICE.replace("total >= 100 and ", ""))
    (root / "tests").mkdir()
    (root / "tests/test_price.py").write_text(
        textwrap.dedent("""\
            import pytest
            from shop.price import Basket, discount


            def test_members_over_100_get_ten_percent_off() -> None:
                assert discount(200, True) == 180


            def test_label() -> None:
                assert Basket().label(10) == "small order"
                with pytest.raises(ValueError):
                    Basket().label(60)
        """)
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "shop"\nversion = "0"\nrequires-python = ">=3.12"\n'
    )
    commit(root, "base")
    (root / "src/shop/price.py").write_text(PRICE)
    commit(root, "require a total of 100")


def sources(directory: Path, group: Group) -> set[Path]:
    return {path.resolve() for path in (directory / "src").rglob("*.py")}


def test_changed_lines_become_the_ranges_the_tools_mutate() -> None:
    diff = textwrap.dedent("""\
        diff --git a/src/a b.ts b/src/a b.ts
        --- a/src/a b.ts\t
        +++ b/src/a b.ts\t
        @@ -2 +2,3 @@ export function discount() {
        @@ -9,2 +11,0 @@
        @@ -20 +22 @@
        --- a/src/gone.ts
        +++ /dev/null
        @@ -1,4 +0,0 @@
    """)
    changed = mutation.changed_lines(diff)
    assert changed == {"src/a b.ts": {2, 3, 4, 22}}
    assert mutation.ranges(changed["src/a b.ts"]) == [(2, 4), (22, 22)]


def test_python_changes_select_the_functions_and_methods_that_hold_them() -> None:
    source = "import os\n\n# helper\n@cache\ndef first():\n    return 1\n\n\ndef second():\n    return 2\n\n\nclass Box:\n    def open(self):\n        return 'open'\n"
    selected = mutation.changed_functions("src/shop/__init__.py", source, {4, 15})
    assert selected == {
        "shop.x_first__mutmut_*": ("src/shop/__init__.py", {"@cache": 4}),
        "shop.xǁBoxǁopen__mutmut_*": ("src/shop/__init__.py", {"return 'open'": 15}),
    }
    with pytest.raises(ValueError, match="not an importable module path"):
        mutation.changed_functions(".hooks/update.py", source, {6})


@pytest.mark.parametrize(
    ("original", "mutated", "noise"),
    [
        ('return "small order"', 'return "XXsmall orderXX"', True),
        ('raise ValueError("too large")', "raise ValueError(None)", True),
        ('print(f"total {total}")', 'print(f"XXtotal XX{total}")', True),
        ("if total >= 100 and member:", "if total > 100 and member:", False),
        ('return label("a")', 'return None("a")', False),
    ],
)
def test_text_only_python_mutants_are_not_reported(
    original: str, mutated: str, noise: bool
) -> None:
    assert mutation.text_only(original, mutated) is noise


def test_mutmut_statuses_count_only_checked_mutants_of_changed_functions() -> None:
    results = """\
    shop.price.x_discount__mutmut_1: killed
    shop.price.x_discount__mutmut_2: survived
    shop.price.x_discount__mutmut_3: no tests
    shop.price.x_discount__mutmut_4: not checked
    shop.price.xǁBasketǁlabel__mutmut_1: survived
"""
    assert mutation.mutmut_statuses(results, ["shop.price.x_discount__mutmut_*"]) == {
        "shop.price.x_discount__mutmut_1": "killed",
        "shop.price.x_discount__mutmut_2": "survived",
        "shop.price.x_discount__mutmut_3": "no tests",
    }


def test_stryker_and_mutation_test_reports_list_what_survived() -> None:
    location = {"start": {"line": 2, "column": 7}, "end": {"line": 2, "column": 19}}
    stryker = {
        "files": {
            "src/price.ts": {
                "source": "export function discount() {\n  if (total >= 100 && member) {\n",
                "mutants": [
                    {"status": "Killed", "location": location, "replacement": "true"},
                    {
                        "status": "Survived",
                        "location": location,
                        "replacement": "total > 100",
                    },
                    {"status": "Ignored", "location": location, "replacement": "x"},
                ],
            }
        }
    }
    assert mutation.stryker_survivors(stryker) == (
        2,
        [
            (
                "src/price.ts",
                2,
                "if (total >= 100 && member) { → if (total > 100 && member) {",
            )
        ],
    )
    xunit = """<?xml version="1.0"?><testsuites><testsuite name="op">
        <testcase name="Line2_0" classname="lib/price.dart"/>
        <testcase name="Line2_1" classname="lib/price.dart">
          <failure type="undetected" message="All tests passed despite changing the code!">
File: lib/price.dart
Line: 2
Original line:   if (total &gt;= 100 &amp;&amp; member) {
Mutation:   if (total &gt; 100 &amp;&amp; member) {
</failure></testcase></testsuite></testsuites>"""
    assert mutation.xunit_survivors(xunit) == (
        2,
        [
            (
                "lib/price.dart",
                2,
                "if (total >= 100 && member) { → if (total > 100 && member) {",
            )
        ],
    )


def test_mutation_report_never_fails_when_a_tool_errors_or_hits_the_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "repo"
    project(root, ["pytest"])
    outcomes = iter([ValueError("mutmut did not finish"), mutation.Capped()])

    def adapter(*_arguments: object) -> mutation.Result:
        raise next(outcomes)

    monkeypatch.setitem(mutation.ADAPTERS, "python", adapter)
    assert mutation.report(root, "HEAD~1", 180, sources) == 0
    assert mutation.report(root, "HEAD~1", 180, sources) == 0
    output = capsys.readouterr().out
    assert "could not run for shop: mutmut did not finish" in output
    assert "stopped at its 180s limit before shop finished" in output
    assert "mutation --base HEAD~1` for the full result" in output


def test_interrupted_mutation_stops_the_tool_it_started(tmp_path: Path) -> None:
    root, marker = tmp_path / "repo", tmp_path / "tool.pid"
    project(root, ["pytest"])
    stubborn = f"import os, pathlib, signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); pathlib.Path({str(marker)!r}).write_text(str(os.getpid())); time.sleep(60)"
    script = f"""
import sys
from pathlib import Path
sys.path.insert(0, {str(SOURCE / ".hooks")!r})
import mutation, ship_actions
def adapter(directory, files, tests, deadline, work):
    mutation.run([sys.executable, "-c", {stubborn!r}], directory, None, work / "log")
mutation.ADAPTERS["python"] = adapter
production = lambda directory, group: set((directory / "src").rglob("*.py"))
ship_actions.mutate(Path({str(root)!r}), "HEAD~1", None, True, production)
"""
    runner = subprocess.Popen([sys.executable, "-c", script], cwd=root)
    deadline = time.monotonic() + 30
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    tool = int(marker.read_text())
    runner.send_signal(signal.SIGTERM)
    assert runner.wait(timeout=30) != 0
    with pytest.raises(ProcessLookupError):
        os.kill(tool, 0)


@pytest.mark.skipif(shutil.which("uv") is None, reason="mutmut runs through uv")
def test_python_mutation_reports_real_survivors_on_changed_lines(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "repo"
    project(root, ["uv", "run", "--no-sync", "pytest"])
    assert mutation.report(root, "HEAD~1", None, sources) == 0
    output = capsys.readouterr().out
    assert "src/shop/price.py:2  if total >= 100 and member: → " in output
    assert "label" not in output
