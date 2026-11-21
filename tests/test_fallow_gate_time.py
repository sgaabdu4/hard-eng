"""The Fallow settings are judged again when the Fallow gate starts, so a script that ran earlier cannot change them after the first judge."""

import contextlib
from pathlib import Path
from types import ModuleType

import pytest
from gate_config import Gate, Group
from resolved_settings import validate_resolved
from test_fallow_resolved import SCAN, gate, need_fallow, repo

LAX = '{"ignorePatterns": ["src/big.ts"], "rules": {"unused-files": "off"}}'


def test_an_untracked_fallow_config_is_refused(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: a Fallow config that Git does not track can be written by a script just before the run."""
    root = repo(
        tmp_path,
        {
            ".gitignore": ".fallowrc.json\n",
            ".fallowrc.json": "{}",
            "src/main.ts": "export {};\n",
        },
    )
    groups: list[Group] = [{"path": ".", "language": "javascript", "checks": [gate()]}]
    with pytest.raises(ValueError, match=r"\.fallowrc\.json is not tracked by Git"):
        validate_resolved(root, groups, 900)


def test_the_runner_judges_the_config_right_before_fallow_starts(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A tests gate `pre` script writes the config after the first judge; the Fallow gate run judges it again and fails before Fallow starts."""
    need_fallow()
    (tmp_path / ".gitignore").write_text(".fallowrc.json\n")
    (tmp_path / ".fallowrc.json").write_text(LAX)
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.ts").write_text("export {};\n")

    def prepare(*_arguments: object) -> list[str]:
        return ["true"]

    monkeypatch.setattr(runner, "prepare_command", prepare)
    fallow: Gate = {
        "name": "fallow",
        "role": "dead-code-duplicates",
        "command": SCAN,
        "report": {"type": "fallow", "path": "coverage/fallow.json"},
    }
    group: Group = {"path": ".", "language": "javascript", "checks": [fallow]}
    failed = runner.run_limited_gate(
        group, fallow, 600, contextlib.nullcontext(), [group]
    )
    assert failed is True
    assert "not tracked by Git" in capsys.readouterr().out
