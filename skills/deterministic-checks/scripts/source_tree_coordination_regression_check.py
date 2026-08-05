#!/usr/bin/env python3
"""Regression proof for coordinated transient source scanners."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import project_gate as project_gate_module
from git_env import git_env, scrub_environ
from project_gate import run_families
from source_tree_coordination import (
    LOCK_NAME,
    POISON_NAME,
    atomic_json,
    git_private_path,
    tree_fingerprint,
)

SCRIPT_DIR = Path(__file__).resolve().parent
GATE = SCRIPT_DIR / "project_gate.py"
ROOT = SCRIPT_DIR.parents[2]

# Contention proofs bound elapsed time against the held-lock delay, never a host
# wall-clock constant: spawn cost scales with load, lock waiting does not.
DOCTOR_DELAY = 3.0
CONTENTION_SLACK = DOCTOR_DELAY / 2
# The crash proof needs a whole-run timeout that outlives measured gate startup on
# this host yet dies far inside the fixture's rewrite delay.
CRASH_DOCTOR_DELAY = 60.0

scrub_environ(ceiling=tempfile.gettempdir())


def fail(message: str) -> None:
    raise SystemExit(f"source-tree-coordination-regressions: FAIL: {message}")


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
        env=git_env(),
    )
    if result.returncode:
        fail(result.stderr.strip() or "fixture Git command failed")
    return result.stdout.strip()


def gate_command(repo: Path, family: str, timeout: str = "30") -> list[str]:
    return [
        sys.executable,
        str(GATE),
        "run",
        "--repo",
        str(repo),
        "--timeout",
        timeout,
        "--family",
        family,
    ]


def invoke(
    repo: Path,
    family: str,
    environment: dict[str, str],
    timeout: str = "30",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        gate_command(repo, family, timeout),
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def wait_for(path: Path, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if path.exists():
            return
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            fail(f"React Doctor fixture exited before rewrite: {stdout}{stderr}")
        time.sleep(0.01)
    process.terminate()
    process.communicate()
    fail("React Doctor fixture never exposed its transient rewrite")


def manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "families": {
            "fallow": [
                "npx",
                "--yes",
                "fallow@latest",
                "--fail-on-issues",
                "--format",
                "json",
                "--quiet",
            ],
            "react-doctor": [
                "npx",
                "--yes",
                "react-doctor@latest",
                ".",
                "--scope",
                "full",
                "--blocking",
                "warning",
                "--no-respect-inline-disables",
                "--no-telemetry",
                "--json",
                "-y",
            ],
        },
    }


def install_fake_npx(path: Path) -> None:
    write(
        path,
        "#!/usr/bin/env python3\n"
        "import json, os, sys, time\n"
        "from pathlib import Path\n"
        "root = Path.cwd()\n"
        "source = root / 'source.tsx'\n"
        "marker = root / '.react-doctor-rewrite-active'\n"
        "package = next(arg for arg in sys.argv[1:] if arg.endswith('@latest'))\n"
        "if package == 'react-doctor@latest':\n"
        "    original = source.read_text(encoding='utf-8')\n"
        "    source.write_text(original.replace('eslint-disable', 'eslint_disable'), "
        "encoding='utf-8')\n"
        "    marker.write_text('active\\n', encoding='utf-8')\n"
        "    try:\n"
        "        time.sleep(float(os.environ.get('HARD_ENG_DOCTOR_DELAY', '0.5')))\n"
        "        print(json.dumps({'ok': True, 'projects': []}))\n"
        "    finally:\n"
        "        source.write_text(original, encoding='utf-8')\n"
        "        marker.unlink(missing_ok=True)\n"
        "        time.sleep(float(os.environ.get("
        "'HARD_ENG_DOCTOR_RESTORED_DELAY', '0')))\n"
        "elif package == 'fallow@latest':\n"
        "    probe_value = os.environ.get('HARD_ENG_FALLOW_PARALLEL_PROBE')\n"
        "    active = None\n"
        "    try:\n"
        "        if probe_value:\n"
        "            probe = Path(probe_value)\n"
        "            active = probe / f'{os.getpid()}.active'\n"
        "            active.write_text('active\\n', encoding='utf-8')\n"
        "            deadline = time.monotonic() + 2\n"
        "            while len(list(probe.glob('*.active'))) < 2:\n"
        "                if time.monotonic() >= deadline:\n"
        "                    raise SystemExit('shared scanner lock was serialized')\n"
        "                time.sleep(0.01)\n"
        "            time.sleep(0.1)\n"
        "        transient = 'eslint_disable' in source.read_text(encoding='utf-8')\n"
        "        print(json.dumps({\n"
        "            'kind': 'combined',\n"
        "            'check': {'total_issues': 0},\n"
        "            'dupes': {'clone_groups': [], 'clone_families': []},\n"
        "            'health': {'findings': ([{'path': 'source.tsx', 'line': 1, "
        "'name': 'transient rewrite', 'severity': 'critical'}] if transient else [])},\n"
        "        }))\n"
        "    finally:\n"
        "        if active:\n"
        "            active.unlink(missing_ok=True)\n"
        "else:\n"
        "    raise SystemExit(f'unexpected package: {package}')\n",
    )
    path.chmod(0o755)


def check_root_cause(
    repo: Path,
    marker: Path,
    environment: dict[str, str],
) -> None:
    commands = manifest()["families"]
    doctor = subprocess.Popen(
        commands["react-doctor"],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    wait_for(marker, doctor)
    fallow = subprocess.run(
        commands["fallow"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    doctor.communicate(timeout=30)
    if doctor.returncode or fallow.returncode:
        fail("unguarded scanner interference fixture failed")
    if not json.loads(fallow.stdout)["health"]["findings"]:
        fail("unguarded Fallow did not observe the transient rewrite")


def check_normal_coordination(
    repo: Path,
    marker: Path,
    environment: dict[str, str],
) -> None:
    alias = repo.parent / "scanner-alias"
    alias.symlink_to(repo, target_is_directory=True)
    if git_private_path(alias, LOCK_NAME) != git_private_path(repo, LOCK_NAME):
        fail("symlink alias resolved a different source-tree lock")
    doctor = subprocess.Popen(
        gate_command(alias, "react-doctor"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    wait_for(marker, doctor)
    fallow = subprocess.Popen(
        gate_command(repo, "fallow"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    doctor_output = doctor.communicate(timeout=30)
    fallow_output = fallow.communicate(timeout=30)
    if doctor.returncode or fallow.returncode:
        fail(
            "coordinated scanners failed through an alias: "
            + "".join((*doctor_output, *fallow_output))
        )
    alias.unlink()

    case_alias = Path(str(repo).swapcase())
    if case_alias.exists() and os.path.samefile(case_alias, repo):
        if git_private_path(case_alias, LOCK_NAME) != git_private_path(repo, LOCK_NAME):
            fail("case-insensitive alias resolved a different source-tree lock")
        if invoke(case_alias, "fallow", environment).returncode:
            fail("case-insensitive alias could not use canonical coordination")

    slow = {**environment, "HARD_ENG_DOCTOR_DELAY": str(DOCTOR_DELAY)}
    doctor = subprocess.Popen(
        gate_command(repo, "react-doctor"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=slow,
    )
    wait_for(marker, doctor)
    started = time.monotonic()
    blocked = invoke(repo, "fallow", environment, timeout="0.1")
    elapsed = time.monotonic() - started
    doctor.communicate(timeout=DOCTOR_DELAY + 20)
    if (
        blocked.returncode == 0
        or "timeout exhausted waiting for source-tree coordination"
        not in blocked.stderr
        or elapsed > CONTENTION_SLACK
    ):
        fail("source-tree lock ignored the whole-run timeout")

    probe = repo.parent / "fallow-parallel"
    probe.mkdir()
    parallel_environment = {
        **environment,
        "HARD_ENG_FALLOW_PARALLEL_PROBE": str(probe),
    }
    gates = [
        subprocess.Popen(
            gate_command(repo, "fallow"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=parallel_environment,
        )
        for _ in range(2)
    ]
    outputs = [gate.communicate(timeout=30) for gate in gates]
    if any(gate.returncode for gate in gates):
        fail("safe shared scans were serialized: " + "".join(sum(outputs, ())))
    if any(probe.iterdir()):
        fail("shared scan probe left artifacts")
    probe.rmdir()


def check_quarantine(
    repo: Path,
    source: Path,
    marker: Path,
    original: str,
    environment: dict[str, str],
) -> None:
    poison = git_private_path(repo, POISON_NAME)
    baseline_started = time.monotonic()
    if invoke(repo, "react-doctor", environment).returncode:
        fail("react-doctor gate failed uncontended before the crash proof")
    crash_timeout = max(2.0, (time.monotonic() - baseline_started) * 3)
    if crash_timeout >= CRASH_DOCTOR_DELAY / 2:
        fail("gate startup cost leaves no room to interrupt the fixture rewrite")
    crashing = {**environment, "HARD_ENG_DOCTOR_DELAY": str(CRASH_DOCTOR_DELAY)}
    doctor = subprocess.Popen(
        gate_command(repo, "react-doctor", timeout=f"{crash_timeout:.3f}"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=crashing,
    )
    wait_for(marker, doctor)
    stdout, stderr = doctor.communicate(timeout=crash_timeout + 20)
    if doctor.returncode == 0 or "did not restore" not in stderr:
        fail(f"interrupted React Doctor was accepted: {stdout}{stderr}")
    blocked = invoke(repo, "fallow", environment)
    if blocked.returncode == 0 or "quarantined" not in blocked.stderr:
        fail("Fallow scanned a known non-restored source tree")
    if "eslint_disable" not in source.read_text(encoding="utf-8"):
        fail("automatic recovery overwrote the interrupted source tree")
    source.write_text(original, encoding="utf-8")
    marker.unlink(missing_ok=True)
    if invoke(repo, "fallow", environment).returncode or poison.exists():
        fail("exact manual restoration did not clear quarantine")

    delayed = {
        **environment,
        "HARD_ENG_DOCTOR_DELAY": "0.8",
        "HARD_ENG_DOCTOR_RESTORED_DELAY": "0.2",
    }
    owner = subprocess.Popen(
        gate_command(repo, "react-doctor"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=delayed,
    )
    wait_for(marker, owner)
    owner.kill()
    if owner.wait(timeout=2) != -signal.SIGKILL:
        fail("project-gate SIGKILL fixture did not terminate its owner")
    blocked = invoke(repo, "fallow", environment)
    if blocked.returncode == 0 or "terminality is proven" not in blocked.stderr:
        fail("missing terminal receipt did not block a later gate")
    deadline = time.monotonic() + 20
    while (marker.exists() or source.read_text(encoding="utf-8") != original):
        if time.monotonic() >= deadline:
            fail("surviving bounded runner did not restore the source tree")
        time.sleep(0.02)
    while True:
        recovered = invoke(repo, "fallow", environment)
        if recovered.returncode == 0:
            if poison.exists():
                fail("terminal recovery left the source tree quarantined")
            break
        if "terminality is proven" not in recovered.stderr:
            fail(f"terminal recovery failed unexpectedly: {recovered.stderr}")
        if time.monotonic() >= deadline:
            fail("terminal receipt did not recover a restored SIGKILL owner")
        time.sleep(0.02)
    owner.communicate(timeout=2)

    receipt_token = "a" * 64
    atomic_json(
        poison,
        {
            "boot_id": "synthetic-previous-boot",
            "expected": tree_fingerprint(repo),
            "receipt": "hard-eng-terminal-1-deadbeef.json",
            "receipt_token": receipt_token,
        },
    )
    if invoke(repo, "fallow", environment).returncode or poison.exists():
        fail("reboot-safe quarantine recovery failed on an exact tree")

    lock_path = git_private_path(repo, LOCK_NAME)
    dead_writer = subprocess.Popen([sys.executable, "-c", "pass"])
    dead_pid = dead_writer.pid
    if dead_writer.wait(timeout=2):
        fail("dead temporary-writer fixture failed")
    dead_poison = lock_path.parent / f".{POISON_NAME}.{dead_pid}.dead.tmp"
    dead_terminal = lock_path.parent / (
        f".hard-eng-terminal-{os.getpid()}-deadbeef.json."
        f"{dead_pid}.dead.tmp"
    )
    live_terminal = lock_path.parent / (
        f".hard-eng-terminal-{os.getpid()}-deadbeef.json."
        f"{os.getpid()}.cafebabe.tmp"
    )
    for temporary in (dead_poison, dead_terminal, live_terminal):
        temporary.write_text("in-progress", encoding="utf-8")
    if invoke(repo, "fallow", environment).returncode:
        fail("temporary-writer liveness gate failed")
    if dead_poison.exists() or dead_terminal.exists():
        fail("dead-writer atomic temporaries were not cleaned")
    if not live_terminal.exists():
        fail("live terminal receipt temporary was deleted by a shared gate")
    live_terminal.unlink()

    orphan = lock_path.parent / "hard-eng-terminal-999999999-deadbeef.json"
    atomic_json(orphan, {"terminal": True, "token": "b" * 64})
    cleaners = [
        subprocess.Popen(
            gate_command(repo, "fallow"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )
        for _ in range(2)
    ]
    cleaner_output = [cleaner.communicate(timeout=30) for cleaner in cleaners]
    if any(cleaner.returncode for cleaner in cleaners) or orphan.exists():
        fail(
            "concurrent dead-owner receipt cleanup failed: "
            + "".join(sum(cleaner_output, ()))
        )

    poison.write_text("", encoding="utf-8")
    blocked = invoke(repo, "fallow", environment)
    if blocked.returncode == 0 or "metadata is invalid" not in blocked.stderr:
        fail("torn final quarantine metadata did not fail closed")
    poison.unlink()
    if invoke(repo, "fallow", environment).returncode:
        fail("explicit torn-metadata cleanup did not restore gate operation")


def check_pre_spawn_rollback(
    repo: Path,
    source: Path,
    original: str,
) -> None:
    poison = git_private_path(repo, POISON_NAME)
    original_runner = project_gate_module._run_bounded

    def fail_before_spawn(
        _command: list[str],
        *,
        capture: bool,
    ) -> subprocess.CompletedProcess[str]:
        del capture
        raise FileNotFoundError("synthetic bounded-run launch failure")

    project_gate_module._run_bounded = fail_before_spawn
    try:
        try:
            run_families(repo, ["react-doctor"], 5)
        except FileNotFoundError:
            pass
        else:
            fail("pre-spawn bounded-run failure was accepted")
    finally:
        project_gate_module._run_bounded = original_runner
    if poison.exists() or source.read_text(encoding="utf-8") != original:
        fail("no-child React Doctor launch failure left quarantine")


def check_modes(repo: Path, source: Path) -> None:
    initial = source.stat().st_mode & 0o777
    before = tree_fingerprint(repo)
    source.chmod(initial | 0o111)
    after = tree_fingerprint(repo)
    source.chmod(initial)
    if before == after:
        fail("worktree mode changes were omitted from the fingerprint")
    run_git(repo, "add", source.name)
    before = tree_fingerprint(repo)
    run_git(repo, "update-index", "--chmod=+x", source.name)
    after = tree_fingerprint(repo)
    run_git(repo, "update-index", "--chmod=-x", source.name)
    if before == after:
        fail("Git index mode changes were omitted from the fingerprint")


def check_linked_worktree(
    repo: Path,
    marker: Path,
    environment: dict[str, str],
) -> None:
    run_git(repo, "config", "user.name", "Hard Eng Test")
    run_git(repo, "config", "user.email", "hard-eng@example.test")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-qm", "scanner fixture")
    linked = repo.parent / "linked-worktree"
    run_git(repo, "worktree", "add", "-q", "-b", "linked", str(linked))
    if git_private_path(linked, LOCK_NAME) == git_private_path(repo, LOCK_NAME):
        fail("linked worktrees unexpectedly shared one source-tree lock")
    baseline_started = time.monotonic()
    baseline = invoke(linked, "fallow", environment)
    baseline_elapsed = time.monotonic() - baseline_started
    if baseline.returncode:
        fail(f"linked worktree gate failed uncontended: {baseline.stderr}")
    delayed = {**environment, "HARD_ENG_DOCTOR_DELAY": str(DOCTOR_DELAY)}
    doctor = subprocess.Popen(
        gate_command(repo, "react-doctor"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=delayed,
    )
    wait_for(marker, doctor)
    started = time.monotonic()
    linked_result = invoke(linked, "fallow", environment)
    elapsed = time.monotonic() - started
    doctor.communicate(timeout=DOCTOR_DELAY + 20)
    if (
        linked_result.returncode
        or doctor.returncode
        or elapsed > baseline_elapsed + CONTENTION_SLACK
    ):
        fail("independent linked worktrees shared scanner coordination")
    run_git(repo, "worktree", "remove", "--force", str(linked))


def check_wiring() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    fallow_script = package.get("scripts", {}).get("fallow", "")
    if "project_gate.py" not in fallow_script or "--family fallow" not in fallow_script:
        fail("package Fallow script bypasses source-tree coordination")
    required = {
        "skills/deterministic-checks/SKILL.md": (
            "`project_gate.py` + `dart_decimate_gate.py` shared source lock"
        ),
        "skills/deterministic-checks/references/fallow.md": (
            "every gate executes the manifest family through `project_gate.py`"
        ),
        "skills/deterministic-checks/references/react-doctor.md": (
            "every gate executes the manifest family through `project_gate.py`"
        ),
        "skills/deterministic-checks/references/dart-decimate.md": (
            "shared source lock + bounded"
        ),
    }
    for relative, anchor in required.items():
        if anchor not in (ROOT / relative).read_text(encoding="utf-8"):
            fail(f"source-tree coordination wiring missing from {relative}")


def main() -> int:
    check_wiring()
    with tempfile.TemporaryDirectory(prefix="source-tree-coordination-") as temporary:
        parent = Path(temporary)
        repo = parent / "repo"
        repo.mkdir()
        run_git(repo, "init", "-q", "-b", "main")
        source = repo / "source.tsx"
        marker = repo / ".react-doctor-rewrite-active"
        original = (
            "// eslint-disable-next-line react-doctor/no-array-index-as-key\n"
            "export const rows = ['one'];\n"
        )
        source.write_text(original, encoding="utf-8")
        (repo / "hard-eng.gates.json").write_text(
            json.dumps(manifest()),
            encoding="utf-8",
        )
        fake_bin = parent / "external-bin"
        npx = fake_bin / "npx"
        install_fake_npx(npx)
        environment = git_env()
        environment["PATH"] = (
            f"{fake_bin}{os.pathsep}{environment.get('PATH', '')}"
        )
        check_root_cause(repo, marker, environment)
        check_normal_coordination(repo, marker, environment)
        check_modes(repo, source)
        check_pre_spawn_rollback(repo, source, original)
        check_quarantine(repo, source, marker, original, environment)
        check_linked_worktree(repo, marker, environment)
        if source.read_text(encoding="utf-8") != original or marker.exists():
            fail("scanner regressions left a source-tree artifact")
    print("source-tree-coordination-regressions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
