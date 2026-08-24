#!/usr/bin/env python3
"""Regression checks for the adversarial-review CLI wrapper."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "skills/adversarial-review/scripts/run_review.py"
SAMPLE_REVIEW = {
    "verdict": "CONCERNS",
    "summary": "One material gap needs host verification.",
    "findings": [
        {
            "severity": "Medium",
            "title": "Missing boundary proof",
            "claim": "The packet does not prove the retry boundary.",
            "evidence": [{"path": "<packet>", "line": None, "fact": "No retry evidence is listed."}],
            "failure_scenario": "A second attempt repeats the same external side effect.",
            "impact": "The operation can run twice.",
            "verification": "Inspect the retry owner and run its focused contract.",
            "confidence": "medium",
        }
    ],
    "coverage": [
        {"area": "outcome and requirements", "status": "checked", "evidence": "Outcome inspected."},
        {"area": "root cause", "status": "checked", "evidence": "Packet claim inspected."},
        {"area": "owner, callers, and blast radius", "status": "checked", "evidence": "Owner inspected."},
        {
            "area": "state, ordering, concurrency, retry, and rollback",
            "status": "checked",
            "evidence": "Retry boundary inspected.",
        },
        {"area": "security, privacy, and data loss", "status": "checked", "evidence": "Data effects inspected."},
        {"area": "test sensitivity", "status": "checked", "evidence": "Test seam inspected."},
        {
            "area": "release, deployment, and observability",
            "status": "unknown",
            "evidence": "No release target supplied.",
        },
        {"area": "simplicity and existing capabilities", "status": "checked", "evidence": "Existing owner inspected."},
    ],
    "unknowns": ["Release target is not supplied."],
}


def write_executable(path: Path, source: str) -> None:
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    path.chmod(0o755)


def fake_claude(path: Path, capture: Path, *, valid: bool = True, failure: str | None = None) -> None:
    response = (
        json.dumps({"type": "result", "is_error": False, "structured_output": SAMPLE_REVIEW}) if valid else "not-json"
    )
    write_executable(
        path,
        f"""\
        #!/usr/bin/env python3
        import json
        import os
        import pathlib
        import sys

        pathlib.Path({str(capture)!r}).write_text(
            json.dumps({{
                "argv": sys.argv[1:],
                "stdin": sys.stdin.read(),
                "environment": {{
                    key: os.environ[key]
                    for key in ("ANTHROPIC_API_KEY", "CLAUDE_CONFIG_DIR", "OPENAI_API_KEY", "CODEX_HOME")
                    if key in os.environ
                }},
            }}),
            encoding="utf-8",
        )
        if {failure!r} is not None:
            print({failure!r}, file=sys.stderr)
            raise SystemExit(1)
        print({response!r})
        """,
    )


def fake_codex(path: Path, capture: Path) -> None:
    review = json.dumps(SAMPLE_REVIEW)
    write_executable(
        path,
        f"""\
        #!/usr/bin/env python3
        import json
        import os
        import pathlib
        import sys

        arguments = sys.argv[1:]
        pathlib.Path({str(capture)!r}).write_text(
            json.dumps({{
                "argv": arguments,
                "stdin": sys.stdin.read(),
                "environment": {{
                    key: os.environ[key]
                    for key in ("ANTHROPIC_API_KEY", "CLAUDE_CONFIG_DIR", "OPENAI_API_KEY", "CODEX_HOME")
                    if key in os.environ
                }},
            }}),
            encoding="utf-8",
        )
        output = pathlib.Path(arguments[arguments.index("-o") + 1])
        output.write_text({review!r}, encoding="utf-8")
        """,
    )


def fake_hanging_claude(path: Path, child_pid: Path) -> None:
    write_executable(
        path,
        f"""\
        #!/usr/bin/env python3
        import pathlib
        import subprocess
        import sys
        import time

        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        pathlib.Path({str(child_pid)!r}).write_text(str(child.pid), encoding="utf-8")
        time.sleep(30)
        """,
    )


def invoke(
    host: str, repo: Path, packet: Path, output: Path, claude: Path, codex: Path, timeout_seconds: int = 10
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--host",
            host,
            "--repo",
            str(repo),
            "--packet",
            str(packet),
            "--output",
            str(output),
            "--timeout-seconds",
            str(timeout_seconds),
            "--claude-bin",
            str(claude),
            "--codex-bin",
            str(codex),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "ANTHROPIC_API_KEY": "anthropic-test-key",
            "CLAUDE_CONFIG_DIR": "/test/claude",
            "OPENAI_API_KEY": "openai-test-key",
            "CODEX_HOME": "/test/codex",
        },
        timeout=30,
    )


def read_capture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def value_after(arguments: list[str], flag: str) -> str:
    return arguments[arguments.index(flag) + 1]


def assert_result(output: Path, host: str, provider: str, model: str) -> None:
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["host"] == host
    assert payload["reviewer"] == {"provider": provider, "model": model, "effort": "max"}
    assert payload["review"] == SAMPLE_REVIEW


def check_claude_route(root: Path, repo: Path, packet: Path) -> None:
    claude_capture = root / "claude-capture.json"
    codex_capture = root / "unused-codex-capture.json"
    claude = root / "claude"
    codex = root / "codex"
    output = root / "claude-review.json"
    fake_claude(claude, claude_capture)
    fake_codex(codex, codex_capture)
    completed = invoke("codex", repo, packet, output, claude, codex)
    assert completed.returncode == 0, completed.stderr
    assert not codex_capture.exists(), "same-provider fallback ran"
    capture = read_capture(claude_capture)
    arguments = capture["argv"]
    assert arguments[0] == "-p"
    assert "--safe-mode" in arguments
    assert value_after(arguments, "--model") == "claude-fable-5"
    assert value_after(arguments, "--effort") == "max"
    assert value_after(arguments, "--permission-mode") == "plan"
    assert value_after(arguments, "--tools") == "Read,Glob,Grep"
    assert value_after(arguments, "--max-turns") == "50"
    assert "--disallowedTools" not in arguments
    assert "--disallowed-tools" not in arguments
    assert "--no-session-persistence" in arguments
    assert value_after(arguments, "--add-dir") == str(repo.resolve())
    assert value_after(arguments, "--output-format") == "json"
    schema = json.loads(value_after(arguments, "--json-schema"))
    assert schema["additionalProperties"] is False
    assert "review packet" in capture["stdin"]
    assert str(repo.resolve()) in capture["stdin"]
    assert capture["environment"] == {"ANTHROPIC_API_KEY": "anthropic-test-key", "CLAUDE_CONFIG_DIR": "/test/claude"}
    assert_result(output, "codex", "anthropic", "claude-fable-5")


def check_codex_route(root: Path, repo: Path, packet: Path) -> None:
    claude_capture = root / "unused-claude-capture.json"
    codex_capture = root / "codex-capture.json"
    claude = root / "claude-two"
    codex = root / "codex-two"
    output = root / "codex-review.json"
    fake_claude(claude, claude_capture)
    fake_codex(codex, codex_capture)
    completed = invoke("claude", repo, packet, output, claude, codex)
    assert completed.returncode == 0, completed.stderr
    assert not claude_capture.exists(), "same-provider fallback ran"
    capture = read_capture(codex_capture)
    arguments = capture["argv"]
    assert arguments[0] == "exec"
    assert "--strict-config" in arguments
    assert "--ignore-user-config" in arguments
    assert "--skip-git-repo-check" in arguments
    assert value_after(arguments, "--sandbox") == "read-only"
    assert "--ephemeral" in arguments
    assert value_after(arguments, "-m") == "gpt-5.6-sol"
    configs = {arguments[index + 1] for index, value in enumerate(arguments) if value == "-c"}
    assert 'model_reasoning_effort="max"' in configs
    assert 'approval_policy="never"' in configs
    assert 'shell_environment_policy.inherit="none"' in configs
    assert 'web_search="disabled"' in configs
    assert "agents.enabled=false" in configs
    disabled = {arguments[index + 1] for index, value in enumerate(arguments) if value == "--disable"}
    assert {
        "apps",
        "browser_use",
        "computer_use",
        "hooks",
        "memories",
        "plugins",
        "skill_search",
        "view_image",
    } <= disabled
    assert value_after(arguments, "--add-dir") == str(repo.resolve())
    assert value_after(arguments, "-C") != str(repo.resolve())
    assert "--output-schema" in arguments
    assert "--dangerously-bypass-approvals-and-sandbox" not in arguments
    assert "--dangerously-bypass-hook-trust" not in arguments
    assert arguments[-1] == "-"
    assert "review packet" in capture["stdin"]
    assert str(repo.resolve()) in capture["stdin"]
    assert capture["environment"] == {"OPENAI_API_KEY": "openai-test-key", "CODEX_HOME": "/test/codex"}
    assert_result(output, "claude", "openai", "gpt-5.6-sol")


def check_invalid_output_stops(root: Path, repo: Path, packet: Path) -> None:
    claude_capture = root / "invalid-claude-capture.json"
    codex_capture = root / "fallback-codex-capture.json"
    claude = root / "invalid-claude"
    codex = root / "fallback-codex"
    output = root / "invalid-review.json"
    fake_claude(claude, claude_capture, valid=False)
    fake_codex(codex, codex_capture)
    completed = invoke("codex", repo, packet, output, claude, codex)
    assert completed.returncode != 0
    assert not output.exists()
    assert not codex_capture.exists(), "invalid output triggered a fallback"
    assert "prepared review packet" not in completed.stderr


def check_usage_limit_is_safe(root: Path, repo: Path, packet: Path) -> None:
    diagnostics = {
        "reached": "You've reached your Fable 5 limit for private-account@example.com.",
        "hit": "You've hit your Opus limit for private-account@example.com.",
    }
    for label, diagnostic in diagnostics.items():
        claude_capture = root / f"{label}-limited-claude-capture.json"
        codex_capture = root / f"{label}-limited-fallback-codex-capture.json"
        claude = root / f"{label}-limited-claude"
        codex = root / f"{label}-limited-fallback-codex"
        output = root / f"{label}-limited-review.json"
        fake_claude(claude, claude_capture, failure=diagnostic)
        fake_codex(codex, codex_capture)
        completed = invoke("codex", repo, packet, output, claude, codex)
        assert completed.returncode != 0
        assert "reason=usage_limit" in completed.stderr
        assert "diagnostic_sha256=" in completed.stderr
        assert "private-account@example.com" not in completed.stderr
        assert not output.exists()
        assert not codex_capture.exists(), "usage limit triggered a fallback"


def check_repository_output_stops_before_review(root: Path, repo: Path, packet: Path) -> None:
    claude_capture = root / "inside-output-claude-capture.json"
    codex_capture = root / "inside-output-codex-capture.json"
    claude = root / "inside-output-claude"
    codex = root / "inside-output-codex"
    output = repo / "review.json"
    fake_claude(claude, claude_capture)
    fake_codex(codex, codex_capture)
    completed = invoke("codex", repo, packet, output, claude, codex)
    assert completed.returncode != 0
    assert "output must be outside the repository" in completed.stderr
    assert not output.exists()
    assert not claude_capture.exists(), "review ran before output validation"
    assert not codex_capture.exists(), "fallback ran before output validation"


def process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def check_timeout_stops_descendants(root: Path, repo: Path, packet: Path) -> None:
    if os.name != "posix":
        return
    child_pid = root / "hanging-child.pid"
    codex_capture = root / "timeout-fallback-codex-capture.json"
    claude = root / "hanging-claude"
    codex = root / "timeout-fallback-codex"
    output = root / "timeout-review.json"
    fake_hanging_claude(claude, child_pid)
    fake_codex(codex, codex_capture)
    started = time.monotonic()
    completed = invoke("codex", repo, packet, output, claude, codex, timeout_seconds=1)
    assert completed.returncode != 0
    assert time.monotonic() - started < 6
    assert "review timed out after 1 seconds" in completed.stderr
    assert child_pid.is_file()
    pid = int(child_pid.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 3
    while process_exists(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not process_exists(pid), "review timeout left a descendant process"
    assert not output.exists()
    assert not codex_capture.exists(), "timeout triggered a fallback"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="adversarial-review-regression-") as temporary:
        root = Path(temporary)
        repo = root / "repo"
        repo.mkdir()
        (repo / "sample.py").write_text("VALUE = 1\n", encoding="utf-8")
        packet = root / "packet.md"
        packet.write_text("prepared review packet\n", encoding="utf-8")
        check_claude_route(root, repo, packet)
        check_codex_route(root, repo, packet)
        check_invalid_output_stops(root, repo, packet)
        check_usage_limit_is_safe(root, repo, packet)
        check_repository_output_stops_before_review(root, repo, packet)
        check_timeout_stops_descendants(root, repo, packet)
    print("adversarial-review regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
