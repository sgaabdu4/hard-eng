#!/usr/bin/env python3
"""More regression checks that kill the surviving mutants of plan_cleanup.py."""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan_cleanup as pc
import plan_cleanup_survivors_regression as base

from scripts.setup import safe_file

fail, require = base.checker("plan-cleanup-survivors-2")

make_repo = base.make_repo
write_plan = base.write_plan
base_plan_text = base.base_plan_text
item_string = base.item_string
run_cleanup = base.run_cleanup
none_lock_path = base.none_lock_path
expect_error = base.expect_error
SABOTAGE = base.SABOTAGE


def check_run_apply_guards(tmp: Path) -> None:
    repo = make_repo(tmp)
    nonterminal_path = write_plan(repo, "guard-nonterminal", base_plan_text("building"), commit=True)
    item = item_string(repo, nonterminal_path)
    expect_error("cleanup apply requires --confirm-delete", run_cleanup, repo, "cancel", [item], apply=True)
    expect_error(
        "invalid legacy cleanup requires --confirm-cancel",
        run_cleanup,
        repo,
        "cancel",
        [item],
        apply=True,
        confirm_delete=True,
    )
    if not nonterminal_path.exists():
        fail("a rejected apply must never delete the PLAN")


def read_note(repo: Path, output: str) -> tuple[dict[str, object], Path]:
    recovery_line = next(line for line in output.splitlines() if line.startswith("recovery_note="))
    note_path = Path(recovery_line.split("=", 1)[1])
    return json.loads(note_path.read_text(encoding="utf-8")), note_path


