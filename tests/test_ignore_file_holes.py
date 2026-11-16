"""A switch-off cannot hide in a link, a config chain or an odd spelling."""

import os
from pathlib import Path

import pytest
from comments import validate_suppressions
from conftest import commit, init
from gitleaks_entries import validate_entries
from whole_project import validate_whole_project

KEY = 'token = "AKIA' + 'IOSFODNN7EXAMPLQ"\n'
RULE = "aws-access-token"


def linked_project(tmp_path: Path, link: str, target: str, text: str) -> Path:
    root = tmp_path / "repo"
    init(root)
    (root / "README.md").write_text("fixture\n")
    (root / "live.py").write_text(KEY)
    (root / target).parent.mkdir(parents=True, exist_ok=True)
    (root / target).write_text(text)
    os.symlink(target, root / link)
    commit(root, "baseline")
    return root


@pytest.mark.parametrize(
    ("link", "target"),
    [
        (".gitleaksignore", "docs/scan-notes.txt"),
        (".semgrepignore", "docs/notes.txt"),
        (".gitleaks.toml", "docs/notes.toml"),
        ("ruff.toml", "docs/ruff-base.toml"),
        (".fallowrc.json", "docs/fallow.json"),
        ("Cargo.toml", "docs/Cargo.toml"),
    ],
)
def test_a_linked_ignore_or_settings_file_is_refused(
    tmp_path: Path, link: str, target: str
) -> None:
    """HE-NO-SWITCH-OFF: a link to an ignore or settings file hides its lines from every check, so the link fails."""
    root = linked_project(tmp_path, link, target, f"live.py:{RULE}:1\n")
    with pytest.raises(ValueError, match=rf"{link}:1 is a link") as error:
        validate_whole_project(root)
    assert "HE-NO-SWITCH-OFF" in str(error.value)


def test_a_linked_root_gitleaks_entry_file_hides_no_secret(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: the entry judge and the changed-file check both refuse the link; Gitleaks would read it."""
    root = linked_project(
        tmp_path, ".gitleaksignore", "docs/scan-notes.txt", f"live.py:{RULE}:1\n"
    )
    with pytest.raises(ValueError, match="is a link"):
        validate_entries(root, 900)
    fresh = tmp_path / "fresh"
    init(fresh)
    (fresh / "README.md").write_text("fixture\n")
    base = commit(fresh, "baseline")
    (fresh / "docs").mkdir()
    (fresh / "docs/scan-notes.txt").write_text(f"live.py:{RULE}:1\n")
    os.symlink("docs/scan-notes.txt", fresh / ".gitleaksignore")
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_suppressions(fresh, base)
    commit(fresh, "link")
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_suppressions(fresh, base)


MUTED = {
    "entropy": "[extend]\nuseDefault = true\n[[rules]]\nid = 'aws-access-token'\nregex = '''AKIA[A-Z0-9]{16}'''\nentropy = 99.0\n",
    "regex": "[extend]\nuseDefault = true\n[[rules]]\nid = 'aws-access-token'\nregex = '''a^'''\n",
    "same regex": "[extend]\nuseDefault = true\n[[rules]]\nid = 'aws-access-token'\nregex = '''AKIA[A-Z0-9]{16}'''\n",
}
NEW_RULE = "[extend]\nuseDefault = true\n[[rules]]\nid = 'my-own-token'\nregex = '''own_[a-z]{12}'''\n"


def leaks(root: Path) -> int:
    from gitleaks_entries import ensure_gitleaks, scan

    ensure_gitleaks(900)
    report = root / "report.json"
    config = ["--config", str(root / ".gitleaks.toml")]
    return len(scan(["dir", "."], root, report, config, 900))


@pytest.mark.parametrize("form", MUTED)
def test_a_gitleaks_rule_that_overrides_a_default_rule_is_refused(
    tmp_path: Path, form: str
) -> None:
    """HE-NO-SWITCH-OFF: a rule with a default rule's id replaces it, so a key can stop matching; the real scan shows the miss."""
    root = tmp_path / "repo"
    init(root)
    (root / "README.md").write_text("fixture\n")
    (root / "live.py").write_text("AKIA" + "IOSFODNN7EXAMPLQ\n")
    (root / ".gitleaks.toml").write_text("[extend]\nuseDefault = true\n")
    assert leaks(root) == 1
    (root / ".gitleaks.toml").write_text(MUTED[form])
    commit(root, "baseline")
    if form != "same regex":
        assert leaks(root) == 0
    with pytest.raises(
        ValueError,
        match=r"\.gitleaks\.toml:\d+ overrides the default rule aws-access-token",
    ):
        validate_whole_project(root)


def test_a_new_gitleaks_rule_passes(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init(root)
    (root / "README.md").write_text("fixture\n")
    (root / ".gitleaks.toml").write_text(NEW_RULE)
    commit(root, "baseline")
    validate_whole_project(root)
