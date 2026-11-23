"""A plan with a visible change names the shared part of each control before any code is built."""

import hashlib
import json
from pathlib import Path

import pytest
from conftest import commit, git, init
from plans import validate_plan

MOCKUP = b"mockup-image-bytes"
NEW_PART = (
    "Search box — new `src/ui/SearchField.tsx` — mockup ![Mockup](design/search.png)"
)


def with_controls(visual_plan: str, line: str | None) -> str:
    text = "" if line is None else f"Controls: {line}\n"
    return visual_plan.replace(
        "Controls: None — the fixture changes only wording.\n", text
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    init(root)
    (root / "src/ui").mkdir(parents=True)
    (root / "src/ui/PasswordField.tsx").write_text("export {};\n")
    (root / "design").mkdir()
    (root / "design/search.png").write_bytes(MOCKUP)
    (root / "README.md").write_text("project\n")
    (root / "hard-eng.gates.json").write_text(
        json.dumps({"shipping": {"ui_paths": ["src/**"]}})
    )
    (root / "src/ui/Card.test.tsx").write_text("export {};\n")
    (root / "src/ui/Untracked.tsx").write_text("export {};\n")
    (root / ".gitignore").write_text("src/ui/Untracked.tsx\n")
    commit(root, "parts")
    return root


def refusal(project: Path, visual_plan: str, line: str | None) -> str:
    path = project / "PLAN.md"
    path.write_text(with_controls(visual_plan, line))
    with pytest.raises(ValueError) as error:
        validate_plan(path)
    return str(error.value)


@pytest.mark.parametrize(
    ("line", "words"),
    [
        (None, "Controls"),
        ("Password box — reuses `src/ui/Missing.tsx`", "src/ui/Missing.tsx"),
        ("Search box — new `src/ui/SearchField.tsx`", "mockup"),
        ("Password box", "reuses"),
        ("Password box — reuses `README.md`", "ui_paths"),
        ("Password box — reuses `.`", "one file"),
        ("Password box — reuses `src/ui`", "one file"),
        ("Password box — reuses `src/ui/Card.test.tsx`", "test file"),
        (
            "Search box — new `src/ui/SearchField.tsx` — mockup ![M](https://example.test/m.png)",
            "image file in the repository",
        ),
        (NEW_PART, "no `look` record"),
    ],
    ids=[
        "missing",
        "path-not-found",
        "new-without-mockup",
        "no-part",
        "outside-ui-paths",
        "dot",
        "folder",
        "test-file",
        "mockup-url",
        "mockup-not-looked-at",
    ],
)
def test_a_visible_plan_needs_a_real_shared_part_for_each_control(
    project: Path, visual_plan: str, line: str | None, words: str
) -> None:
    assert words in refusal(project, visual_plan, line)


def record_look(project: Path) -> None:
    folder = project / ".git/hard-eng/look"
    folder.mkdir(parents=True)
    digest = hashlib.sha256(MOCKUP).hexdigest()
    (folder / "abc.json").write_text(
        json.dumps({"images": [{"sha256": digest, "read": True}]})
    )


@pytest.mark.parametrize(
    "line",
    [
        "Password box — reuses `src/ui/PasswordField.tsx`",
        f"Password box — reuses `src/ui/PasswordField.tsx`; {NEW_PART}",
        "None — only the wording of a heading changes",
    ],
    ids=["reuse", "reuse-and-new", "none"],
)
def test_reused_new_and_no_controls_are_accepted(
    project: Path, visual_plan: str, line: str
) -> None:
    record_look(project)
    path = project / "PLAN.md"
    path.write_text(with_controls(visual_plan, line))
    assert validate_plan(path) == "Complete"


def test_the_full_gate_refuses_a_reused_part_that_git_does_not_track(
    project: Path,
) -> None:
    from plan_controls import tracked_problem

    line = "Controls: Password box — reuses `src/ui/Untracked.tsx`\n"
    assert "not a tracked file" in str(tracked_problem(line, project))
    kept = "Controls: Password box — reuses `src/ui/PasswordField.tsx`\n"
    assert tracked_problem(kept, project) is None
    assert tracked_problem("no controls here\n", project) is None


def committed_plan(project: Path, visual_plan: str) -> None:
    (project / "PLAN.md").write_text(with_controls(visual_plan, NEW_PART))
    commit(project, "plan with a new part")


def plan_in_push_snapshot(project: Path) -> str:
    """The plan check as pre-push runs it: in a fresh worktree of the pushing checkout."""
    from ship_actions import snapshot, snapshot_environment

    with snapshot(project, "HEAD", snapshot_environment(project), False) as checkout:
        return validate_plan(checkout / "PLAN.md")


def test_a_look_record_of_the_pushing_checkout_counts_in_the_push_snapshot(
    project: Path, visual_plan: str
) -> None:
    committed_plan(project, visual_plan)
    record_look(project)
    assert plan_in_push_snapshot(project) == "Complete"


def test_a_mockup_nobody_looked_at_is_still_refused_in_the_push_snapshot(
    project: Path, visual_plan: str
) -> None:
    committed_plan(project, visual_plan)
    with pytest.raises(ValueError, match="no `look` record"):
        plan_in_push_snapshot(project)


def test_a_look_record_of_a_linked_worktree_counts_in_the_push_snapshot(
    project: Path, visual_plan: str
) -> None:
    committed_plan(project, visual_plan)
    linked = project.parent / "linked"
    git(project, "worktree", "add", "-q", "--detach", str(linked))
    folder = linked / git(linked, "rev-parse", "--git-path", "hard-eng/look").strip()
    folder.mkdir(parents=True)
    digest = hashlib.sha256(MOCKUP).hexdigest()
    (folder / "abc.json").write_text(
        json.dumps({"images": [{"sha256": digest, "read": True}]})
    )
    assert plan_in_push_snapshot(project) == "Complete"
