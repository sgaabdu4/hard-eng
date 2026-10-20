"""Each plan acceptance line names a test that exists and was not skipped."""

import json
from pathlib import Path
from types import ModuleType

import gate_config
import pytest
from conftest import commit, configure, gate, git, init, plan_document
from plans import validate_plan, validate_plans

# Fixture IDs are built so this file names no real registry ID.
REQ = "REQ"
EXIT_ID = f"{REQ}-APP-EXIT"
VALUE_ID = f"{REQ}-APP-VALUE"
UNPROVED = "- [x] Observe the configured command exit → N/A — fixture plan has no product test."


@pytest.mark.parametrize("status", ["Ready", "Complete"])
@pytest.mark.parametrize(
    ("line", "accepted"),
    [
        ("- [x] Observe the configured command exit.", False),
        ("- [x] Exit observed → N/A — rule text only, read in review.", True),
        ("- [x] Exit observed → `tests/test_app.py::test_exit[0|1]`.", True),
        ("- [x] Exit observed → `test/exit.test.ts::reports the exit`.", True),
        (f"- [x] Exit observed → {EXIT_ID}.", True),
    ],
)
def test_each_acceptance_line_names_its_test_or_why_none_applies(
    tmp_path: Path, completed_plan: str, status: str, line: str, accepted: bool
) -> None:
    path = tmp_path / "PLAN.md"
    plan = completed_plan.replace("Status: Complete", f"Status: {status}")
    path.write_text(plan.replace(UNPROVED, line))
    if accepted:
        assert validate_plan(path) == status
    else:
        with pytest.raises(
            ValueError, match="Acceptance .*`path::test name`.*requirement ID"
        ):
            validate_plan(path)


@pytest.mark.parametrize(
    ("reference", "exists"),
    [
        ("tests/test_app.py::test_exit", True),
        ("tests/test_app.py::test_exit[0|1]", True),
        ("test/exit.test.ts::reports the exit", True),
        ("tests/test_app.py::TestApp::test_method", True),
        ("tests/test_app.py::test_gone", False),
        ("tests/test_other.py::test_exit", False),
        ("app.py::test_exit", False),
        ("../outside/tests/test_app.py::test_exit", False),
    ],
)
def test_complete_plan_cannot_name_a_missing_test(
    runner: ModuleType, reference: str, exists: bool
) -> None:
    root = runner.ROOT
    (root / "tests").mkdir()
    (root / "tests/test_app.py").write_text(
        "def test_exit() -> None: ...\n"
        "class TestApp:\n    def test_method(self) -> None: ...\n"
    )
    (root / "app.py").write_text("def test_exit() -> None: ...\n")
    (root / "test").mkdir()
    (root / "test/exit.test.ts").write_text("it('reports the exit', () => {});\n")
    plan = root / "PLAN.md"
    plan.write_text(
        plan.read_text().replace(UNPROVED, f"- [x] Exit observed → `{reference}`.")
    )
    if exists:
        assert validate_plans(root, base="0" * 40, stage="Complete") == "Complete"
    else:
        with pytest.raises(ValueError, match="tests that do not exist: "):
            validate_plans(root, base="0" * 40, stage="Complete")


@pytest.mark.parametrize(
    ("registry", "covered", "accepted"),
    [
        ("Proof: check", True, True),
        ("Proof: check", False, False),
        ("Proof: guidance", False, False),
        ("Status: Retired", True, False),
        (None, True, False),
    ],
    ids=["tested", "untested", "guidance", "retired", "unknown"],
)
def test_complete_plan_resolves_a_requirement_id_to_its_tests(
    runner: ModuleType, registry: str | None, covered: bool, accepted: bool
) -> None:
    root = runner.ROOT
    if registry:
        (root / "docs").mkdir()
        (root / "docs/requirements.md").write_text(
            f"## {EXIT_ID} — Exit code\n\nThe command exits with zero.\n\n{registry}\n"
        )
    (root / "tests").mkdir()
    docstring = f'    """{EXIT_ID}: exit is zero."""\n' if covered else ""
    (root / "tests/test_app.py").write_text(f"def test_exit() -> None:\n{docstring}")
    plan = root / "PLAN.md"
    plan.write_text(plan.read_text().replace(UNPROVED, f"- [x] Exit → {EXIT_ID}."))
    if accepted:
        assert validate_plans(root, base="0" * 40, stage="Complete") == "Complete"
    else:
        with pytest.raises(ValueError, match=f"untested requirements: {EXIT_ID}"):
            validate_plans(root, base="0" * 40, stage="Complete")


