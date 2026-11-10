from pathlib import Path

import pytest
import update_pr
import update_runner
from test_update_runner import refused_release


def test_update_pr_fails_after_a_remembered_refusal(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target, _ = refused_release(release, monkeypatch)
    assert update_runner.apply_update(target) == 0
    capsys.readouterr()
    assert update_pr.publish(target) == 1
    printed = capsys.readouterr().out
    assert "Hard Eng update failed" in printed
    assert "secrets-files requires native" in printed
    assert "Nothing to publish" not in printed
