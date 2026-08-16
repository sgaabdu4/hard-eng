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
from typing import NoReturn

import project_gate as project_gate_module
from git_env import git_env, scrub_environ
from project_gate import REACT_DOCTOR_COMMAND, run_families
from source_tree_coordination import (
    CoordinationError,
    LOCK_NAME,
    POISON_NAME,
    atomic_json,
    git_private_path,
    tree_fingerprint,
)

SCRIPT_DIR = Path(__file__).resolve().parent
GATE = SCRIPT_DIR / "project_gate.py"
ROOT = SCRIPT_DIR.parents[2]

# Contention proofs observe whether the held-lock fixture is still active when
# the waiting gate returns, so process startup cost does not affect the result.
DOCTOR_DELAY = 0.15
# The crash proof needs a whole-run timeout that outlives measured gate startup on
# this host yet dies far inside the fixture's rewrite delay.

scrub_environ(ceiling=tempfile.gettempdir())


def fail(message: str) -> NoReturn:
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


def families() -> dict[str, list[str]]:
    return {
        "fallow": [
            "npx",
            "--yes",
            "fallow@latest",
            "--fail-on-issues",
            "--format",
            "json",
            "--quiet",
        ],
        "react-doctor": list(REACT_DOCTOR_COMMAND),
    }


def manifest() -> dict[str, object]:
    return {"schema_version": 1, "families": families()}


