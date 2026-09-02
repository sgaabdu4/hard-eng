"""Direct-route receipt commands for Hard Eng execution evidence."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import secrets
import sys
from datetime import date
from pathlib import Path

from evidence_lib import (
    FINGERPRINT,
    STOP_BEFORE,
    EvidenceError,
    action_digest,
    atomic_json,
    direct_receipt_path,
    fail,
    git_private_path,
    load_json,
    protected_binding_digest,
    repo_path,
    repository_context,
    repository_identity,
    repository_relative_path,
    require_digest,
    text_digest,
    utc_now,
    utc_text,
)
from safe_plan_io import consume_if_unchanged, read_snapshot
from skill_source_policy import skill_content_needs_primary_source


def validate_external_actions(value: object) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        fail("direct-route external actions must be a list")
    actions: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != {"action_digest", "effect", "tool_name"}:
            fail("direct-route external actions require tool_name, action_digest, and effect")
        tool_name = entry.get("tool_name")
        digest = entry.get("action_digest")
        effect = entry.get("effect")
        if not isinstance(tool_name, str) or not tool_name or tool_name != tool_name.casefold():
            fail("direct-route external action tool names must be canonical")
        if not isinstance(digest, str) or not FINGERPRINT.fullmatch(digest):
            fail("direct-route external action digest is invalid")
        if (
            not isinstance(effect, str)
            or effect != effect.strip()
            or not effect
            or len(effect) > 500
            or not effect.isprintable()
        ):
            fail("direct-route external action effect must be readable text")
        identity = (tool_name, digest)
        if identity in seen:
            fail("direct-route external action is duplicated")
        seen.add(identity)
        actions.append({"action_digest": digest, "effect": effect, "tool_name": tool_name})
    return actions


def parse_external_actions(values: list[str]) -> list[dict[str, str]]:
    decoded: list[object] = []
    for raw in values:
        try:
            entry = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise EvidenceError("external-action must be a JSON object") from error
        if isinstance(entry, dict) and isinstance(entry.get("tool_name"), str):
            entry = {**entry, "tool_name": entry["tool_name"].casefold()}
        decoded.append(entry)
    return validate_external_actions(decoded)


def validate_direct_receipt(repo: Path, *, value: dict[str, object] | None = None) -> dict[str, object]:
    """Validate the direct route against the repository identity, never a session or request."""
    value = load_json(direct_receipt_path(repo)) if value is None else value
    identity = repository_identity(repo)
    context = value.get("repository_context")
    if (
        value.get("schema_version") != 2
        or value.get("route") != "direct"
        or not isinstance(context, dict)
        or any(context.get(key) != identity[key] for key in ("checkout_digest", "repository_digest"))
        or not isinstance(value.get("created_at"), str)
    ):
        fail("direct-route receipt does not belong to this repository")
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
    validate_external_actions(value.get("external_actions"))
    if value.get("allowed") not in (["reversible-local-work"], ["reversible-local-work", "parallel-subagents"]):
        fail("direct-route receipt has an invalid action scope")
    if value.get("stop_before") != STOP_BEFORE:
        fail("direct-route stop boundary drifted")
    if not isinstance(value.get("write_nonce"), str) or not FINGERPRINT.fullmatch(str(value["write_nonce"])):
        fail("direct-route receipt requires a one-use write nonce")
    for key in ("question", "decision"):
        if not isinstance(value.get(key), str) or not value[key]:
            fail(f"direct-route receipt requires {key}")
    return value


def command_check_direct(args: argparse.Namespace) -> None:
    repo = repo_path(args.repo)
    value = validate_direct_receipt(repo)
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
    validate_direct_receipt(repo, value=value)
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


def protected_receipt(args: argparse.Namespace, *, plan_fingerprint: str, plan_id_value: str) -> dict[str, object]:
    require_digest(args.action_digest, "action digest")
    if not args.target.strip() or not args.effect.strip() or not args.tool_name.strip():
        fail("protected authorization requires exact target, effect, and tool name")
    if not args.approval_reply.strip():
        fail("protected authorization requires the user's literal approval reply")
    value: dict[str, object] = {
        "action_digest": args.action_digest,
        "approval_digest": text_digest(args.approval_reply),
        "approval_kind": args.kind,
        "authorized_at": utc_text(utc_now()),
        "effect": args.effect.strip(),
        "plan_fingerprint": plan_fingerprint,
        "plan_id": plan_id_value,
        "schema_version": 2,
        "status": "authorized",
        "target": args.target.strip(),
        "tool_name": args.tool_name.casefold(),
    }
    value["binding_digest"] = protected_binding_digest(value)
    return value


def protected_receipt_matches(
    value: dict[str, object], args: argparse.Namespace, *, plan_fingerprint: str, plan_id_value: str
) -> bool:
    return (
        value.get("schema_version") == 2
        and value.get("status") == "authorized"
        and value.get("approval_kind") == args.kind
        and value.get("plan_fingerprint") == plan_fingerprint
        and value.get("plan_id") == plan_id_value
        and isinstance(value.get("target"), str)
        and bool(value.get("target"))
        and isinstance(value.get("effect"), str)
        and bool(value.get("effect"))
        and value.get("tool_name") == args.tool_name.casefold()
        and value.get("action_digest") == require_digest(args.action_digest, "action digest")
        and value.get("binding_digest") == protected_binding_digest(value)
    )


def command_authorize_protected_direct(args: argparse.Namespace) -> None:
    repo = repo_path(args.repo)
    value = protected_receipt(args, plan_fingerprint="direct", plan_id_value="direct")
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
    if not protected_receipt_matches(value, args, plan_fingerprint="direct", plan_id_value="direct"):
        fail("protected authorization does not match the current action")
    consume_if_unchanged(path.parent, Path(path.name), raw, mode)
    print("protected-action-consume: PASS")


def command_start_direct(args: argparse.Namespace) -> None:
    repo = repo_path(args.repo)
    intended: list[dict[str, str]] = []
    for item in dict.fromkeys(args.intended_path):
        relative_path = repository_relative_path(repo, item, "direct intended path")
        if not relative_path.parts:
            fail("direct intended path cannot be the whole repository")
        scope = "tree" if item.endswith("/") or (repo / relative_path).is_dir() else "file"
        intended.append({"path": relative_path.as_posix(), "scope": scope})
    if not intended:
        fail("direct route requires at least one intended path")
    external_actions = parse_external_actions(args.external_action)
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
    value: dict[str, object] = {
        "allowed": ["reversible-local-work"] + (["parallel-subagents"] if args.allow_subagents else []),
        "created_at": utc_text(utc_now()),
        "decision": args.decision.strip(),
        "external_actions": external_actions,
        "fresh_until": fresh_until.isoformat(),
        "intended_paths": intended,
        "question": args.question.strip(),
        "repository_context": repository_context(repo),
        "route": "direct",
        "schema_version": 2,
        "scope": args.scope,
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
    direct.add_argument("--external-action", action="append", default=[])
    direct.set_defaults(action=command_start_direct)
    check_direct = commands.add_parser("check-direct")
    check_direct.add_argument("--repo", required=True)
    check_direct.set_defaults(action=command_check_direct)
    consume_direct = commands.add_parser("consume-direct")
    consume_direct.add_argument("--repo", required=True)
    consume_direct.add_argument("--write-nonce", required=True)
    consume_direct.set_defaults(action=command_consume_direct)
    digest = commands.add_parser("action-digest")
    digest.add_argument("--tool-name", required=True)
    digest.set_defaults(action=command_action_digest)
