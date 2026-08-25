#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import re
import secrets
import sys
import time
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import execution_direct
from evidence_lib import (
    APPROVAL_RESPONSE,
    AUTONOMOUS_DIRECTIVE,
    DEFAULT_CHALLENGE_SECONDS,
    EXACT_APPROVAL_KINDS,
    FINGERPRINT,
    MAX_CHALLENGE_SECONDS,
    STOP_BEFORE,
    EvidenceError,
    action_digest,
    enforcement_configured,
    expiry,
    fail,
    git_value,
    json_bytes,
    load_receipt,
    plan_id,
    plan_path,
    protected_binding_digest,
    receipt_path,
    repo_path,
    repository_context,
    repository_identity,
    require_digest,
    require_session,
    safe_receipt_json,
    text_digest,
    utc_now,
    utc_text,
)
from plan_sections import PlanError, frozen_fingerprint, parse_sections
from safe_plan_io import consume_if_unchanged, replace_if_unchanged


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
    if value["repository_head"] != repository_identity(repo)["repository_head"]:
        fail(
            "research receipt does not match the current repository HEAD; "
            "re-run execution_evidence.py record-research on the current tree"
        )
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


def create_challenge(
    repo: Path,
    plan: Path,
    *,
    name: str,
    fingerprint: str,
    session_id: str,
    request_digest: str,
    approval_kind: str,
    target: str,
    effect: str,
    tool_name: str,
    action_digest_value: str,
    allowed: list[str],
    max_material_spend: str,
    expires_in_seconds: int,
) -> str:
    validate_research(repo, plan)
    require_digest(fingerprint, "PLAN fingerprint")
    require_digest(request_digest, "request digest")
    if not target.strip() or not effect.strip() or not tool_name.strip():
        fail("challenge requires exact target, effect, and tool name")
    created, expires = expiry(expires_in_seconds)
    challenge_id = secrets.token_hex(3).upper()
    response = f"APPROVE {challenge_id}"
    require_digest(action_digest_value, "action digest")
    value: dict[str, object] = {
        "action_digest": action_digest_value,
        "allowed": allowed,
        "approval_kind": approval_kind,
        "challenge_id": challenge_id,
        "created_at": utc_text(created),
        "effect": effect.strip(),
        "expires_at": utc_text(expires),
        "expires_at_epoch": int(expires.timestamp()),
        "max_material_spend": max_material_spend.strip() or "none",
        "plan_fingerprint": fingerprint,
        "plan_id": plan_id(plan),
        "repository_context": repository_context(repo),
        "request_digest": request_digest,
        "response_digest": text_digest(response),
        "schema_version": 2,
        "session_digest": require_session(session_id),
        "status": "pending",
        "target": target.strip(),
        "tool_name": tool_name.casefold(),
    }
    safe_receipt_json(repo, receipt_path(plan, name), value)
    print(f"action={value['effect']} target={value['target']} tool={value['tool_name']}")
    print(f"expires_at={value['expires_at']}")
    print(f"response={response}")
    return response


def consume_challenge(
    repo: Path,
    plan: Path,
    *,
    name: str,
    reply: str,
    fingerprint: str,
    session_id: str,
    request_digest: str,
    expected_kind: str,
    expected_target: str,
    expected_effect: str,
    tool_name: str,
    expected_action_digest: str,
) -> dict[str, object]:
    value, raw, mode = load_receipt(repo, plan, name)
    challenge_expiry = value.get("expires_at_epoch")
    checks = (
        ("schema_version", value.get("schema_version") == 2),
        ("status", value.get("status") == "pending"),
        ("plan_id", value.get("plan_id") == plan_id(plan)),
        ("plan_fingerprint", value.get("plan_fingerprint") == fingerprint),
        ("session", value.get("session_digest") == require_session(session_id)),
        ("request_digest", value.get("request_digest") == require_digest(request_digest, "request digest")),
        ("approval_kind", value.get("approval_kind") == expected_kind),
        ("target", value.get("target") == expected_target),
        ("effect", value.get("effect") == expected_effect),
        ("tool_name", value.get("tool_name") == tool_name.casefold()),
        ("action_digest", value.get("action_digest") == require_digest(expected_action_digest, "action digest")),
        ("repository_context", value.get("repository_context") == repository_context(repo)),
        ("expiry", isinstance(challenge_expiry, int) and challenge_expiry >= int(time.time())),
    )
    failed = [check for check, passed in checks if not passed]
    if failed:
        fail(
            "approval challenge is expired or does not match the current action and state "
            f"(failed: {', '.join(failed)}; plan_fingerprint means the brief changed after the code was issued — reissue and re-ask)"
        )
    canonical = f"APPROVE {value.get('challenge_id', '')}"
    if not APPROVAL_RESPONSE.fullmatch(reply) or not hmac.compare_digest(reply, canonical):
        fail("approval response must exactly match the current challenge")
    if value.get("response_digest") != text_digest(reply):
        fail("approval challenge response digest does not match")
    consume_if_unchanged(repo, receipt_path(plan, name).relative_to(repo), raw, mode)
    return value


