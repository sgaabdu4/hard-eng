#!/usr/bin/env python3
"""Focused regression proof for the lean Feature Brief contract."""

from __future__ import annotations

import importlib.util
import hashlib
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from safe_plan_io_regression import (
    check_ancestor_swap,
    check_archive_cas_race,
    check_exchange_editor_save,
    check_gitlinks,
    check_index_transition_stability,
    check_init_preimage,
    check_plan_lock,
    check_rollback_failure_recovery,
    check_write_failure_cleanup,
)
ROOT = Path(__file__).resolve().parents[3]
STATE_PATH = ROOT / "skills/he/scripts/plan_state.py"


def fail(message: str) -> None:
    raise SystemExit(f"he-plan-check: {message}")


def load_state():
    specification = importlib.util.spec_from_file_location("lean_plan_state", STATE_PATH)
    if specification is None or specification.loader is None:
        fail("cannot load plan_state.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def filled(text: str) -> str:
    replacements = {
        "## Outcome\n- TBD": "## Outcome\n- A user receives one observable result.",
        "## Non-goals\n- TBD": "## Non-goals\n- Adjacent workflow changes are excluded.",
        "## Material decisions\n- TBD": "## Material decisions\n- Existing policy remains canonical.",
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


def legacy_v4(
    repo: Path, lifecycle: str, approved: bool, newline: str = "\n", final: bool = False
) -> bytes:
    stages = (
        "repository,research,feature,flows,ux,contracts,technical,testing,"
        "rollout,slices,consistency,approval"
    )
    axes = (
        "intent-spec:pass,deterministic:pass,tests:pass,review:pass,"
        "security:na,ui-design:na,e2e-runtime:na,docs-context:pass,unknowns:pass"
    )
    post_plan = lifecycle != "planning"
    building = lifecycle == "building"
    shipped = lifecycle == "shipped"
    state = {
        "state_version": "4",
        "plan_id": "generic-loop",
        "feature_slug": "generic-loop",
        "repository_root": "/missing/old/worktree",
        "branch": "old-branch",
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "updated_at_utc": "2026-01-01T00:00:00Z",
        "lifecycle_status": lifecycle,
        "current_stage": "ship" if shipped else ("build" if post_plan else "plan"),
        "plan_stage": "none" if post_plan else "feature",
        "approved_plan_stages": stages if post_plan else "repository,research",
        "skipped_plan_stages": "none",
        "stage_status": "complete" if shipped else ("pending" if lifecycle == "build-ready" else "in-progress"),
        "next_action": "Continue the preserved active slice.",
        "waiting_for": "agent",
        "plan_approved": "yes" if post_plan else "no",
        "approved_plan_digest": "sha256:" + "c" * 64 if post_plan else "none",
        "open_blockers": "none",
        "open_issues": "none",
        "open_unknowns": "none",
        "active_slice": "final" if final else ("S-2" if building else "none"),
        "slice_count": "2" if post_plan else "none",
        "completed_slices": "S-1,S-2" if shipped or final else ("S-1" if building else "none"),
        "build_round": "1" if building or shipped else "0",
        "snapshot_id": "sha256:" + "d" * 64 if building or shipped else "none",
        "artifact_id": "sha256:" + "e" * 64 if building or shipped else "none",
        "build_axes": axes if building or shipped else "none",
        "build_readiness": "100" if building or shipped else "none",
        "build_evidence": "current" if building or shipped else "none",
    }
    rows = "\n".join(f"- {key} = {value}" for key, value in state.items())
    text = (
        "# Generic loop\n\n## State\n"
        f"{rows}\n\n## Audit policy\n- risk_tier = critical\n\n"
        "## Feature\n- Preserve a generic accepted behavior.\n"
    )
    return text.replace("\n", newline).encode("utf-8")


def git_repo(path: Path) -> None:
    subprocess.run(
        ["git", "init", "-q", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )


def migration_case(
    state, lifecycle: str, approved: bool, newline: str, resume_archive: bool = False,
    final: bool = False,
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        git_repo(repo)
        plan = repo / "features/generic-loop/PLAN.md"
        plan.parent.mkdir(parents=True)
        original = legacy_v4(repo, lifecycle, approved, newline, final)
        plan.write_bytes(original)
        os.chmod(plan, 0o640)
        digest = "sha256:" + hashlib.sha256(original).hexdigest()
        archive = plan.with_name(
            f"PLAN.legacy-v4.{digest.removeprefix('sha256:')}.md"
        )

        stale = subprocess.run(
            [
                sys.executable, str(STATE_PATH), "migrate-v4",
                "--repo", str(repo), "--plan", str(plan),
                "--expect-token", "sha256:" + "0" * 64,
            ],
            check=False, capture_output=True, text=True,
        )
        if stale.returncode == 0 or plan.read_bytes() != original or archive.exists():
            fail("stale v4 migration mutated state")
        if resume_archive:
            archive.write_bytes(original)
            os.chmod(archive, 0o640)

        migrated = subprocess.run(
            [
                sys.executable, str(STATE_PATH), "migrate-v4",
                "--repo", str(repo), "--plan", str(plan), "--expect-token", digest,
            ],
            check=False, capture_output=True, text=True,
        )
        if migrated.returncode != 0:
            fail(f"v4 migration failed: {migrated.stderr}")
        output = dict(
            line.split("=", 1) for line in migrated.stdout.splitlines() if "=" in line
        )
        required_output = {
            "result", "plan", "old_hash", "new_hash", "archive", "archive_hash",
            "token", "lifecycle_status", "approval_status", "route_target",
            "active_slice", "completed_slices", "approval_provenance", "next_action",
        }
        if set(output) != required_output:
            fail(f"v4 migration output fields mismatch: {sorted(set(output) ^ required_output)}")
        expected_completed = "S-1,S-2" if final else ("S-1" if lifecycle == "building" else "none")
        if output["completed_slices"] != expected_completed:
            fail("v4 migration output lost completed slices")
        expected_provenance = (
            f"legacy-v4:{digest}" if approved else "none"
        )
        if output["approval_provenance"] != expected_provenance:
            fail("v4 migration output lost approval provenance")
        if archive.read_bytes() != original:
            fail("v4 archive is not byte-exact")
        if stat.S_IMODE(archive.stat().st_mode) != 0o640:
            fail("v4 archive did not preserve mode")
        resulting = state.validate_text(plan.read_text(encoding="utf-8"))
        expected = lifecycle if approved else "planning"
        if resulting["lifecycle_status"] != expected:
            fail("v4 lifecycle mapping changed state")
        expected_active = "none" if final else ("S-2" if lifecycle == "building" else "none")
        if resulting["active_slice"] != expected_active:
            fail("v4 active slice was not preserved")
        if resulting["next_action"] != "Continue the preserved active slice.":
            fail("v4 next action was not preserved")
        migrated_text = plan.read_text(encoding="utf-8")
        provenance_label = (
            "accepted legacy v4 document"
            if approved else "unapproved legacy v4 planning document"
        )
        if provenance_label not in migrated_text:
            fail("v4 migration mislabeled approval provenance in readable evidence")
        expected_slice = "final" if final else "S-2" if lifecycle == "building" else "S-1"
        if state.parse_sections(migrated_text)["First vertical slice"].splitlines()[0] != f"- {expected_slice} = continue the active legacy vertical slice.": fail("v4 migration generated the wrong continuation slice")

        after_plan = plan.read_bytes()
        after_archive = archive.read_bytes()
        second = subprocess.run(
            [
                sys.executable, str(STATE_PATH), "migrate-v4",
                "--repo", str(repo), "--plan", str(plan),
                "--expect-token", "sha256:" + hashlib.sha256(after_plan).hexdigest(),
            ],
            check=False, capture_output=True, text=True,
        )
        if (
            second.returncode == 0
            or plan.read_bytes() != after_plan
            or archive.read_bytes() != after_archive
        ):
            fail("second v4 migration did not fail unchanged")


def malformed_migration_case() -> None:
    mutations = (
        (b"- build_evidence = none\n", b""),
        (b"- base_sha = " + b"a" * 40, b"- base_sha = bad"),
        (b"- updated_at_utc = 2026-01-01T00:00:00Z", b"- updated_at_utc = yesterday"),
        (b"- approved_plan_stages = repository,research", b"- approved_plan_stages = research,repository"),
        (b"- open_issues = none", b"- open_issues = bad"),
        (b"- slice_count = none", b"- slice_count = 0"),
        (b"- current_stage = plan", b"- current_stage = build"),
        (b"- waiting_for = agent", b"- waiting_for = "),
    )
    for old, new in mutations:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            git_repo(repo)
            plan = repo / "features/generic-loop/PLAN.md"
            plan.parent.mkdir(parents=True)
            malformed = legacy_v4(repo, "planning", False).replace(old, new)
            plan.write_bytes(malformed)
            digest = "sha256:" + hashlib.sha256(malformed).hexdigest()
            result = subprocess.run(
                [
                    sys.executable, str(STATE_PATH), "migrate-v4",
                    "--repo", str(repo), "--plan", str(plan), "--expect-token", digest,
                ],
                check=False, capture_output=True, text=True,
            )
            if result.returncode == 0 or plan.read_bytes() != malformed:
                fail("malformed v4 migration did not fail unchanged")
            if list(plan.parent.glob("PLAN.legacy-v4.*.md")):
                fail("malformed v4 migration created an archive")
    for old, new in (
        (b"- build_readiness = 100", b"- build_readiness = 50"),
        (b"- active_slice = S-2", b"- active_slice = S-3"),
        (b"review:pass", b"review:unknown"),
    ):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            git_repo(repo)
            plan = repo / "features/generic-loop/PLAN.md"
            plan.parent.mkdir(parents=True)
            malformed = legacy_v4(repo, "building", True).replace(old, new)
            plan.write_bytes(malformed)
            digest = "sha256:" + hashlib.sha256(malformed).hexdigest()
            result = subprocess.run(
                [
                    sys.executable, str(STATE_PATH), "migrate-v4",
                    "--repo", str(repo), "--plan", str(plan), "--expect-token", digest,
                ],
                check=False, capture_output=True, text=True,
            )
            if result.returncode == 0 or plan.read_bytes() != malformed:
                fail("malformed building v4 migrated")
            if list(plan.parent.glob("PLAN.legacy-v4.*.md")):
                fail("malformed building v4 created archive")


def symlink_migration_cases() -> None:
    for kind in ("directory", "file"):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve() / "repo"
            outside = Path(directory).resolve() / "outside"
            repo.mkdir()
            outside.mkdir()
            git_repo(repo)
            source = legacy_v4(repo, "planning", False)
            if kind == "directory":
                target = outside / "generic-loop"
                target.mkdir()
                plan = target / "PLAN.md"
                plan.write_bytes(source)
                (repo / "features").mkdir()
                (repo / "features/generic-loop").symlink_to(target, target_is_directory=True)
                requested = repo / "features/generic-loop/PLAN.md"
            else:
                plan = outside / "PLAN.md"
                plan.write_bytes(source)
                requested = repo / "features/generic-loop/PLAN.md"
                requested.parent.mkdir(parents=True)
                requested.symlink_to(plan)
            before = plan.read_bytes()
            digest = "sha256:" + hashlib.sha256(before).hexdigest()
            result = subprocess.run(
                [
                    sys.executable, str(STATE_PATH), "migrate-v4",
                    "--repo", str(repo), "--plan", str(requested),
                    "--expect-token", digest,
                ],
                check=False, capture_output=True, text=True,
            )
            if result.returncode == 0 or plan.read_bytes() != before:
                fail(f"{kind} symlink migration mutated target")
            if tuple(outside.rglob("PLAN.legacy-v4.*.md")):
                fail(f"{kind} symlink migration created archive")
            inspected = subprocess.run(
                [sys.executable, str(STATE_PATH), "inspect", "--repo", str(repo)],
                check=False, capture_output=True, text=True,
            )
            if inspected.returncode == 0 or plan.read_bytes() != before:
                fail(f"repo-wide inspect followed {kind} symlink")
            alias = Path(directory).resolve() / "repo-alias"
            alias.symlink_to(repo, target_is_directory=True)
            try:
                state_path = load_state()
                state_path.safe_plan_path(repo, alias / "features/generic-loop/PLAN.md")
            except state_path.PlanError:
                pass
            else:
                fail("alias-to-repository path bypassed lexical containment")
            escaped = repo / "features" / ".." / ".." / "outside" / "PLAN.md"
            try:
                state_path.safe_plan_path(repo, escaped)
            except state_path.PlanError:
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
        if tuple(plan.parent.glob("PLAN.legacy-v4.*.md")):
            fail("stale checkpoint loser created migration archive")


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
        subprocess.run(["git", "-C", str(repo), "add", "owner.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "complete green"], check=True)
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

    migration_case(state, "planning", False, "\r\n", resume_archive=True)
    migration_case(state, "build-ready", True, "\n")
    migration_case(state, "building", True, "\n")
    migration_case(state, "building", True, "\n", final=True)
    check_plan_lock(state, fail)
    malformed_migration_case()
    symlink_migration_cases()
    check_ancestor_swap(fail)
    check_exchange_editor_save(fail)
    check_rollback_failure_recovery(fail)
    check_archive_cas_race(fail)
    check_write_failure_cleanup(fail)
    check_gitlinks(fail)
    check_index_transition_stability(fail)
    check_init_preimage(fail)
    concurrent_stale_case(state)
    terminal_and_green_cases(state)
    if "building" not in state.TRANSITIONS["green"] or state.ROUTES["building"] != "he-build":
        fail("green engineering drift cannot return to Implement Verify")

    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        git_repo(repo)
        terminal = repo / "features/generic-loop/PLAN.md"
        terminal.parent.mkdir(parents=True)
        terminal.write_bytes(legacy_v4(repo, "shipped", True))
        before = terminal.read_bytes()
        inspected = subprocess.run(
            [sys.executable, str(STATE_PATH), "inspect", "--repo", str(repo)],
            check=False, capture_output=True, text=True,
        )
        if inspected.returncode != 2 or terminal.read_bytes() != before:
            fail("terminal v4 was not ignored unchanged by active discovery")

    skill = (ROOT / "skills/he-plan/SKILL.md").read_text(encoding="utf-8")
    router = (ROOT / "skills/he/SKILL.md").read_text(encoding="utf-8")
    reference = (
        ROOT / "skills/he-plan/references/feature-brief.md"
    ).read_text(encoding="utf-8")
    legacy_reference = (
        ROOT / "skills/he/references/legacy-v4.md"
    ).read_text(encoding="utf-8")
    anchors = (
        (skill, "[feature-brief.md](references/feature-brief.md)"),
        (reference, "Ready to build this Feature Brief?"),
        (skill, "Unknown implementation owner/file/test"),
        (router, "Engineering-only discovery"),
        (router, "material security/privacy/data-loss/irreversible contract"),
        (router, "[legacy-v4.md](references/legacy-v4.md)"),
        (reference, "Approval fingerprint = frozen content only."),
        (legacy_reference, "build-ready/building approved"),
    )
    if any(anchor not in source for source, anchor in anchors):
        fail("skill/reference parity anchor missing")

    print("he-plan-check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
