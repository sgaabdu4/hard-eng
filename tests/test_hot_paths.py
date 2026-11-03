"""Known slow patterns fail the security gate, old code included."""

import json
import re
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from gate_config import Gate, Group
from hot_paths import RULES, findings, scan_all, unowned_paths
from reports import validate_semgrep

SOURCE = Path(__file__).resolve().parents[1]
FIXTURES = SOURCE / "tests/fixtures/performance"
ANNOTATION = re.compile(r"ruleid: (\S+)")


def git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


def test_each_rule_finds_exactly_the_annotated_lines(tmp_path: Path) -> None:
    """HE-HOT-PATH: every rule fires on its annotated line and nowhere else."""
    expected = []
    for fixture in sorted(FIXTURES.iterdir()):
        name = fixture.name.removesuffix(".txt")
        lines = fixture.read_text().splitlines()
        for number, line in enumerate(lines, 1):
            if match := ANNOTATION.search(line):
                expected.append((name, match[1], number + 1))
                lines[number - 1] = ""
        (tmp_path / "src").mkdir(exist_ok=True)
        (tmp_path / "src" / name).write_text("\n".join(lines) + "\n")
    actual = [
        (
            Path(str(result["path"])).name,
            str(result["check_id"]).rsplit(".", 1)[-1],
            result["start"]["line"],
        )
        for result in findings(tmp_path, ["src"], 600)
        if isinstance(result["start"], dict)
    ]
    assert sorted(actual) == sorted(expected)
    rules = yaml.safe_load(RULES.read_text())["rules"]
    assert {rule for _, rule, _ in actual} == {rule["id"] for rule in rules}


def test_every_security_gate_fails_old_slow_code(runner: ModuleType) -> None:
    """HE-HOT-PATH: each security gate fails committed slow code, says how to fix it and skips generated files."""
    old = "import re\n\n\ndef old(text):\n    return re.findall(r'a+', text)\n"
    package = runner.ROOT / "ios"
    package.mkdir()
    (package / "app.py").write_text(old)
    (package / "client.py").write_text(old)
    (runner.ROOT / ".gitattributes").write_text("ios/client.py linguist-generated\n")
    git(runner.ROOT, "add", ".")
    git(runner.ROOT, "commit", "-qm", "base")
    group: Group = {"path": "ios", "checks": []}
    gate: Gate = {
        "name": "security",
        "role": "security",
        "command": ["semgrep", "scan", "--error", "--metrics=off", "--json", "."],
    }
    command = runner.prepare_command(group, gate, 5)
    other = runner.prepare_command(group, {**gate, "role": "lint"}, 5)

    result = subprocess.run(
        command, cwd=package, capture_output=True, text=True, check=False
    )

    assert "--exclude=/ios/client.py" in command
    assert not any("performance.yaml" in part for part in other)
    assert result.returncode == 1
    (found,) = json.loads(result.stdout)["results"]
    assert (found["path"], found["start"]["line"]) == ("app.py", 5)
    report = package / "semgrep.json"
    report.write_text(result.stdout)
    with pytest.raises(ValueError, match=r"app\.py:5 Compile this constant regex"):
        validate_semgrep(report)


def test_generated_folders_become_one_exclude_each() -> None:
    """HE-HOT-PATH: a vendored folder is one exclude, so large ones fit the command line."""
    names = [f"ios/Pods/{index}.m" for index in range(3)] + ["ios/Runner/App.swift"]
    names += [
        "types.ts",
        "src/types.ts",
        "src/app/[id]/page.ts",
        "src/app/[id]/form.ts",
    ]
    generated = {*names[:3], "types.ts", "src/app/[id]/page.ts"}

    assert unowned_paths(names, generated) == [
        "ios/Pods/",
        "src/app/[id]/page.ts",
        "types.ts",
    ]


def test_a_repository_scan_lists_every_finding_and_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """HE-HOT-PATH: `hot-paths` lists every finding and fails while any remain."""
    (tmp_path / "app.py").write_text(
        "from functools import cache\n\n\n@cache\ndef square(x):\n    return x * x\n"
    )
    assert scan_all(tmp_path, 600) == 1
    output = capsys.readouterr().out
    assert "app.py:4 Remove this cache" in output
    assert "HE-HOT-PATH: 1 findings" in output
    (tmp_path / "app.py").write_text("def square(x):\n    return x * x\n")
    assert scan_all(tmp_path, 600) == 0


def test_a_partly_parsed_file_still_reports_its_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """HE-HOT-PATH: a SwiftUI preview that Semgrep cannot parse does not fail the scan."""
    (tmp_path / "View.swift").write_text(
        "import SwiftUI\n\nfunc flags(size: Int) -> [Bool] {\n"
        "  return [Bool](repeating: false, count: size)\n}\n\n"
        '#Preview {\n  Text("Hello")\n}\n'
    )
    found = findings(tmp_path, ["View.swift"], 600)
    assert [
        result["start"]["line"] for result in found if isinstance(result["start"], dict)
    ] == [4]
    assert "HE-HOT-PATH: partly scanned" in capsys.readouterr().out