def authorize_execution(
    repo: Path,
    plan: Path,
    fingerprint: str,
    reply: str,
    session_id: str,
    request_digest: str,
    requested_actions: list[str],
    expires_in_seconds: int = MAX_CHALLENGE_SECONDS,
) -> str:
    if enforcement_configured(repo):
        validate_research(repo, plan)
    require_digest(fingerprint, "approved PLAN fingerprint")
    require_digest(request_digest, "request digest")
    reply = reply.strip()
    if reply == AUTONOMOUS_DIRECTIVE:
        mode = "autonomous"
        allowed = allowed_actions(requested_actions)
        created, expires = expiry(expires_in_seconds)
        challenge_id = "current-task-autonomous"
        target = plan_id(plan)
        effect = "build the approved Feature Brief within the recorded action scope"
    else:
        mode = "standard"
        challenge = consume_challenge(
            repo,
            plan,
            name="approval-challenge.json",
            reply=reply,
            fingerprint=fingerprint,
            session_id=session_id,
            request_digest=request_digest,
            expected_kind="ready-to-build",
            expected_target=plan_id(plan),
            expected_effect="build the approved Feature Brief",
            tool_name="plan_state.approve",
            expected_action_digest=action_digest("plan_state.approve", {"fingerprint": fingerprint}),
        )
        allowed = allowed_actions(string_list(challenge.get("allowed"), "challenge allowed"), standard=True)
        created, expires = expiry(expires_in_seconds)
        challenge_id = str(challenge["challenge_id"])
        target = str(challenge["target"])
        effect = str(challenge["effect"])
    value: dict[str, object] = {
        "allowed": allowed,
        "approval_digest": text_digest(reply),
        "challenge_id": challenge_id,
        "created_at": utc_text(created),
        "effect": effect,
        "expires_at": utc_text(expires),
        "expires_at_epoch": int(expires.timestamp()),
        "mode": mode,
        "plan_fingerprint": fingerprint,
        "plan_id": plan_id(plan),
        "repository_context": repository_context(repo),
        "request_digest": request_digest,
        "schema_version": 2,
        "session_digest": require_session(session_id),
        "stop_before": STOP_BEFORE,
        "target": target,
    }
    safe_receipt_json(repo, receipt_path(plan, "authorization.json"), value)
    return mode


def command_authorize(args: argparse.Namespace) -> None:
    repo = repo_path(args.repo)
    plan = plan_path(repo, args.plan)
    mode = authorize_execution(
        repo,
        plan,
        args.fingerprint,
        args.approval_reply,
        args.session_id,
        args.request_digest,
        args.allowed_action,
        args.expires_in_seconds,
    )
    print(f"execution-authorization: PASS plan={plan} mode={mode}")


def validate_execution(
    repo: Path,
    plan: Path,
    fingerprint: str,
    session_id: str,
    request_digest: str,
    *,
    allow_repository_drift: bool = False,
    allow_head_drift: bool = False,
) -> str:
    if enforcement_configured(repo):
        validate_research(repo, plan)
    value, _, _ = load_receipt(repo, plan, "authorization.json")
    if value.get("schema_version") != 2 or value.get("plan_id") != plan_id(plan):
        fail("authorization receipt requires a new exact current-task authorization")
    if value.get("mode") not in {"standard", "autonomous"}:
        fail("authorization receipt has an invalid mode")
    allowed_actions(
        string_list(value.get("allowed"), "authorization allowed"), standard=value.get("mode") == "standard"
    )
    if not isinstance(value.get("approval_digest"), str) or not FINGERPRINT.fullmatch(str(value["approval_digest"])):
        fail("authorization receipt requires an approval digest")
    if value.get("plan_fingerprint") != fingerprint:
        fail("authorization receipt does not match the approved PLAN fingerprint")
    if value.get("session_digest") != require_session(session_id):
        fail("authorization receipt does not match the current session")
    if value.get("request_digest") != require_digest(request_digest, "request digest"):
        fail("authorization receipt does not match the current request")
    stored_context = value.get("repository_context")
    current_context = repository_context(repo)
    if not isinstance(stored_context, dict):
        fail("authorization receipt has invalid repository identity")
    if allow_repository_drift:
        immutable_keys = ["checkout_digest", "repository_digest"]
        if not allow_head_drift:
            immutable_keys.append("repository_head")
        immutable_context = {key: current_context[key] for key in immutable_keys}
        if any(stored_context.get(key) != item for key, item in immutable_context.items()):
            fail("authorization receipt does not match the current repository identity")
    elif stored_context != current_context:
        fail("authorization receipt does not match the current repository state")
    authorization_expiry = value.get("expires_at_epoch")
    if not isinstance(authorization_expiry, int) or authorization_expiry < int(time.time()):
        fail("authorization receipt expired")
    if value.get("stop_before") != STOP_BEFORE:
        fail("authorization stop boundary drifted")
    return str(value["mode"])


