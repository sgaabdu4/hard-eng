#!/usr/bin/env python3
"""Regression checks for workflow execution identity and containment."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True

from run_workflow import ContractError, run_phase, validate_job
from run_workflow_regression_check import PYTHON, invoke, make_project, phase_receipt, sha256, write_json


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def document(job: Path) -> dict:
    return json.loads(job.read_text(encoding="utf-8"))


def save(job: Path, value: dict) -> None:
    write_json(job, value)


def actor_path(value: dict) -> Path:
    return Path(value["phases"]["discovery"]["argv"][1])


def replace_actor(job: Path, source: str) -> None:
    value = document(job)
    actor = actor_path(value)
    actor.write_text(source, encoding="utf-8")
    identity = sha256(actor)
    for phase in value["phases"].values():
        phase["argument_schema"][0]["sha256"] = identity
    save(job, value)


def local_python(job: Path, *, mode: int = 0o700) -> Path:
    value = document(job)
    executable = job.parent / "approved-python"
    shutil.copy2(PYTHON, executable)
    executable.chmod(mode)
    identity = sha256(executable)
    for phase in value["phases"].values():
        phase["argv"][0] = str(executable)
        phase["executable_sha256"] = identity
    save(job, value)
    return executable


def enforced(job: Path) -> None:
    value = document(job)
    value["phases"]["discovery"]["containment"] = {"mode": "enforced-local"}
    save(job, value)


def supported_backend() -> bool:
    return (platform.system() == "Darwin" and Path("/usr/bin/sandbox-exec").is_file()) or (
        platform.system() == "Linux" and any(path.is_file() for path in (Path("/usr/bin/bwrap"), Path("/bin/bwrap")))
    )


def case_executable_changed(base: Path) -> None:
    job, attempt = make_project(base, "executable-changed", "success")
    executable = local_python(job)
    context = validate_job(job)
    with executable.open("ab") as handle:
        handle.write(b"changed-after-validation")
    try:
        run_phase(context, "discovery", None)
    except ContractError:
        pass
    else:
        raise AssertionError("changed executable was accepted")
    require(
        phase_receipt(attempt)["runner_failure"] == "execution-boundary", "changed executable failure was not bound"
    )


def case_executable_symlink(base: Path) -> None:
    job, _ = make_project(base, "executable-symlink", "success")
    value = document(job)
    link = job.parent / "python-link"
    link.symlink_to(PYTHON)
    phase = value["phases"]["discovery"]
    phase["argv"][0] = str(link)
    phase["executable_sha256"] = sha256(PYTHON)
    save(job, value)
    result = invoke(job, "validate")
    require(result.returncode != 0 and "symlink" in result.stderr, "executable symlink was accepted")


def case_unsupported_executable(base: Path) -> None:
    job, _ = make_project(base, "unsupported-executable", "success")
    local_python(job, mode=0o777)
    result = invoke(job, "validate")
    require(
        result.returncode != 0 and "group/other writable" in result.stderr,
        "unsafe executable permissions were accepted",
    )


def case_unexpected_argument(base: Path) -> None:
    job, _ = make_project(base, "unexpected-argument", "success")
    value = document(job)
    value["phases"]["discovery"]["argv"].append("--unexpected")
    save(job, value)
    result = invoke(job, "validate")
    require(result.returncode != 0 and "bind every argument" in result.stderr, "unexpected argument was accepted")


def case_environment_injection(base: Path) -> None:
    job, _ = make_project(base, "environment-injection", "success")
    value = document(job)
    value["phases"]["discovery"]["environment"] = {"SAFE": "claimed"}
    save(job, value)
    result = invoke(job, "validate")
    require(result.returncode != 0 and "fields" in result.stderr, "job environment was accepted")


def case_production_endpoint(base: Path) -> None:
    job, _ = make_project(base, "production-endpoint", "success")
    value = document(job)
    phase = value["phases"]["discovery"]
    argument = "--endpoint=https://cloud.appwrite.io/v1"
    phase["argv"].append(argument)
    phase["argument_schema"].append({"kind": "literal", "value": argument})
    save(job, value)
    result = invoke(job, "validate")
    require(result.returncode != 0 and "synthetic endpoint" in result.stderr, "production endpoint was accepted")


def case_unsupported_host(base: Path) -> None:
    job, _ = make_project(base, "unsupported-host", "success")
    enforced(job)
    with patch("workflow_boundary.platform.system", return_value="UnsupportedOS"):
        try:
            validate_job(job)
        except ContractError as exc:
            require("unavailable" in str(exc), "unsupported host failure was not explicit")
        else:
            raise AssertionError("unsupported host claimed enforced containment")


def case_declarative_label(base: Path) -> None:
    job, attempt = make_project(base, "declarative-label", "success")
    result = invoke(job, "run", "--phase", "discovery")
    require(result.returncode == 0, f"declarative fixture failed: {result.stderr}")
    boundary = phase_receipt(attempt)["execution_boundary"]
    require(
        boundary["classification"] == "declarative-not-enforced"
        and boundary["filesystem"]["enforced"] is False
        and boundary["network"]["enforced"] is False,
        "declarative mode was labelled as enforced",
    )


def case_timeout_kills_descendants(base: Path) -> None:
    job, attempt = make_project(base, "timeout-descendant", "success")
    marker = attempt / "descendant-marker"
    source = f"""#!/usr/bin/env python3
