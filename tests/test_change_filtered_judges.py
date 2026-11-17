"""A run limited to the changed packages still judges each package against every group."""

import json
from pathlib import Path
from types import ModuleType

import gitleaks_entries
import pytest
import resolved_settings
from conftest import SOURCE, commit, gate, git
from gate_config import Group


def nothing(*_arguments: object) -> None:
    return None


def never(*_arguments: object) -> bool:
    return False


def test_a_base_run_judges_the_changed_group_against_every_group(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real runner, given `--base`, runs only the changed group, but the settings judge sees both."""
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(runner, "provision_tools", nothing)
    monkeypatch.setattr(runner, "run_gates", never)
    seen: list[list[str]] = []

    def judge(
        _root: Path,
        groups: list[Group],
        _timeout: float,
        every: list[Group] | None = None,
    ) -> None:
        seen.append([group["path"] for group in groups])
        seen.append([group["path"] for group in every or []])

    monkeypatch.setattr(resolved_settings, "validate_resolved", judge)
    monkeypatch.setattr(gitleaks_entries, "validate_entries", nothing)
    (tmp_path / ".gitignore").write_text(".hard-eng/\ncoverage/\n")
    for path in ("first", "second"):
        (tmp_path / path).mkdir(parents=True, exist_ok=True)
    extra = [
        gate("lock", "pass", role="lockfiles"),
        gate("osv", "pass", role="vulnerabilities"),
    ]
    shared = json.loads((SOURCE / "hard-eng.gates.json").read_text())["shared"]
    secrets = [g for g in shared if g["role"] in {"secrets-files", "secrets-history"}]
    (tmp_path / "hard-eng.gates.json").write_text(
        json.dumps(
            {
                "packages": [
                    {
                        "path": path,
                        "depends_on": [],
                        "checks": [gate("suite", "pass")],
                    }
                    for path in ("first", "second")
                ],
                "shared": [*extra, *secrets],
            }
        )
    )
    (tmp_path / "first/a.txt").write_text("one\n")
    (tmp_path / "second/b.txt").write_text("one\n")
    git(tmp_path, "config", "user.email", "fixture@example.invalid")
    git(tmp_path, "config", "user.name", "Fixture")
    base = commit(tmp_path, "base")
    (tmp_path / "first/a.txt").write_text("two\n")
    commit(tmp_path, "change the parent only")
    assert runner.check(base=base) == 0
    assert "second" not in seen[0]
    assert {"first", "second"} <= set(seen[1])