def refresh_execution_state(repo: Path, plan: Path, fingerprint: str, session_id: str, request_digest: str) -> None:
    validate_execution(
        repo, plan, fingerprint, session_id, request_digest, allow_repository_drift=True, allow_head_drift=True
    )
    value, raw, mode = load_receipt(repo, plan, "authorization.json")
    authorization_expiry = value.get("expires_at_epoch")
    if (
        value.get("schema_version") != 2
        or value.get("plan_id") != plan_id(plan)
        or value.get("plan_fingerprint") != fingerprint
        or not isinstance(authorization_expiry, int)
        or authorization_expiry < int(time.time())
    ):
        fail("authorization receipt cannot be refreshed for the current plan")
    value["repository_context"] = repository_context(repo)
    value["state_refreshed_at"] = utc_text(utc_now())
    replace_if_unchanged(repo, receipt_path(plan, "authorization.json").relative_to(repo), raw, mode, json_bytes(value))


def command_check(args: argparse.Namespace) -> None:
    repo = repo_path(args.repo)
    plan = plan_path(repo, args.plan)
    mode = validate_execution(
        repo,
        plan,
        args.fingerprint,
        args.session_id,
        args.request_digest,
        allow_repository_drift=args.allow_repository_drift,
    )
    print(f"execution-evidence: PASS plan={plan} mode={mode}")


def require_current_brief_fingerprint(plan: Path, fingerprint: str) -> None:
    try:
        current = frozen_fingerprint(parse_sections(plan.read_text(encoding="utf-8")))
    except PlanError as error:
        fail(f"Feature Brief is not approval-ready: {error}")
    if fingerprint != current:
        fail(
            f"PLAN fingerprint {fingerprint} does not match the current brief fingerprint {current}; "
            "take brief_fingerprint from plan_state.py inspect and reissue before showing the user a code"
        )


def command_challenge_ready(args: argparse.Namespace) -> None:
    repo = repo_path(args.repo)
    plan = plan_path(repo, args.plan)
    require_current_brief_fingerprint(plan, args.fingerprint)
    create_challenge(
        repo,
        plan,
        name="approval-challenge.json",
        fingerprint=args.fingerprint,
        session_id=args.session_id,
        request_digest=args.request_digest,
        approval_kind="ready-to-build",
        target=plan_id(plan),
        effect="build the approved Feature Brief",
        tool_name="plan_state.approve",
        action_digest_value=action_digest("plan_state.approve", {"fingerprint": args.fingerprint}),
        allowed=allowed_actions(args.allowed_action, standard=True),
        max_material_spend="none",
        expires_in_seconds=args.expires_in_seconds,
    )


def approved_fingerprint(plan: Path) -> str:
    text = plan.read_text(encoding="utf-8")
    matches = re.findall(r"(?m)^- approval_fingerprint = (sha256:[0-9a-f]{64})$", text)
    if len(matches) != 1 or "- approval_status = approved" not in text:
        fail("protected action requires an approved active PLAN")
    return matches[0]


def command_challenge_protected(args: argparse.Namespace) -> None:
    if args.plan == "direct":
        fail(
            "the direct route records the user's plain yes without a challenge code; "
            "run authorize-protected --plan direct --approval-reply '<their literal reply>'"
        )
    repo = repo_path(args.repo)
    plan = plan_path(repo, args.plan)
    fingerprint = approved_fingerprint(plan)
    validate_execution(repo, plan, fingerprint, args.session_id, args.request_digest)
    create_challenge(
        repo,
        plan,
        name="protected-challenge.json",
        fingerprint=fingerprint,
        session_id=args.session_id,
        request_digest=args.request_digest,
        approval_kind=args.kind,
        target=args.target,
        effect=args.effect,
        tool_name=args.tool_name,
        action_digest_value=args.action_digest,
        allowed=[args.kind],
        max_material_spend=args.max_material_spend,
        expires_in_seconds=args.expires_in_seconds,
    )


