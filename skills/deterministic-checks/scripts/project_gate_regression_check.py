#!/usr/bin/env python3
"""Focused regressions for repository-owned project gate commands."""

# Size exception: dense contract cases for the single project gate runner.

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import NoReturn

from git_env import git_env, scrub_environ
from project_gate import (
    AUDIT_FLAG,
    REACT_DOCTOR_COMMAND,
    ProjectGateError,
    family_outcome,
    load_manifest,
    load_phase,
    validate_quality_report,
)
from script_runner import ScriptResult, run_script

SCRIPT_DIR = Path(__file__).resolve().parent
GATE = SCRIPT_DIR / "project_gate.py"
ROOT = SCRIPT_DIR.parents[2]

# The overrun proof bounds elapsed time against the killed command's own sleep,
# never a host wall-clock constant: spawn cost scales with load, the sleep does not.
OVERRUN_SLEEP = 5.0

scrub_environ(ceiling=tempfile.gettempdir())


def fail(message: str) -> NoReturn:
    raise SystemExit(f"project-gate-check: FAIL: {message}")


def write_families(repo: Path, families: dict[str, list[str]]) -> None:
    (repo / "hard-eng.gates.json").write_text(json.dumps({"schema_version": 1, "families": families}), encoding="utf-8")


def write_phases(repo: Path, families: dict[str, list[str]], phases: dict[str, list[str]]) -> None:
    enforcement = {"schema_version": 1, "required_paths": ["hard-eng.gates.json"]}
    manifest = {"schema_version": 1, "enforcement": enforcement, "families": families, "phases": phases}
    (repo / "hard-eng.gates.json").write_text(json.dumps(manifest), encoding="utf-8")


def gate_command(repo: Path, family: str, timeout: str = "30") -> list[str]:
    return ["run", "--timeout", timeout, "--family", family, "--repo", str(repo)]


def invoke(
    repo: Path, family: str = "targeted", timeout: str = "30", environment: dict[str, str] | None = None
) -> ScriptResult:
    return run_script(GATE, gate_command(repo, family, timeout), env=environment)


def invoke_families(repo: Path, families: tuple[str, ...], timeout: str = "30") -> ScriptResult:
    command = ["run", "--repo", str(repo), "--timeout", timeout]
    for family in families:
        command += ["--family", family]
    return run_script(GATE, command)


def check_migration_contract() -> None:
    required = {
        "AGENTS.md": "`gate-migration` before first product mutation",
        "skills/deterministic-checks/SKILL.md": ("[Gate migration](references/gate-migration.md)"),
        "skills/deterministic-checks/references/gate-migration.md": (
            "baseline + wiring + feature diff mixing = forbidden"
        ),
        "skills/he-build/SKILL.md": ("`gate-migration` pauses the slice without resetting PLAN state"),
        "skills/he-ship/SKILL.md": "Ship never wires it",
    }
    for relative, anchor in required.items():
        if anchor not in (ROOT / relative).read_text(encoding="utf-8"):
            fail(f"gate migration contract missing from {relative}")


def check_react_doctor_docs_contract() -> None:
    guidance = (ROOT / "skills/deterministic-checks/references/react-doctor.md").read_text(encoding="utf-8")
    required = (
        "npx --yes react-doctor@latest . --scope full --blocking warning "
        "--no-respect-inline-disables --no-telemetry --json -y"
    )
    if required not in guidance or "`--scope=full` + `--fail-on=warning`" not in guidance:
        fail("React Doctor manifest guidance does not match the runner")


def react_doctor_report(**overrides: object) -> str:
    report: dict[str, object] = {
        "schemaVersion": 3,
        "mode": "full",
        "reactDetected": True,
        "version": "0.9.5",
        "ok": True,
        "directory": ".",
        "diff": None,
        "projects": [
            {
                "directory": ".",
                "diagnostics": [],
                "score": None,
                "skippedChecks": [],
                "analyzedFileCount": 1,
                "complete": True,
            }
        ],
        "diagnostics": [],
        "summary": {"errorCount": 0, "warningCount": 0, "affectedFileCount": 0, "totalDiagnosticCount": 0},
        "elapsedMilliseconds": 12,
        "error": None,
    }
    report.update(overrides)
    return json.dumps(report)