def install_fake_npx(path: Path) -> None:
    write(
        path,
        "#!/usr/bin/env python3\n"
        "import json, os, sys, time\n"
        "from pathlib import Path\n"
        "root = Path.cwd()\n"
        "source = root / 'source.tsx'\n"
        "marker = root / '.react-doctor-rewrite-active'\n"
        "if '--help' in sys.argv[1:]:\n"
        "    options = {'--scope': '--scope <value>', "
        "'--blocking': '--blocking <level>', "
        "'--no-respect-inline-disables': '--no-respect-inline-disables', "
        "'--no-telemetry': '--no-telemetry', '--json': '--json', "
        "'--json-out': '--json-out <path>', '-y': '-y, --yes'}\n"
        "    options.pop(os.environ.get('HARD_ENG_DOCTOR_DROP_FLAG', ''), None)\n"
        "    stream = sys.stderr if os.environ.get('HARD_ENG_DOCTOR_HELP_STREAM') "
        "== 'stderr' else sys.stdout\n"
        "    stream.write('Options:\\n' + ''.join(f'  {text}\\n' "
        "for text in options.values()))\n"
        "    raise SystemExit(int(os.environ.get('HARD_ENG_DOCTOR_HELP_EXIT', '0')))\n"
        "package = next(arg for arg in sys.argv[1:] if arg.endswith('@latest'))\n"
        "if package == 'react-doctor@latest':\n"
        "    original = source.read_text(encoding='utf-8')\n"
        "    source.write_text(original.replace('eslint-disable', 'eslint_disable'), "
        "encoding='utf-8')\n"
        "    marker.write_text('active\\n', encoding='utf-8')\n"
        "    try:\n"
        "        time.sleep(float(os.environ.get('HARD_ENG_DOCTOR_DELAY', '0.02')))\n"
        "        hold_file = os.environ.get('HARD_ENG_DOCTOR_HOLD_FILE')\n"
        "        if hold_file:\n"
        "            hold = Path(hold_file)\n"
        "            while not hold.exists():\n"
        "                time.sleep(0.01)\n"
        "        found = ([{'filePath': 'source.tsx', 'line': 1, "
        "'plugin': 'react-doctor', 'rule': 'no-array-index-as-key', "
        "'severity': 'error'}]\n"
        "                 if os.environ.get('HARD_ENG_DOCTOR_FINDING') else [])\n"
        "        print(json.dumps({\n"
        "            'schemaVersion': 3, 'mode': 'full', 'reactDetected': True,\n"
        "            'version': '0.9.5', 'ok': True, 'directory': '.', 'diff': None,\n"
        "            'projects': [{'directory': '.', 'diagnostics': found, "
        "'score': None,\n"
        "                          'skippedChecks': [], 'analyzedFileCount': 1,\n"
        "                          'complete': True}],\n"
        "            'diagnostics': found,\n"
        "            'summary': {'errorCount': len(found), 'warningCount': 0,\n"
        "                        'affectedFileCount': len(found),\n"
        "                        'totalDiagnosticCount': len(found)},\n"
        "            'elapsedMilliseconds': 1, 'error': None,\n"
        "        }))\n"
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
        f"            deadline = time.monotonic() + {DOCTOR_DELAY}\n"
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
    commands = families()
    release = repo.parent / ".react-doctor-root-cause-release"
    delayed = {
        **environment,
        "HARD_ENG_DOCTOR_DELAY": "0",
        "HARD_ENG_DOCTOR_HOLD_FILE": str(release),
    }
    doctor = subprocess.Popen(
        commands["react-doctor"],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=delayed,
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
    release.write_text("release\n", encoding="utf-8")
    doctor.communicate(timeout=DOCTOR_DELAY + 20)
    release.unlink()
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

    timeout_release = repo.parent / ".react-doctor-timeout-release"
    slow = {
        **environment,
        "HARD_ENG_DOCTOR_DELAY": "0",
        "HARD_ENG_DOCTOR_HOLD_FILE": str(timeout_release),
    }
    doctor = subprocess.Popen(
        gate_command(repo, "react-doctor"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=slow,
    )
    wait_for(marker, doctor)
    blocked = invoke(repo, "fallow", environment, timeout="0.1")
    holder_active = marker.exists()
    timeout_release.write_text("release\n", encoding="utf-8")
    doctor.communicate(timeout=DOCTOR_DELAY + 20)
    timeout_release.unlink()
    if (
        blocked.returncode == 0
        or "timeout exhausted waiting for source-tree coordination"
        not in blocked.stderr
        or not holder_active
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
    if invoke(repo, "react-doctor", environment).returncode:
        fail("react-doctor gate failed uncontended before the crash proof")
    crash_timeout = 1.5
    crash_hold = repo.parent / ".react-doctor-crash-hold"
    crashing = {
        **environment,
        "HARD_ENG_DOCTOR_DELAY": "0",
        "HARD_ENG_DOCTOR_HOLD_FILE": str(crash_hold),
    }
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
        "HARD_ENG_DOCTOR_DELAY": str(DOCTOR_DELAY),
        "HARD_ENG_DOCTOR_RESTORED_DELAY": str(DOCTOR_DELAY / 2),
    }
    release = repo.parent / ".react-doctor-release"
    delayed["HARD_ENG_DOCTOR_HOLD_FILE"] = str(release)
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
    release.write_text("release\\n", encoding="utf-8")
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


def check_flag_preflight(
    repo: Path,
    source: Path,
    original: str,
    environment: dict[str, str],
) -> None:
    poison = git_private_path(repo, POISON_NAME)
    # React Doctor drops unrecognized flags without erroring, so every flag the scan
    # depends on has to be caught on its own option surface before the scan runs.
    rejected = (
        ("renamed audit flag",
         {"HARD_ENG_DOCTOR_DROP_FLAG": "--no-respect-inline-disables"},
         "no longer advertises"),
        ("reported findings", {"HARD_ENG_DOCTOR_FINDING": "1"},
         "react-doctor report contains findings"),
    )
    for label, overrides, anchor in rejected:
        result = invoke(repo, "react-doctor", {**environment, **overrides})
        if result.returncode == 0 or anchor not in result.stderr:
            fail(f"React Doctor {label} was accepted: {result.stderr}")
        if poison.exists():
            fail(f"React Doctor {label} left a source-tree quarantine")
        if source.read_text(encoding="utf-8") != original:
            fail(f"React Doctor {label} left a rewritten source tree")

def check_pre_spawn_rollback(
    repo: Path,
    source: Path,
    original: str,
    external_bin: Path,
) -> None:
    poison = git_private_path(repo, POISON_NAME)
    original_runner = project_gate_module._run_bounded
    previous_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{external_bin}{os.pathsep}{previous_path}"

    def fail_before_spawn(
        _command: list[str],
        *,
        capture: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        del capture, timeout
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
        os.environ["PATH"] = previous_path
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


def check_ambiguous_entries(parent: Path) -> None:
    repo = parent / "ambiguous-repo"
    repo.mkdir()
    run_git(repo, "init", "-q", "-b", "main")
    conflict = repo / "conflict.txt"
    conflict.write_text("base\n", encoding="utf-8")
    run_git(repo, "add", "conflict.txt")
    run_git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "base")
    blobs = []
    for value in ("ours\n", "theirs\n"):
        result = subprocess.run(
            ["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
            input=value,
            text=True,
            capture_output=True,
            check=True,
            env=git_env(),
        )
        blobs.append(result.stdout.strip())
    run_git(repo, "update-index", "--force-remove", "conflict.txt")
    subprocess.run(
        ["git", "-C", str(repo), "update-index", "--index-info"],
        input=(
            f"100644 {blobs[0]} 2\tconflict.txt\n"
            f"100644 {blobs[1]} 3\tconflict.txt\n"
        ),
        text=True,
        check=True,
        env=git_env(),
    )
    try:
        tree_fingerprint(repo)
    except CoordinationError:
        pass
    else:
        fail("multi-stage index metadata received a source-tree fingerprint")

    if hasattr(os, "mkfifo"):
        special_repo = parent / "special-repo"
        special_repo.mkdir()
        run_git(special_repo, "init", "-q", "-b", "main")
        special = special_repo / "special"
        special.write_text("tracked\n", encoding="utf-8")
        run_git(special_repo, "add", "special")
        special.unlink()
        os.mkfifo(special)
        try:
            tree_fingerprint(special_repo)
        except CoordinationError:
            pass
        else:
            fail("special worktree entry received a source-tree fingerprint")


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
    linked_release = repo.parent / ".react-doctor-linked-release"
    delayed = {
        **environment,
        "HARD_ENG_DOCTOR_DELAY": "0",
        "HARD_ENG_DOCTOR_HOLD_FILE": str(linked_release),
    }
    doctor = subprocess.Popen(
        gate_command(repo, "react-doctor"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=delayed,
    )
    wait_for(marker, doctor)
    linked_result = invoke(linked, "fallow", environment)
    holder_active = marker.exists()
    linked_release.write_text("release\n", encoding="utf-8")
    doctor.communicate(timeout=DOCTOR_DELAY + 20)
    linked_release.unlink()
    if (
        linked_result.returncode
        or doctor.returncode
        or not holder_active
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
    reference = ROOT / "skills/deterministic-checks/references/react-doctor.md"
    if " ".join(REACT_DOCTOR_COMMAND) not in reference.read_text(encoding="utf-8"):
        fail("documented React Doctor argv drifted from the enforced command")


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
        check_flag_preflight(repo, source, original, environment)
        check_pre_spawn_rollback(repo, source, original, fake_bin)
        check_quarantine(repo, source, marker, original, environment)
        check_linked_worktree(repo, marker, environment)
        check_ambiguous_entries(parent)
        if source.read_text(encoding="utf-8") != original or marker.exists():
            fail("scanner regressions left a source-tree artifact")
    print("source-tree-coordination-regressions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
