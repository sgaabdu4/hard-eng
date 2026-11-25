"""The reviewer sessions of `look`: the command for each other agent, the first one that runs, and the proof that it opened its images."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from challenge import host_for, reviewers_for, without_host_markers
from models import cli_flags, trusted_base_ref
from process_group import run_in_group

TIMEOUT_SECONDS = 1800
LOOK_REVIEWERS = ("claude", "codex")


def command(
    reviewer: str, prompt: str, folder: Path, root: Path | None = None
) -> list[str]:
    flags = cli_flags(reviewer, "reasoning", root, trusted_ref=trusted_base_ref(root))
    if reviewer == "codex":
        return [
            "codex",
            "exec",
            *flags,
            "--json",
            "--sandbox",
            "read-only",
            "-c",
            "features.plugins=false",
            "--skip-git-repo-check",
            "--cd",
            str(folder),
            prompt,
        ]
    return [
        "claude",
        "--print",
        prompt,
        *flags,
        "--safe-mode",
        "--tools",
        "Read",
        "--allowedTools",
        "Read",
        "--permission-mode",
        "dontAsk",
        "--no-session-persistence",
        "--output-format",
        "stream-json",
        "--verbose",
    ]


def rows(text: str) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            found.append(row)
    return found


def content(row: dict[str, object]) -> list[dict[str, object]]:
    message = row.get("message")
    parts = message.get("content") if isinstance(message, dict) else None
    return (
        [part for part in parts if isinstance(part, dict)]
        if isinstance(parts, list)
        else []
    )


def claude_proof(stream: str) -> tuple[dict[str, str], str, str]:
    """The image paths that a Read call opened with an image result, with the read time, the session id and the final text."""
    asked: dict[object, object] = {}
    opened: dict[str, str] = {}
    session, answer = "", ""
    for row in rows(stream):
        session = str(row.get("session_id") or session)
        if row.get("type") == "result" and row.get("is_error") is not True:
            answer = str(row.get("result") or "")
        for part in content(row):
            if part.get("type") == "tool_use" and part.get("name") == "Read":
                arguments = part.get("input")
                asked[part.get("id")] = (
                    arguments.get("file_path") if isinstance(arguments, dict) else None
                )
            inner = part.get("content")
            seen = isinstance(inner, list) and any(
                isinstance(item, dict) and item.get("type") == "image" for item in inner
            )
            if (
                part.get("type") == "tool_result"
                and seen
                and part.get("is_error") is not True
            ):
                path = asked.get(part.get("tool_use_id"))
                if isinstance(path, str):
                    opened[path] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return opened, session, answer


def codex_session_file(thread: str) -> Path | None:
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    found = sorted((home / "sessions").glob(f"**/rollout-*-{thread}.jsonl"))
    return found[-1] if found else None


def codex_proof(stream: str) -> tuple[dict[str, str], str, str]:
    """The image paths in the thread's session file as ImageView items, with their times, the thread id and the final text."""
    thread, answer = "", ""
    for row in rows(stream):
        thread = str(row.get("thread_id") or thread)
        item = row.get("item")
        if (
            row.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "agent_message"
        ):
            answer = str(item.get("text") or "")
    opened: dict[str, str] = {}
    session = codex_session_file(thread) if thread else None
    for row in rows(session.read_text(errors="replace")) if session else []:
        payload = row.get("payload")
        item = payload.get("item") if isinstance(payload, dict) else None
        if isinstance(item, dict) and item.get("type") == "ImageView":
            opened[str(item.get("path", "")).removeprefix("file://")] = str(
                row.get("timestamp")
            )
    return opened, thread, answer


def failure_message(stream: str) -> str:
    """The message of the last `error` object in a JSON stream; Codex writes its limit text there, not to stderr."""
    for row in reversed(rows(stream)):
        error = row.get("error")
        message = error.get("message") if isinstance(error, dict) else None
        if isinstance(message, str) and message:
            return message
    return ""


def run_reviewer(
    reviewer: str, folder: Path, prompt: str, root: Path | None = None
) -> tuple[subprocess.CompletedProcess[str] | None, str, bool]:
    try:
        result = run_in_group(
            command(reviewer, prompt, folder, root),
            cwd=folder,
            env=without_host_markers(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return None, f"not done: {reviewer} is not installed", False
    except subprocess.TimeoutExpired:
        return None, f"not done: {reviewer} timed out after {TIMEOUT_SECONDS}s", False
    if result.returncode:
        reason = failure_message(result.stdout) or (
            result.stderr.strip().rpartition("\n")[2] or "no error output"
        )
        return None, f"not done: {reviewer} exited {result.returncode}: {reason}", True
    return result, "", False


def reviewer_attempts(
    host: str | None, root: Path | None = None
) -> list[tuple[str, bool]]:
    """The installed supported other agents in challenge_order, then a fresh same-agent session when supported."""
    current = host_for(host)
    candidates = [
        name for name in reviewers_for(current, root) if name in LOOK_REVIEWERS
    ]
    attempts = [(name, False) for name in candidates if shutil.which(name)]
    if current in LOOK_REVIEWERS:
        attempts.append((current, True))
    return attempts or [(candidates[0], False)]


def run_first_reviewer(
    host: str | None, folder: Path, prompt: str, root: Path | None
) -> tuple[str, bool, subprocess.CompletedProcess[str] | None, str, list[str]]:
    """Move to the next reviewer only when one exits non-zero; a review that ran is never retried."""
    skipped: list[str] = []
    attempts = reviewer_attempts(host, root)
    for reviewer, fresh in attempts[:-1]:
        result, problem, exited = run_reviewer(reviewer, folder, prompt, root)
        if not exited:
            return reviewer, fresh, result, problem, skipped
        skipped.append(problem)
    reviewer, fresh = attempts[-1]
    result, problem, _ = run_reviewer(reviewer, folder, prompt, root)
    return reviewer, fresh, result, problem, skipped