def check_react_doctor_report() -> None:
    validate_quality_report("react-doctor", react_doctor_report())
    finding = {
        "filePath": "src/App.tsx",
        "line": 3,
        "plugin": "react-doctor",
        "rule": "exhaustive-deps",
        "severity": "error",
    }
    # React Doctor exits zero for a silenced analyzer, so every one of these
    # reports arrives with returncode 0 and has to fail on content alone.
    rejected = (
        (
            "findings",
            {
                "diagnostics": [finding],
                "summary": {"errorCount": 1, "warningCount": 0, "affectedFileCount": 1, "totalDiagnosticCount": 1},
            },
            ("react-doctor report contains findings", "src/App.tsx:3", "react-doctor/exhaustive-deps"),
        ),
        (
            "counted-but-undisclosed findings",
            {"summary": {"errorCount": 0, "warningCount": 1, "affectedFileCount": 1, "totalDiagnosticCount": 1}},
            ("react-doctor report contains findings",),
        ),
        (
            "incomplete project",
            {"projects": [{"directory": ".", "complete": False, "skippedChecks": []}]},
            ("react-doctor scan is incomplete",),
        ),
        (
            "skipped checks",
            {
                "projects": [
                    {
                        "directory": ".",
                        "complete": True,
                        "skippedChecks": ["lint"],
                        "skippedCheckReasons": {"lint": "EACCES"},
                    }
                ]
            },
            ("react-doctor scan is incomplete", "lint"),
        ),
        (
            "skipped projects",
            {"skippedProjects": [{"directory": "packages/app", "reason": "max-duration"}]},
            ("react-doctor skipped 1 project",),
        ),
        ("narrowed scope", {"mode": "baseline"}, ("react-doctor report is not a full scan",)),
        ("no React detected", {"reactDetected": False}, ("react-doctor scanned no React project",)),
        ("nothing scanned", {"projects": []}, ("react-doctor report has an invalid scan shape",)),
        (
            "tool error",
            {"ok": False, "error": {"kind": "CliInputError", "message": "bad flags"}},
            ("react-doctor reported a tool error",),
        ),
        ("unknown schema", {"schemaVersion": 4}, ("react-doctor report is not schemaVersion 3",)),
        (
            "invalid counts",
            {"summary": {"errorCount": None, "warningCount": 0, "totalDiagnosticCount": 0}},
            ("react-doctor summary has an invalid count shape",),
        ),
    )
    for label, overrides, anchors in rejected:
        try:
            validate_quality_report("react-doctor", react_doctor_report(**overrides))
        except ProjectGateError as error:
            missing = [anchor for anchor in anchors if anchor not in str(error)]
            if missing:
                fail(f"React Doctor {label} lost evidence: {missing} in {error}")
        else:
            fail(f"React Doctor {label} was accepted")

    absent = json.loads(react_doctor_report())
    del absent["reactDetected"]
    outputs = ("", "{}", "React Doctor 0.9.5\n3 issues\n", json.dumps(absent))
    expect_rejected("react-doctor", outputs, "malformed or unscanned React Doctor report was accepted")


def expect_rejected(family: str, outputs: tuple[str, ...], message: str) -> None:
    for malformed in outputs:
        try:
            validate_quality_report(family, malformed)
        except ProjectGateError:
            continue
        fail(message)


