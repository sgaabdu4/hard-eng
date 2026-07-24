#!/usr/bin/env python3
"""Focused regression proof for the lean Feature Brief contract."""

from __future__ import annotations

import importlib.util
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from safe_plan_io_regression import (
    check_ancestor_swap,
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


def git_repo(path: Path) -> None:
    subprocess.run(
        ["git", "init", "-q", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )


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

    check_plan_lock(state, fail)
    check_ancestor_swap(fail)
    check_exchange_editor_save(fail)
    check_rollback_failure_recovery(fail)
    check_write_failure_cleanup(fail)
    check_gitlinks(fail)
    check_index_transition_stability(fail)
    check_init_preimage(fail)
    path_safety_cases(state)
    concurrent_stale_case(state)
    unsupported_state_case()
    terminal_and_green_cases(state)
    if "building" not in state.TRANSITIONS["green"] or state.ROUTES["building"] != "he-build":
        fail("green engineering drift cannot return to Implement Verify")

    skill = (ROOT / "skills/he-plan/SKILL.md").read_text(encoding="utf-8")
    router = (ROOT / "skills/he/SKILL.md").read_text(encoding="utf-8")
    reference = (
        ROOT / "skills/he-plan/references/feature-brief.md"
    ).read_text(encoding="utf-8")
    anchors = (
        (skill, "[feature-brief.md](references/feature-brief.md)"),
        (reference, "Ready to build this Feature Brief?"),
        (skill, "Unknown implementation owner/file/test"),
        (router, "Engineering-only discovery"),
        (router, "material security/privacy/data-loss/irreversible contract"),
        (reference, "Approval fingerprint = frozen content only."),
    )
    if any(anchor not in source for source, anchor in anchors):
        fail("skill/reference parity anchor missing")

    print("he-plan-check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