import subprocess
import sys
import time
subprocess.Popen([sys.executable, "-c", {json.dumps(f"import time; time.sleep(1.5); open({str(marker)!r}, 'w').write('leaked')")}])
time.sleep(5)
"""
    replace_actor(job, source)
    value = document(job)
    value["phases"]["discovery"]["timeout_seconds"] = 1
    save(job, value)
    result = invoke(job, "run", "--phase", "discovery")
    require(result.returncode != 0, "timed-out actor was accepted")
    time.sleep(1.7)
    require(not marker.exists(), "timed-out descendant survived")


def case_network_denied(base: Path) -> None:
    job, _ = make_project(base, "network-denied", "success")
    replace_actor(
        job,
        """#!/usr/bin/env python3
import socket
import sys
from pathlib import Path
_, _, _, _, evidence = sys.argv[1:]
sock = socket.socket()
sock.bind(("127.0.0.1", 0))
Path(evidence).parent.mkdir(parents=True, exist_ok=True)
Path(evidence).write_text("network was available")
""",
    )
    enforced(job)
    result = invoke(job, "run", "--phase", "discovery")
    require(result.returncode != 0, "enforced local phase reached the network")


def case_filesystem_denied(base: Path) -> None:
    job, _ = make_project(base, "filesystem-denied", "success")
    replace_actor(
        job,
        """#!/usr/bin/env python3
import sys
from pathlib import Path
_, _, attempt, _, evidence = sys.argv[1:]
Path(attempt).parent.joinpath("outside-boundary").write_text("escaped")
Path(evidence).parent.mkdir(parents=True, exist_ok=True)
Path(evidence).write_text("filesystem escape worked")
""",
    )
    enforced(job)
    result = invoke(job, "run", "--phase", "discovery")
    require(result.returncode != 0, "enforced local phase wrote outside its artifact root")


def case_valid_contained(base: Path) -> None:
    job, attempt = make_project(base, "valid-contained", "success")
    enforced(job)
    result = invoke(job, "run", "--phase", "discovery")
    require(result.returncode == 0, f"valid contained fixture failed: {result.stderr}")
    boundary = phase_receipt(attempt)["execution_boundary"]
    require(
        boundary["classification"] == "enforced"
        and boundary["filesystem"]["enforced"] is True
        and boundary["network"]["enforced"] is True,
        "contained receipt omitted enforced evidence",
    )


CASES: list[tuple[str, Callable[[Path], None]]] = [
    ("executable-changed", case_executable_changed),
    ("executable-symlink", case_executable_symlink),
    ("unsupported-executable", case_unsupported_executable),
    ("unexpected-argument", case_unexpected_argument),
    ("environment-injection", case_environment_injection),
    ("production-endpoint", case_production_endpoint),
    ("unsupported-host", case_unsupported_host),
    ("declarative-label", case_declarative_label),
    ("timeout-descendants", case_timeout_kills_descendants),
]
if supported_backend():
    CASES.extend(
        (
            ("network-denied", case_network_denied),
            ("filesystem-denied", case_filesystem_denied),
            ("valid-contained", case_valid_contained),
        )
    )


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="workflow-boundary-") as raw:
        base = Path(raw).resolve()
        for name, check in CASES:
            try:
                check(base)
            except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as exc:
                failures.append(f"{name}: {exc}")
    if failures:
        for failure in failures:
            print(f"workflow-boundary-regression: FAIL | {failure}", file=sys.stderr)
        return 1
    print(f"workflow-boundary-regression: PASS | checks={len(CASES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
