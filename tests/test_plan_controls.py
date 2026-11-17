"""A plan with a visible change names the shared part of each control before any code is built."""

import hashlib
import json
from pathlib import Path

import pytest
from conftest import commit, init
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
