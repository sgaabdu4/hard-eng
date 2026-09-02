#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import execution_direct
from evidence_lib import (
    AUTONOMOUS_DIRECTIVE,
    EXACT_APPROVAL_KINDS,
    FINGERPRINT,
    STOP_BEFORE,
    EvidenceError,
    enforcement_configured,
    fail,
    git_value,
    invalidate_direct_receipt,
    load_receipt,
    plan_id,
    plan_path,
    receipt_path,
    repo_path,
    require_digest,
    safe_receipt_json,
    text_digest,
    utc_now,
    utc_text,
)
from safe_plan_io import consume_if_unchanged


def validate_research(repo: Path, plan: Path) -> dict[str, object]:
    value, _, _ = load_receipt(repo, plan, "research.json")
    if value.get("schema_version") != 1 or value.get("plan_id") != plan_id(plan):
        fail("research receipt does not match the active PLAN")
    scope = value.get("scope")
    sources = value.get("sources")
    if scope not in {"local", "external"} or not isinstance(sources, list) or not sources:
        fail("research receipt requires local or external sources")
    if not all(isinstance(item, str) and item for item in sources):
        fail("research sources must be nonempty strings")
    versions = value.get("source_versions")
    if not isinstance(versions, list) or len(versions) != len(sources):
        fail("research requires one source version for each source")
    if not all(isinstance(item, str) and item for item in versions):
        fail("research source versions must be nonempty strings")
    if scope == "external" and not all(str(item).startswith("https://") for item in sources):
        fail("external research requires HTTPS primary sources")
    if scope == "local":
        for item, version in zip(sources, versions, strict=True):
            raw = Path(str(item))
            if raw.is_absolute() or ".." in raw.parts:
                fail("local research sources must be repository-relative")
            path = (repo / raw).resolve()
            try:
                path.relative_to(repo)
            except ValueError:
                fail("local research source escaped the repository")
            if not path.is_file() or path.is_symlink():
                fail(f"local research source is missing: {item}")
            current = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            if version != current:
                fail(f"local research source changed: {item}")
    for key in ("question", "decision", "checked_at", "fresh_until", "repository_head"):
        if not isinstance(value.get(key), str) or not value[key]:
            fail(f"research receipt requires {key}")
    try:
        checked_at = date.fromisoformat(str(value["checked_at"]))
        fresh_until = date.fromisoformat(str(value["fresh_until"]))
    except ValueError:
        fail("research dates must use YYYY-MM-DD")
    if checked_at > utc_now().date() or utc_now().date() > fresh_until:
        fail("research receipt is not current; re-run execution_evidence.py record-research")
    verified = value.get("verified")
    if not isinstance(verified, list) or not verified or not all(isinstance(item, str) and item for item in verified):
        fail("research receipt requires at least one verified result")
    unknown = value.get("unknown")
    if not isinstance(unknown, list) or not all(isinstance(item, str) and item for item in unknown):
        fail("research receipt requires an explicit unknown list")
    return value


def command_record_research(args: argparse.Namespace) -> None:
    repo = repo_path(args.repo)
    plan = plan_path(repo, args.plan)
    sources = list(dict.fromkeys(args.source))
    try:
        fresh_until = date.fromisoformat(args.fresh_until)
    except ValueError:
        fail("fresh-until must use YYYY-MM-DD")
    if fresh_until < utc_now().date():
        fail("research freshness cannot already be expired")
    if args.scope == "external" and not all(item.startswith("https://") for item in sources):
        fail("external research requires HTTPS primary sources")
    if args.scope == "external" and len(args.source_version) != len(sources):
        fail("external research requires one source-version per source")
    versions = args.source_version
    if args.scope == "local":
        versions = []
        for item in sources:
            raw = Path(item)
            if raw.is_absolute() or ".." in raw.parts:
                fail(f"local research source is invalid: {item}")
            path = (repo / raw).resolve()
            if not path.exists() or repo not in (path, *path.parents):
                fail(f"local research source is invalid: {item}")
            if not path.is_file():
                fail(f"local research source must be a file: {item}")
            versions.append("sha256:" + hashlib.sha256(path.read_bytes()).hexdigest())
    try:
        head = git_value(repo, "rev-parse", "--verify", "HEAD")
    except EvidenceError:
        head = "unborn"
    value: dict[str, object] = {
        "checked_at": utc_now().date().isoformat(),
        "decision": args.decision.strip(),
        "fresh_until": fresh_until.isoformat(),
        "inferred": args.inferred,
        "plan_id": plan_id(plan),
        "question": args.question.strip(),
        "repository_head": head,
        "schema_version": 1,
        "scope": args.scope,
        "sources": sources,
        "source_versions": versions,
        "unknown": [] if args.unknown == ["none"] else args.unknown,
        "verified": args.verified,
    }
    if not value["question"] or not value["decision"] or not sources or not args.verified:
        fail("research requires question, decision, source, and verified result")
    safe_receipt_json(repo, receipt_path(plan, "research.json"), value)
    print(f"research-evidence: PASS plan={plan} scope={args.scope}")


