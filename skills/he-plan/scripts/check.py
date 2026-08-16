#!/usr/bin/env python3
"""Focused regression proof for the lean Feature Brief contract."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import NoReturn
from safe_plan_io_regression import (
    check_ancestor_swap,
    check_exchange_editor_save,
    check_init_preimage,
    check_plan_lock,
    check_rollback_failure_recovery,
    check_write_failure_cleanup,
)
from ux_reference_regression import check_linked_worktree, check_targets
ROOT = Path(__file__).resolve().parents[3]
GIT_ENV_SCRIPTS = ROOT / "skills/deterministic-checks/scripts"
if str(GIT_ENV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GIT_ENV_SCRIPTS))

from git_env import scrub_environ

scrub_environ(ceiling=tempfile.gettempdir())

STATE_PATH = ROOT / "skills/he/scripts/plan_state.py"
AUTONOMOUS_DIRECTIVE = "YES — use Hard Eng autonomous mode for this task."
APPROVAL_CONTEXT = (
    "--session-id", "he-plan-contract",
    "--request-digest", "sha256:" + "d" * 64,
    "--allowed-action", "build-and-verify",
)
os.environ["HARD_ENG_SESSION_ID"] = "he-plan-contract"
os.environ["HARD_ENG_REQUEST_DIGEST"] = "sha256:" + "d" * 64


def fail(message: str) -> NoReturn:
    raise SystemExit(f"he-plan-check: {message}")


def load_state():
    specification = importlib.util.spec_from_file_location("lean_plan_state", STATE_PATH)
    if specification is None or specification.loader is None:
        fail("cannot load plan_state.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def authorize_fixture(state, repo: Path, plan: Path, fingerprint: str) -> None:
    state.authorize_execution(
        repo, plan, fingerprint, AUTONOMOUS_DIRECTIVE,
        "he-plan-contract", "sha256:" + "d" * 64, ["build-and-verify"],
    )


def filled(text: str) -> str:
    replacements = {
        "## Outcome\n- TBD": "## Outcome\n- A user receives one observable result.",
        "## Non-goals\n- TBD": "## Non-goals\n- Adjacent workflow changes are excluded.",
        "## Material decisions\n- TBD": "## Material decisions\n- Existing policy remains canonical.",
        "- ux_reference = TBD": "- ux_reference = n/a",
        "- ux_reference_sources = TBD": "- ux_reference_sources = n/a",
        "## Acceptance examples\n- TBD": (
            "## Acceptance examples\n"
            "- Given an eligible user, when they act, then the result is visible."
        ),
        "## Affected canonical areas\n- TBD": (
            "## Affected canonical areas\n- Existing command owner and route."
        ),
        "- rollback = TBD": "- rollback = disable the route and preserve stored state.",
        "## First vertical slice\n- S-1 = TBD\n- proof = TBD": (
            "## First vertical slice\n"
            "- S-1 = command to stored result to visible response.\n"
            "- proof = focused behavior test."
        ),
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def ux_reference_cases(state) -> None:
    brief = filled(state.template("lean-loop", "lean-loop-test"))
    try:
        state.approval_candidate(brief)
    except state.PlanError:
        fail("ux_reference = n/a must allow Ready-to-build")
    missing = brief.replace("- ux_reference = n/a\n", "")
    try:
        state.validate_text(missing)
    except state.PlanError as error:
        if "ux_reference" not in str(error):
            fail("missing ux_reference row must name the field")
    else:
        fail("missing ux_reference row must be invalid")
    referenced_without_sources = brief.replace(
        "- ux_reference = n/a", "- ux_reference = docs/mock-home.png"
    )
    try:
        state.require_ux_reference_target(Path.cwd(), referenced_without_sources)
    except state.PlanError as error:
        if "ux_reference_sources" not in str(error):
            fail("missing ux_reference provenance must name ux_reference_sources")
    else:
        fail("visual ux_reference without provenance must be invalid")
    pending = brief.replace("- ux_reference = n/a", "- ux_reference = TBD")
    try:
        state.approval_candidate(pending)
    except state.PlanError as error:
        if "placeholder" not in str(error).lower():
            fail("TBD ux_reference must block approval as a placeholder")
    else:
        fail("TBD ux_reference must not reach Ready-to-build")
    referenced = brief.replace(
        "- ux_reference = n/a", "- ux_reference = docs/mock-home.png"
    )
    candidate, _ = state.approval_candidate(referenced)
    mutated = candidate.replace(
        "- ux_reference = docs/mock-home.png", "- ux_reference = docs/mock-home-v2.png"
    )
    try:
        state.validate_text(mutated)
    except state.PlanError as error:
        if "frozen" not in str(error):
            fail("approved ux_reference drift must report frozen bytes")
    else:
        fail("approved ux_reference change must require reopen")


def git_repo(path: Path) -> None:
    subprocess.run(
        ["git", "init", "-q", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    (path / "hard-eng.gates.json").write_text(
        json.dumps({
            "schema_version": 1,
            "families": {
                "targeted": [sys.executable, "-c", "raise SystemExit(0)", "targeted"],
            },
        }),
        encoding="utf-8",
    )


def gate_receipts(repo: Path, names: tuple[str, ...]) -> None:
    for name in names:
        scope = ("--full",) if name == "full" else ("--slice", name)
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "skills/deterministic-checks/scripts/slice_gate.py"),
                "run", "--repo", str(repo),
                "--plan", str(repo / "features/lean-loop/PLAN.md"), *scope,
                "--timeout", "60", "--behavior", "fixture behavior",
                "--check", "targeted",
                "--e2e", "not-applicable:fixture",
                "--security", "not-applicable:fixture",
                "--review", "fixture diff reviewed",
            ],
            check=False, capture_output=True, text=True,
        )
        if result.returncode != 0:
            fail(f"slice gate fixture receipt failed: {result.stderr}")


def approval_reply_cases(state) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        git_repo(repo)
        plan = repo / "features/lean-loop/PLAN.md"
        plan.parent.mkdir(parents=True)

        def call(action: str, *extra: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [
                    sys.executable, str(STATE_PATH), action,
                    "--repo", str(repo), "--plan", str(plan), *extra,
                ],
                check=False, capture_output=True, text=True,
            )

        draft = state.template("lean-loop", "lean-loop-test")
        plan.write_text(draft, encoding="utf-8")
        draft_validation = call("validate")
        if (
            draft_validation.returncode != 0
            or "ready_for_approval=" in draft_validation.stdout
        ):
            fail("incomplete planning brief reported ready_for_approval")
        brief = filled(draft)
        plan.write_text(brief, encoding="utf-8")
        validated = call("validate")
        if validated.returncode != 0 or "ready_for_approval=yes" not in validated.stdout:
            fail("complete planning brief did not report ready_for_approval")
        original = plan.read_bytes()
        for empty in ("", "   "):
            rejected = call(
                "approve", "--expect-token", state.token_for(brief),
                "--approval-reply", empty, *APPROVAL_CONTEXT,
            )
            if rejected.returncode == 0 or plan.read_bytes() != original:
                fail("empty reply received approval")
        approved = call(
            "approve", "--expect-token", state.token_for(brief),
            "--approval-reply", AUTONOMOUS_DIRECTIVE, *APPROVAL_CONTEXT,
        )
        if approved.returncode != 0:
            fail(f"exact autonomous directive failed to approve: {approved.stderr}")
        approved_text = plan.read_text(encoding="utf-8")
        legacy_text = approved_text.replace("- ux_reference = n/a\n", "").replace(
            "- ux_reference_sources = n/a\n", ""
        )
        legacy_text = state.render_state(legacy_text, {
            "approval_fingerprint": state.frozen_fingerprint(
                state.parse_sections(legacy_text)
            ),
        })
        plan.write_text(legacy_text, encoding="utf-8")
        authorize_fixture(
            state,
            repo,
            plan,
            state.parse_state(legacy_text)["approval_fingerprint"],
        )
        legacy_reopened = call(
            "reopen", "--expect-token", state.token_for(legacy_text),
            "--reason", "changed-outcome",
        )
        if legacy_reopened.returncode != 0:
            fail(
                "approved legacy brief without ux_reference could not reopen: "
                f"{legacy_reopened.stderr}"
            )
        migrated_text = plan.read_text(encoding="utf-8")
        if "- ux_reference = TBD" not in migrated_text:
            fail("legacy reopen did not add the required ux_reference placeholder")
        if "- ux_reference_sources = TBD" not in migrated_text:
            fail("legacy reopen did not add the required UX provenance placeholder")
        plan.write_text(approved_text, encoding="utf-8")
        authorize_fixture(
            state,
            repo,
            plan,
            state.parse_state(approved_text)["approval_fingerprint"],
        )
        reopened = call(
            "reopen", "--expect-token", state.token_for(approved_text),
            "--reason", "changed-outcome",
        )
        if reopened.returncode != 0:
            fail(f"approved brief could not reopen: {reopened.stderr}")
        changed = plan.read_text(encoding="utf-8").replace(
            "A user receives one observable result.",
            "A user receives a materially different result.",
        )
        plan.write_text(changed, encoding="utf-8")
        current = call(
            "approve", "--expect-token", state.token_for(changed),
            "--approval-reply", AUTONOMOUS_DIRECTIVE, *APPROVAL_CONTEXT,
        )
        if current.returncode != 0:
            fail(f"reapproval after reopen failed: {current.stderr}")


def path_safety_cases(state) -> None:
    source = state.template("lean-loop", "lean-loop-test").encode("utf-8")
    for kind in ("directory", "file"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            repo = root / "repo"
            outside = root / "outside"
            repo.mkdir()
            outside.mkdir()
            git_repo(repo)
            if kind == "directory":
                target = outside / "lean-loop"
                target.mkdir()
                plan = target / "PLAN.md"
                plan.write_bytes(source)
                (repo / "features").mkdir()
                (repo / "features/lean-loop").symlink_to(
                    target, target_is_directory=True
                )
                requested = repo / "features/lean-loop/PLAN.md"
            else:
                plan = outside / "PLAN.md"
                plan.write_bytes(source)
                requested = repo / "features/lean-loop/PLAN.md"
                requested.parent.mkdir(parents=True)
                requested.symlink_to(plan)
            before = plan.read_bytes()
            explicit = subprocess.run(
                [
                    sys.executable, str(STATE_PATH), "inspect",
                    "--repo", str(repo), "--plan", str(requested),
                ],
                check=False, capture_output=True, text=True,
            )
            if explicit.returncode == 0 or plan.read_bytes() != before:
                fail(f"explicit inspect followed {kind} symlink")
            discovered = subprocess.run(
                [sys.executable, str(STATE_PATH), "inspect", "--repo", str(repo)],
                check=False, capture_output=True, text=True,
            )
            if discovered.returncode == 0 or plan.read_bytes() != before:
                fail(f"repo-wide inspect followed {kind} symlink")
            if tuple(outside.rglob("PLAN.*.md")):
                fail(f"{kind} symlink rejection created an extra PLAN record")

            alias = root / "repo-alias"
            alias.symlink_to(repo, target_is_directory=True)
            try:
                state.safe_plan_path(repo, alias / "features/lean-loop/PLAN.md")
            except state.PlanError:
                pass
            else:
                fail("alias-to-repository path bypassed lexical containment")
            escaped = repo / "features" / ".." / ".." / "outside" / "PLAN.md"
            try:
                state.safe_plan_path(repo, escaped)
            except state.PlanError:
                pass
            else:
                fail("parent-segment PLAN path escaped repository containment")


def concurrent_stale_case(state) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        git_repo(repo)
        plan = repo / "features/lean-loop/PLAN.md"
        plan.parent.mkdir(parents=True)
        approved = filled(state.template("lean-loop", "lean-loop-test"))
        fingerprint = state.frozen_fingerprint(state.parse_sections(approved))
        approved = state.render_state(approved, {
            "lifecycle_status": "build-ready",
            "approval_status": "approved",
            "approval_fingerprint": fingerprint,
            "approval_provenance": "ready-to-build",
        })
        plan.write_text(approved, encoding="utf-8")
        authorize_fixture(state, repo, plan, fingerprint)
        token = state.token_for(approved)
        command = [
            sys.executable, str(STATE_PATH), "checkpoint",
            "--repo", str(repo), "--plan", str(plan), "--expect-token", token,
            "--set", "lifecycle_status=building",
        ]
        first = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        second = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        first.communicate(timeout=10)
        second.communicate(timeout=10)
        if sorted((first.returncode, second.returncode)) != [0, 4]:
            fail("serialized same-token commands did not produce one stale loser")
        state.validate_text(plan.read_text(encoding="utf-8"))
        if tuple(plan.parent.glob("PLAN.*.md")):
            fail("stale checkpoint loser created an extra PLAN record")


def unsupported_state_case() -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        git_repo(repo)
        plan = repo / "features/obsolete-record/PLAN.md"
        plan.parent.mkdir(parents=True)
        original = b"# Obsolete Feature Record\n\n## State\n- state_version = 4\n"
        plan.write_bytes(original)
        inspected = subprocess.run(
            [
                sys.executable, str(STATE_PATH), "inspect",
                "--repo", str(repo), "--plan", str(plan),
            ],
            check=False, capture_output=True, text=True,
        )
        if inspected.returncode == 0 or plan.read_bytes() != original:
            fail("unsupported state was accepted or mutated")
        if "requires exactly one v1 State block" not in inspected.stderr:
            fail("unsupported state did not fail through the canonical validator")
        if tuple(plan.parent.glob("PLAN.*.md")):
            fail("unsupported state created an extra PLAN record")


def terminal_and_green_cases(state) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        git_repo(repo)
        product = repo / "owner.txt"
        product.write_text("green", encoding="utf-8")
        os.chmod(product, 0o755)
        stable_link = repo / "stable-link"
        stable_link.symlink_to("owner.txt")
        subprocess.run(
            ["git", "-C", str(repo), "add", "owner.txt", "stable-link"], check=True
        )
        plan = repo / "features/lean-loop/PLAN.md"
        plan.parent.mkdir(parents=True)
        text = filled(state.template("lean-loop", "lean-loop-test"))
        fingerprint = state.frozen_fingerprint(state.parse_sections(text))
        building = state.render_state(text, {
            "lifecycle_status": "building",
            "approval_status": "approved",
            "approval_fingerprint": fingerprint,
            "approval_provenance": "ready-to-build",
        })
        plan.write_text(building, encoding="utf-8")
        authorize_fixture(state, repo, plan, fingerprint)
        jumped = subprocess.run(
            [
                sys.executable, str(STATE_PATH), "checkpoint",
                "--repo", str(repo), "--plan", str(plan),
                "--expect-token", state.token_for(building),
                "--set", "completed_slices=S-1,S-2",
                "--set", "active_slice=S-3",
            ],
            check=False, capture_output=True, text=True,
        )
        if jumped.returncode == 0 or plan.read_text(encoding="utf-8") != building:
            fail("checkpoint skipped unverified slice progress")
        unreceipted = subprocess.run(
            [
                sys.executable, str(STATE_PATH), "checkpoint",
                "--repo", str(repo), "--plan", str(plan),
                "--expect-token", state.token_for(building),
                "--set", "completed_slices=S-1",
                "--set", "active_slice=S-2",
                "--set", "next_action=Next behavior.",
            ],
            check=False, capture_output=True, text=True,
        )
        if unreceipted.returncode == 0 or "slice-gate receipt" not in unreceipted.stderr:
            fail("slice completion without a slice-gate receipt was accepted")
        gate_receipts(repo, ("S-1", "full"))
        green = subprocess.run(
            [
                sys.executable, str(STATE_PATH), "checkpoint",
                "--repo", str(repo), "--plan", str(plan),
                "--expect-token", state.token_for(building),
                "--set", "lifecycle_status=green",
                "--set", "active_slice=none",
                "--set", "completed_slices=S-1",
            ],
            check=False, capture_output=True, text=True,
        )
        if green.returncode != 0:
            fail(f"building to green failed: {green.stderr}")
        green_text = plan.read_text(encoding="utf-8")
        green_state = state.validate_text(green_text)
        if not state.FINGERPRINT.fullmatch(green_state["green_artifact"]):
            fail("green transition did not bind artifact")
        asserted = subprocess.run(
            [sys.executable, str(STATE_PATH), "assert-green", "--repo", str(repo), "--plan", str(plan)],
            check=False, capture_output=True, text=True,
        )
        if asserted.returncode != 0 or "completed_slices=S-1" not in asserted.stdout:
            fail("fresh green artifact did not assert complete slice progress")
        sessionless_environment = {
            key: value
            for key, value in os.environ.items()
            if key not in {"HARD_ENG_SESSION_ID", "HARD_ENG_REQUEST_DIGEST"}
        }
        sessionless = subprocess.run(
            [
                sys.executable, str(STATE_PATH), "assert-green",
                "--repo", str(repo), "--plan", str(plan), "--artifact-only",
            ],
            check=False, capture_output=True, text=True, env=sessionless_environment,
        )
        if sessionless.returncode != 0 or "completed_slices=S-1" not in sessionless.stdout:
            fail("session-free green artifact validation did not pass")
        unauthenticated = subprocess.run(
            [sys.executable, str(STATE_PATH), "assert-green", "--repo", str(repo), "--plan", str(plan)],
            check=False, capture_output=True, text=True, env=sessionless_environment,
        )
        if unauthenticated.returncode == 0 or "runtime session id" not in unauthenticated.stderr:
            fail("normal green assertion accepted a missing runtime identity")
        baseline = green_state["green_artifact"]
        if state.repository_artifact(repo) != baseline or state.repository_artifact(repo) != baseline:
            fail("unchanged artifact binding is unstable")
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=Test", "-c",
             "user.email=test@example.invalid", "commit", "-qm", "bind artifact"],
            check=True,
        )
        if state.repository_artifact(repo) != baseline:
            fail("commit changed unchanged working-tree artifact")
        added = repo / "added.txt"
        added.write_text("added", encoding="utf-8")
        if state.repository_artifact(repo) == baseline:
            fail("added file did not change artifact")
        added.unlink()
        link = repo / "owner-link"
        link.symlink_to("owner.txt")
        if state.repository_artifact(repo) == baseline:
            fail("symlink did not change artifact")
        link.unlink()
        product.unlink()
        deleted_artifact = state.repository_artifact(repo)
        if deleted_artifact == baseline:
            fail("deleted tracked file did not change artifact")
        subprocess.run(["git", "-C", str(repo), "add", "-u", "owner.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=Test", "-c",
             "user.email=test@example.invalid", "commit", "-qm", "delete artifact"],
            check=True,
        )
        if state.repository_artifact(repo) != deleted_artifact:
            fail("delete commit changed unchanged working-tree artifact")
        product.write_text("green", encoding="utf-8")
        os.chmod(product, 0o755)
        other = repo / "features/other/PLAN.md"
        other.parent.mkdir(parents=True)
        other.write_text("unrelated lifecycle metadata", encoding="utf-8")
        if state.repository_artifact(repo) != baseline:
            fail("unrelated Feature Brief created product artifact drift")
        product.write_text("drift", encoding="utf-8")
        drifted = subprocess.run(
            [sys.executable, str(STATE_PATH), "assert-green", "--repo", str(repo), "--plan", str(plan)],
            check=False, capture_output=True, text=True,
        )
        if drifted.returncode == 0:
            fail("artifact drift remained green")
        wrong_identity = subprocess.run(
            [
                sys.executable, str(STATE_PATH), "checkpoint",
                "--repo", str(repo), "--plan", str(plan),
                "--expect-token", state.token_for(green_text),
                "--session-id", "wrong-session",
                "--request-digest", "sha256:" + "d" * 64,
                "--set", "lifecycle_status=building",
            ],
            check=False, capture_output=True, text=True,
        )
        if wrong_identity.returncode == 0 or plan.read_text(encoding="utf-8") != green_text:
            fail("green drift recovery accepted a wrong session or changed the PLAN")
        back = subprocess.run(
            [
                sys.executable, str(STATE_PATH), "checkpoint",
                "--repo", str(repo), "--plan", str(plan),
                "--expect-token", state.token_for(green_text),
                "--set", "lifecycle_status=building",
            ],
            check=False, capture_output=True, text=True,
        )
        if back.returncode != 0:
            fail("green drift could not return to building")
        if state.parse_state(plan.read_text(encoding="utf-8"))["green_artifact"] != "none":
            fail("green artifact was not reset on return to building")

        product.write_text("green-again", encoding="utf-8")
        gate_receipts(repo, ("full",))
        state.refresh_execution_state(
            repo,
            plan,
            fingerprint,
            "he-plan-contract",
            "sha256:" + "d" * 64,
        )
        building_text = plan.read_text(encoding="utf-8")
        second_green = subprocess.run(
            [
                sys.executable, str(STATE_PATH), "checkpoint",
                "--repo", str(repo), "--plan", str(plan),
                "--expect-token", state.token_for(building_text),
                "--set", "lifecycle_status=green",
                "--set", "active_slice=none",
                "--set", "completed_slices=S-1",
            ],
            check=False, capture_output=True, text=True,
        )
        if second_green.returncode != 0:
            fail("second green transition failed")
        green_text = plan.read_text(encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(repo), "add", "owner.txt", "hard-eng.gates.json"],
            check=True,
        )
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "complete green"], check=True)
        state.refresh_execution_state(
            repo,
            plan,
            fingerprint,
            "he-plan-contract",
            "sha256:" + "d" * 64,
        )
        git_dir_result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--git-dir"],
            check=True, capture_output=True, text=True,
        )
        git_dir = Path(git_dir_result.stdout.strip())
        if not git_dir.is_absolute():
            git_dir = repo / git_dir
        direct_receipt = git_dir.resolve() / "hard-eng/current-direct.json"
        direct_receipt.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        direct_receipt.write_text("{}\n", encoding="utf-8")
        shipped = subprocess.run(
            [
                sys.executable, str(STATE_PATH), "checkpoint",
                "--repo", str(repo), "--plan", str(plan),
                "--expect-token", state.token_for(green_text),
                "--set", "lifecycle_status=shipped",
            ],
            check=False, capture_output=True, text=True,
        )
        if shipped.returncode != 0:
            fail("green to shipped failed")
        if direct_receipt.exists():
            fail("terminal transition did not invalidate the direct-route receipt")
        direct_receipt.write_text("{}\n", encoding="utf-8")
        synced = subprocess.run(
            [
                sys.executable, str(STATE_PATH), "sync-excludes",
                "--repo", str(repo), "--plan", str(plan),
            ],
            check=False, capture_output=True, text=True,
        )
        if synced.returncode != 0 or direct_receipt.exists():
            fail("terminal cleanup recovery did not invalidate the direct-route receipt")
        terminal = plan.read_bytes()
        terminal_token = "sha256:" + hashlib.sha256(terminal).hexdigest()
        for action in (
            ["checkpoint", "--set", "next_action=mutate"],
            ["reopen", "--reason", "changed-outcome"],
        ):
            rejected = subprocess.run(
                [
                    sys.executable, str(STATE_PATH), *action,
                    "--repo", str(repo), "--plan", str(plan),
                    "--expect-token", terminal_token,
                ],
                check=False, capture_output=True, text=True,
            )
            if rejected.returncode == 0 or plan.read_bytes() != terminal:
                fail("terminal v1 mutation was not rejected unchanged")

    invalid = state.render_state(
        filled(state.template("lean-loop", "lean-loop-test")),
        {
            "lifecycle_status": "green",
            "approval_status": "approved",
            "approval_fingerprint": "sha256:" + "a" * 64,
            "approval_provenance": "ready-to-build",
            "green_artifact": "sha256:" + "b" * 64,
        },
    )
    try:
        state.validate_text(invalid)
    except state.PlanError:
        pass
    else:
        fail("green state with active slice passed validation")
    skipped = state.render_state(invalid, {
        "lifecycle_status": "building",
        "green_artifact": "none",
        "active_slice": "S-3",
        "completed_slices": "S-1",
    })
    try:
        state.validate_text(skipped)
    except state.PlanError:
        pass
    else:
        fail("building state skipped a slice in active progress")


def main() -> int:
    state = load_state()
    brief = filled(state.template("lean-loop", "lean-loop-test"))
    parsed = state.validate_text(brief)
    if parsed["state_version"] != "1" or parsed["lifecycle_status"] != "planning":
        fail("fresh brief is not planning")

    fingerprint = state.frozen_fingerprint(state.parse_sections(brief))
    approved = state.render_state(brief, {
        "lifecycle_status": "build-ready",
        "approval_status": "approved",
        "approval_fingerprint": fingerprint,
        "approval_provenance": "ready-to-build",
        "next_action": "Build the first vertical slice.",
    })
    state.validate_text(approved)

    engineering_edit = approved.replace(
        "Existing command owner and route.",
        "Existing command owner, route, and focused test seam.",
    )
    state.validate_text(engineering_edit)

    cancelled = state.render_state(brief, {
        "lifecycle_status": "cancelled",
        "active_slice": "none",
        "next_action": "None.",
    })
    state.validate_text(cancelled)

    changed_outcome = approved.replace(
        "A user receives one observable result.",
        "A user receives a materially different result.",
    )
    try:
        state.validate_text(changed_outcome)
    except state.PlanError as error:
        if "restore them" not in str(error):
            fail(f"wrong frozen-change failure: {error}")
    else:
        fail("changed frozen constraint stayed approved")

    placeholder = state.template("lean-loop", "lean-loop-test")
    try:
        state.validate_text(
            state.render_state(placeholder, {
                "lifecycle_status": "build-ready",
                "approval_status": "approved",
                "approval_fingerprint": state.frozen_fingerprint(
                    state.parse_sections(placeholder)
                ),
                "approval_provenance": "ready-to-build",
            })
        )
    except state.PlanError as error:
        if "placeholders" not in str(error):
            fail(f"wrong placeholder failure: {error}")
    else:
        fail("placeholder brief received approval")

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        path = root / "features/lean-loop/PLAN.md"
        state.create_new(root, Path("features/lean-loop/PLAN.md"), approved.encode(), 0o644)
        if state.resolve_plan(Path(directory), None) != path.resolve():
            fail("active plan discovery failed")

    check_plan_lock(state, fail)
    check_ancestor_swap(fail)
    check_exchange_editor_save(fail)
    check_rollback_failure_recovery(fail)
    check_write_failure_cleanup(fail)
    check_init_preimage(fail)
    independent = (
        lambda: approval_reply_cases(state),
        lambda: ux_reference_cases(state),
        lambda: check_targets(state, git_repo, fail),
        lambda: check_linked_worktree(state, git_repo, fail),
        lambda: path_safety_cases(state),
        lambda: concurrent_stale_case(state),
        unsupported_state_case,
        lambda: terminal_and_green_cases(state),
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = tuple(pool.submit(case) for case in independent)
    for result in results:
        result.result()
    if "building" not in state.TRANSITIONS["green"] or state.ROUTES["building"] != "he-build":
        fail("green engineering drift cannot return to Implement Verify")

    print("he-plan-check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
