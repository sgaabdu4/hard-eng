"""Known slow patterns fail only on added lines; judgment cases print as notes."""

import re
import subprocess
from pathlib import Path

import pytest
import yaml
from hot_paths import RULES, findings, scan_all, scan_changes

SOURCE = Path(__file__).resolve().parents[1]
FIXTURES = SOURCE / "tests/semgrep/performance"
ANNOTATION = re.compile(r"ruleid: (\S+)")


def install_rules(root: Path) -> None:
    (root / RULES).parent.mkdir(parents=True)
    (root / RULES).write_text((SOURCE / RULES).read_text())


def git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


def test_each_rule_finds_exactly_the_annotated_lines(tmp_path: Path) -> None:
    """HE-HOT-PATH: every rule fires on its annotated line and nowhere else."""
    install_rules(tmp_path)
    expected = set()
    for fixture in sorted(FIXTURES.iterdir()):
        name = fixture.name.removesuffix(".txt")
        lines = fixture.read_text().splitlines()
        for number, line in enumerate(lines, 1):
            if match := ANNOTATION.search(line):
                expected.add((name, match[1], number + 1))
                lines[number - 1] = ""
        (tmp_path / "src").mkdir(exist_ok=True)
        (tmp_path / "src" / name).write_text("\n".join(lines) + "\n")
    actual = {
        (
            Path(str(result["path"])).name,
            str(result["check_id"]).rsplit(".", 1)[-1],
            result["start"]["line"],
        )
        for result in findings(tmp_path, ["src"], 600)
        if isinstance(result["start"], dict)
    }
    assert actual == expected
    rules = yaml.safe_load((SOURCE / RULES).read_text())["rules"]
    assert {rule for _, rule, _ in actual} == {rule["id"] for rule in rules}


def test_added_slow_code_fails_while_old_code_and_notes_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """HE-HOT-PATH: added slow code fails, old slow code passes, judgment cases are notes."""
    install_rules(tmp_path)
    git(tmp_path, "init", "-q", "-b", "main")
    old = "import re\n\n\ndef old(text):\n    return re.findall(r'a+', text)\n"
    (tmp_path / "app.py").write_text(old)
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "base")
    (tmp_path / "app.py").write_text(
        old + "\n\nasync def load(client, ids):\n"
        "    for item in ids:\n        await client.get(item)\n"
    )
    scan_changes(tmp_path, "HEAD", 600)
    output = capsys.readouterr().out
    assert "Performance note (HE-HOT-PATH): app.py:10 Each loop pass waits" in output
    assert "app.py:5" not in output

    (tmp_path / "app.py").write_text(
        old + "\n\ndef new(text):\n    return re.findall(r'b+', text)\n"
    )
    with pytest.raises(ValueError, match=r"HE-HOT-PATH: .*app\.py:9 Compile") as error:
        scan_changes(tmp_path, "HEAD", 600)
    assert "app.py:5" not in str(error.value)


def test_a_repository_scan_lists_old_and_new_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """HE-HOT-PATH: a requested whole-repository scan lists every finding and passes."""
    install_rules(tmp_path)
    (tmp_path / "app.py").write_text(
        "from functools import cache\n\n\n@cache\ndef square(x):\n    return x * x\n"
    )
    assert scan_all(tmp_path, 600) == 0
    output = capsys.readouterr().out
    assert "fix: app.py:4 Remove this cache" in output
    assert "HE-HOT-PATH: 1 findings" in output