def check_run_apply_nonterminal(tmp: Path) -> None:
    repo = make_repo(tmp)
    slug = "apply-nonterminal"
    path = write_plan(repo, slug, base_plan_text("building"), commit=True)
    relative = path.relative_to(repo)
    before_hash = pc._digest(path.read_bytes())
    before_mode = oct(stat.S_IMODE(os.stat(path).st_mode))
    item = item_string(repo, path)
    decision = "cancel by exact decision"
    guard_lock = none_lock_path()
    guard_lock.unlink(missing_ok=True)
    output = run_cleanup(repo, decision, [item], apply=True, confirm_delete=True, confirm_cancel=True)
    if guard_lock.exists():
        fail("run() must lock using the real repo identity, not None")
    lines = output.splitlines()
    if "result=removed" not in lines or "removed_count=1" not in lines:
        fail(f"apply must report removal exactly: {output!r}")
    if not any(line.startswith("action_digest=") for line in lines):
        fail(f"apply must print the action_digest line: {output!r}")
    if path.exists():
        fail("apply must remove the PLAN file after cleanup")
    note, _note_path = read_note(repo, output)
    expected_note_keys = {
        "action_digest",
        "completed",
        "decision",
        "entries",
        "operation",
        "repo",
        "schema_version",
        "status",
    }
    if set(note) != expected_note_keys:
        fail(f"note top-level key set drifted: {sorted(note)}")
    if (
        note["operation"] != "hard-eng-plan-cleanup"
        or note["schema_version"] != 1
        or note["repo"] != str(repo.resolve())
    ):
        fail(f"note field values drifted: {note}")
    if note["status"] != "completed" or note["completed"] != [str(relative)]:
        fail(f"note must record completion for the removed item: {note}")
    entry = cast(list[dict[str, object]], note["entries"])[0]
    if entry["before_hash"] != before_hash or entry["path"] != str(relative):
        fail(f"note entry must record the exact before hash and path: {entry}")
    if entry["mode"] != before_mode:
        fail(f"note entry mode drifted: {entry['mode']!r} vs {before_mode!r}")
    if entry["source_status"] != "building":
        fail(f"note entry source_status must reflect the real STATUS match: {entry}")
    if entry["restore_command"] != f"git restore --source=HEAD -- {relative}":
        fail(f"note entry restore_command drifted: {entry['restore_command']!r}")
    if entry["route"] != "nonterminal->cancelled->removed" or entry["validation_error"] != "none":
        fail(f"note entry route/validation_error drifted: {entry}")
    if entry["terminal_status"] != "cancelled":
        fail("nonterminal route must land on cancelled terminal status")
    exclude_text = (repo / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    if f"/features/{slug}/PLAN.md" not in exclude_text:
        fail("apply must register the PLAN under the shared local exclude")


def check_run_apply_already_terminal(tmp: Path) -> None:
    repo = make_repo(tmp)
    slug = "apply-terminal"
    path = write_plan(repo, slug, base_plan_text("shipped"), commit=True)
    before = path.read_bytes()
    item = item_string(repo, path)
    output = run_cleanup(repo, "cancel", [item], apply=True, confirm_delete=True, confirm_cancel=False)
    if "result=removed" not in output.splitlines():
        fail("an already-terminal PLAN must be removable without cancel confirmation")
    if path.exists():
        fail("apply must remove an already-terminal PLAN too")
    note, _ = read_note(repo, output)
    entry = cast(list[dict[str, object]], note["entries"])[0]
    if entry["route"] != "terminal->removed" or entry["terminal_hash"] != pc._digest(before):
        fail(f"terminal route must keep the exact original bytes as the terminal hash: {entry}")


def check_run_apply_invalid_legacy(tmp: Path) -> None:
    repo = make_repo(tmp)
    slug = "apply-invalid"
    path = write_plan(repo, slug, "# PLAN: apply-invalid\n\nINVALID-MARKER\n", commit=True)
    item = item_string(repo, path)
    output = run_cleanup(repo, "cancel", [item], apply=True, confirm_delete=True, confirm_cancel=True)
    if "result=removed" not in output.splitlines():
        fail("an invalid legacy PLAN must still be removable with both confirmations")
    note, _ = read_note(repo, output)
    entry = cast(list[dict[str, object]], note["entries"])[0]
    if entry["route"] != "invalid->cancelled->removed" or entry["validation_error"] != "stub: invalid plan content":
        fail(f"invalid legacy route must record the exact validation failure: {entry}")
    if entry["source_status"] != "unknown":
        fail(f"invalid legacy route source_status must be unknown, no STATUS match exists: {entry}")
    if entry["terminal_status"] != "cancelled":
        fail("invalid legacy route must still land on cancelled")


def check_run_partial_and_failed(tmp: Path) -> None:
    repo = make_repo(tmp)
    first_path = write_plan(repo, "rollback-first", base_plan_text(tag="rollback-first"), commit=True)
    second_path = write_plan(repo, "rollback-second", base_plan_text(tag="rollback-second"), commit=True)
    first_item = item_string(repo, first_path)
    second_item = item_string(repo, second_path)
    second_text = second_path.read_text(encoding="utf-8")
    SABOTAGE[second_text] = (second_path, b"tampered after snapshot")
    try:
        run_cleanup(repo, "cancel", [first_item, second_item], apply=True, confirm_delete=True, confirm_cancel=True)
    except safe_file.SafeFileError:
        pass
    else:
        fail("a preimage tampered mid-run must raise instead of silently succeeding")
    resolved_repo = repo.resolve()
    first_action = pc._action_digest(resolved_repo, "cancel", pc._parse_items([first_item, second_item]))
    note_path = pc._note_path(resolved_repo, first_action)
    note = json.loads(note_path.read_text(encoding="utf-8"))
    if note["status"] != "partial" or note["completed"] != [str(first_path.relative_to(repo))]:
        fail(f"a mid-run failure must record a partial note with only the completed item: {note}")
    if first_path.exists():
        fail("the item that completed before the failure must still be removed")

    solo_path = write_plan(repo, "rollback-solo", base_plan_text(tag="rollback-solo"), commit=True)
    solo_item = item_string(repo, solo_path)
    solo_text = solo_path.read_text(encoding="utf-8")
    SABOTAGE[solo_text] = (solo_path, b"tampered before its own apply")
    try:
        run_cleanup(repo, "cancel", [solo_item], apply=True, confirm_delete=True, confirm_cancel=True)
    except safe_file.SafeFileError:
        pass
    else:
        fail("a solo item tampered before apply must raise")
    solo_action = pc._action_digest(resolved_repo, "cancel", pc._parse_items([solo_item]))
    solo_note_path = pc._note_path(resolved_repo, solo_action)
    solo_note = json.loads(solo_note_path.read_text(encoding="utf-8"))
    if solo_note["status"] != "failed" or solo_note["completed"] != []:
        fail(f"a failure with nothing completed must record status=failed: {solo_note}")


def check_run_needs_cancel_mixed(tmp: Path) -> None:
    repo = make_repo(tmp)
    terminal_path = write_plan(repo, "mixed-terminal", base_plan_text("shipped"), commit=True)
    nonterminal_path = write_plan(repo, "mixed-nonterminal", base_plan_text("building"), commit=True)
    items = [item_string(repo, terminal_path), item_string(repo, nonterminal_path)]
    output = run_cleanup(repo, "cancel", items)
    if "requires_confirm_cancel=yes" not in output:
        fail("mixing a terminal item with a nonterminal item must still require cancel confirmation")
    only_terminal = run_cleanup(repo, "cancel", [item_string(repo, terminal_path)])
    if "requires_confirm_cancel=no" not in only_terminal:
        fail("an all-terminal batch must not require cancel confirmation")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="plan-cleanup-survivors2-") as raw:
        tmp = Path(raw)
        check_run_apply_guards(tmp)
        check_run_apply_nonterminal(tmp)
        check_run_apply_already_terminal(tmp)
        check_run_apply_invalid_legacy(tmp)
        check_run_partial_and_failed(tmp)
        check_run_needs_cancel_mixed(tmp)
    print("plan-cleanup-survivors-2: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