def allowed_actions(values: list[str], *, standard: bool = False) -> list[str]:
    actions = list(dict.fromkeys(item.strip() for item in values if item.strip()))
    if not actions or any(not re.fullmatch(r"[a-z0-9][a-z0-9._:/@+-]{1,159}", item) for item in actions):
        fail("authorization requires a narrow explicit allowed-action list")
    if standard and "approved-build" not in actions:
        fail("Ready-to-build authorization must include approved-build")
    if standard and not set(actions) <= {"approved-build", "parallel-subagents"}:
        fail("standard authorization contains an action outside its exact challenge")
    return actions


def string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        fail(f"{label} must be a string list")
    return value


def authorize_execution(repo: Path, plan: Path, fingerprint: str, reply: str, requested_actions: list[str]) -> str:
    if enforcement_configured(repo):
        validate_research(repo, plan)
    require_digest(fingerprint, "approved PLAN fingerprint")
    reply = reply.strip()
    if not reply:
        fail("Ready-to-build approval requires the user's literal reply")
    if reply == AUTONOMOUS_DIRECTIVE:
        mode = "autonomous"
        allowed = allowed_actions(requested_actions)
    else:
        mode = "standard"
        allowed = allowed_actions(["approved-build", *requested_actions], standard=True)
    value: dict[str, object] = {
        "allowed": allowed,
        "approval_digest": text_digest(reply),
        "approved_at": utc_text(utc_now()),
        "effect": "build the approved Feature Brief",
        "mode": mode,
        "plan_fingerprint": fingerprint,
        "plan_id": plan_id(plan),
        "schema_version": 2,
        "stop_before": STOP_BEFORE,
        "target": plan_id(plan),
    }
    safe_receipt_json(repo, receipt_path(plan, "authorization.json"), value)
    invalidate_direct_receipt(repo)
    return mode


def command_authorize(args: argparse.Namespace) -> None:
    repo = repo_path(args.repo)
    plan = plan_path(repo, args.plan)
    mode = authorize_execution(repo, plan, args.fingerprint, args.approval_reply, args.allowed_action)
    print(f"execution-authorization: PASS plan={plan} mode={mode}")


def validate_execution(repo: Path, plan: Path, fingerprint: str) -> str:
    if enforcement_configured(repo):
        validate_research(repo, plan)
    value, _, _ = load_receipt(repo, plan, "authorization.json")
    if value.get("schema_version") != 2 or value.get("plan_id") != plan_id(plan):
        fail("authorization receipt does not belong to this Feature Brief")
    if value.get("mode") not in {"standard", "autonomous"}:
        fail("authorization receipt has an invalid mode")
    allowed_actions(
        string_list(value.get("allowed"), "authorization allowed"), standard=value.get("mode") == "standard"
    )
    if not isinstance(value.get("approval_digest"), str) or not FINGERPRINT.fullmatch(str(value["approval_digest"])):
        fail("authorization receipt requires an approval digest")
    if value.get("plan_fingerprint") != fingerprint:
        fail("authorization receipt does not match the approved PLAN fingerprint")
    if value.get("stop_before") != STOP_BEFORE:
        fail("authorization stop boundary drifted")
    return str(value["mode"])