@pytest.mark.parametrize("by_id", [False, True], ids=["path", "id"])
@pytest.mark.parametrize("skipped", [False, True])
def test_check_fails_when_an_acceptance_test_was_skipped(
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    skipped: bool,
    by_id: bool,
) -> None:
    """Only gate loading is faked; the plan, gate run, report and check are real."""
    root = runner.ROOT
    (root / "main.py").write_text(f"value = {VALUE_ID!r}\n")
    (root / "tests").mkdir()
    (root / "tests/test_main.py").write_text(
        f'def test_value() -> None:\n    """{VALUE_ID}: value kept."""\n'
    )
    (root / "docs").mkdir()
    (root / "docs/requirements.md").write_text(
        f"## {VALUE_ID} — Value\n\nThe value is kept.\n\nProof: check\n"
    )
    proof = VALUE_ID if by_id else "`tests/test_main.py::test_value`"
    plan = root / "PLAN.md"
    plan.write_text(plan.read_text().replace(UNPROVED, f"- [x] Value kept → {proof}."))
    marker = "<skipped/>" if skipped else ""
    junit = f'<testsuite><testcase name="test_other"/><testcase name="test_value">{marker}</testcase></testsuite>'
    coverage = {
        "files": {"main.py": {"summary": {"covered_lines": 1, "num_statements": 1}}}
    }
    code = (
        "from pathlib import Path;Path('coverage').mkdir(exist_ok=True);"
        f"Path('coverage/junit.xml').write_text({junit!r});"
        f"Path('coverage/coverage.json').write_text({json.dumps(coverage)!r})"
    )
    tests = gate(
        "tests",
        code,
        role="tests",
        report={
            "type": "python-tests",
            "tests": "coverage/junit.xml",
            "coverage": "coverage/coverage.json",
        },
    )
    group = {"path": ".", "language": "python", "sources": ["main.py"]}
    configure(root, [])

    def load_groups(*_: object, **__: object) -> list[dict[str, object]]:
        return [{**group, "checks": [tests]}]

    monkeypatch.setattr(gate_config, "load_groups", load_groups)
    assert runner.check(base="0" * 40, plan_stage="Complete") == int(skipped)
    output = capsys.readouterr().out
    assert ("skipped: test_value" in output) is skipped


def test_feature_check_sees_plans_the_release_will_check(tmp_path: Path) -> None:
    """A plan edited on the integration branch fails the feature PR, not only the release."""
    root = tmp_path / "project"
    init(root)
    legacy = plan_document().replace(
        UNPROVED, "- [x] Observe the configured command exit."
    )
    (root / "features/old").mkdir(parents=True)
    (root / "features/old/PLAN.md").write_text(legacy)
    commit(root, "release")
    git(root, "branch", "-M", "main")
    git(root, "checkout", "-qb", "develop")
    (root / "features/old/PLAN.md").write_text(legacy + "\nReopened on develop.\n")
    commit(root, "edit plan on develop")
    git(root, "checkout", "-qb", "feature")
    (root / "app.py").write_text("value = 1\n")
    commit(root, "feature code")
    with pytest.raises(ValueError, match="features/old/PLAN.md: Acceptance"):
        validate_plans(root, base="develop", stage="Complete")
