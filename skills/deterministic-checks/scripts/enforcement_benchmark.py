#!/usr/bin/env python3
"""Repeatable performance receipt for Hard Eng enforcement."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

from bounded_run import run_captured
from git_env import git_env


def _run(
    command: list[str],
    *,
    cwd: Path,
    timeout: float,
    payload: str | None = None,
    environment: dict[str, str] | None = None,
) -> float:
    started = time.perf_counter()
    result = run_captured(
        command,
        timeout,
        cwd=str(cwd),
        input_data=payload.encode("utf-8") if payload is not None else None,
        env=environment,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).decode("utf-8", "replace").strip()
        raise RuntimeError(f"benchmark command failed: {' '.join(command)}: {detail[-1000:]}")
    return (time.perf_counter() - started) * 1000


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, int(len(ordered) * percentile + 0.999999) - 1)]


def _summary(values: list[float], budget: float) -> dict[str, object]:
    median = statistics.median(values)
    p95 = _percentile(values, 0.95)
    return {
        "samples": len(values),
        "p50_ms": round(median, 2),
        "p95_ms": round(p95, 2),
        "p50_budget_ms": budget,
        "p95_budget_ms": budget * 1.5,
        "verdict": "PASS" if median <= budget and p95 <= budget * 1.5 else "FAIL",
    }


def _hook_summary(values: list[float], budget: float) -> dict[str, object]:
    median = statistics.median(values)
    p95 = _percentile(values, 0.95)
    result = _summary(values, budget)
    result["p95_budget_ms"] = budget * 2
    result["verdict"] = "PASS" if median <= budget and p95 <= budget * 2 else "FAIL"
    return result


def _version(command: list[str], repo: Path) -> str:
    result = run_captured(command, 10, cwd=str(repo))
    output = (result.stdout or result.stderr).decode("utf-8", "replace")
    return output.strip().splitlines()[0] if result.returncode == 0 else "unavailable"


def _fixture(root: Path, configured: bool) -> Path:
    repo = root / ("configured" if configured else "unconfigured")
    (repo / ".git").mkdir(parents=True)
    if not configured:
        return repo
    manifest = {
        "schema_version": 1,
        "enforcement": {"schema_version": 1},
        "families": {"targeted": ["python3", "check.py"]},
        "phases": {"commit": ["targeted"], "push": ["targeted"], "ci": ["targeted"]},
    }
    (repo / "hard-eng.gates.json").write_text(json.dumps(manifest), encoding="utf-8")
    feature = repo / "features/benchmark"
    feature.mkdir(parents=True)
    plan = (
        "# Feature Brief\n- lifecycle_status = building\n"
        "- approval_status = approved\n"
        f"- approval_fingerprint = sha256:{'a' * 64}\n"
    )
    (feature / "PLAN.md").write_text(plan, encoding="utf-8")
    (repo / "source.py").write_text("value = 1\n", encoding="utf-8")
    (repo / "notes.md").write_text("notes\n", encoding="utf-8")
    return repo


def benchmark(repo: Path, samples: int, timeout: float, tree_digest: str) -> dict[str, object]:
    if samples < 3:
        raise ValueError("benchmark requires at least 3 phase samples")
    hook = repo / "scripts/hooks/agent-hook.sh"
    runner = repo / "skills/deterministic-checks/scripts/project_gate.py"
    contracts = repo / "scripts/check-skill-contracts.py"
    hook_results: dict[str, dict[str, object]] = {}
    with tempfile.TemporaryDirectory(prefix="hard-eng-benchmark-") as temporary:
        root = Path(temporary)
        plain = _fixture(root, False)
        configured = _fixture(root, True)
        cases = {
            "unconfigured": (plain, "pretooluse", "Edit", {"file_path": str(plain / "source.py")}, 25),
            "source": (configured, "pretooluse", "Edit", {"file_path": str(configured / "source.py")}, 75),
            "markdown": (configured, "pretooluse", "Edit", {"file_path": str(configured / "notes.md")}, 25),
            "shell_pre": (configured, "pretooluse", "Bash", {"command": "printf ok"}, 35),
            "shell_post": (configured, "posttooluse", "Bash", {"command": "printf ok"}, 35),
        }

        def hook_call(case: tuple[Path, str, str, dict[str, str], int]) -> float:
            target, event, tool, arguments, _ = case
            payload = json.dumps({"cwd": str(target), "tool_name": tool, "tool_input": arguments})
            return _run(["bash", str(hook), "codex", event], cwd=target, timeout=timeout, payload=payload)

        cold = hook_call(cases["source"])
        for name, case in cases.items():
            for _ in range(5):
                hook_call(case)
            values = [hook_call(case) for _ in range(35)]
            hook_results[name] = _hook_summary(values, case[4])
        hook_results["cold_source"] = {
            "samples": 1,
            "milliseconds": round(cold, 2),
            "budget_ms": 150,
            "verdict": "PASS" if cold <= 150 else "FAIL",
        }

    environment = dict(os.environ, FALLOW_AUDIT_BASE="HEAD")
    phase_commands = {
        "commit": [
            sys.executable,
            str(runner),
            "phase",
            "--repo",
            str(repo),
            "--timeout",
            str(timeout),
            "--phase",
            "commit",
        ],
        "push": [
            sys.executable,
            str(runner),
            "phase",
            "--repo",
            str(repo),
            "--timeout",
            str(timeout),
            "--phase",
            "push",
        ],
        "contracts": [sys.executable, str(contracts)],
    }
    cold_contracts = _run(
        [sys.executable, str(contracts), "--fresh"], cwd=repo, timeout=timeout, environment=environment
    )
    phase_budgets = {"commit": 1000, "push": 12000, "contracts": 10000}
    phase_results = {
        name: _summary(
            [_run(command, cwd=repo, timeout=timeout, environment=environment) for _ in range(samples)],
            phase_budgets[name],
        )
        for name, command in phase_commands.items()
    }
    manifest = (repo / "hard-eng.gates.json").read_bytes()
    adapter = (repo / "scripts/enforcement_policy.pl").read_bytes()
    head_result = run_captured(["git", "rev-parse", "HEAD"], 20, cwd=str(repo), env=git_env())
    if head_result.returncode:
        raise RuntimeError("benchmark cannot resolve repository HEAD")
    head = head_result.stdout.decode("utf-8", "replace").strip()
    verdict = (
        "PASS"
        if all(result["verdict"] == "PASS" for result in (*hook_results.values(), *phase_results.values()))
        else "FAIL"
    )
    return {
        "schema_version": 1,
        "verdict": verdict,
        "repository": str(repo.resolve()),
        "tree_digest": tree_digest,
        "baseline_revision": head,
        "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
        "adapter_sha256": hashlib.sha256(adapter).hexdigest(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "versions": {
            "python": platform.python_version(),
            "node": _version(["node", "--version"], repo),
            "perl": _version(["perl", "-e", "print $^V"], repo),
        },
        "warmups": 5,
        "cold_contracts": {"milliseconds": round(cold_contracts, 2), "command_verdict": "PASS"},
        "hooks": hook_results,
        "phases": phase_results,
    }
