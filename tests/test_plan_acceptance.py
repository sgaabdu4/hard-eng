"""Each plan acceptance line names a test that exists and was not skipped."""

import json
from pathlib import Path
from types import ModuleType

import change_size
import gate_config
import pytest
from change_size import plan_tests
from conftest import add_origin, commit, configure, gate, git, init, plan_document
from gate_config import repository_files
from plans import is_plan_path, plan_files, validate_plan, validate_plans
from test_plans import edit, new_file, released_branch

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
        ("Tests/AppTests/ExitTests.swift::reportsTheExit", True),
        ("Tests/AppTests/ExitTests.swift::testExitCode", True),
        ("Tests/AppTests/ExitTests.swift::reportsTheExitCode", False),
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
    (root / "Tests/AppTests").mkdir(parents=True)
    (root / "Tests/AppTests/ExitTests.swift").write_text(
        "@Test func reportsTheExit() {}\nfinal class ExitCases: XCTestCase {\n"
        "    func testExitCode() throws {}\n}\n"
    )
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


def test_plan_stage_cannot_reuse_an_old_plan_for_changed_work(tmp_path: Path) -> None:
    root = tmp_path / "project"
    init(root)
    (root / "PLAN.md").write_text(plan_document())
    commit(root, "finished work")
    assert validate_plans(root, stage="Complete") == "Complete"
    (root / "app.py").write_text("value = 1\n")
    with pytest.raises(ValueError, match="need an applicable PLAN.md"):
        validate_plans(root, stage="Complete")


def test_plan_listing_matches_the_full_listing_filter(tmp_path: Path) -> None:
    root = tmp_path / "project"
    init(root)
    (root / ".gitignore").write_text("features/ignored/\n")
    (root / "Plan.MD").write_text(plan_document())
    for name in ("features/a/PLAN.md", "features/deep/er/plan.md", "features/PLAN.md"):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(plan_document())
    (root / "docs").mkdir()
    (root / "docs/PLAN.md").write_text("not a plan path\n")
    (root / "other/features").mkdir(parents=True)
    (root / "other/features/PLAN.md").write_text("not a plan path\n")
    (root / "features/ignored").mkdir()
    (root / "features/ignored/PLAN.md").write_text(plan_document())
    (root / "features/linked").mkdir()
    (root / "features/linked/PLAN.md").symlink_to(root / "Plan.MD")
    commit(root, "plans")
    (root / "features/new").mkdir()
    (root / "features/new/PLAN.md").write_text(plan_document())
    expected = [
        path for path in repository_files(root) if is_plan_path(path.relative_to(root))
    ]
    assert len(expected) == 5
    assert plan_files(root) == expected


