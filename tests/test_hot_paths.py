"""Known slow patterns fail the security gate, old code included."""

import json
import re
import subprocess
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest
import yaml
from gate_config import Gate, Group
from hot_paths import RULES, findings, require_parsed, scan_all, unowned_paths
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


def coordinates(results: list[dict[str, object]]) -> list[tuple[str, str, int]]:
    return [
        (
            Path(str(result["path"])).name,
            str(result["check_id"]).rsplit(".", 1)[-1],
            result["start"]["line"],
        )
        for result in results
        if isinstance(result["start"], dict)
    ]


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
    with patch("hot_paths.require_parsed") as parsed:
        results = findings(tmp_path, ["src"], 900)
    parsed.assert_called_once_with([])
    actual = coordinates(results)
    assert sorted(actual) == sorted(expected)
    rules = yaml.safe_load(RULES.read_text())["rules"]
    assert {rule for _, rule, _ in actual} == {rule["id"] for rule in rules}


def test_exact_reported_inputs_keep_all_expected_findings(tmp_path: Path) -> None:
    fixtures = SOURCE / "tests/fixtures/reviewer-inputs"
    expected = json.loads((fixtures / "expected.json").read_text())
    for fixture in fixtures.glob("*.txt"):
        (tmp_path / fixture.name.removesuffix(".txt")).write_bytes(fixture.read_bytes())
    with patch("hot_paths.require_parsed") as parsed:
        results = findings(tmp_path, ["."], 900)
    parsed.assert_called_once()
    errors = parsed.call_args.args[0]
    require_parsed(errors)
    assert sorted(
        (Path(span["file"]).name, span["start"]["line"], error["type"][0])
        for error in errors
        for span in error["spans"]
    ) == [
        ("f3_q4_py_generic.py", 52, "PartialParsing"),
        ("f3_q4fmt_py_generic.py", 70, "PartialParsing"),
        ("r22_opus_p21e_nested_iter.swift", 5, "PartialParsing"),
        ("r22_opus_p21e_nested_iter.swift", 14, "PartialParsing"),
        ("r22_twin_opus_p21e_nested_iter.swift", 5, "PartialParsing"),
        ("r22_twin_opus_p21e_nested_iter.swift", 14, "PartialParsing"),
        ("r23_opus_p22_py_py.py", 19, "PartialParsing"),
        ("r23_twin_opus_p22_py_py.py", 23, "PartialParsing"),
    ]
    actual = coordinates(results)
    assert sorted(actual) == sorted(
        (name, rule, line)
        for name, rules in expected.items()
        for rule, lines in rules.items()
        for line in lines
    )


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

    assert not any(part.startswith("--exclude") for part in command)
    assert not any("performance.yaml" in part for part in other)
    assert result.returncode == 1
    (found,) = json.loads(result.stdout)["results"]
    assert (found["path"], found["start"]["line"]) == ("app.py", 5)
    report = package / "semgrep.json"
    report.write_text(result.stdout)
    with pytest.raises(ValueError, match=r"app\.py:5 Compile this constant regex"):
        validate_semgrep(report)


def test_generated_files_skip_only_hard_eng_rules(runner: ModuleType) -> None:
    """HE-HOT-PATH: a generated file leaves Hard Eng's rules but registry packs still scan it."""
    old = "import re\n\n\ndef old(text):\n    return re.findall(r'a+', text)\n"
    package = runner.ROOT / "ios"
    package.mkdir()
    for name in ("app.py", "client.py"):
        (package / name).write_text(old)
    (runner.ROOT / ".gitattributes").write_text("ios/client.py linguist-generated\n")
    (package / "pack.yaml").write_text(
        "rules:\n  - id: pack-rule\n    languages: [python]\n    severity: ERROR\n"
        "    message: pack\n    pattern: re.findall(...)\n"
    )
    git(runner.ROOT, "add", ".")
    git(runner.ROOT, "commit", "-qm", "base")
    gate: Gate = {
        "name": "security",
        "role": "security",
        "command": [
            "semgrep",
            "scan",
            "--metrics=off",
            "--json",
            "--config",
            "pack.yaml",
            ".",
        ],
    }
    command = runner.prepare_command({"path": "ios", "checks": []}, gate, 5)

    result = subprocess.run(
        command, cwd=package, capture_output=True, text=True, check=False
    )

    found = sorted(
        (item["path"], item["check_id"].rsplit(".", 1)[-1])
        for item in json.loads(result.stdout)["results"]
    )
    assert found == [
        ("app.py", "pack-rule"),
        ("app.py", "regex-built-in-function-python"),
        ("client.py", "pack-rule"),
    ]
    rules = yaml.safe_load(Path(command[command.index("--config") + 1]).read_text())
    assert all("/ios/client.py" in rule["paths"]["exclude"] for rule in rules["rules"])


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


def test_a_focused_scan_reads_only_the_named_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """HE-HOT-PATH: a focused check scans only the touched files it names."""
    cached = (
        "from functools import cache\n\n\n@cache\ndef square(x):\n    return x * x\n"
    )
    (tmp_path / "old.py").write_text(cached)
    (tmp_path / "new.py").write_text("def square(x):\n    return x * x\n")
    assert scan_all(tmp_path, 600, ["new.py"]) == 0
    assert "HE-HOT-PATH: 0 findings" in capsys.readouterr().out
    assert scan_all(tmp_path, 600, ["new.py", "old.py"]) == 1


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
    assert "Semgrep partly scanned View.swift:7" in capsys.readouterr().out