def command_authorize_protected(args: argparse.Namespace) -> None:
    if args.plan == "direct":
        execution_direct.command_authorize_protected_direct(args)
        return
    repo = repo_path(args.repo)
    plan = plan_path(repo, args.plan)
    fingerprint = approved_fingerprint(plan)
    validate_execution(repo, plan, fingerprint, args.session_id, args.request_digest)
    challenge = consume_challenge(
        repo,
        plan,
        name="protected-challenge.json",
        reply=args.approval_reply,
        fingerprint=fingerprint,
        session_id=args.session_id,
        request_digest=args.request_digest,
        expected_kind=args.kind,
        expected_target=args.target,
        expected_effect=args.effect,
        tool_name=args.tool_name,
        expected_action_digest=args.action_digest,
    )
    value: dict[str, object] = {
        key: challenge[key]
        for key in (
            "action_digest",
            "approval_kind",
            "challenge_id",
            "effect",
            "expires_at",
            "expires_at_epoch",
            "max_material_spend",
            "plan_fingerprint",
            "plan_id",
            "repository_context",
            "request_digest",
            "session_digest",
            "target",
            "tool_name",
        )
    }
    value.update(
        {
            "approval_digest": text_digest(args.approval_reply),
            "authorized_at": utc_text(utc_now()),
            "binding_digest": protected_binding_digest(value),
            "schema_version": 2,
            "status": "authorized",
        }
    )
    safe_receipt_json(repo, receipt_path(plan, "protected-action.json"), value)
    print(f"protected-action: PASS plan={plan} kind={args.kind} target={args.target}")


def command_consume_protected(args: argparse.Namespace) -> None:
    if args.plan == "direct":
        execution_direct.command_consume_protected_direct(args)
        return
    repo = repo_path(args.repo)
    plan = plan_path(repo, args.plan)
    fingerprint = approved_fingerprint(plan)
    validate_execution(repo, plan, fingerprint, args.session_id, args.request_digest)
    value, raw, mode = load_receipt(repo, plan, "protected-action.json")
    protected_expiry = value.get("expires_at_epoch")
    valid = (
        value.get("schema_version") == 2
        and value.get("status") == "authorized"
        and value.get("approval_kind") == args.kind
        and value.get("plan_fingerprint") == fingerprint
        and value.get("session_digest") == require_session(args.session_id)
        and value.get("request_digest") == require_digest(args.request_digest, "request digest")
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
    if not valid:
        fail("protected authorization does not match the current action and state")
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
    ready = commands.add_parser("challenge-ready")
    for name in ("repo", "plan", "fingerprint", "session-id", "request-digest"):
        ready.add_argument(f"--{name}", required=True)
    ready.add_argument("--allowed-action", action="append", required=True)
    ready.add_argument("--expires-in-seconds", type=int, default=DEFAULT_CHALLENGE_SECONDS)
    ready.set_defaults(action=command_challenge_ready)
    for name, action in (
        ("challenge-protected", command_challenge_protected),
        ("authorize-protected", command_authorize_protected),
    ):
        protected = commands.add_parser(name)
        for argument in (
            "repo",
            "plan",
            "session-id",
            "request-digest",
            "target",
            "effect",
            "tool-name",
            "action-digest",
        ):
            protected.add_argument(f"--{argument}", required=True)
        protected.add_argument("--kind", choices=EXACT_APPROVAL_KINDS, required=True)
        if name == "challenge-protected":
            protected.add_argument("--max-material-spend", default="none")
        else:
            protected.add_argument("--approval-reply", required=True)
        protected.add_argument("--expires-in-seconds", type=int, default=DEFAULT_CHALLENGE_SECONDS)
        protected.set_defaults(action=action)
    consume = commands.add_parser("consume-protected")
    for argument in ("repo", "plan", "session-id", "request-digest", "tool-name", "action-digest"):
        consume.add_argument(f"--{argument}", required=True)
    consume.add_argument("--kind", choices=EXACT_APPROVAL_KINDS, required=True)
    consume.set_defaults(action=command_consume_protected)
    execution_direct.register(commands)
    for name, action in (("authorize", command_authorize), ("check", command_check)):
        command = commands.add_parser(name)
        for argument in ("repo", "plan", "session-id", "request-digest"):
            command.add_argument(f"--{argument}", required=True)
        if name == "authorize":
            command.add_argument("--fingerprint", required=True)
            command.add_argument("--approval-reply", required=True)
            command.add_argument("--allowed-action", action="append", default=[])
            command.add_argument("--expires-in-seconds", type=int, default=MAX_CHALLENGE_SECONDS)
        else:
            command.add_argument("--fingerprint")
            command.add_argument("--allow-repository-drift", action="store_true")
        command.set_defaults(action=action)
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
