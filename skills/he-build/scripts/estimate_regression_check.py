#!/usr/bin/env python3
"""Focused regressions for planned-scope estimate admission."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import audit_admission as admission
import related_context as context_api

PLAN_STATE = Path(__file__).resolve().parents[2] / "he/scripts/plan_state.py"


def fail(message: str) -> None:
    raise SystemExit(f"estimate-regressions: FAIL | {message}")


def plan_text(paths: str) -> str:
    return ("# Fixture\n### S-1 — First\n" f"- planned_paths = {paths}\n"
            "### S-2 — Second\n- planned_paths = second.py\n")


def initialize_cli_plan(root: Path, paths: str) -> tuple[Path, str]:
    initialized = subprocess.run(
        [sys.executable, str(PLAN_STATE), "init", "--repo", str(root),
         "--feature-slug", "fixture", "--plan-id", "fixture"],
        capture_output=True, text=True, check=True,
    )
    plan = root / "features/fixture/PLAN.md"
    plan.write_text(
        plan.read_text(encoding="utf-8") + "\n## Slices\n\n### S-1 — Estimate\n"
        f"- planned_paths = {paths}\n",
        encoding="utf-8",
    )
    inspected = subprocess.run(
        [sys.executable, str(PLAN_STATE), "inspect", "--repo", str(root), "--plan", str(plan)],
        capture_output=True, text=True, check=True,
    )
    token = next(line.split("=", 1)[1] for line in inspected.stdout.splitlines()
                 if line.startswith("checkpoint_token="))
    return plan, token


def advance_cli_plan_to_slices(root: Path, plan: Path, token: str) -> None:
    subprocess.run(
        [sys.executable, str(PLAN_STATE), "checkpoint", "--repo", str(root), "--plan", str(plan),
         "--expect-token", token, "--set", "plan_stage=slices", "--set",
         "approved_plan_stages=repository,research,feature,flows,contracts,technical,testing,rollout",
         "--set", "skipped_plan_stages=ux"],
        capture_output=True, text=True, check=True,
    )


def check_manifest() -> None:
    with tempfile.TemporaryDirectory(prefix="he-estimate-domain-") as temporary:
        root = Path(temporary).resolve()
        plan = root / "features/fixture/PLAN.md"
        plan.parent.mkdir(parents=True)
        plan.write_text(plan_text("owner.py, future.py"), encoding="utf-8")
        (root / "owner.py").write_text("value = 1\n", encoding="utf-8")
        paths = admission.parse_planned_paths(plan, "S-1", root, lambda value: value == ".env")
        if paths != ("owner.py", "future.py"):
            fail("valid manifest was not preserved in declared order")
        invalid = {
            "missing": (plan_text("owner.py").replace("- planned_paths = owner.py\n", ""), "S-1"),
            "duplicate": (plan_text("owner.py, owner.py"), "S-1"),
            "traversal": (plan_text("../owner.py"), "S-1"), "glob": (plan_text("*.py"), "S-1"),
            "absolute": (plan_text("/owner.py"), "S-1"),
            "plan": (plan_text("features/fixture/PLAN.md"), "S-1"),
            "sensitive": (plan_text(".env"), "S-1"), "unknown": (plan_text("owner.py"), "S-9"),
        }
        (root / "directory").mkdir()
        invalid["directory"] = (plan_text("directory"), "S-1")
        for label, (text, unit) in invalid.items():
            plan.write_text(text, encoding="utf-8")
            try:
                admission.parse_planned_paths(plan, unit, root, lambda value: value == ".env")
            except ValueError:
                continue
            fail(f"manifest accepted {label}")


def check_budgets() -> None:
    exact = admission.evaluate_estimate(
        base_snapshot_id="sha256:" + "1" * 64, base_sha="a" * 40, unit_id="S-1",
        planned_paths=("owner.py",), unresolved_paths=("future.py",),
        related_units=tuple((f"owner-{i}.py", 1) for i in range(96)),
        packet_units=(("packet", 700 * 1024),))
    if exact["result"] != "pass" or exact["unresolvedPlannedPaths"] != ["future.py"]:
        fail("exact boundaries or absent path reporting drifted")
    section_units = tuple((f"owner-{i}.py", 1) for i in range(97))
    section = admission.evaluate_estimate(
        base_snapshot_id="sha256:" + "2" * 64, base_sha="b" * 40, unit_id="S-1",
        planned_paths=tuple(f"owner-{i}.py" for i in range(188)), unresolved_paths=(),
        related_units=section_units, packet_units=(("packet", 1),), related_bytes_override=551678)
    expected = {"code": "RELATED_CONTEXT_SECTIONS", "actual": 97, "limit": 96,
                "owner": "owner-96.py"}
    if section["error"] != expected or section["plannedPathCount"] != 188:
        fail("high-cardinality recurrence did not fail with first section owner")
    byte_report = admission.evaluate_estimate(
        base_snapshot_id="sha256:" + "3" * 64, base_sha="c" * 40, unit_id="S-1",
        planned_paths=("first.py", "crossing.py"), unresolved_paths=(),
        related_units=(("first.py", 112 * 1024), ("crossing.py", 1)),
        packet_units=(("packet", 1),))
    packet_report = admission.evaluate_estimate(
        base_snapshot_id="sha256:" + "4" * 64, base_sha="d" * 40, unit_id="S-1",
        planned_paths=("owner.py",), unresolved_paths=(), related_units=(("owner.py", 1),),
        packet_units=(("header", 700 * 1024), ("crossing-unit", 1)))
    if byte_report["error"].get("owner") != "crossing.py":
        fail("related byte overflow omitted first crossing owner")
    if packet_report["error"].get("owner") != "crossing-unit":
        fail("packet overflow omitted first crossing owner")
    rendered = json.dumps(section, separators=(",", ":"))
    if len(section["largestUnits"]) > 10 or "551678" not in rendered:
        fail("recurrence diagnostics are incomplete or unbounded")


def check_full_file_context() -> None:
    with tempfile.TemporaryDirectory(prefix="he-estimate-context-") as temporary:
        root = Path(temporary).resolve()
        files = {
            "owner.py": "def public_api(value):\n    return value\n",
            "caller.py": "from owner import public_api\n\nvalue = public_api(1)\n",
            "tests/test_owner.py": (
                "from owner import public_api\n\n"
                "def test_public_api():\n    assert public_api(1) == 1\n"
            ),
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(root), "-c", "user.name=Fixture", "-c",
             "user.email=fixture@example.com", "commit", "-q", "-m", "base"], check=True
        )
        default = context_api.related_context(root, ("owner.py",), "HEAD")
        full = context_api.related_context(
            root, ("owner.py",), "HEAD", full_file_paths=("owner.py",)
        )
        consumer = context_api.related_context(
            root, ("caller.py",), "HEAD", full_file_paths=("caller.py",)
        )
        labels = "\n".join(entry[1] for entry in full)
        consumer_rendered = "\n".join(f"{entry[0]}\n{entry[1]}\n{entry[2]}" for entry in consumer)
        if any("Related caller" in entry[1] or "Related test" in entry[1] for entry in default):
            fail("default changed-range context behavior drifted")
        if "Related caller" not in labels or "Related test" not in labels:
            fail("full-file context omitted unchanged caller or test")
        if "owner.py" not in consumer_rendered or "tests/test_owner.py" not in consumer_rendered:
            fail("full-file consumer omitted its unchanged dependency owner or connected test")
        try:
            context_api.related_context(
                root, ("owner.py",), "HEAD", full_file_paths=("caller.py",)
            )
        except context_api.RelatedContextError:
            pass
        else:
            fail("full-file context accepted a path outside changed scope")


def check_estimate_cli() -> None:
    audit = Path(__file__).with_name("audit.py")
    with tempfile.TemporaryDirectory(prefix="he-estimate-cli-") as temporary:
        root = Path(temporary).resolve()
        files = {
            "AGENTS.md": "# Rules\n- Review only.\n",
            "PRODUCT.md": "# Product\n- Outcome = fixture.\n",
            "DESIGN.md": "# Design\n- UI = none.\n",
            "owner.py": "def public_api(value):\n    return value\n",
            "caller.py": "from owner import public_api\nvalue = public_api(1)\n",
            "tests/test_owner.py": "from owner import public_api\nassert public_api(1) == 1\n",
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(root), "-c", "user.name=Fixture", "-c",
             "user.email=fixture@example.com", "commit", "-q", "-m", "base"], check=True
        )
        plan, token = initialize_cli_plan(
            root, "owner.py, caller.py, tests/test_owner.py, future.py"
        )
        draft = subprocess.run(
            [sys.executable, str(audit), "--admission", "--estimate-unit", "S-1",
             "--repo", str(root), "--plan", str(plan)],
            capture_output=True, text=True, check=False,
        )
        draft_report = json.loads(draft.stdout) if draft.stdout else {}
        if draft.returncode != 1 or draft_report.get("error", {}).get("code") != "INVALID_PLAN":
            fail("estimate accepted an unaccepted repository-stage manifest")
        advance_cli_plan_to_slices(root, plan, token)
        before = subprocess.check_output(
            [sys.executable, str(audit), "--snapshot-only", "--repo", str(root)], text=True
        ).strip()
        result = subprocess.run(
            [sys.executable, str(audit), "--admission", "--estimate-unit", "S-1",
             "--repo", str(root), "--plan", str(plan)],
            capture_output=True, text=True, check=False,
        )
        after = subprocess.check_output(
            [sys.executable, str(audit), "--snapshot-only", "--repo", str(root)], text=True
        ).strip()
        report = json.loads(result.stdout) if result.stdout else {}
        required = {
            "mode", "result", "baseSnapshotId", "baseSha", "unitId", "plannedPathCount",
            "unresolvedPlannedPaths", "relatedContext", "packet", "largestUnits", "error",
        }
        if (result.returncode != 0 or set(report) != required or report.get("result") != "pass"
                or report.get("unitId") != "S-1" or report.get("plannedPathCount") != 4
                or report.get("unresolvedPlannedPaths") != ["future.py"] or before != after):
            fail("estimate CLI schema, PASS, or source immutability drifted")
        accepted_plan = plan.read_text(encoding="utf-8")
        accepted_head = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        plan.write_text(
            accepted_plan.replace(
                f"- head_sha = {accepted_head}", f"- head_sha = {'0' * 40}",
            ),
            encoding="utf-8",
        )
        stale = subprocess.run(
            [sys.executable, str(audit), "--admission", "--estimate-unit", "S-1",
             "--repo", str(root), "--plan", str(plan)],
            capture_output=True, text=True, check=False,
        )
        stale_report = json.loads(stale.stdout) if stale.stdout else {}
        plan.write_text(accepted_plan, encoding="utf-8")
        if stale.returncode != 1 or stale_report.get("error", {}).get("code") != "INVALID_PLAN":
            fail("estimate accepted a stale accepted PLAN identity")
        missing_mode = subprocess.run(
            [sys.executable, str(audit), "--admission", "--repo", str(root), "--plan", str(plan)],
            capture_output=True, text=True, check=False,
        )
        if missing_mode.returncode != 2 or "exactly one" not in missing_mode.stderr:
            fail("generic current-snapshot admission remains publicly reachable")
        legacy = subprocess.run(
            [sys.executable, str(audit), "--snapshot-only", "--self-test", "--repo", str(root)],
            capture_output=True, text=True, check=False,
        )
        if legacy.returncode != 0 or legacy.stdout.strip() != "audit-self-test: PASS":
            fail("legacy snapshot/self-test combination changed")


def main() -> int:
    check_manifest()
    check_budgets()
    check_full_file_context()
    check_estimate_cli()
    print("estimate-regressions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