def test_an_unpushed_plan_on_the_default_branch_covers_a_later_fix(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    init(root)
    (root / "README.md").write_text("first\n")
    commit(root, "first")
    add_origin(root)
    git(root, "fetch", "-q", "origin")
    (root / "PLAN.md").write_text(plan_document())
    commit(root, "plan and work")
    (root / "app.py").write_text("value = 1\n")
    assert validate_plans(root, stage="Complete") == "Complete"


def test_the_skip_rule_and_the_plan_rule_judge_the_same_plans(tmp_path: Path) -> None:
    root = tmp_path / "project"
    init(root)
    (root / ".hooks").mkdir()
    (root / ".hooks/hard-eng.py").write_text("")
    (root / "a.py").write_text("value = 0\n")
    (root / "PLAN.md").write_text(
        plan_document().replace(
            UNPROVED, "- [x] Moved → `tests/test_moved.py::test_moved`."
        )
    )
    commit(root, "base")
    add_origin(root)
    git(root, "fetch", "-q", "origin")
    git(root, "switch", "-qc", "work")
    (root / "features/moved").mkdir(parents=True)
    git(root, "mv", "PLAN.md", "features/moved/PLAN.md")
    commit(root, "move the plan")
    assert plan_tests(root, None) == set()
    git(root, "switch", "-q", "main")
    (root / "features/open").mkdir(parents=True)
    (root / "features/open/PLAN.md").write_text(
        plan_document()
        .replace("Status: Complete", "Status: Ready")
        .replace(UNPROVED, "- [x] Open → `tests/test_open.py::test_open`.")
    )
    commit(root, "open plan on the base")
    git(root, "push", "-q", "origin", "main")
    git(root, "switch", "-q", "work")
    git(root, "merge", "-q", "main")
    (root / "a.py").write_text("value = 1\nother = 2\n" * 20)
    commit(root, "big change")
    assert plan_tests(root, None) == {"test_open"}
    with pytest.raises(ValueError, match="features/open/PLAN.md: plan is Ready"):
        validate_plans(root)


def open_plan_on_the_base(repository: Path, completed_plan: str, status: str) -> None:
    (repository / "PLAN.md").write_text(
        completed_plan.replace("Status: Complete", f"Status: {status}")
    )
    released_branch(repository)


@pytest.mark.parametrize("status", ["Draft", "Ready"])
def test_a_small_change_needs_no_plan_when_the_base_holds_an_open_plan(
    repository: Path,
    completed_plan: str,
    capsys: pytest.CaptureFixture[str],
    status: str,
) -> None:
    open_plan_on_the_base(repository, completed_plan, status)
    edit(repository, "a.py", 3)
    commit(repository, "small code change")
    assert validate_plans(repository) == "Complete"
    assert "Size: small" in capsys.readouterr().out
    assert validate_plans(repository, stage="Ready") == "Ready"
    assert validate_plans(repository, "main") == "Complete"


@pytest.mark.parametrize("status", ["Draft", "Ready"])
def test_a_big_change_is_judged_by_the_open_plan_of_the_base(
    repository: Path, completed_plan: str, status: str
) -> None:
    open_plan_on_the_base(repository, completed_plan, status)
    new_file(repository)
    commit(repository, "big code change")
    with pytest.raises(ValueError, match=f"plan is {status}; this check requires"):
        validate_plans(repository)


@pytest.mark.parametrize("big", [False, True], ids=["small", "big"])
def test_a_branch_that_edits_the_open_plan_is_judged_by_it(
    repository: Path,
    completed_plan: str,
    monkeypatch: pytest.MonkeyPatch,
    big: bool,
) -> None:
    open_plan_on_the_base(repository, completed_plan, "Ready")
    new_file(repository) if big else edit(repository, "a.py", 3)
    (repository / "PLAN.md").write_text(
        completed_plan.replace("Status: Complete", "Status: Ready") + "\nmore\n"
    )
    commit(repository, "code and plan")
    asked: list[Path] = []

    def size_asked(root: Path) -> tuple[bool, str]:
        asked.append(root)
        return True, ""

    monkeypatch.setattr(change_size, "size_verdict", size_asked)
    with pytest.raises(ValueError, match="plan is Ready; this check requires"):
        validate_plans(repository)
    assert asked == []


@pytest.mark.parametrize(
    ("old", "new", "refusal"),
    [
        ("Retro: None — fixture command, no check failed.", "Retro: None", "Retro"),
        ("Retro: None — fixture command, no check failed.", "Retro: none.", "Retro"),
        (
            "Same cause: N/A — fixture command, not a fix.",
            "Same cause: NONE",
            "Same cause",
        ),
        (
            "Retro: None — fixture command, no check failed.",
            "Retro: Fixed in `tests/test_gone.py::test_gone`.",
            "tests that do not exist: tests/test_gone.py::test_gone",
        ),
        (
            "Same cause: N/A — fixture command, not a fix.",
            "Same cause: One owner; `tests/test_gone.py::test_gone` proves it.",
            "tests that do not exist: tests/test_gone.py::test_gone",
        ),
        (
            "Retro: None — fixture command, no check failed.",
            "Retro: Fixed in `tests/test_real.py::test_real`.",
            None,
        ),
        (
            "Same cause: N/A — fixture command, not a fix.",
            "Same cause: HE-YAGNI, step 3 of the plan.",
            None,
        ),
        (
            "Same cause: N/A — fixture command, not a fix.",
            "Same cause: `gate_schedule.py::run_checks` grew past its limit.",
            None,
        ),
    ],
)
def test_a_retro_or_same_cause_line_needs_a_reason_and_real_tests(
    repository: Path, completed_plan: str, old: str, new: str, refusal: str | None
) -> None:
    (repository / "tests").mkdir()
    (repository / "tests/test_real.py").write_text("def test_real() -> None: ...\n")
    (repository / "PLAN.md").write_text(completed_plan.replace(old, new))
    if refusal is None:
        assert validate_plans(repository, "0" * 40, "Complete") == "Complete"
        return
    with pytest.raises(ValueError, match=refusal) as error:
        validate_plans(repository, "0" * 40, "Complete")
    if "exist" not in refusal:
        assert "None — <reason>" in str(error.value)


def test_the_missing_reason_refusal_names_its_line(
    repository: Path, completed_plan: str
) -> None:
    line = "Evidence: The test asserts the exit, N/A for the rest of this long line"
    (repository / "PLAN.md").write_text(
        completed_plan.replace(
            "Evidence: The test asserts the observed command exit; this is fixture data.",
            line,
        )
    )
    with pytest.raises(ValueError, match="needs an inline reason") as error:
        validate_plans(repository, "0" * 40, "Complete")
    assert line[:60] in str(error.value)
    assert line[:61] not in str(error.value)


RETRO_LINE = "Retro: None — fixture command, no check failed."


def test_a_test_named_on_a_later_line_of_the_retro_value_must_exist(
    repository: Path, completed_plan: str
) -> None:
    (repository / "PLAN.md").write_text(
        completed_plan.replace(
            RETRO_LINE,
            "Retro: these items, each with its test.\n"
            "- Fixed → `tests/test_gone.py::test_gone`.",
        )
    )
    with pytest.raises(ValueError, match="tests/test_gone.py::test_gone"):
        validate_plans(repository, "0" * 40, "Complete")


def test_a_test_named_in_a_later_field_is_not_counted_for_the_retro_line(
    repository: Path, completed_plan: str
) -> None:
    (repository / "PLAN.md").write_text(
        completed_plan.replace(
            RETRO_LINE,
            RETRO_LINE + "\nDelivery: see `tests/test_gone.py::test_gone`.",
        )
    )
    assert validate_plans(repository, "0" * 40, "Complete") == "Complete"


def test_a_missing_retro_test_is_reported_for_the_retro_line(
    repository: Path, completed_plan: str
) -> None:
    (repository / "PLAN.md").write_text(
        completed_plan.replace(
            RETRO_LINE, "Retro: Fixed in `tests/test_gone.py::test_gone`."
        )
    )
    with pytest.raises(
        ValueError,
        match="Retro names tests that do not exist: tests/test_gone.py::test_gone",
    ):
        validate_plans(repository, "0" * 40, "Complete")
