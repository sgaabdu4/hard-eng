"""Hook events keep the project's Git file watcher out of file listings and its data in the index."""

import json
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from conftest import SOURCE, configure, gate, git
from test_gate_speed import QUIET_STOP, quiet_stop

# Only a compare of the whole work tree with a commit gains from a watcher's answer.
WATCHER_ASKS = re.compile(
    r"git (-c core\.quotepath=off )?"
    r"(--no-optional-locks status --porcelain=v2|diff (-U0|--name-only|--name-status|--numstat)) "
)


def watched(repository: Path, tmp_path: Path) -> Path:
    """Git asks a watcher that writes the asking command to a file and reports every path changed."""
    asked, watcher = tmp_path / "asked", tmp_path / "watcher"
    watcher.write_text(
        f"#!/bin/sh\nps -o args= -p $PPID >> {asked}\nprintf 'token\\0/\\0'\n"
    )
    watcher.chmod(0o755)
    git(repository, "config", "core.fsmonitor", str(watcher))
    return asked


def hook_event(repository: Path, event: str, payload: Mapping[str, object]) -> str:
    return subprocess.run(
        [sys.executable, str(repository / ".hooks/hard-eng.py"), event, "claude"],
        cwd=repository,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    ).stdout


def test_hook_events_ask_the_file_watcher_only_for_whole_tree_compares(
    repository: Path, tmp_path: Path
) -> None:
    configure(repository, [gate("suite", "pass", role="lint")])
    for name in ("PRODUCT.md", "DESIGN.md"):
        (repository / name).write_text((SOURCE / name).read_text())
    (repository / "app.py").write_text("value = 1\n")
    quiet_stop(repository)
    asked = watched(repository, tmp_path)
    assert "No changes" in hook_event(repository, "stop", QUIET_STOP)
    (repository / "app.py").write_text("value = 2\n")
    hook_event(repository, "session", {"session_id": "watched"})
    assert "quick checks passed" in hook_event(repository, "stop", QUIET_STOP)
    lines = asked.read_text().splitlines()
    assert lines
    assert [line for line in lines if not WATCHER_ASKS.match(line)] == []


def test_a_session_start_keeps_the_file_watcher_data_in_the_index(
    repository: Path, tmp_path: Path
) -> None:
    quiet_stop(repository)
    watched(repository, tmp_path)
    git(repository, "status")
    index = repository / ".git/index"
    assert b"FSMN" in index.read_bytes()
    hook_event(repository, "session", {"session_id": "watched"})
    kept = b"FSMN" in index.read_bytes()
    assert kept
