#!/usr/bin/env python3
"""Regression proof: slice-gate receipts deterministically gate lifecycle checkpoints."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STATE_PATH = ROOT / "skills/he/scripts/plan_state.py"
GATE_PATH = ROOT / "skills/deterministic-checks/scripts/slice_gate.py"
JS_CHECKS = (
    "typecheck=echo tsc-proof",
    "lint=echo eslint-proof",
    "tests=echo vitest-proof",
    "fallow=echo fallow audit-proof",
)
REACT_CHECKS = (*JS_CHECKS, "react-doctor=echo react-doctor-proof")
DART_CHECKS = (
    "dart-analyze=echo dart analyze-proof",
    "dart-test=echo dart test-proof",
    "dart-decimate=echo dart_decimate_gate.py-proof",
)
EVIDENCE = (
    "--behavior", "one demonstrated observable behavior",
    "--security", "not-applicable:fixture slice",
    "--review", "actual diff reviewed in fixture",
)


def fail(message: str) -> None:
    raise SystemExit(f"slice-gate-check: {message}")


def load_state():
    specification = importlib.util.spec_from_file_location("gate_plan_state", STATE_PATH)
    if specification is None or specification.loader is None:
        fail("cannot load plan_state.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def filled(state, slug: str, plan_id: str) -> str:
    text = state.template(slug, plan_id)
    for old, new in {
        "## Outcome\n- TBD": "## Outcome\n- A user receives one observable result.",
        "## Non-goals\n- TBD": "## Non-goals\n- Adjacent workflow changes are excluded.",
        "## Material decisions\n- TBD": "## Material decisions\n- Existing policy remains canonical.",
        "- ux_reference = TBD": "- ux_reference = n/a",
        "## Acceptance examples\n- TBD": (
            "## Acceptance examples\n- Given a user, when they act, then the result is visible."
        ),
        "## Affected canonical areas\n- TBD": (
            "## Affected canonical areas\n- Existing command owner and route."
        ),
        "- rollback = TBD": "- rollback = disable the route.",
        "## First vertical slice\n- S-1 = TBD\n- proof = TBD": (
            "## First vertical slice\n- S-1 = one behavior.\n- proof = focused test."
        ),
    }.items():
        text = text.replace(old, new)
    return text


def e2e_fixture(root: Path) -> Path | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        return None
    e2e_scripts = str(ROOT / "skills/e2e/scripts")
    if e2e_scripts not in sys.path:
        sys.path.insert(0, e2e_scripts)
    from visual_evidence import probe_media
    from visual_evidence_regression_check import base_receipt
    media = root / "proof.mp4"
    generated = subprocess.run(
        [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=size=64x48:duration=1",
         "-pix_fmt", "yuv420p", str(media)],
        check=False, capture_output=True, timeout=60,
    )
    if generated.returncode != 0:
        return None
    metadata = probe_media(media, "video")
    receipt = base_receipt(media)
    artifact = receipt["evidence"]["visual"]["artifacts"][0]
    artifact["duration_seconds"] = metadata["duration_seconds"]
    artifact["dimensions"] = {"width": 64, "height": 48}
    review = receipt["evidence"]["visual"]["review"]["artifacts"][0]
    review["required_steps"][0]["timestamp_seconds"] = 0.2
    review["required_steps"][1]["timestamp_seconds"] = 0.8
    review["timeline"]["final"]["timestamp_seconds"] = metadata["duration_seconds"]
    review["timeline"]["samples"] = [
        {"timestamp_seconds": 0.0, "observed": "initial state"},
        {"timestamp_seconds": metadata["duration_seconds"], "observed": "final state"},
    ]
    path = root / "e2e-receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return path


def make_repo(root: Path, state, *, react: bool = False, dart: bool = False,
              critical: bool = False, ux: str = "n/a", slug: str = "portal",
              state_changes: dict[str, str] | None = None) -> Path:
    repo = root / f"fixture-{slug}"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    (repo / "app").mkdir()
    (repo / "owner.txt").write_text("owner\n", encoding="utf-8")
    if react:
        (repo / "package.json").write_text(
            '{"dependencies":{"react":"19.0.0","next":"15.0.0"}}\n', encoding="utf-8"
        )
        (repo / "app/page.tsx").write_text("export const x = () => 1\n", encoding="utf-8")
    if dart:
        (repo / "app/logic.dart").write_text("main() {}\n", encoding="utf-8")
    text = filled(state, slug, f"{slug}-test")
    if ux != "n/a":
        (repo / "assets").mkdir()
        (repo / "assets/mock.png").write_bytes(b"\x89PNG mock")
        text = text.replace("- ux_reference = n/a", f"- ux_reference = {ux}")
    if critical:
        text = text.replace("- risk_level = standard", "- risk_level = critical")
        text = text.replace(
            "- critical_overlay = none",
            "- critical_overlay = S-1 protected boundary + negative proof",
        )
    changes = {
        "lifecycle_status": "building",
        "approval_status": "approved",
        "approval_fingerprint": state.frozen_fingerprint(state.parse_sections(text)),
        "approval_provenance": "ready-to-build",
    }
    changes.update(state_changes or {})
    plan = repo / f"features/{slug}/PLAN.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(state.render_state(text, changes), encoding="utf-8")
    return repo


def plan_path(repo: Path) -> Path:
    return next((repo / "features").glob("*/PLAN.md"))


def checkpoint(state, repo: Path, *sets: str) -> subprocess.CompletedProcess[str]:
    plan = plan_path(repo)
    token = state.token_for(plan.read_text(encoding="utf-8"))
    command = [
        sys.executable, str(STATE_PATH), "checkpoint",
        "--repo", str(repo), "--plan", str(plan), "--expect-token", token,
    ]
    for assignment in sets:
        command += ["--set", assignment]
    return subprocess.run(command, check=False, capture_output=True, text=True)


def gate(repo: Path, scope: tuple[str, ...], checks: tuple[str, ...],
         *extra: str) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable, str(GATE_PATH), "run",
        "--repo", str(repo), "--plan", str(plan_path(repo)),
        *scope, "--timeout", "120", *EVIDENCE,
        "--e2e", "not-applicable:fixture slice",
    ]
    for check in checks:
        command += ["--check", check]
    command += extra
    return subprocess.run(command, check=False, capture_output=True, text=True)


def inspect(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(STATE_PATH), "inspect", "--repo", str(repo),
         "--plan", str(plan_path(repo))],
        check=False, capture_output=True, text=True,
    )


def receipt_of(repo: Path, name: str) -> Path:
    return plan_path(repo).parent / "receipts" / f"{name}.json"


def mixed_and_runner_cases(state, root: Path) -> None:
    repo = make_repo(root, state, react=True, dart=True, slug="mixed")
    completed = checkpoint(
        state, repo, "completed_slices=S-1", "active_slice=none",
        "next_action=Run the full pre-ship gate.",
    )
    if completed.returncode == 0 or "slice-gate receipt" not in completed.stderr:
        fail("mixed slice completed without any receipt")
    only_tests = gate(repo, ("--slice", "S-1"), ("tests=echo vitest-proof",))
    if only_tests.returncode == 0 or "missing required check families" not in only_tests.stderr:
        fail("targeted tests alone satisfied a mixed React+Dart slice")
    no_fallow = gate(
        repo, ("--slice", "S-1"),
        tuple(check for check in (*REACT_CHECKS, *DART_CHECKS) if not check.startswith("fallow")),
    )
    if no_fallow.returncode == 0 or "fallow" not in no_fallow.stderr:
        fail("missing Fallow was accepted for a JS slice")
    no_doctor = gate(repo, ("--slice", "S-1"), (*JS_CHECKS, *DART_CHECKS))
    if no_doctor.returncode == 0 or "react-doctor" not in no_doctor.stderr:
        fail("missing React Doctor was accepted for a React slice")
    no_decimate = gate(
        repo, ("--slice", "S-1"),
        (*REACT_CHECKS, *(check for check in DART_CHECKS if "decimate" not in check)),
    )
    if no_decimate.returncode == 0 or "dart-decimate" not in no_decimate.stderr:
        fail("missing Dart Decimate was accepted for a Dart slice")
    failing = gate(
        repo, ("--slice", "S-1"),
        (*REACT_CHECKS[:-1], "react-doctor=false # react-doctor", *DART_CHECKS),
    )
    if failing.returncode == 0 or receipt_of(repo, "S-1").exists():
        fail("failing check produced a receipt")
    mislabeled = gate(
        repo, ("--slice", "S-1"),
        (*REACT_CHECKS[:-1], "react-doctor=echo eslint-proof", *DART_CHECKS),
    )
    if mislabeled.returncode == 0 or "does not look like" not in mislabeled.stderr:
        fail("mislabeled family command was accepted")
    full_set = gate(repo, ("--slice", "S-1"), (*REACT_CHECKS, *DART_CHECKS))
    if full_set.returncode != 0:
        fail(f"complete mixed check set failed: {full_set.stderr}")
    completed = checkpoint(
        state, repo, "completed_slices=S-1", "active_slice=S-2",
        "next_action=Demonstrate the next behavior.",
    )
    if completed.returncode != 0:
        fail(f"receipted mixed completion failed: {completed.stderr}")
    if receipt_of(repo, "full").exists():
        fail("slice receipt run produced an unexpected full receipt")


def pure_react_cases(state, root: Path) -> None:
    repo = make_repo(root, state, react=True, slug="reactonly")
    result = gate(repo, ("--slice", "S-1"), REACT_CHECKS)
    if result.returncode != 0:
        fail(f"pure React slice demanded more than JS+React rows: {result.stderr}")
    payload = json.loads(receipt_of(repo, "S-1").read_text(encoding="utf-8"))
    if any(family.startswith("dart") for family in payload["applicable"]):
        fail("pure React slice derived Dart families")
    stale_edit = repo / "app/page.tsx"
    stale_edit.write_text("export const x = () => 2\n", encoding="utf-8")
    completed = checkpoint(
        state, repo, "completed_slices=S-1", "active_slice=S-2",
        "next_action=Demonstrate the next behavior.",
    )
    if completed.returncode == 0 or "stale receipt" not in completed.stderr:
        fail("post-receipt edit did not stale the slice receipt")
    result = gate(repo, ("--slice", "S-1"), REACT_CHECKS)
    completed = checkpoint(
        state, repo, "completed_slices=S-1", "active_slice=S-2",
        "next_action=Demonstrate the next behavior.",
    )
    if result.returncode != 0 or completed.returncode != 0:
        fail("rerun slice gate on final tree did not restore completion")


def identity_cases(state, root: Path) -> None:
    repo = make_repo(root, state, slug="identity")
    result = gate(repo, ("--slice", "S-1"), ("targeted=echo targeted-proof",))
    if result.returncode != 0:
        fail(f"plain targeted slice gate failed: {result.stderr}")
    receipt = receipt_of(repo, "S-1")
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    tampered = dict(payload)
    tampered["plan_id"] = "another-plan"
    receipt.write_text(json.dumps(tampered, indent=1, sort_keys=True), encoding="utf-8")
    completed = checkpoint(
        state, repo, "completed_slices=S-1", "active_slice=S-2",
        "next_action=Demonstrate the next behavior.",
    )
    if completed.returncode == 0 or "integrity" not in completed.stderr:
        fail("tampered receipt bytes were accepted")
    wrong_slice = receipt_of(repo, "S-2")
    wrong_slice.parent.mkdir(exist_ok=True)
    receipt.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    wrong_slice.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    other = make_repo(root, state, slug="identityb")
    foreign = receipt_of(other, "S-1")
    foreign.parent.mkdir(exist_ok=True)
    foreign.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    stolen = checkpoint(
        state, other, "completed_slices=S-1", "active_slice=S-2",
        "next_action=Demonstrate the next behavior.",
    )
    if stolen.returncode == 0 or "another plan" not in stolen.stderr:
        fail("receipt from another plan/repository was accepted")
    completed = checkpoint(
        state, repo, "completed_slices=S-1", "active_slice=S-2",
        "next_action=Demonstrate the next behavior.",
    )
    if completed.returncode != 0:
        fail(f"restored receipt failed: {completed.stderr}")
    reused = checkpoint(
        state, repo, "completed_slices=S-1,S-2", "active_slice=S-3",
        "next_action=Demonstrate the next behavior.",
    )
    if reused.returncode == 0 or "receipt identity does not match S-2" not in reused.stderr:
        fail("S-1 receipt bytes were accepted as S-2 completion proof")


def resume_and_full_gate_cases(state, root: Path) -> None:
    repo = make_repo(root, state, slug="resume")
    debt = inspect(repo)
    if "slice_receipt=missing" not in debt.stdout:
        fail("resume inspect did not expose missing slice proof")
    result = gate(repo, ("--slice", "S-1"), ("targeted=echo targeted-proof",))
    if result.returncode != 0:
        fail(f"resume fixture gate failed: {result.stderr}")
    debt = inspect(repo)
    if "slice_receipt=current" not in debt.stdout:
        fail("resume inspect did not expose satisfied slice proof")
    completed = checkpoint(
        state, repo, "completed_slices=S-1", "active_slice=none",
        "next_action=Run the full pre-ship gate.",
    )
    if completed.returncode != 0:
        fail(f"final slice completion failed: {completed.stderr}")
    debt = inspect(repo)
    if "full_receipt=missing" not in debt.stdout:
        fail("resume inspect did not expose owed full-gate proof")
    green = checkpoint(
        state, repo, "lifecycle_status=green", "next_action=Request delivery approval.",
    )
    if green.returncode == 0 or "full pre-ship gate" not in green.stderr:
        fail("green transition succeeded without a full receipt")
    result = gate(repo, ("--full",), ("targeted=echo targeted-proof",))
    if result.returncode != 0:
        fail(f"full gate run failed: {result.stderr}")
    green = checkpoint(
        state, repo, "lifecycle_status=green", "next_action=Request delivery approval.",
    )
    if green.returncode != 0:
        fail(f"green transition with full receipt failed: {green.stderr}")
    (repo / "owner.txt").write_text("drift\n", encoding="utf-8")
    asserted = subprocess.run(
        [sys.executable, str(STATE_PATH), "assert-green", "--repo", str(repo),
         "--plan", str(plan_path(repo))],
        check=False, capture_output=True, text=True,
    )
    if asserted.returncode == 0:
        fail("green proof survived a snapshot change")


def compatibility_and_terminal_cases(state, root: Path) -> None:
    legacy = make_repo(
        root, state, slug="legacy",
        state_changes={"completed_slices": "S-1", "active_slice": "S-2"},
    )
    if inspect(legacy).returncode != 0:
        fail("existing active plan with receiptless history became invalid")
    result = gate(legacy, ("--slice", "S-2"), ("targeted=echo targeted-proof",))
    completed = checkpoint(
        state, legacy, "completed_slices=S-1,S-2", "active_slice=S-3",
        "next_action=Demonstrate the next behavior.",
    )
    if result.returncode != 0 or completed.returncode != 0:
        fail(f"existing active plan could not continue: {completed.stderr}")
    terminal = make_repo(
        root, state, slug="terminal",
        state_changes={
            "lifecycle_status": "cancelled", "active_slice": "none",
            "next_action": "None.",
        },
    )
    plan = plan_path(terminal)
    before = plan.read_bytes()
    mutated = checkpoint(state, terminal, "next_action=mutate")
    if mutated.returncode == 0 or plan.read_bytes() != before:
        fail("terminal plan was mutated")


def evidence_hardening_cases(state, root: Path) -> None:
    repo = make_repo(root, state, critical=True, slug="critical")
    joined = gate(
        repo, ("--slice", "S-1"), ("targeted=echo targeted-proof",),
        "--behavior", "role/schema foundation + submission/reply + admin queue",
        "--security", "RBAC boundary reviewed with negative cases",
    )
    if joined.returncode == 0 or "one observable behavior" not in joined.stderr:
        fail("multi-behavior slice declaration was accepted")
    waived = gate(repo, ("--slice", "S-1"), ("targeted=echo targeted-proof",))
    if waived.returncode == 0 or "critical overlay" not in waived.stderr:
        fail("critical overlay slice accepted not-applicable security evidence")
    reviewed = gate(
        repo, ("--slice", "S-1"), ("targeted=echo targeted-proof",),
        "--security", "RBAC boundary reviewed with negative cases",
    )
    if reviewed.returncode != 0:
        fail(f"critical slice with review summary failed: {reviewed.stderr}")

    escalated = make_repo(root, state, slug="escalated")
    result = gate(escalated, ("--slice", "S-1"), ("targeted=echo targeted-proof",))
    if result.returncode != 0:
        fail(f"standard slice gate failed: {result.stderr}")
    plan = plan_path(escalated)
    text = plan.read_text(encoding="utf-8")
    text = text.replace("- risk_level = standard", "- risk_level = critical")
    text = text.replace(
        "- critical_overlay = none",
        "- critical_overlay = S-1 protected boundary + negative proof",
    )
    text = state.render_state(text, {
        "approval_fingerprint": state.frozen_fingerprint(state.parse_sections(text)),
    })
    plan.write_text(text, encoding="utf-8")
    completed = checkpoint(
        state, escalated, "completed_slices=S-1", "active_slice=S-2",
        "next_action=Demonstrate the next behavior.",
    )
    if completed.returncode == 0 or "critical overlay" not in completed.stderr:
        fail("escalated-to-critical plan accepted a security-waived receipt")

    garbage = make_repo(root, state, slug="garbage")
    bad = garbage / "bad-e2e.json"
    bad.write_text("{}", encoding="utf-8")
    invalid = gate(
        garbage, ("--slice", "S-1"), ("targeted=echo targeted-proof",),
        "--e2e", str(bad),
    )
    if invalid.returncode == 0 or "canonical e2e receipt" not in invalid.stderr:
        fail("non-canonical e2e receipt was accepted")

    surface = make_repo(root, state, react=True, ux="assets/mock.png", slug="surface")
    waived_media = gate(surface, ("--slice", "S-1"), REACT_CHECKS)
    if waived_media.returncode == 0 or "actual-media" not in waived_media.stderr:
        fail("UI slice with ux_reference accepted --e2e not-applicable")
    plain_ux = make_repo(root, state, ux="assets/mock.png", slug="plainux")
    non_ui = gate(plain_ux, ("--slice", "S-1"), ("targeted=echo targeted-proof",))
    if non_ui.returncode != 0:
        fail(f"non-UI slice under ux_reference demanded media proof: {non_ui.stderr}")

    e2e_receipt = e2e_fixture(root)
    if e2e_receipt is None:
        print("slice-gate-check: e2e PASS-path skipped (ffmpeg unavailable)")
        return
    proven_surface = gate(
        surface, ("--slice", "S-1"), REACT_CHECKS, "--e2e", str(e2e_receipt),
    )
    if proven_surface.returncode != 0:
        fail(f"UI slice with actual-media receipt failed: {proven_surface.stderr}")
    completed = checkpoint(
        state, surface, "completed_slices=S-1", "active_slice=S-2",
        "next_action=Obtain user look-and-feel acceptance for the surface media.",
    )
    if completed.returncode != 0:
        fail(f"media-proven UI slice completion failed: {completed.stderr}")
    bound = make_repo(root, state, slug="bound")
    result = gate(
        bound, ("--slice", "S-1"), ("targeted=echo targeted-proof",),
        "--e2e", str(e2e_receipt),
    )
    if result.returncode != 0:
        fail(f"canonical e2e receipt was rejected: {result.stderr}")
    original = e2e_receipt.read_text(encoding="utf-8")
    e2e_receipt.write_text(original + "\n", encoding="utf-8")
    completed = checkpoint(
        state, bound, "completed_slices=S-1", "active_slice=S-2",
        "next_action=Demonstrate the next behavior.",
    )
    if completed.returncode == 0 or "e2e receipt changed" not in completed.stderr:
        fail("mutated e2e receipt did not stale the slice receipt")
    e2e_receipt.write_text(original, encoding="utf-8")
    completed = checkpoint(
        state, bound, "completed_slices=S-1", "active_slice=S-2",
        "next_action=Demonstrate the next behavior.",
    )
    if completed.returncode != 0:
        fail(f"restored e2e receipt failed: {completed.stderr}")


def transcript_shaped_cases(state, root: Path) -> None:
    codex = make_repo(root, state, react=True, slug="oversized")
    for index in range(6):
        (codex / f"app/area{index}.tsx").write_text(
            f"export const area{index} = () => {index}\n", encoding="utf-8"
        )
    premature = checkpoint(
        state, codex, "completed_slices=S-1", "active_slice=none",
        "next_action=Obtain exact approval for production launch.",
    )
    if premature.returncode == 0 or "slice-gate receipt" not in premature.stderr:
        fail("oversized Codex-shaped S-1 completed without proof")
    tests_only = gate(codex, ("--slice", "S-1"), ("tests=echo vitest-proof",))
    if tests_only.returncode == 0:
        fail("oversized S-1 passed the gate with targeted tests only")
    covered = gate(codex, ("--slice", "S-1"), REACT_CHECKS)
    completed = checkpoint(
        state, codex, "completed_slices=S-1", "active_slice=none",
        "next_action=Run the full pre-ship gate.",
    )
    if covered.returncode != 0 or completed.returncode != 0:
        fail(f"fully proven completion failed: {completed.stderr}")

    claude = make_repo(root, state, react=True, slug="iterations")
    media_root = root / "iterations-media"
    media_root.mkdir()
    e2e_receipt = e2e_fixture(media_root)
    media_proof = (
        ("--e2e", str(e2e_receipt)) if e2e_receipt is not None
        else ("--e2e", "not-applicable:ffmpeg unavailable in fixture")
    )
    for index, slice_id in enumerate(("S-1", "S-2", "S-3")):
        (claude / "app/page.tsx").write_text(
            f"export const x = () => {index}\n", encoding="utf-8"
        )
        blocked = checkpoint(
            state, claude, f"completed_slices={','.join(f'S-{n}' for n in range(1, index + 2))}",
            f"active_slice=S-{index + 2}", "next_action=Demonstrate the next behavior.",
        )
        if blocked.returncode == 0:
            fail(f"iteration {slice_id} completed before its checks + media proof")
        result = gate(claude, ("--slice", slice_id), REACT_CHECKS, *media_proof)
        if result.returncode != 0:
            fail(f"iteration {slice_id} gate failed: {result.stderr}")
        advanced = checkpoint(
            state, claude, f"completed_slices={','.join(f'S-{n}' for n in range(1, index + 2))}",
            f"active_slice=S-{index + 2}", "next_action=Demonstrate the next behavior.",
        )
        if advanced.returncode != 0:
            fail(f"iteration {slice_id} completion failed: {advanced.stderr}")
    missing_media = gate(claude, ("--slice", "S-4"), REACT_CHECKS, "--e2e", "absent.png")
    if missing_media.returncode == 0 or "does not exist" not in missing_media.stderr:
        fail("missing E2E media receipt was accepted")


def doc_parity_cases() -> None:
    reference = (
        ROOT / "skills/deterministic-checks/references/slice-gate.md"
    ).read_text(encoding="utf-8")
    gate_source = GATE_PATH.read_text(encoding="utf-8")
    for family in ("typecheck", "lint", "tests", "fallow", "react-doctor",
                   "dart-analyze", "dart-test", "dart-decimate", "targeted"):
        if f'"{family}"' not in gate_source or family not in reference:
            fail(f"family drift between slice_gate.py and slice-gate.md: {family}")


def main() -> int:
    state = load_state()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        mixed_and_runner_cases(state, root)
        pure_react_cases(state, root)
        identity_cases(state, root)
        resume_and_full_gate_cases(state, root)
        compatibility_and_terminal_cases(state, root)
        evidence_hardening_cases(state, root)
        transcript_shaped_cases(state, root)
    doc_parity_cases()
    print("slice-gate-check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
