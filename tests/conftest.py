"""Load the actual installed-script entry points without invoking their CLI."""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from shipping import ShippingPolicy

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / ".hooks"))

import update


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=root, text=True).strip()


def commit(root: Path, message: str) -> str:
    git(root, "add", ".")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD")


def init(root: Path) -> None:
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")


@pytest.fixture
def installer() -> ModuleType:
    return load_module("installer", SOURCE / "setup.py")


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    init(root)
    git(root, "commit", "--allow-empty", "-qm", "baseline")
    return root


def plan_document() -> str:
    return """# Fixture command behavior
Status: Complete
## Outcome + scope
Verify fixture command exits; no product release.
## Repository context
The test creates commands in a temporary Git repository.
## Decisions + authorization
Blockers: None
Handoff: Approval
Authorized test fixture; no external actions.
## Acceptance + steps
- [x] Observe the configured command exit.
## Baseline + execution
Result: Passed
Evidence: Controlled fixture baseline; not production acceptance.
One test actor.
## Risks + recovery
N/A — temporary fixture is removed by pytest.
## ux_reference
N/A — fixture commands have no visual interface.
## Verification
Result: Passed
Evidence: The test asserts the observed command exit; this is fixture data.
E2E: Passed — fixture command is invoked through the native CLI and its exit is asserted.
"""


@pytest.fixture
def completed_plan() -> str:
    return plan_document()


@pytest.fixture
def visual_plan(completed_plan: str) -> str:
    return completed_plan.replace(
        "N/A — fixture commands have no visual interface.",
        "Result: Passed\n"
        "Evidence: Synthetic capture contract for this test, not app acceptance.\n"
        "Surface: Existing — /account, rendered by app/account/page.tsx\n"
        "Before: ![Before](https://example.test/account-before.png)\n"
        "Proposed: ![Proposed](https://example.test/account-proposed.png)\n"
        "Capture: Native browser test account.spec.ts passed the route and screen assertions.\n"
        "Review: Inspected both account captures at the same viewport; only the proposed label differs.",
    )


@pytest.fixture
def runner(tmp_path: Path, completed_plan: str) -> ModuleType:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    module = load_module("runner", SOURCE / ".hooks/hard-eng.py")
    module.__dict__["ROOT"] = tmp_path
    (tmp_path / "PLAN.md").write_text(completed_plan)
    for name in ("PRODUCT.md", "DESIGN.md"):
        (tmp_path / name).write_text((SOURCE / name).read_text())
    return module


@pytest.fixture
def shipping_policy() -> "ShippingPolicy":
    return {
        "base": "main",
        "checks": ["hard-eng"],
        "ui_paths": [],
        "ci_seconds": 180.0,
        "pre_push_seconds": 180.0,
        "delivery": [],
    }


@pytest.fixture
def release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shipping_policy: "ShippingPolicy"
) -> tuple[Path, Path, str]:
    source, target = tmp_path / "source", tmp_path / "target"
    init(source)
    for name in (".hooks", ".agents", ".github"):
        shutil.copytree(
            SOURCE / name,
            source / name,
            ignore=shutil.ignore_patterns(
                "__pycache__", "skill-sources", "node_modules"
            ),
        )
    for name in (
        "setup.py",
        "setup.sh",
        "AGENTS.md",
        "PRODUCT.md",
        "DESIGN.md",
        ".gitignore",
        "pyproject.toml",
        "uv.lock",
    ):
        shutil.copyfile(SOURCE / name, source / name)
    (source / "hard-eng.gates.json").write_text(
        json.dumps(
            {
                "packages": [],
                "shared": [
                    {
                        "name": "source-check",
                        "command": ["python3", "-c", "print('SOURCE_CHECK')"],
                    }
                ],
            }
        )
    )
    old = commit(source, "source baseline")
    init(target)
    (target / "package.json").write_text('{"private":true}')
    (target / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    (target / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [], "shared": [], "shipping": shipping_policy})
    )
    subprocess.run(
        ["python3", str(source / "setup.py"), str(target)],
        check=True,
        capture_output=True,
    )
    for name in ("PRODUCT.md", "DESIGN.md"):
        shutil.copyfile(SOURCE / name, target / name)
    (target / "hard-eng.gates.json").write_text(
        json.dumps(
            {
                "packages": [],
                "shared": [
                    {
                        "name": "application-check",
                        "command": ["python3", "-c", "raise SystemExit(1)"],
                    },
                    {
                        "name": "actionlint",
                        "role": "workflows",
                        "command": ["python3", "-c", "print('WORKFLOW_CHECK')"],
                    },
                    {
                        "name": "zizmor",
                        "role": "ci-security",
                        "command": ["python3", "-c", "print('CI_SECURITY_CHECK')"],
                    },
                ],
            }
        )
    )
    (target / "project.txt").write_text("original\n")
    commit(target, "installed baseline")
    reference = source / ".agents/skills/he/references/workflow.md"
    reference.write_text(reference.read_text() + "\nUpdated fixture instruction.\n")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{source.as_uri()}.insteadOf")
    monkeypatch.setenv(
        "GIT_CONFIG_VALUE_0", f"https://github.com/{update.UPSTREAM}.git"
    )
    return source, target, old
