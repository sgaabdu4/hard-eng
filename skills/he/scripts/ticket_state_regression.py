#!/usr/bin/env python3
"""Regression suite for ticket_state.py + ticket_decompose.py; tempdir git fixtures only, host repo untouched."""

from __future__ import annotations

import argparse
import contextlib
import functools
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, NoReturn

SCRIPT_DIR = Path(__file__).resolve().parent
DET_SCRIPTS = SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"
REPO_ROOT = SCRIPT_DIR.parents[2]
for _extra in (DET_SCRIPTS, SCRIPT_DIR, REPO_ROOT):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from git_env import scrub_environ

scrub_environ(ceiling=tempfile.gettempdir())

import checkout_policy
import plan_state
import safe_plan_io
import setup_state
import slice_gate
import source_tree_coordination
import ticket_decompose
import ticket_parser
import ticket_state

AUTONOMOUS_DIRECTIVE = "YES — use Hard Eng autonomous mode for this task."
SESSION_ID = "ticket-state-contract"
REJECT_TYPES = (ValueError, RuntimeError, SystemExit, OSError)


def fail(message: str) -> NoReturn:
    raise SystemExit(f"ticket-state-check: {message}")


def require(condition: bool, label: str) -> None:
    condition or fail(label)


def expect_reject(action, label: str) -> str:
    try:
        action()
    except REJECT_TYPES as error:
        return str(error)
    fail(f"{label}: expected rejection but the call succeeded")


def reject_has(action, substring: str, *, suffix: bool = False) -> str:
    error = expect_reject(action, substring)
    matched = error.endswith(substring) if suffix else substring in error
    require(matched, f"expected {'suffix' if suffix else 'substring'} {substring!r} in {error!r}")
    return error


