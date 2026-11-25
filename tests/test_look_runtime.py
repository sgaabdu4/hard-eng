"""`look` loads PyYAML the way the other commands do, and never reads the DESIGN.md tokens as none without a word."""

import sys
from pathlib import Path
from types import ModuleType

import look_facts
import pytest
import tool_setup
from conftest import SOURCE

FRONT = "---\nrounded:\n  sm: 6px\n---\n# Design\n"


def test_look_loads_the_yaml_runtime_before_it_reads_anything(
    browser: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(tool_setup, "ensure_python_runtime", lambda: calls.append("."))
    with pytest.raises(SystemExit):
        browser.run(SOURCE, ["look", "--help"])
    assert calls == ["."]


def test_an_unreadable_runtime_is_a_clear_refusal_not_a_silent_fallback(
    browser: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def missing() -> None:
        raise FileNotFoundError("uv is not on PATH; Hard Eng needs it.")

    monkeypatch.setattr(tool_setup, "ensure_python_runtime", missing)
    assert browser.run(SOURCE, ["look", "--help"]) == 1
    assert "uv is not on PATH" in capsys.readouterr().err


def test_a_design_front_matter_is_never_read_as_no_tokens_without_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(sys.modules, "yaml", None)
    with pytest.raises(ValueError, match="PyYAML"):
        look_facts.tokens_from_text(FRONT)
    assert look_facts.tokens_from_text("# Design\n\nPlain.\n") == look_facts.Tokens(
        {}, [], []
    )
    (tmp_path / "DESIGN.md").write_text(FRONT)
    with pytest.raises(ValueError, match="PyYAML"):
        look_facts.design_tokens(tmp_path)
