"""A Hard Eng release must not turn an installed project red because of Hard Eng's own files."""

import json
import shutil
import subprocess
from pathlib import Path

import yaml
from conftest import SOURCE

RULES = SOURCE / ".agents/skills/he/semgrep"
ASYNC_RULES = {
    "await-in-loop-python",
    "in-order-needs-reason-python",
    "sequential-awaits-python",
}


def python_rules(path: Path) -> list[object]:
    rules = yaml.safe_load(path.read_text())["rules"]
    return [
        rule
        for rule in rules
        if rule.get("languages") == ["python"] and rule["id"] not in ASYNC_RULES
    ]


def test_the_consumer_semgrep_rules_find_nothing_in_the_hooks(tmp_path: Path) -> None:
    """The security gate of an installed project runs Hard Eng's Semgrep rules over `.hooks`; a regex built inside a function or an in-process cache there fails that gate."""
    rules = tmp_path / "rules.yaml"
    rules.write_text(
        yaml.safe_dump({"rules": python_rules(RULES / "performance.yaml")})
    )
    launcher = ["semgrep"] if shutil.which("semgrep") else ["uvx", "semgrep@latest"]
    report = tmp_path / "semgrep.json"
    done = subprocess.run(
        [
            *launcher,
            "scan",
            "--config",
            str(rules),
            "--config",
            str(RULES / "python.yaml"),
            "--metrics=off",
            "--timeout",
            "60",
            "--json",
            "--output",
            str(report),
            str(SOURCE / ".hooks"),
        ],
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    found = [
        f"{item['check_id'].rsplit('.', 1)[-1]} {item['path']}:{item['start']['line']}"
        for item in json.loads(report.read_text())["results"]
    ]
    assert not found
