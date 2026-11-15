"""The full check judges every tracked file, old code included."""

from pathlib import Path

import pytest
from conftest import commit, init
from switch_off_forms import RETRY_FORMS, SWITCHES
from whole_project import validate_whole_project

OFF = "A change must not switch a check off"
HIDDEN = "ok = 1\nx = 1  # no" + "qa\n"


def project(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "repo"
    tmp_path.mkdir(parents=True, exist_ok=True)
    init(root)
    for name, text in {"README.md": "fixture\n", **files}.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    commit(root, "baseline")
    return root


def refusal(root: Path) -> str:
    with pytest.raises(ValueError) as error:
        validate_whole_project(root)
    return str(error.value)


OLD_FORMS = [row for row in [*SWITCHES, *RETRY_FORMS] if row[0] != ".gitleaks.toml"]


@pytest.mark.parametrize(("name", "text", "pattern"), OLD_FORMS)
def test_old_switch_offs_anywhere_in_the_project_fail(
    tmp_path: Path, name: str, text: str, pattern: str
) -> None:
    """HE-NO-SWITCH-OFF: a switch-off that the project held before the change fails too."""
    root = project(tmp_path, {name: "ok = 1\n" + text})
    message = refusal(root)
    assert OFF in message
    assert f"{name}:2 holds {pattern!r}" in message


def test_switch_offs_in_generated_output_pass(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: generated output and scaffold paths stay exempt."""
    files = {
        ".gitattributes": "*.g.py linguist-generated=true\n",
        "made.g.py": HIDDEN,
        ".hooks/tool.py": HIDDEN,
        ".agents/skills/tool/run.py": HIDDEN,
        ".claude/rules/run.py": HIDDEN,
    }
    validate_whole_project(project(tmp_path, files))
    assert "app.py:2 holds" in refusal(project(tmp_path / "own", {"app.py": HIDDEN}))


ALLOWLIST_FORMS = {
    "[allowlist]": "[allowlist]\npaths = ['''a''']\n",
    "[[allowlists]]": "[[allowlists]]\npaths = ['''a''']\n",
    "rule allowlists": "[[rules]]\nid = 'mine'\nregex = '''a'''\n[[rules.allowlists]]\npaths = ['''a''']\n",
    "rule allowlist": "[[rules]]\nid = 'mine'\nregex = '''a'''\n[rules.allowlist]\npaths = ['''a''']\n",
}
DETECTION_ONLY = "[extend]\nuseDefault = true\n[[rules]]\nid = 'mine'\nregex = '''AKIA[A-Z0-9]{16}'''\n"


def test_gitleaks_rules_pass_and_allowlists_fail(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: an allowlist entry in the Gitleaks config fails; a detection rule does not."""
    notes = {".gitleaksignore": "# a note\n\n", ".semgrepignore": "# a note\n"}
    validate_whole_project(
        project(tmp_path / "rules", {".gitleaks.toml": DETECTION_ONLY, **notes})
    )
    for form, text in ALLOWLIST_FORMS.items():
        message = refusal(
            project(
                tmp_path / form.strip("[]").replace(" ", "-"), {".gitleaks.toml": text}
            )
        )
        assert ".gitleaks.toml holds an allowlist" in message, form