def run_git(repo: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", "-C", str(repo), *arguments], check=True, capture_output=True)


def commit_all(repo: Path, message: str) -> None:
    run_git(repo, "add", "-A")
    status = subprocess.run(["git", "-C", str(repo), "diff", "--cached", "--quiet"], capture_output=True, check=False)
    if status.returncode != 0:
        run_git(repo, "commit", "-q", "-m", message)


def make_repo(base: Path, name: str, *, tracker: bool = False) -> Path:
    origin = base / f"{name}-origin.git"
    run_git(base, "init", "-q", "--bare", "-b", "main", str(origin))
    repo = base / name
    run_git(base, "clone", "-q", str(origin), str(repo))
    run_git(repo, "config", "user.email", "ticket-check@example.invalid")
    run_git(repo, "config", "user.name", "Ticket Check")
    manifest: dict = {"schema_version": 1, "families": {"targeted": [sys.executable, "-c", "pass"]}}
    tracker and manifest.update(tracker={"adapter": "github", "repository": "example/ticket-fixture"})
    (repo / "hard-eng.gates.json").write_text(json.dumps(manifest), encoding="utf-8")
    commit_all(repo, "seed manifest")
    run_git(repo, "push", "-u", "-q", "origin", "main")
    run_git(repo, "remote", "set-head", "origin", "main")
    return repo


def _set_section(text: str, heading: str, body: str) -> str:
    marker = f"## {heading}\n"
    start = text.find(marker)
    require(start != -1, f"template missing section heading: {heading}")
    body_start = start + len(marker)
    end = text.find("\n## ", body_start)
    end = text.find("\n<!-- hard-eng-state", body_start) if end == -1 else end
    end = end + 1 if end != -1 else len(text)
    return text[:body_start] + body.rstrip("\n") + "\n" + text[end:]


def auth(repo: Path, plan: Path, fp: str) -> None:
    plan_state.authorize_execution(repo, plan, fp, AUTONOMOUS_DIRECTIVE, ["build-and-verify"])


def reauthorize(repo: Path, plan: Path) -> None:
    auth(repo, plan, plan_state.parse_state(plan.read_text(encoding="utf-8"))["approval_fingerprint"])


def reapprove_with_acceptance(repo: Path, plan: Path, acceptance: list[str]) -> None:
    text = plan.read_text(encoding="utf-8")
    new_text = _set_section(text, "Acceptance examples", "\n".join(f"- {item}" for item in acceptance))
    fingerprint = plan_state.frozen_fingerprint(plan_state.parse_sections(new_text))
    rendered = plan_state.render_state(new_text, {"approval_fingerprint": fingerprint, "approval_status": "approved"})
    plan.write_text(rendered, encoding="utf-8")
    commit_all(repo, "reapprove with updated acceptance examples")
    auth(repo, plan, fingerprint)


def approve_epic(
    repo: Path,
    slug: str,
    acceptance: list[str],
    *,
    lifecycle_status: str = "build-ready",
    approval_status: str = "approved",
    extra_changes: dict[str, str] | None = None,
) -> Path:
    plan_id = f"{slug}-test"
    text = plan_state.template(slug, plan_id)
    sections = {
        "Outcome": "Ship parallel ticket decomposition for this epic.",
        "Non-goals": "- Not touching unrelated skills.",
        "Material decisions": (
            "- Tickets partition slices with no shared ownership.\n- ux_reference = n/a\n- ux_reference_sources = n/a"
        ),
        "Acceptance examples": "\n".join(f"- {item}" for item in acceptance),
        "Affected canonical areas": "- skills/he/scripts/",
        "Risk and rollback": "- risk_level = standard\n- critical_overlay = none\n- rollback = revert the commit",
        "Vertical slices": "- S-1 = initial ticket decomposition scaffold; depends_on = none",
    }
    for heading, body in sections.items():
        text = _set_section(text, heading, body)
    plan = repo / "features" / slug / "PLAN.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    fingerprint = plan_state.frozen_fingerprint(plan_state.parse_sections(text))
    changes = {
        "lifecycle_status": lifecycle_status,
        "approval_status": approval_status,
        "approval_fingerprint": fingerprint,
        "approval_provenance": "ready-to-build",
    }
    extra_changes and changes.update(extra_changes)
    plan.write_text(plan_state.render_state(text, changes), encoding="utf-8")
    commit_all(repo, f"seed {slug} epic plan")
    approval_status == "approved" and auth(repo, plan, fingerprint)
    return plan


def ticket_token(repo: Path, slug: str, ticket_id: str) -> str:
    return plan_state.token_for(ticket_path(repo, slug, ticket_id).read_text(encoding="utf-8"))


def base_args(repo: Path, plan: Path, **extra: object) -> argparse.Namespace:
    values = {
        "repo": str(repo),
        "epic_plan": str(plan.relative_to(repo)),
        "session_id": SESSION_ID,
        "dry_run": False,
        "expect_token": plan_state.token_for(plan.read_text(encoding="utf-8")),
        "confirm_cancel": False,
        "force_release": False,
        "pull": False,
    }
    values.update(extra)
    return argparse.Namespace(**values)


def _run(command, repo: Path, plan: Path, tickets: list | None = None, **extra: object) -> str:
    args = base_args(repo, plan, **extra)
    buffer = io.StringIO()
    original_stdin = sys.stdin
    sys.stdin = io.StringIO(json.dumps({"tickets": tickets or []}))
    try:
        with contextlib.redirect_stdout(buffer):
            command(args)
    finally:
        sys.stdin = original_stdin
    return buffer.getvalue()


run_decompose = functools.partial(_run, ticket_decompose.command_decompose)
run_amend = functools.partial(_run, ticket_decompose.command_amend)
run_reconcile = functools.partial(_run, ticket_decompose.command_reconcile)


def ticket_path(repo: Path, slug: str, ticket_id: str) -> Path:
    return repo / "features" / slug / "tickets" / f"{ticket_id}.md"


def read_ticket_state(repo: Path, slug: str, ticket_id: str) -> dict[str, str]:
    text = ticket_path(repo, slug, ticket_id).read_text(encoding="utf-8")
    return ticket_parser.parse_state(text)


def expect_status(repo: Path, slug: str, ticket_id: str, expected: str, label: str = "") -> None:
    actual = read_ticket_state(repo, slug, ticket_id).get("status")
    require(actual == expected, label or f"{slug}/{ticket_id} expected status={expected}, got {actual!r}")


GREEN_FIELDS = {
    "claimed_by": "fixture-session",
    "claimed_at": "2026-01-01T00:00:00Z",
    "worktree": "/tmp/fixture-worktree",
    "branch": "ticket/fixture",
    "green_artifact": "sha256:" + "9" * 64,
    "delivery": "none",
}
SHIP_FIELDS = {**GREEN_FIELDS, "delivery": "https://example.invalid@abc1234"}


def force_ticket_state(repo: Path, slug: str, ticket_id: str, changes: dict[str, str]) -> None:
    path = ticket_path(repo, slug, ticket_id)
    path.write_text(ticket_parser.render_state(path.read_text(encoding="utf-8"), changes), encoding="utf-8")
    commit_all(repo, f"force {ticket_id} state for fixture")


def ticket_entry(
    ticket_id: str, slices: list[str], covers: list[str], touches: list[str]
) -> ticket_decompose.TicketSpec:
    return {
        "ticket_id": ticket_id,
        "slices": tuple(slices),
        "depends_on": (),
        "covers": tuple(covers),
        "touches": tuple(touches),
        "goal_text": f"Build {slices[0]}.",
        "acceptance_text": f"{covers[0]} behaves.",
    }


def behaves(*slices: str) -> list[str]:
    return [f"{s} behaves." for s in slices]


def three_way_tickets(*, touching_overlap: bool = False) -> list[ticket_decompose.TicketSpec]:
    touches_b = ["skills/he/scripts/ticket_worktree.py"] if touching_overlap else ["skills/he-plan/scripts/check.py"]
    return [
        ticket_entry("T-1", ["S-1"], ["A-1"], ["skills/he/scripts/ticket_state.py"]),
        ticket_entry("T-2", ["S-2"], ["A-2"], touches_b),
        ticket_entry("T-3", ["S-3"], ["A-3"], ["skills/atomic-ui/scripts/lint.py"]),
    ]


def claim(repo: Path, plan: Path, *, ticket: str | None = None, next_: bool = False, refresh: bool = False) -> str:
    run_git(repo, "push", "-f", "-q", "origin", "HEAD:main")
    args = base_args(repo, plan, ticket=ticket, next=next_, refresh=refresh, expect_token=None)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        ticket_state.command_claim(args)
    return buffer.getvalue()


def do_checkpoint(repo: Path, plan: Path, slug: str, ticket_id: str, fields: list[str], **extra: object) -> None:
    ticket = str(ticket_path(repo, slug, ticket_id).relative_to(repo))
    token = ticket_token(repo, slug, ticket_id)
    args = base_args(repo, plan, ticket=ticket, set=fields, expect_token=token, **extra)
    ticket_state.command_checkpoint(args)


def do_release(repo: Path, plan: Path, slug: str, ticket_id: str, **extra: object) -> None:
    args = base_args(repo, plan, ticket=ticket_id, expect_token=ticket_token(repo, slug, ticket_id), **extra)
    ticket_state.command_release(args)


def setup_epic(
    base: Path, name: str, slug: str, acceptance: list[str], *, tracker: bool = False, **extra: Any
) -> tuple[Path, Path]:
    repo = make_repo(base, name, tracker=tracker)
    return repo, approve_epic(repo, slug, acceptance, **extra)


def install_fake_gh(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / "gh-calls.jsonl"
    script = directory / "gh"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "log = os.environ.get('FAKE_GH_LOG')\n"
        "log and open(log, 'a', encoding='utf-8').write(json.dumps(sys.argv[1:]) + chr(10))\n"
        "n = sum(1 for _ in open(log, encoding='utf-8')) if log and os.path.exists(log) else 1\n"
        "print(f'https://example.invalid/issues/{n}' if sys.argv[1:3] == ['issue', 'create'] else "
        "json.dumps({'number': 7, 'url': 'https://example.invalid/issues/7', 'state': 'OPEN'}))\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    os.environ["FAKE_GH_LOG"] = str(log_path)
    os.environ["PATH"] = f"{directory}{os.pathsep}{os.environ.get('PATH', '')}"
    return log_path


def read_gh_log(log_path: Path) -> list[list[str]]:
    text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def reset_gh_log(log_path: Path) -> None:
    log_path.unlink(missing_ok=True)


def check_decompose_accept(base: Path) -> None:
    repo, plan = setup_epic(base, "decompose-accept", "portal", behaves("S-1", "S-2", "S-3"))
    run_decompose(repo, plan, three_way_tickets())
    for ticket_id in ("T-1", "T-2", "T-3"):
        expect_status(repo, "portal", ticket_id, "todo")
    require("lifecycle_status = building" in plan.read_text(encoding="utf-8"), "epic did not move to building")


def check_decompose_reject_state(base: Path) -> None:
    repo, wrong_status = setup_epic(base, "reject-state", "wrongstatus", behaves("S-1"), lifecycle_status="planning")
    expect_reject(lambda: run_decompose(repo, wrong_status, [three_way_tickets()[0]]), "lifecycle_status=planning")
    repo2, wrong_approval = setup_epic(base, "reject-approval", "wrongappr", behaves("S-1"), approval_status="pending")
    expect_reject(lambda: run_decompose(repo2, wrong_approval, [three_way_tickets()[0]]), "approval_status=pending")
    repo3, stale_plan = setup_epic(base, "reject-token", "staletoken", behaves("S-1"))
    expect_reject(
        lambda: run_decompose(repo3, stale_plan, [three_way_tickets()[0]], expect_token="sha256:" + "0" * 64),
        "stale expect_token",
    )


def check_decompose_reject_checkout_policy(base: Path) -> None:
    repo = make_repo(base, "decompose-reject-checkout")
    (repo / "AGENTS.override.md").write_text("- checkout_policy = primary-only\n", encoding="utf-8")
    commit_all(repo, "set checkout policy")
    require(checkout_policy.checkout_policy(repo) == "primary-only", "checkout_policy override did not take effect")
    plan = approve_epic(repo, "checkoutgated", behaves("S-1", "S-2", "S-3"))
    expect_reject(lambda: run_decompose(repo, plan, three_way_tickets()), "checkout_policy=primary-only must refuse")


def check_decompose_reject_partition(base: Path) -> None:
    repo, plan = setup_epic(base, "reject-gap", "gapslices", behaves("S-1", "S-2", "S-3"))
    tickets = three_way_tickets()
    tickets[1]["slices"] = ("S-3",)
    expect_reject(lambda: run_decompose(repo, plan, tickets), "slice gap (missing S-2) must be refused")
    repo2, plan2 = setup_epic(base, "reject-overlap", "overlaps", behaves("S-1", "S-2", "S-3"))
    tickets2 = three_way_tickets()
    tickets2[0]["slices"] = ("S-1", "S-2")
    tickets2[1]["slices"] = ("S-2", "S-3")
    expect_reject(lambda: run_decompose(repo2, plan2, tickets2), "slice overlap (S-2 duplicated) must be refused")


def check_decompose_reject_dag_cycle(base: Path) -> None:
    repo, plan = setup_epic(base, "reject-cycle", "cyclic", behaves("S-1", "S-2", "S-3"))
    tickets = three_way_tickets()
    tickets[0]["depends_on"] = ("T-2",)
    tickets[1]["depends_on"] = ("T-1",)
    expect_reject(lambda: run_decompose(repo, plan, tickets), "T-1<->T-2 dependency cycle must be refused")


def check_decompose_reject_uncovered_acceptance(_base: Path) -> None:
    tickets = three_way_tickets()
    tickets[2]["covers"] = ("A-2",)
    reject_has(lambda: ticket_decompose.validate_acceptance_coverage(tickets, ("A-1", "A-2", "A-3")), "A-3")


def check_dry_run_threshold_matrix(base: Path) -> None:
    repo, plan = setup_epic(base, "dry-run-zero", "dryzero", behaves("S-1"))
    expect_reject(lambda: run_decompose(repo, plan, [], dry_run=True), "zero tickets must be refused")
    repo2, plan2 = setup_epic(base, "dry-run-two", "drytwo", behaves("S-1", "S-2"))
    two_tickets = three_way_tickets()[:2]
    output_two = run_decompose(repo2, plan2, two_tickets, dry_run=True)
    require("result=dry-run tickets=2 parallel_safe=2" in output_two, f"two-ticket verdict: {output_two!r}")
    require(not ticket_path(repo2, "drytwo", "T-1").exists(), "dry-run must not write ticket files")
    repo3, plan3 = setup_epic(base, "dry-three-clear", "threeclear", behaves("S-1", "S-2", "S-3"))
    output_three = run_decompose(repo3, plan3, three_way_tickets(), dry_run=True)
    require("result=dry-run tickets=3 parallel_safe=3" in output_three, f"three-ticket verdict: {output_three!r}")
    repo4, plan4 = setup_epic(base, "dry-three-ovl", "threeovl", behaves("S-1", "S-2", "S-3"))
    output_overlap = run_decompose(repo4, plan4, three_way_tickets(touching_overlap=True), dry_run=True)
    require("result=dry-run tickets=3 parallel_safe=2" in output_overlap, f"overlap collapse: {output_overlap!r}")


def check_amend(base: Path) -> None:
    repo, plan = setup_epic(base, "amend-additive", "amendok", behaves("S-1", "S-2", "S-3", "S-4"))
    run_decompose(repo, plan, three_way_tickets())
    reauthorize(repo, plan)
    before_t1 = ticket_path(repo, "amendok", "T-1").read_bytes()
    extra = ticket_entry("T-4", ["S-4"], ["A-4"], ["skills/he/scripts/tracker_github.py"])
    run_amend(repo, plan, [extra])
    require(ticket_path(repo, "amendok", "T-4").exists(), "additive ticket must be created")
    require(ticket_path(repo, "amendok", "T-1").read_bytes() == before_t1, "existing ticket bytes must be unchanged")
    require("T-4" in read_ticket_state(repo, "amendok", "T-int").get("depends_on", ""), "T-int.depends_on must extend")
    gap9 = ticket_entry("T-9", ["S-9"], ["A-4"], ["skills/he/scripts/tracker_github.py"])
    reject_has(lambda: run_amend(repo, plan, [gap9]), "gap")
    repo2, plan2 = setup_epic(base, "amend-frozen", "amendfrozen", behaves("S-1", "S-2", "S-3", "S-4"))
    run_decompose(repo2, plan2, three_way_tickets())
    mutated_text = _set_section(plan2.read_text(encoding="utf-8"), "Outcome", "Something never approved by anyone.")
    plan2.write_text(mutated_text, encoding="utf-8")
    extra2 = ticket_entry("T-4", ["S-4"], ["A-4"], ["skills/he/scripts/tracker_github.py"])
    expect_reject(lambda: run_amend(repo2, plan2, [extra2]), "mutating the epic's frozen Outcome must be refused")
    repo3, plan3 = setup_epic(base, "amend-tint", "amendtint", behaves("S-1", "S-2"))
    run_decompose(repo3, plan3, three_way_tickets()[:2])
    reauthorize(repo3, plan3)
    force_ticket_state(repo3, "amendtint", "T-int", {"status": "green", **GREEN_FIELDS})
    tint5 = ticket_entry("T-5", ["S-3"], ["A-3"], ["skills/he/scripts/tracker_github.py"])
    expect_reject(lambda: run_amend(repo3, plan3, [tint5]), "T-int must release to todo before amending")
    repo4, plan4 = setup_epic(base, "amend-refill", "amendrefill", behaves("S-1", "S-2", "S-3", "S-4"))
    refill_tickets = three_way_tickets()
    refill_tickets[1]["covers"] = ("A-2", "A-4")
    run_decompose(repo4, plan4, refill_tickets)
    reauthorize(repo4, plan4)
    reapprove_with_acceptance(repo4, plan4, behaves("S-1", "S-2", "S-3"))
    reconciled = run_reconcile(repo4, plan4)
    require("ticket=T-2 verdict=cancelled" in reconciled, f"T-2 must cancel when A-4 drops: {reconciled!r}")
    require("gap=A-2" in reconciled, f"T-int must absorb orphaned A-2 as a gap: {reconciled!r}")
    refill = ticket_entry("T-4", ["S-2"], ["A-2"], ["skills/he/scripts/tracker_github.py"])
    refill_out = run_amend(repo4, plan4, [refill])
    require("result=amended tickets=1" in refill_out, f"reclaiming a cancelled slice must succeed: {refill_out!r}")
    require(ticket_path(repo4, "amendrefill", "T-4").exists(), "replacement ticket must be created")


def check_reconcile_matrix(base: Path) -> None:
    repo, plan = setup_epic(base, "reconcile-preview", "reconcileprev", behaves("S-1", "S-2", "S-3"), tracker=True)
    reconcile_log = install_fake_gh(base / "reconcile-tracker-shim")
    run_decompose(repo, plan, three_way_tickets())
    reauthorize(repo, plan)
    claim(repo, plan, ticket="T-3")
    reapprove_with_acceptance(repo, plan, behaves("S-1", "S-2"))
    preview = run_reconcile(repo, plan, dry_run=True)
    require("ticket=T-3 verdict=cancelled" in preview, f"expected T-3 cancelled: {preview!r}")
    require("ticket=T-1 verdict=survive" in preview, f"expected T-1 survive: {preview!r}")
    require(read_ticket_state(repo, "reconcileprev", "T-3").get("status") != "cancelled", "dry-run mutated status")
    reset_gh_log(reconcile_log)
    applied = run_reconcile(repo, plan)
    require("ticket=T-int verdict=survive" in applied, f"T-int must always survive: {applied!r}")
    expect_status(repo, "reconcileprev", "T-3", "cancelled", "dropped coverage must cancel")
    require("cleanup=" in applied, f"a cancelled ticket's prior worktree needs a cleanup line: {applied!r}")
    require(len(read_gh_log(reconcile_log)) > 0, "cancelling a ticket must emit a tracker close call")
    new_fingerprint = plan_state.frozen_fingerprint(plan_state.parse_sections(plan.read_text(encoding="utf-8")))
    fps = {read_ticket_state(repo, "reconcileprev", t).get("epic_fingerprint") for t in ("T-1", "T-2", "T-int")}
    require(fps == {new_fingerprint}, "surviving tickets and T-int should share the refreshed epic_fingerprint")
    tint_depends = read_ticket_state(repo, "reconcileprev", "T-int").get("depends_on", "")
    require(
        "T-1" in tint_depends and "T-2" in tint_depends and "T-3" not in tint_depends,
        f"T-int.depends_on must track only the surviving tickets: {tint_depends!r}",
    )


def check_epic_green_gate(base: Path) -> None:
    repo, plan = setup_epic(base, "epic-green-gate", "greengate", behaves("S-1", "S-2", "S-3"))
    run_decompose(repo, plan, three_way_tickets())
    state = plan_state.parse_state(plan.read_text(encoding="utf-8"))
    err = ticket_state.epic_green_gate_error(repo, plan, state)
    require(bool(err) and "not yet shipped or cancelled" in err, f"all-todo must block on unshipped work: {err!r}")
    force_ticket_state(repo, "greengate", "T-1", {"status": "shipped", **SHIP_FIELDS})
    force_ticket_state(repo, "greengate", "T-2", {"status": "cancelled", "worktree": "none", "branch": "none"})
    force_ticket_state(repo, "greengate", "T-3", {"status": "shipped", **SHIP_FIELDS})
    err = ticket_state.epic_green_gate_error(repo, plan, state)
    require(err == "integration ticket T-int is not green (status=todo)", f"a non-green T-int must block, got: {err!r}")
    force_ticket_state(repo, "greengate", "T-int", {"status": "green", **GREEN_FIELDS})
    err = ticket_state.epic_green_gate_error(repo, plan, state)
    require(
        err == "shipped tickets do not cover the full slice partition; amend replacement tickets for the "
        "cancelled slices",
        f"a cancelled slice with no shipped replacement must block, got: {err!r}",
    )
    force_ticket_state(repo, "greengate", "T-2", {"status": "shipped", **SHIP_FIELDS})
    full_state = dict(state, completed_slices="S-1,S-2,S-3")
    err = ticket_state.epic_green_gate_error(repo, plan, full_state)
    require(err is None, f"fully shipped tickets + green T-int must accept: {err!r}")


def check_concurrent_claim_race(base: Path) -> None:
    repo, plan = setup_epic(base, "claim-race", "raceclaim", behaves("S-1", "S-2", "S-3"))
    run_decompose(repo, plan, three_way_tickets())
    reauthorize(repo, plan)
    run_git(repo, "push", "-f", "-q", "origin", "HEAD:main")
    results: list[tuple[bool, str]] = []
    lock = threading.Lock()

    def attempt() -> None:
        args = base_args(repo, plan, ticket="T-1", next=False, refresh=False, expect_token=None)
        try:
            ticket_state.command_claim(args)
            entry = (True, "")
        except REJECT_TYPES as error:
            entry = (False, str(error))
        with lock:
            results.append(entry)

    threads = [threading.Thread(target=attempt) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    require(len(results) == 4, f"expected all 4 attempts to finish, got {len(results)}")
    winners = [entry for entry in results if entry[0]]
    require(len(winners) == 1, f"expected exactly one winner, got {len(winners)}")
    state = read_ticket_state(repo, "raceclaim", "T-1")
    require(state.get("status") == "claimed", "winning ticket must be claimed")
    require(bool(state.get("claimed_by")), "claimed_by must be recorded")


def check_dependency_gating_and_next(base: Path) -> None:
    repo, plan = setup_epic(base, "dependency-gating", "depgate", behaves("S-1", "S-2", "S-3"))
    tickets = three_way_tickets()
    tickets[1]["depends_on"] = ("T-1",)
    run_decompose(repo, plan, tickets)
    reauthorize(repo, plan)
    expect_reject(lambda: claim(repo, plan, ticket="T-2"), "claiming T-2 before T-1 ships must be refused")
    claim(repo, plan, next_=True)
    picked = [t for t in ("T-1", "T-3") if read_ticket_state(repo, "depgate", t).get("status") == "claimed"]
    require(len(picked) == 1, f"--next: expected exactly one dependency-free ticket claimed, got {picked}")


def check_ticket_checkpoint_and_release(base: Path) -> None:
    repo, plan = setup_epic(base, "checkpoint-release", "checkptrel", behaves("S-1", "S-2"))
    tickets = [three_way_tickets()[0]]
    tickets[0]["slices"] = ("S-1", "S-2")
    run_decompose(repo, plan, tickets)
    reauthorize(repo, plan)
    claim(repo, plan, ticket="T-1")
    claimed_state = read_ticket_state(repo, "checkptrel", "T-1")
    auth_path = Path(claimed_state["worktree"]) / "features" / "checkptrel" / "receipts" / "authorization.json"
    minted_auth = json.loads(auth_path.read_text(encoding="utf-8"))
    require(
        "approved_at" in minted_auth and "expires_at" not in minted_auth,
        f"mirrored worktree authorization must carry approved_at and no expires_at: {minted_auth!r}",
    )
    refreshed = claim(repo, plan, ticket="T-1", refresh=True)
    require("result=refreshed" in refreshed, f"claim --refresh must print result=refreshed: {refreshed!r}")
    expect_status(repo, "checkptrel", "T-1", "claimed", "claim --refresh moved off claimed")
    reject_has(lambda: do_checkpoint(repo, plan, "checkptrel", "T-1", ["completed_slices=S-2"]), "ordered prefix")
    do_checkpoint(repo, plan, "checkptrel", "T-1", ["status=building"])
    expect_status(repo, "checkptrel", "T-1", "building", "claimed -> building failed")
    expect_reject(
        lambda: do_checkpoint(repo, plan, "checkptrel", "T-1", ["status=green"]), "green without a receipt must refuse"
    )
    state = read_ticket_state(repo, "checkptrel", "T-1")
    worktree = Path(state["worktree"])
    mirrored_plan = worktree / "features" / "checkptrel" / "PLAN.md"
    receipt_paths = slice_gate.changed_paths(worktree, full=True)
    receipt_applicable = slice_gate.applicable_families(worktree, receipt_paths)
    receipt_commands = slice_gate.load_manifest(worktree)
    payload = {
        "receipt_version": slice_gate.RECEIPT_VERSION,
        "kind": "full",
        "plan_id": state.get("epic_plan_id", "checkptrel-test"),
        "slice": "full",
        "behavior": "one demonstrated observable behavior",
        "review": "actual diff reviewed in fixture",
        "security": "not-applicable:fixture ticket",
        "artifact": safe_plan_io.repository_artifact(worktree),
        "head": slice_gate.head_commit(worktree),
        "e2e": "not-applicable:fixture ticket",
        "e2e_sha256": slice_gate.e2e_sha(worktree, "not-applicable:fixture ticket"),
        "changed_paths": list(receipt_paths),
        "applicable": list(receipt_applicable),
        "checks": [
            {"family": family, "command": list(receipt_commands[family]), "exit": 0} for family in receipt_applicable
        ],
    }
    payload["integrity"] = slice_gate.payload_hash(payload)
    receipt_target = slice_gate.receipt_file(mirrored_plan, "full")
    receipt_target.parent.mkdir(parents=True, exist_ok=True)
    source_tree_coordination.atomic_json(receipt_target, payload)
    do_checkpoint(repo, plan, "checkptrel", "T-1", ["completed_slices=S-1,S-2", "status=green"])
    expect_status(repo, "checkptrel", "T-1", "green", "building -> green with a receipt failed")
    expect_reject(lambda: do_release(repo, plan, "checkptrel", "T-1"), "a green ticket must always refuse release")
    expect_reject(
        lambda: do_release(repo, plan, "checkptrel", "T-1", force_release=True),
        "--force-release opened a path from green",
    )
    reject_has(
        lambda: do_checkpoint(repo, plan, "checkptrel", "T-int", ["status=cancelled"], confirm_cancel=True),
        "T-int cannot be cancelled",
    )
    repo2, plan2 = setup_epic(base, "release-paths", "releasepaths", behaves("S-1", "S-2", "S-3", "S-4"))
    run_decompose(repo2, plan2, [*three_way_tickets(), ticket_entry("T-4", ["S-4"], ["A-4"], ["skills/he/x.py"])])
    reauthorize(repo2, plan2)
    for ticket_id in ("T-1", "T-2", "T-3", "T-4"):
        claim(repo2, plan2, ticket=ticket_id)
    reject_has(
        lambda: do_release(repo2, plan2, "releasepaths", "T-1", session_id="other"), "claimed by another session"
    )
    state_0 = read_ticket_state(repo2, "releasepaths", "T-1")
    do_release(repo2, plan2, "releasepaths", "T-1")
    state_1 = read_ticket_state(repo2, "releasepaths", "T-1")
    cleared = {"status": "todo", "worktree": "none", "branch": "none", "claimed_by": "none", "claimed_at": "none"}
    require({k: state_1.get(k) for k in cleared} == cleared, f"clean release must clear every claim field: {state_1!r}")
    require(not Path(state_0["worktree"]).exists(), "released worktree directory must be gone")
    verify = subprocess.run(
        ["git", "-C", str(repo2), "rev-parse", "--verify", "--quiet", f"refs/heads/{state_0['branch']}"],
        capture_output=True,
        check=False,
    )
    require(verify.returncode != 0, "released branch ref must be deleted")
    claim(repo2, plan2, ticket="T-1")
    expect_status(repo2, "releasepaths", "T-1", "claimed", "re-claim after release failed")
    do_checkpoint(repo2, plan2, "releasepaths", "T-2", ["status=building"])
    expect_reject(lambda: do_release(repo2, plan2, "releasepaths", "T-2"), "a building ticket must be refused")
    do_release(repo2, plan2, "releasepaths", "T-2", force_release=True)
    expect_status(repo2, "releasepaths", "T-2", "cancelled", "force-release must cancel")
    worktree_3 = Path(read_ticket_state(repo2, "releasepaths", "T-3")["worktree"])
    (worktree_3 / "stray.txt").write_text("stray", encoding="utf-8")
    reject_has(
        lambda: do_release(repo2, plan2, "releasepaths", "T-3"),
        "; pass --force-release to discard in-progress ticket work",
        suffix=True,
    )
    do_release(repo2, plan2, "releasepaths", "T-3", force_release=True)
    expect_status(repo2, "releasepaths", "T-3", "todo", "force-release past a stray file")
    worktree_4 = Path(read_ticket_state(repo2, "releasepaths", "T-4")["worktree"])
    (worktree_4 / "real.txt").write_text("real change", encoding="utf-8")
    commit_all(worktree_4, "advance ticket branch")
    reject_has(lambda: do_release(repo2, plan2, "releasepaths", "T-4"), "holds commits not on the base ref")
    do_release(repo2, plan2, "releasepaths", "T-4", force_release=True)
    expect_status(repo2, "releasepaths", "T-4", "todo", "force-release past a dirty branch")


def check_invalid_and_forged_states(base: Path) -> None:
    repo, plan = setup_epic(base, "forged-states", "forged", behaves("S-1", "S-2", "S-3"))
    run_decompose(repo, plan, three_way_tickets())
    target = ticket_path(repo, "forged", "T-1")
    original = target.read_text(encoding="utf-8")
    target.write_text(re.sub(r"(?m)^- status = .*$", "- status = bogus-status", original, count=1), encoding="utf-8")
    error = reject_has(lambda: _run(ticket_state.command_board, repo, plan), "bogus-status")
    require("T-1" in error, f"board error must name the forged ticket: {error!r}")
    target.write_text(original, encoding="utf-8")
    force_ticket_state(repo, "forged", "T-2", {"status": "shipped", **GREEN_FIELDS})
    state = plan_state.parse_state(plan.read_text(encoding="utf-8"))
    err = ticket_state.epic_green_gate_error(repo, plan, state)
    require(
        bool(err) and "T-2" in err and "delivery" in err,
        f"shipped ticket without delivery proof must block the epic gate: {err!r}",
    )
    rendered = ticket_parser.render_state(original, {"status": "shipped", **GREEN_FIELDS})
    reject_has(lambda: ticket_parser.validate_ticket_text(rendered), "shipped requires a recorded delivery")
    greenless = ticket_parser.render_state(original, {"status": "green", **GREEN_FIELDS, "green_artifact": "none"})
    reject_has(lambda: ticket_parser.validate_ticket_text(greenless), "requires a recorded green_artifact")


def check_release_shipped_cleanup(base: Path) -> None:
    repo, plan = setup_epic(base, "release-shipped", "relshipped", behaves("S-1", "S-2", "S-3"))
    run_decompose(repo, plan, three_way_tickets())
    reauthorize(repo, plan)
    claim(repo, plan, ticket="T-1")
    state = read_ticket_state(repo, "relshipped", "T-1")
    worktree = Path(state["worktree"])
    force_ticket_state(
        repo,
        "relshipped",
        "T-1",
        {"status": "shipped", "green_artifact": "sha256:" + "9" * 64, "delivery": "https://example.invalid@abc1234"},
    )
    reject_has(lambda: do_release(repo, plan, "relshipped", "T-1", force_release=True), "never force")
    do_release(repo, plan, "relshipped", "T-1")
    after = read_ticket_state(repo, "relshipped", "T-1")
    cleared = {"status": "shipped", "worktree": "none", "branch": "none"}
    require({k: after.get(k) for k in cleared} == cleared, f"shipped release must clear worktree state: {after!r}")
    require(not worktree.exists(), "released shipped worktree directory must be gone")
    verify = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"refs/heads/{state['branch']}"],
        capture_output=True,
        check=False,
    )
    require(verify.returncode != 0, "released shipped branch ref must be deleted")
    reject_has(lambda: do_release(repo, plan, "relshipped", "T-1"), "already released")


def check_tracker_ops_and_pull(base: Path) -> None:
    repo, plan = setup_epic(base, "tracker-ops", "trackerops", behaves("S-1", "S-2", "S-3"), tracker=True)
    log_path = install_fake_gh(base / "tracker-shim")
    reset_gh_log(log_path)
    run_decompose(repo, plan, three_way_tickets())
    require(len(read_gh_log(log_path)) > 0, "decompose must emit at least one tracker call")
    reset_gh_log(log_path)
    before = read_ticket_state(repo, "trackerops", "T-1")
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        ticket_state.command_sync_tracker(base_args(repo, plan, pull=True))
    calls_during_pull = read_gh_log(log_path)
    after = read_ticket_state(repo, "trackerops", "T-1")
    require(before == after, "sync-tracker --pull must not mutate local ticket state")
    require(not any("close" in " ".join(call) for call in calls_during_pull), "--pull must never mutate the tracker")
    target = ticket_path(repo, "trackerops", "T-2")
    corrupted = re.sub(r"(?m)^- tracker_ref = .*$", "- tracker_ref = none", target.read_text(encoding="utf-8"))
    target.write_text(corrupted, encoding="utf-8")
    commit_all(repo, "corrupt tracker_ref for self-heal check")
    require(read_ticket_state(repo, "trackerops", "T-2").get("tracker_ref") == "none", "corruption did not take effect")
    reset_gh_log(log_path)
    with contextlib.redirect_stdout(io.StringIO()):
        ticket_state.command_sync_tracker(base_args(repo, plan))
    require(
        bool(read_ticket_state(repo, "trackerops", "T-2").get("tracker_ref")), "missing tracker_ref must be re-linked"
    )
    require(len(read_gh_log(log_path)) > 0, "self-heal must call the tracker adapter")


def check_v1_untouched(base: Path) -> None:
    repo = make_repo(base, "v1-untouched")
    setup_state.seed_receipt_for_fixture(repo)
    slug, plan_id = "classic", "classic-test"
    args = argparse.Namespace(repo=str(repo), feature_slug=slug, plan_id=plan_id)
    plan_state.command_init(args)
    plan = repo / "features" / slug / "PLAN.md"
    require(plan.exists(), "v1: command_init must still create a PLAN.md")
    text = plan.read_text(encoding="utf-8")
    require("state_version = 1" in text or "state_version = 2" in text, "v1: state block must still render")
    require(not (repo / "features" / slug / "tickets").exists(), "v1: init must never create a tickets/ directory")


CASES = (
    ("decompose accept", check_decompose_accept),
    ("decompose reject: state matrix", check_decompose_reject_state),
    ("decompose reject: checkout policy", check_decompose_reject_checkout_policy),
    ("decompose reject: slice partition gap/overlap", check_decompose_reject_partition),
    ("decompose reject: dependency DAG cycle", check_decompose_reject_dag_cycle),
    ("decompose reject: uncovered acceptance ordinal", check_decompose_reject_uncovered_acceptance),
    ("dry-run threshold matrix (0/2/3, touches-overlap flip)", check_dry_run_threshold_matrix),
    ("amend additive-accept + frozen-change-reject", check_amend),
    ("reconcile preview/apply survive-cancel matrix", check_reconcile_matrix),
    ("epic green gate", check_epic_green_gate),
    ("concurrent claim race: exactly one winner", check_concurrent_claim_race),
    ("dependency gating + --next ordering", check_dependency_gating_and_next),
    ("ticket checkpoint contiguity + release semantics", check_ticket_checkpoint_and_release),
    ("forged/invalid ticket states fail loud", check_invalid_and_forged_states),
    ("shipped ticket worktree cleanup", check_release_shipped_cleanup),
    ("tracker ops emitted + sync-tracker --pull report-only", check_tracker_ops_and_pull),
    ("v1 plans untouched", check_v1_untouched),
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ticket-state-check-") as raw_base:
        base = Path(raw_base)
        for label, case in CASES:
            try:
                case(base)
            except SystemExit as error:
                print(f"FAIL [{label}]: {error}", file=sys.stderr)
                return 1
            except Exception as error:
                print(f"FAIL [{label}]: unexpected {type(error).__name__}: {error}", file=sys.stderr)
                return 1
    print("ticket-state regression: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