def check_quality_report() -> None:
    summary = {"dead_code_issues": 0, "complexity_findings": 0, "duplication_clone_groups": 0}
    attribution = {"gate": "new-only", "dead_code_introduced": 0}
    clean = {"kind": "audit", "verdict": "pass", "summary": summary, "attribution": attribution}
    validate_quality_report("fallow", json.dumps(clean))
    validate_quality_report("fallow", json.dumps({**clean, "verdict": "warn"}))
    failing = {**clean, "verdict": "fail", "attribution": {"gate": "new-only", "complexity_introduced": 1}}
    owner = {"path": "src/owner.ts", "line": 7, "name": "owner", "introduced": True}
    try:
        validate_quality_report("fallow", json.dumps({**failing, "health": {"findings": [owner]}}))
    except ProjectGateError as error:
        if "complexity_introduced=1" not in str(error) or "src/owner.ts:7" not in str(error):
            fail(f"Fallow audit failure lost compact evidence: {error}")
    else:
        fail("Fallow fail verdict was accepted")
    score = {"path": "score.ts", "name": "score", "line": 1, "introduced": True}
    audit_fail = json.dumps({**failing, "health": None, "complexity": {"findings": [score]}})
    for stdout, stderr, expected in (
        (audit_fail, "", ("score.ts:1 score", "verdict=fail")),
        ("", "fallow: command not found", ("fallow: command not found",)),
    ):
        error, detail = family_outcome("fallow", 1, stdout, stderr, True)
        if error is not None or any(text not in detail.split("\n", 1)[0] for text in expected):
            fail(f"fallow failure detail must lead with {expected}: {detail[:200]}")
    if family_outcome("tests", 1, "boom", "", True) != (None, "boom"):
        fail("non-fallow failures keep their raw output")
    combined = {"kind": "combined", "check": {"total_issues": 0}, "dupes": {}, "health": {}}
    outputs = ("", "{}", json.dumps(combined), json.dumps({**clean, "verdict": "maybe"}))
    expect_rejected("fallow", outputs, "malformed or non-audit Fallow report was accepted")


def check_clones_manifest(repo: Path) -> None:
    baseline = repo / ".jscpd-baseline.json"
    baseline.write_text('{"version": 1, "fingerprints": {}}', encoding="utf-8")
    good = ["jscpd", "--format", "python,dart", "--reporters", "console", "--baseline", ".jscpd-baseline.json"]
    good += ["--fail-on-new-clones", "."]
    write_families(repo, {"clones": good})
    load_manifest(repo)
    write_families(
        repo, {"clones": ["jscpd", "--baseline-from-ref", "origin/main", "-r", "console", "--fail-on-new-clones", "."]}
    )
    load_manifest(repo)
    rejected = {
        "--update-baseline": [*good, "--update-baseline"],
        "--reporters console": [item if item != "console" else "json" for item in good],
        "--fail-on-new-clones": [item for item in good if item != "--fail-on-new-clones"],
        "--baseline": ["jscpd", "--reporters", "console", "--fail-on-new-clones", "."],
        "baseline file is missing": [item if item != ".jscpd-baseline.json" else "absent.json" for item in good],
    }
    for expected, command in rejected.items():
        write_families(repo, {"clones": command})
        try:
            load_manifest(repo)
        except ProjectGateError as error:
            if expected not in str(error):
                fail(f"clones rejection lost its reason ({expected}): {error}")
            continue
        fail(f"clones manifest accepted a command lacking {expected}")
    baseline.unlink()
    write_families(repo, {})


def latest_commands() -> dict[str, list[str]]:
    return {
        "fallow": ["npx", "--yes", "fallow@latest", "audit", "--max-crap", "30", "--format", "json"],
        "react-doctor": list(REACT_DOCTOR_COMMAND),
        "dart-decimate": ["npx", "--yes", "dart-decimate@latest", "json", ".", "--workspace", "functions/example"],
    }


def check_react_doctor_manifest(repo: Path) -> None:
    canonical = latest_commands()["react-doctor"]

    def reject(label: str, command: list[str], anchor: str) -> None:
        write_families(repo, {"react-doctor": command})
        try:
            load_manifest(repo)
        except ProjectGateError as error:
            if anchor not in str(error):
                fail(f"React Doctor {label} failed for the wrong reason: {error}")
        else:
            fail(f"React Doctor {label} was accepted")

    def accept(label: str, command: list[str]) -> None:
        write_families(repo, {"react-doctor": command})
        try:
            load_manifest(repo)
        except ProjectGateError as error:
            fail(f"React Doctor {label} was rejected: {error}")

    mode = "react-doctor requires --scope full"
    # --full was removed upstream and now exits 1, so accepting it admits a
    # command that cannot run.
    reject("removed --full spelling", [*canonical[:4], "--full", *canonical[6:]], mode)
    reject("narrowed scope", [*canonical[:4], "--scope=changed", *canonical[6:]], mode)
    reject("dropped scope", [*canonical[:4], *canonical[6:]], mode)
    reject("missing audit flag", [argument for argument in canonical if argument != AUDIT_FLAG], mode)
    reject("missing --json", [argument for argument in canonical if argument != "--json"], mode)
    reject("downgraded blocking", [*canonical[:6], "--blocking", "error", *canonical[8:]], mode)

    narrowing = "scoped/baseline flags are forbidden"
    for flag in (
        "--base",
        "--category",
        "--changed-files-from",
        "--diff",
        "--json-out",
        "--max-duration",
        "--no-dead-code",
        "--no-lint",
        "--no-supply-chain",
        "--no-warnings",
        "--output-dir",
        "--project",
        "--score",
        "--staged",
    ):
        reject(f"narrowing {flag}", [*canonical, flag], narrowing)
        # React Doctor accepts --flag=value, so the token set must be split on "=".
        reject(f"narrowing {flag}=", [*canonical, f"{flag}=main"], narrowing)

    reject("joined options", [*canonical[:4], "--scope=full", "--blocking=warning", *canonical[8:]], "command must be")
    reject(
        "removed StaffToDo options",
        [
            *canonical[:4],
            "--scope=full",
            "--fail-on=warning",
            "--no-respect-inline-disables",
            "--no-telemetry",
            "--json",
            "--yes",
        ],
        "command must be",
    )
    accept("canonical command", canonical)