def test_a_partly_parsed_page_passes_the_gate_but_its_findings_fail_it(
    runner: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """HE-HOT-PATH: the stock Next.js page, which Semgrep parses only in part, passes; slow code in it fails."""
    page = runner.ROOT / "page.tsx"
    link = (
        '<a href="https://vercel.com/templates?framework=next.js&utm_source=app">Go</a>'
    )
    slow = "export function seen(text: string) {\n  return /a+b/.test(text);\n}\n"
    gate: Gate = {
        "name": "security",
        "role": "security",
        "command": ["semgrep", "scan", "--error", "--strict", "--metrics=off"]
        + ["--time", "--json", "--output", "semgrep.json", "."],
    }
    command = runner.prepare_command({"path": ".", "checks": []}, gate, 5)
    report = runner.ROOT / "semgrep.json"
    for code, failed in ((slow, 1), ("", 0)):
        page.write_text(
            f"{code}export default function Page() {{\n  return {link};\n}}\n"
        )
        result = subprocess.run(command, cwd=runner.ROOT, check=False)
        assert result.returncode == failed
        if failed:
            with pytest.raises(ValueError, match=r"page\.tsx:2 Build this constant"):
                validate_semgrep(report)
    validate_semgrep(report)
    assert "Semgrep partly scanned page.tsx:" in capsys.readouterr().out


@pytest.mark.parametrize(
    "fixture_name", ["await-condition.swift.txt", "task-group-next.swift.txt"]
)
def test_swift_awaited_throwing_condition_reports_its_parser_gap(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fixture_name: str
) -> None:
    fixture = SOURCE / "tests/fixtures/parse-gaps" / fixture_name
    (tmp_path / "condition.swift").write_text(fixture.read_text())
    assert findings(tmp_path, ["condition.swift"], 900) == []
    assert "Semgrep partly scanned condition.swift:3" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("language", "extension", "forms", "names"),
    [
        (
            "javascript",
            "js",
            (
                "function",
                "export",
                "default",
                "arrow",
                "method",
                "expression",
                "renamed",
                "default_parameter",
            ),
            ("inOrder", "inOrderSteps"),
        ),
        (
            "typescript",
            "ts",
            ("typed", "generic_arrow", "typed_method", "typed_default"),
            ("inOrder", "inOrderSteps"),
        ),
        (
            "dart",
            "dart",
            (
                "generic",
                "unnamed",
                "futureor",
                "typedef",
                "named_first",
                "named_last",
                "method",
            ),
            ("inOrder", "inOrderSteps"),
        ),
        ("python", "py", ("plain", "typed", "method"), ("in_order", "in_order_steps")),
        ("swift", "swift", ("plain", "throws", "method"), ("inOrder", "inOrderSteps")),
    ],
)
def test_async_helpers_keep_honest_and_escape_controls_in_each_language(
    language: str, extension: str, forms: tuple[str, ...], names: tuple[str, ...]
) -> None:
    for form in forms:
        for name in names:
            for control in ("honest", "escape"):
                fixture = FIXTURES / (
                    f"variant_{language}_{form}_{name}_{control}.{extension}.txt"
                )
                source = fixture.read_text()
                assert source.count(name) >= 2
                assert bool(ANNOTATION.search(source)) == (control == "escape")


def test_security_scans_skip_only_the_installed_hard_eng_files(
    runner: ModuleType,
) -> None:
    """A project's own files under .agents and any nested .hooks stay scanned."""
    root = runner.ROOT
    for name in (
        ".hooks/hard-eng-source.json",
        ".hooks/x.py",
        ".agents/skills/he/x.py",
        ".agents/skills/own/x.py",
        "src/.hooks/y.py",
    ):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("x = 1\n")
    marker = root / ".hooks/hard-eng-source.json"
    marker.write_text('{"revision": "abc", "skills": ["he"]}\n')
    (root / ".claude/skills").mkdir(parents=True)
    for skill in ("he", "own"):
        (root / ".claude/skills" / skill).symlink_to(f"../../.agents/skills/{skill}")
    git(root, "add", ".")
    group: Group = {"path": ".", "checks": []}
    gate: Gate = {
        "name": "security",
        "role": "security",
        "command": ["semgrep", "scan", "--error", "--metrics=off", "--json", "."],
    }

    command = runner.prepare_command(group, gate, 5)

    excludes = [part for part in command if part.startswith("--exclude")]
    assert excludes == ["--exclude=/.hooks/", "--exclude=/.agents/skills/he/"]
    marker.write_text('{"revision": "abc"}\n')
    older = runner.prepare_command(group, gate, 5)
    assert [part for part in older if part.startswith("--exclude")] == [
        "--exclude=/.hooks/"
    ]
    marker.unlink()
    source = runner.prepare_command(group, gate, 5)
    assert not [part for part in source if part.startswith("--exclude")]
