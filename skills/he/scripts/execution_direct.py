"""Direct-route receipt commands for Hard Eng execution evidence."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import secrets
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from evidence_lib import (
    FINGERPRINT,
    STOP_BEFORE,
    EvidenceError,
    action_digest,
    atomic_json,
    direct_receipt_path,
    expiry,
    fail,
    git_private_path,
    load_json,
    protected_binding_digest,
    repo_path,
    repository_context,
    repository_relative_path,
    require_digest,
    require_session,
    text_digest,
    utc_now,
    utc_text,
)
from safe_plan_io import consume_if_unchanged, read_snapshot
from skill_source_policy import skill_content_needs_primary_source


def validate_direct_receipt(
    repo: Path, session_id: str, request_digest: str, *, value: dict[str, object] | None = None
) -> dict[str, object]:
    """Validate the direct route with the same identity owner used for approvals."""
    if not session_id.strip():
        fail("direct route requires a runtime session id")
    require_digest(request_digest, "request digest")
    value = load_json(direct_receipt_path(repo)) if value is None else value
    today = utc_now().date()
    created_text = value.get("created_at")
    expires_text = value.get("expires_at")
    expires_epoch = value.get("expires_at_epoch")
    if (
        value.get("schema_version") != 2
        or value.get("route") != "direct"
        or value.get("session_digest") != text_digest(session_id)
        or value.get("request_digest") != request_digest
        or value.get("repository_context") != repository_context(repo)
        or not isinstance(created_text, str)
        or not isinstance(expires_text, str)
        or value.get("checked_at") != created_text[:10]
        or not isinstance(expires_epoch, int)
        or expires_epoch < int(time.time())
    ):
        fail("direct-route receipt does not match the current task and repository state")
    try:
        created = datetime.fromisoformat(created_text.replace("Z", "+00:00"))
        expires = datetime.fromisoformat(expires_text.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvidenceError("direct-route receipt timestamps are invalid") from error
    if created.tzinfo is None or expires.tzinfo is None or expires <= created:
        fail("direct-route receipt timestamps must be absolute UTC values")
    if expires.timestamp() != expires_epoch or today > expires.date():
        fail("direct-route receipt has expired")
    if value.get("checked_at") != today.isoformat() and today > expires.date():
        fail("direct-route receipt has expired")
    sources = value.get("sources")
    versions = value.get("source_versions")
    if (
        not isinstance(sources, list)
        or not sources
        or not all(isinstance(item, str) and item for item in sources)
        or not isinstance(versions, list)
        or len(versions) != len(sources)
        or not all(isinstance(item, str) and item for item in versions)
    ):
        fail("direct-route receipt requires source versions")
    if value.get("scope") == "external":
        if not all(item.startswith("https://") for item in sources):
            fail("external direct research requires HTTPS primary sources")
    elif value.get("scope") == "local":
        for item, version in zip(sources, versions, strict=True):
            relative = repository_relative_path(repo, item, "local direct research source")
            path = repo / relative
            if not path.is_file() or path.is_symlink():
                fail(f"local direct research source is invalid: {item}")
            current = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            if version != current:
                fail(f"local direct research source changed: {item}")
    else:
        fail("direct-route receipt has an invalid research scope")
    intended = value.get("intended_paths")
    if not isinstance(intended, list) or not intended:
        fail("direct-route receipt requires intended paths")
    skill_gap = skill_content_needs_primary_source(
        [str(entry.get("path", "")) for entry in intended if isinstance(entry, dict)],
        str(value.get("scope", "")),
        [item for item in sources if isinstance(item, str)],
    )
    if skill_gap:
        fail(skill_gap)
    for entry in intended:
        if not isinstance(entry, dict):
            fail("direct-route intended paths must be objects")
        relative = repository_relative_path(repo, str(entry.get("path", "")), "direct intended path")
        if str(entry.get("path")) != relative.as_posix():
            fail("direct-route intended path is not canonical")
        if entry.get("scope") not in {"file", "tree"}:
            fail("direct-route intended path has an invalid scope")
    if value.get("allowed") not in (["reversible-local-work"], ["reversible-local-work", "parallel-subagents"]):
        fail("direct-route receipt has an invalid action scope")
    if value.get("stop_before") != STOP_BEFORE:
        fail("direct-route stop boundary drifted")
    if not isinstance(value.get("write_nonce"), str) or not FINGERPRINT.fullmatch(str(value["write_nonce"])):
        fail("direct-route receipt requires a one-use write nonce")
    for key in ("question", "decision", "repository_head"):
        if not isinstance(value.get(key), str) or not value[key]:
            fail(f"direct-route receipt requires {key}")
    return value


def command_check_direct(args: argparse.Namespace) -> None:
    repo = repo_path(args.repo)
    value = validate_direct_receipt(repo, args.session_id, args.request_digest)
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))


def command_consume_direct(args: argparse.Namespace) -> None:
    repo = repo_path(args.repo)
    path = direct_receipt_path(repo)
    raw, mode = read_snapshot(path.parent, Path(path.name))
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise EvidenceError("direct-route receipt is invalid") from error
    if not isinstance(value, dict):
        fail("direct-route receipt is invalid")
    validate_direct_receipt(repo, args.session_id, args.request_digest, value=value)
    if not hmac.compare_digest(str(value["write_nonce"]), args.write_nonce):
        fail("direct-route write nonce does not match")
    consume_if_unchanged(path.parent, Path(path.name), raw, mode)
    print("direct-route-consume: PASS")


def protected_direct_path(repo: Path) -> Path:
    return git_private_path(repo, "protected-action.json")


def command_action_digest(args: argparse.Namespace) -> None:
    raw = sys.stdin.read()
    try:
        tool_input = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise EvidenceError("action-digest requires the exact tool_input as JSON on stdin") from error
    if not isinstance(tool_input, dict):
        fail("action-digest requires a JSON object tool_input")
    print(action_digest(args.tool_name, tool_input))


def command_authorize_protected_direct(args: argparse.Namespace) -> None:
    repo = repo_path(args.repo)
    session_digest = require_session(args.session_id)
    require_digest(args.request_digest, "request digest")
    require_digest(args.action_digest, "action digest")
    if not args.target.strip() or not args.effect.strip() or not args.tool_name.strip():
        fail("protected authorization requires exact target, effect, and tool name")
    if not args.approval_reply.strip():
        fail("protected authorization requires the user's literal approval reply")
    created, expires = expiry(args.expires_in_seconds)
    value: dict[str, object] = {
        "action_digest": args.action_digest,
        "approval_digest": text_digest(args.approval_reply),
        "approval_kind": args.kind,
        "authorized_at": utc_text(created),
        "challenge_id": "direct",
        "effect": args.effect.strip(),
        "expires_at": utc_text(expires),
        "expires_at_epoch": int(expires.timestamp()),
        "max_material_spend": "none",
        "plan_fingerprint": "direct",
        "plan_id": "direct",
        "repository_context": repository_context(repo),
        "request_digest": args.request_digest,
        "schema_version": 2,
        "session_digest": session_digest,
        "status": "authorized",
        "target": args.target.strip(),
        "tool_name": args.tool_name.casefold(),
    }
    value["binding_digest"] = protected_binding_digest(value)
    atomic_json(protected_direct_path(repo), value)
    print(f"protected-action: PASS plan=direct kind={args.kind} target={value['target']}")


def command_consume_protected_direct(args: argparse.Namespace) -> None:
    repo = repo_path(args.repo)
    path = protected_direct_path(repo)
    raw, mode = read_snapshot(path.parent, Path(path.name))
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise EvidenceError("direct protected authorization is invalid") from error
    if not isinstance(value, dict):
        fail("direct protected authorization is invalid")
    protected_expiry = value.get("expires_at_epoch")
    stored_request = value.get("request_digest")
    valid = (
        value.get("schema_version") == 2
        and value.get("status") == "authorized"
        and value.get("approval_kind") == args.kind
        and value.get("plan_fingerprint") == "direct"
        and value.get("plan_id") == "direct"
        and value.get("session_digest") == require_session(args.session_id)
        and isinstance(stored_request, str)
        and bool(FINGERPRINT.fullmatch(stored_request))
        and isinstance(value.get("target"), str)
        and bool(value.get("target"))
        and isinstance(value.get("effect"), str)
        and bool(value.get("effect"))
        and isinstance(value.get("tool_name"), str)
        and value.get("tool_name") == args.tool_name.casefold()
        and value.get("action_digest") == require_digest(args.action_digest, "action digest")
        and value.get("repository_context") == repository_context(repo)
        and value.get("binding_digest") == protected_binding_digest(value)
        and isinstance(protected_expiry, int)
        and protected_expiry >= int(time.time())
    )
    if valid and args.request_digest:
        valid = stored_request == require_digest(args.request_digest, "request digest")
    if not valid:
        fail("protected authorization does not match the current action and state")
    consume_if_unchanged(path.parent, Path(path.name), raw, mode)
    print("protected-action-consume: PASS")


def command_start_direct(args: argparse.Namespace) -> None:
    repo = repo_path(args.repo)
    if not args.session_id.strip():
        fail("direct route requires a runtime session id")
    require_digest(args.request_digest, "request digest")
    intended: list[dict[str, str]] = []
    for item in dict.fromkeys(args.intended_path):
        relative_path = repository_relative_path(repo, item, "direct intended path")
        if not relative_path.parts:
            fail("direct intended path cannot be the whole repository")
        scope = "tree" if item.endswith("/") or (repo / relative_path).is_dir() else "file"
        intended.append({"path": relative_path.as_posix(), "scope": scope})
    if not intended:
        fail("direct route requires at least one intended path")
    sources = list(dict.fromkeys(args.source))
    skill_gap = skill_content_needs_primary_source([entry["path"] for entry in intended], args.scope, sources)
    if skill_gap:
        fail(skill_gap)
    try:
        fresh_until = date.fromisoformat(args.fresh_until)
    except ValueError:
        fail("fresh-until must use YYYY-MM-DD")
    if fresh_until < utc_now().date():
        fail("direct research freshness cannot already be expired")
    if args.scope == "external":
        if not all(item.startswith("https://") for item in sources):
            fail("external direct research requires HTTPS primary sources")
        if len(args.source_version) != len(sources):
            fail("external direct research requires one source-version per source")
        versions = args.source_version
    else:
        versions = []
        for item in sources:
            relative = repository_relative_path(repo, item, "local direct research source")
            path = repo / relative
            if not path.is_file() or path.is_symlink():
                fail(f"local direct research source is invalid: {item}")
            versions.append("sha256:" + hashlib.sha256(path.read_bytes()).hexdigest())
    if not sources or not args.verified or not args.question.strip() or not args.decision.strip():
        fail("direct route requires question, decision, source, and verified result")
    created = utc_now()
    expires = datetime.combine(fresh_until, datetime.max.time().replace(tzinfo=timezone.utc))
    if expires <= created:
        fail("direct route freshness must extend beyond the current time")
    session_digest = "sha256:" + hashlib.sha256(args.session_id.encode("utf-8")).hexdigest()
    context = repository_context(repo)
    value: dict[str, object] = {
        "allowed": ["reversible-local-work"] + (["parallel-subagents"] if args.allow_subagents else []),
        "checked_at": created.date().isoformat(),
        "created_at": utc_text(created),
        "decision": args.decision.strip(),
        "expires_at": utc_text(expires),
        "expires_at_epoch": int(expires.timestamp()),
        "fresh_until": fresh_until.isoformat(),
        "intended_paths": intended,
        "question": args.question.strip(),
        "request_digest": args.request_digest,
        "repository_context": context,
        "repository_head": context["repository_head"],
        "route": "direct",
        "schema_version": 2,
        "scope": args.scope,
        "session_digest": session_digest,
        "source_versions": versions,
        "sources": sources,
        "stop_before": STOP_BEFORE,
        "unknown": [] if args.unknown == ["none"] else args.unknown,
        "verified": args.verified,
        "write_nonce": "sha256:" + secrets.token_hex(32),
    }
    atomic_json(direct_receipt_path(repo), value)
    print(f"direct-route: PASS repo={repo} paths={len(intended)}")


def register(commands: argparse._SubParsersAction) -> None:
    direct = commands.add_parser("start-direct")
    direct.add_argument("--repo", required=True)
    direct.add_argument("--session-id", required=True)
    direct.add_argument("--request-digest", required=True)
    direct.add_argument("--intended-path", action="append", required=True)
    direct.add_argument("--scope", choices=("local", "external"), required=True)
    direct.add_argument("--question", required=True)
    direct.add_argument("--decision", required=True)
    direct.add_argument("--source", action="append", required=True)
    direct.add_argument("--source-version", action="append", default=[])
    direct.add_argument("--verified", action="append", required=True)
    direct.add_argument("--unknown", action="append", required=True)
    direct.add_argument("--fresh-until", required=True)
    direct.add_argument("--allow-subagents", action="store_true")
    direct.set_defaults(action=command_start_direct)
    check_direct = commands.add_parser("check-direct")
    check_direct.add_argument("--repo", required=True)
    check_direct.add_argument("--session-id", required=True)
    check_direct.add_argument("--request-digest", required=True)
    check_direct.set_defaults(action=command_check_direct)
    consume_direct = commands.add_parser("consume-direct")
    consume_direct.add_argument("--repo", required=True)
    consume_direct.add_argument("--session-id", required=True)
    consume_direct.add_argument("--request-digest", required=True)
    consume_direct.add_argument("--write-nonce", required=True)
    consume_direct.set_defaults(action=command_consume_direct)
    digest = commands.add_parser("action-digest")
    digest.add_argument("--tool-name", required=True)
    digest.set_defaults(action=command_action_digest)