def command_check(args: argparse.Namespace) -> None:
    repo = repo_path(args.repo)
    plan = plan_path(repo, args.plan)
    mode = validate_execution(repo, plan, args.fingerprint or approved_fingerprint(plan))
    print(f"execution-evidence: PASS plan={plan} mode={mode}")


def approved_fingerprint(plan: Path) -> str:
    text = plan.read_text(encoding="utf-8")
    matches = re.findall(r"(?m)^- approval_fingerprint = (sha256:[0-9a-f]{64})$", text)
    if len(matches) != 1 or "- approval_status = approved" not in text:
        fail("protected action requires an approved active PLAN")
    return matches[0]


def command_authorize_protected(args: argparse.Namespace) -> None:
    if args.plan == "direct":
        execution_direct.command_authorize_protected_direct(args)
        return
    repo = repo_path(args.repo)
    plan = plan_path(repo, args.plan)
    fingerprint = approved_fingerprint(plan)
    validate_execution(repo, plan, fingerprint)
    value = execution_direct.protected_receipt(args, plan_fingerprint=fingerprint, plan_id_value=plan_id(plan))
    safe_receipt_json(repo, receipt_path(plan, "protected-action.json"), value)
    print(f"protected-action: PASS plan={plan} kind={args.kind} target={value['target']}")


def command_consume_protected(args: argparse.Namespace) -> None:
    if args.plan == "direct":
        execution_direct.command_consume_protected_direct(args)
        return
    repo = repo_path(args.repo)
    plan = plan_path(repo, args.plan)
    fingerprint = approved_fingerprint(plan)
    validate_execution(repo, plan, fingerprint)
    value, raw, mode = load_receipt(repo, plan, "protected-action.json")
    if not execution_direct.protected_receipt_matches(
        value, args, plan_fingerprint=fingerprint, plan_id_value=plan_id(plan)
    ):
        fail("protected authorization does not match the current action")
    consume_if_unchanged(repo, receipt_path(plan, "protected-action.json").relative_to(repo), raw, mode)
    print("protected-action-consume: PASS")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    research = commands.add_parser("record-research")
    research.add_argument("--repo", required=True)
    research.add_argument("--plan", required=True)
    research.add_argument("--scope", choices=("local", "external"), required=True)
    research.add_argument("--question", required=True)
    research.add_argument("--decision", required=True)
    research.add_argument("--source", action="append", required=True)
    research.add_argument("--verified", action="append", required=True)
    research.add_argument("--inferred", action="append", default=[])
    research.add_argument("--unknown", action="append", required=True)
    research.add_argument("--fresh-until", required=True)
    research.add_argument("--source-version", action="append", default=[])
    research.set_defaults(action=command_record_research)
    protected = commands.add_parser("authorize-protected")
    for argument in ("repo", "plan", "target", "effect", "tool-name", "action-digest", "approval-reply"):
        protected.add_argument(f"--{argument}", required=True)
    protected.add_argument("--kind", choices=EXACT_APPROVAL_KINDS, required=True)
    protected.set_defaults(action=command_authorize_protected)
    consume = commands.add_parser("consume-protected")
    for argument in ("repo", "plan", "tool-name", "action-digest"):
        consume.add_argument(f"--{argument}", required=True)
    consume.add_argument("--kind", choices=EXACT_APPROVAL_KINDS, required=True)
    consume.set_defaults(action=command_consume_protected)
    execution_direct.register(commands)
    authorize = commands.add_parser("authorize")
    for argument in ("repo", "plan", "fingerprint", "approval-reply"):
        authorize.add_argument(f"--{argument}", required=True)
    authorize.add_argument("--allowed-action", action="append", default=[])
    authorize.set_defaults(action=command_authorize)
    check = commands.add_parser("check")
    check.add_argument("--repo", required=True)
    check.add_argument("--plan", required=True)
    check.add_argument("--fingerprint")
    check.set_defaults(action=command_check)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        args.action(args)
    except (EvidenceError, OSError, UnicodeError) as error:
        print(f"execution-evidence: FAIL: {error}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