def check_npx_contract(repo: Path) -> None:
    commands = latest_commands()
    write_families(repo, commands)
    try:
        loaded = load_manifest(repo)
    except ProjectGateError as error:
        fail(f"canonical latest commands were rejected: {error}")
    if any(list(loaded[name]) != command for name, command in commands.items()):
        fail("canonical latest commands changed during validation")

    wrapper = repo / "tools/npx"
    wrapper.parent.mkdir()
    wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    wrapper.chmod(0o755)
    write_families(repo, {"fallow": [str(wrapper), *commands["fallow"][1:]]})
    try:
        load_manifest(repo)
    except ProjectGateError as error:
        if "literal npx" not in str(error):
            fail("repo-local npx wrapper failed for the wrong reason")
    else:
        fail("repo-local npx wrapper path was accepted")

    previous_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{wrapper.parent}{os.pathsep}{previous_path}"
    try:
        write_families(repo, {"fallow": commands["fallow"]})
        try:
            load_manifest(repo)
        except ProjectGateError as error:
            if "outside" not in str(error):
                fail("repo-local npx resolution failed for the wrong reason")
        else:
            fail("literal npx resolved to a repo-local wrapper")
    finally:
        os.environ["PATH"] = previous_path

    runtime = repo / "node_modules/fallow"
    runtime.mkdir(parents=True)
    write_families(repo, {"fallow": commands["fallow"]})
    try:
        load_manifest(repo)
    except ProjectGateError as error:
        if "scanner runtime" not in str(error):
            fail("extraneous scanner runtime failed for the wrong reason")
    else:
        fail("extraneous project-local scanner runtime was accepted")
    shutil.rmtree(repo / "node_modules")

    binary_root = repo / "node_modules/.bin"
    binary_root.mkdir(parents=True)
    binary = binary_root / "react-doctor"
    binary.symlink_to(repo / "missing-react-doctor")
    try:
        load_manifest(repo)
    except ProjectGateError as error:
        if "scanner binary" not in str(error):
            fail("scanner binary symlink failed for the wrong reason")
    else:
        fail("project-local scanner binary symlink was accepted")
    shutil.rmtree(repo / "node_modules")

    package = repo / "package.json"
    for scanner in ("dart-decimate", "fallow", "react-doctor"):
        package.write_text(json.dumps({"devDependencies": {scanner: "latest"}}), encoding="utf-8")
        write_families(repo, {"fallow": commands["fallow"]})
        try:
            load_manifest(repo)
        except ProjectGateError as error:
            if "dependencies" not in str(error):
                fail(f"local {scanner} dependency failed for the wrong reason")
        else:
            fail(f"local {scanner} dependency was accepted")
    package.unlink()

    (repo / ".gitignore").write_text("package.json\n", encoding="utf-8")
    package.write_text(json.dumps({"dependencies": {"fallow": "latest"}}), encoding="utf-8")
    try:
        load_manifest(repo)
    except ProjectGateError as error:
        if "dependencies" not in str(error):
            fail("ignored root package.json failed for the wrong reason")
    else:
        fail("ignored root package.json scanner dependency was accepted")
    package.unlink()
    (repo / ".gitignore").unlink()

    wrapper.unlink()
    wrapper.parent.rmdir()

    write_families(repo, {"fallow": ["npx", "--yes", "fallow@latest", "--fail-on-issues", "--format", "json"]})
    try:
        load_manifest(repo)
    except ProjectGateError as error:
        if "audit mode" not in str(error):
            fail(f"non-audit fallow command rejected for the wrong reason: {error}")
    else:
        fail("non-audit fallow command was accepted")
    scoped = {
        "fallow": ["npx", "--yes", "fallow@latest", "audit", "--changed-since", "main"],
        "react-doctor": [*latest_commands()["react-doctor"], "--changed-files-from"],
        "dart-decimate": ["npx", "--yes", "dart-decimate@latest", "audit", ".", "--base", "main"],
    }
    for family, command in scoped.items():
        write_families(repo, {family: command})
        try:
            load_manifest(repo)
        except ProjectGateError:
            continue
        fail(f"{family} accepted a changed/baseline-only quality gate")

    check_react_doctor_manifest(repo)
    check_clones_manifest(repo)


def check_execution(repo: Path) -> None:
    script = repo / "targeted-check.py"
    script.write_text("raise SystemExit(0)\n", encoding="utf-8")
    write_families(repo, {"targeted": [sys.executable, script.name]})
    valid = invoke(repo)
    if valid.returncode:
        fail("valid repository-owned argv failed: " + (valid.stderr.strip() or valid.stdout.strip()))

    for invalid in ("0", "-1", "nan", "inf"):
        rejected = invoke(repo, timeout=invalid)
        if (
            rejected.returncode == 0
            or "timeout must be finite and positive" not in rejected.stderr
            or "Traceback" in rejected.stderr
        ):
            fail(f"invalid whole-run timeout was accepted: {invalid}")

    overrun = repo / "overrun.txt"
    script.write_text(
        "import time\n"
        "from pathlib import Path\n"
        f"time.sleep({OVERRUN_SLEEP})\n"
        "Path('overrun.txt').write_text('ran\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    started = time.monotonic()
    rejected = invoke(repo, timeout="0.1")
    elapsed = time.monotonic() - started
    if rejected.returncode == 0 or elapsed > OVERRUN_SLEEP / 2 or overrun.exists():
        fail("whole-run timeout allowed an internal command to overrun")

    script.write_text("raise SystemExit(0)\n", encoding="utf-8")
    deleted = repo / "deleted-owner.txt"
    deleted.write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", deleted.name], check=True, env=git_env())
    deleted.unlink()
    if invoke(repo).returncode:
        fail("gate could not snapshot an intentional tracked deletion")

    write_families(repo, {"targeted": ["echo", "targeted"]})
    rejected = invoke(repo)
    if rejected.returncode == 0 or "forbidden no-op/shell" not in rejected.stderr:
        fail("echo no-op proof was accepted")

    write_families(repo, {"targeted": ["npx", "--yes", "--package", "react-doctor", "react-doctor", "targeted"]})
    rejected = invoke(repo)
    if rejected.returncode == 0 or "exact semver or @latest" not in rejected.stderr:
        fail("unpinned npx package was accepted")

    script.write_text(
        "import os, sys\nraise SystemExit(os.environ.get('HARD_ENG_PYTHON') != sys.executable)\n", encoding="utf-8"
    )
    write_families(repo, {"targeted": [sys.executable, script.name]})
    hostile_environment = os.environ.copy()
    hostile_environment["HARD_ENG_PYTHON"] = "/tmp/caller-controlled-python"
    if invoke(repo, environment=hostile_environment).returncode:
        fail("project gate did not bind the nested Python runtime")

    unsafe = repo / "scripts/unsafe.mjs"
    unsafe.parent.mkdir()
    unsafe.write_text(
        "import { spawnSync } from 'node:child_process';\nspawnSync('git', ['status']);\n", encoding="utf-8"
    )
    write_families(repo, {"targeted": [sys.executable, script.name]})
    rejected = invoke(repo)
    if rejected.returncode == 0 or "Git child process" not in rejected.stderr:
        fail("project gate skipped Git environment hygiene")
    unsafe.unlink()

    (repo / ".gitignore").write_text(".secret\n", encoding="utf-8")
    (repo / ".worktreeinclude").write_text(".secret\n", encoding="utf-8")
    (repo / ".secret").write_text("preserve\n", encoding="utf-8")
    script.write_text("from pathlib import Path\nPath('.secret').write_text('changed')\n", encoding="utf-8")
    rejected = invoke(repo)
    if rejected.returncode == 0 or "mutated the repository tree" not in rejected.stderr:
        fail("mutation of a required ignored input was accepted")
    if any(part not in rejected.stderr for part in ("dirty_paths=", ".secret", "do not restore, overwrite, or delete")):
        fail("mutated-tree error did not list the dirty paths and warn against touching them")


def check_phase_manifest(repo: Path) -> None:
    families = {"format": [sys.executable, "format-check.py"], "lint": [sys.executable, "lint-check.py"]}
    phases = {"commit": ["format", "lint"], "push": ["format", "lint"], "ci": ["format", "lint"]}
    write_phases(repo, families, phases)
    if load_phase(repo, "commit") != ["format", "lint"]:
        fail("phase family order did not come from the manifest")
    missing_family_phases = {**phases, "push": ["format", "missing"], "ci": ["format", "missing"]}
    write_phases(repo, families, missing_family_phases)
    try:
        load_phase(repo, "ci")
    except ProjectGateError as error:
        if "missing" not in str(error):
            fail("missing phase family error omitted its name")
    else:
        fail("phase accepted a family without a command")
    write_phases(repo, families, {**phases, "ci": ["format"]})
    try:
        load_phase(repo, "push")
    except ProjectGateError as error:
        if "push and ci" not in str(error):
            fail("phase mismatch failed for the wrong reason")
    else:
        fail("local push and CI accepted different family lists")
    write_phases(repo, families, phases)
    manifest = json.loads((repo / "hard-eng.gates.json").read_text(encoding="utf-8"))
    manifest["enforcement"]["required_paths"] = ["missing-policy.pl"]
    (repo / "hard-eng.gates.json").write_text(json.dumps(manifest), encoding="utf-8")
    try:
        load_phase(repo, "commit")
    except ProjectGateError as error:
        if "missing-policy.pl" not in str(error):
            fail("missing enforcement owner error omitted its path")
    else:
        fail("phase accepted a missing enforcement owner")


def check_commit_divergence(repo: Path) -> None:
    script = repo / "targeted-check.py"
    script.write_text("raise SystemExit(0)\n", encoding="utf-8")
    write_phases(
        repo,
        {"targeted": [sys.executable, script.name]},
        {"commit": ["targeted"], "push": ["targeted"], "ci": ["targeted"]},
    )
    source = repo / "diverged.py"
    source.write_text("bad = 'staged'\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=git_env())
    source.write_text("good = 'worktree'\n", encoding="utf-8")

    def phase(name: str) -> ScriptResult:
        return run_script(GATE, ["phase", "--repo", str(repo), "--timeout", "30", "--phase", name])

    rejected = phase("commit")
    if rejected.returncode == 0 or "diverged.py" not in rejected.stderr:
        fail("staged content diverging from the worktree was accepted by the commit phase")
    if phase("push").returncode:
        fail("divergence enforcement leaked beyond the commit phase")
    subprocess.run(["git", "-C", str(repo), "add", "diverged.py"], check=True, env=git_env())
    aligned = phase("commit")
    if aligned.returncode:
        fail("aligned staged state failed the commit phase: " + (aligned.stderr.strip() or aligned.stdout.strip()))


def check_python_security_manifest(repo: Path) -> None:
    ruff_format = ["ruff", "format", "--check", "--no-cache", "."]
    ruff_lint = ["ruff", "check", "--no-cache", "."]
    secrets = ["gitleaks", "dir", ".", "--no-banner", "--redact", "--exit-code", "1"]
    families = {"python-format": ruff_format, "python-lint": ruff_lint, "secrets": secrets}

    def reject(label: str, rejected_families: dict[str, list[str]], anchor: str) -> None:
        write_families(repo, rejected_families)
        try:
            load_manifest(repo)
        except ProjectGateError as error:
            if anchor not in str(error):
                fail(f"{label} failed for the wrong reason: {error}")
        else:
            fail(f"{label} was accepted")

    reject("mutating python-format", {"python-format": ["ruff", "format", "--no-cache", "."]}, "--check")
    reject("fixing python-lint", {"python-lint": [*ruff_lint, "--fix"]}, "--fix")
    reject("cache-writing python-lint", {"python-lint": ["ruff", "check", "."]}, "--no-cache")
    reject("cache-writing python-tests", {"python-tests": ["pytest", "-q"]}, "no:cacheprovider")
    reject("unredacted secrets", {"secrets": ["gitleaks", "dir", ".", "--exit-code", "1"]}, "--redact")
    reject("baseline-suppressed secrets", {"secrets": [*secrets, "--baseline-path", "b.json"]}, "baseline")
    reject("finding-tolerant secrets", {"secrets": [*secrets[:-1], "0"]}, "--exit-code 0")
    write_families(repo, families)
    try:
        load_manifest(repo)
    except ProjectGateError as error:
        fail(f"canonical python/security wiring was rejected: {error}")
    quality = ["python-format", "python-lint", "secrets"]
    write_phases(repo, families, {"commit": ["secrets"], "push": quality, "ci": quality})
    try:
        load_phase(repo, "push")
    except ProjectGateError as error:
        if "commit phase cannot run security families" not in str(error):
            fail(f"commit secrets ban failed for the wrong reason: {error}")
    else:
        fail("commit phase accepted a security family")
    write_phases(repo, families, {"commit": ["python-format"], "push": quality, "ci": quality})
    if load_phase(repo, "push") != quality:
        fail("canonical python/security phases did not load")


def check_parallel_execution(repo: Path) -> None:
    probe = Path(tempfile.mkdtemp(prefix="hard-eng-parallel-probe-"))
    script = repo / "parallel-check.py"
    script.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "import time\n"
        "root = Path(sys.argv[1])\n"
        "name = sys.argv[2]\n"
        "expected = int(sys.argv[3])\n"
        "(root / f'ready-{name}').write_text(name, encoding='utf-8')\n"
        "deadline = time.monotonic() + 5\n"
        "while len(tuple(root.glob('ready-*'))) < expected and time.monotonic() < deadline:\n"
        "    time.sleep(0.01)\n"
        "if len(tuple(root.glob('ready-*'))) < expected:\n"
        "    raise SystemExit(1)\n"
        "(root / f'done-{name}').write_text(name, encoding='utf-8')\n",
        encoding="utf-8",
    )
    families = ("typecheck", "format", "boundary-contracts")
    write_families(
        repo, {family: [sys.executable, script.name, str(probe), family, str(len(families))] for family in families}
    )
    result = invoke_families(repo, families)
    if result.returncode != 0:
        fail(f"shared gate families did not run in parallel: {result.stderr}")
    expected_output = tuple(f"project-gate: {family} PASS" for family in families)
    if tuple(result.stdout.splitlines()) != expected_output:
        fail("parallel gate results lost manifest order")

    failure_script = repo / "parallel-fail.py"
    failure_script.write_text(
        "import sys\nraise SystemExit(1 if sys.argv[1] in {'typecheck', 'format'} else 0)\n", encoding="utf-8"
    )
    write_families(repo, {family: [sys.executable, failure_script.name, family] for family in families})
    result = invoke_families(repo, families)
    if (
        result.returncode == 0
        or "project-gate: typecheck FAIL" not in result.stdout
        or "project-gate: format FAIL" not in result.stdout
        or "project-gate: boundary-contracts PASS" not in result.stdout
    ):
        fail("parallel gate execution hid independent failures")
    shutil.rmtree(probe, ignore_errors=True)


def main() -> int:
    check_migration_contract()
    check_react_doctor_docs_contract()
    check_quality_report()
    check_react_doctor_report()
    with tempfile.TemporaryDirectory(prefix="hard-eng-project-gate-") as temporary:
        repo = Path(temporary)
        subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
        check_execution(repo)
        check_phase_manifest(repo)
        check_commit_divergence(repo)
        check_python_security_manifest(repo)
        check_parallel_execution(repo)
        check_npx_contract(repo)
    print("project-gate-check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
