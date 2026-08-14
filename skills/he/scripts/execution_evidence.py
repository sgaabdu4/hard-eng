#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import NoReturn

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"))
from git_env import git_env


FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
AFFIRMATIVE = re.compile(
    r"(?i)(?:\byes\b|\bapprov(?:e|ed)\b|\bgo ahead\b|\bproceed\b|\bdo it\b|\bbuild it\b)"
)
AUTONOMOUS = re.compile(r"(?i)\bautonomous(?:ly)?\b|\bautonomy\b")
AUTONOMOUS_DIRECTIVE = re.compile(
    r"(?i)(?:\b(?:use|run|enable|start|choose)\b.{0,50}\bautonomous(?:ly)?\b|"
    r"\A\s*autonomous(?:\s+(?:mode|function|flow|task))?\s*[:,-]\s*\S)"
)
NEGATED_AUTONOMY = re.compile(
    r"(?i)\b(?:do\s+not|don['’]?t|dont|never|without)\b.{0,50}\bautonomous(?:ly)?\b"
)
SUBAGENT = re.compile(r"(?i)\bsub-?agents?\b|\bparallel agents?\b")
STOP_BEFORE = [
    "account-or-permission-change",
    "data-deletion-or-destructive-schema",
    "force-or-history-rewrite",
    "material-payment-or-spend",
    "protected-live-write-retry",
    "secret-exposure",
]
EXACT_APPROVAL_KINDS = [*STOP_BEFORE, "external-live-write-or-delivery"]
AUTONOMOUS_ALLOWS = [
    "additive-live-data-or-schema",
    "build-and-verify",
    "commit-push-pr-merge-ci",
    "named-deployment",
    "parallel-subagents",
    "planning-and-engineering-decisions",
]


class EvidenceError(ValueError):
    pass


def enforcement_configured(repo: Path) -> bool:
    try:
        value = json.loads((repo / "hard-eng.gates.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(value, dict) and isinstance(value.get("enforcement"), dict)


def fail(message: str) -> NoReturn:
    raise EvidenceError(message)


def repo_path(value: str) -> Path:
    repo = Path(value).resolve()
    if not (repo / ".git").exists():
        fail("repository is not a Git checkout")
    return repo


def plan_path(repo: Path, value: str) -> Path:
    raw = Path(value)
    lexical = Path(os.path.abspath(raw if raw.is_absolute() else repo / raw))
    try:
        relative = lexical.relative_to(repo)
    except ValueError:
        fail("PLAN must be inside the repository")
    current = repo
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            fail(f"PLAN path contains a symlink: {current}")
    path = lexical.resolve()
    try:
        relative = path.relative_to(repo)
    except ValueError:
        fail("PLAN must be inside the repository")
    if len(relative.parts) != 3 or relative.parts[0] != "features" or relative.name != "PLAN.md":
        fail("PLAN must be features/<feature>/PLAN.md")
    if not path.is_file() or path.is_symlink():
        fail("PLAN must be a regular file")
    return path


def plan_id(plan: Path) -> str:
    text = plan.read_text(encoding="utf-8")
    matches = re.findall(r"(?m)^- plan_id = (\S+)$", text)
    if len(matches) != 1:
        fail("PLAN requires exactly one plan_id")
    return matches[0]


def receipt_path(plan: Path, name: str) -> Path:
    return plan.parent / "receipts" / name


def action_digest(tool_name: str, tool_input: dict[str, object]) -> str:
    action = json.dumps(
        {"tool_input": tool_input, "tool_name": tool_name.casefold()},
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(action.encode("utf-8")).hexdigest()


def git_private_path(repo: Path, name: str) -> Path:
    resolved = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
        env=git_env(),
    )
    if resolved.returncode != 0 or not resolved.stdout.strip():
        fail("cannot find the repository Git-private directory")
    git_dir = Path(resolved.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = repo / git_dir
    return git_dir.resolve() / "hard-eng" / name


def atomic_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink():
        fail("receipt directory must not be a symlink")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_json(path: Path) -> dict[str, object]:
    if not path.is_file() or path.is_symlink():
        fail(f"missing regular receipt: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        fail(f"invalid receipt {path.name}: {error}")
    if not isinstance(value, dict):
        fail(f"invalid receipt {path.name}: root must be an object")
    return value


def validate_research(repo: Path, plan: Path) -> dict[str, object]:
    value = load_json(receipt_path(plan, "research.json"))
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
    if checked_at > date.today() or date.today() > fresh_until:
        fail("research receipt is not current")
    verified = value.get("verified")
    if not isinstance(verified, list) or not verified or not all(
        isinstance(item, str) and item for item in verified
    ):
        fail("research receipt requires at least one verified result")
    unknown = value.get("unknown")
    if not isinstance(unknown, list) or not all(
        isinstance(item, str) and item for item in unknown
    ):
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
    if fresh_until < date.today():
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
    resolved = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
        env=git_env(),
    )
    head = resolved.stdout.strip() if resolved.returncode == 0 else "unborn"
    value: dict[str, object] = {
        "checked_at": date.today().isoformat(),
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
    atomic_json(receipt_path(plan, "research.json"), value)
    print(f"research-evidence: PASS plan={plan} scope={args.scope}")


def authorize_execution(repo: Path, plan: Path, fingerprint: str, reply: str) -> str:
    validate_research(repo, plan)
    reply = reply.strip()
    directive = AUTONOMOUS_DIRECTIVE.search(reply)
    if not AFFIRMATIVE.search(reply) and not directive:
        fail("execution authorization requires a clear affirmative reply")
    if not FINGERPRINT.fullmatch(fingerprint):
        fail("execution authorization requires the approved PLAN fingerprint")
    mode = (
        "autonomous"
        if not NEGATED_AUTONOMY.search(reply)
        and AUTONOMOUS.search(reply)
        and (AFFIRMATIVE.search(reply) or directive)
        else "standard"
    )
    allowed = AUTONOMOUS_ALLOWS if mode == "autonomous" else ["approved-build"]
    if mode == "standard" and SUBAGENT.search(reply):
        allowed = [*allowed, "parallel-subagents"]
    value: dict[str, object] = {
        "allowed": allowed,
        "approval_digest": "sha256:" + hashlib.sha256(reply.encode("utf-8")).hexdigest(),
        "fingerprint": fingerprint,
        "mode": mode,
        "plan_id": plan_id(plan),
        "schema_version": 1,
        "stop_before": STOP_BEFORE,
    }
    atomic_json(receipt_path(plan, "authorization.json"), value)
    return mode


def command_authorize(args: argparse.Namespace) -> None:
    repo = repo_path(args.repo)
    plan = plan_path(repo, args.plan)
    mode = authorize_execution(repo, plan, args.fingerprint, args.approval_reply)
    print(f"execution-authorization: PASS plan={plan} mode={mode}")


def validate_execution(repo: Path, plan: Path, fingerprint: str | None = None) -> str:
    validate_research(repo, plan)
    value = load_json(receipt_path(plan, "authorization.json"))
    if value.get("schema_version") != 1 or value.get("plan_id") != plan_id(plan):
        fail("authorization receipt does not match the active PLAN")
    if value.get("mode") not in {"standard", "autonomous"}:
        fail("authorization receipt has an invalid mode")
    allowed = value.get("allowed")
    expected_allowed = AUTONOMOUS_ALLOWS if value.get("mode") == "autonomous" else ["approved-build"]
    if value.get("mode") == "standard" and allowed == ["approved-build", "parallel-subagents"]:
        expected_allowed = allowed
    if allowed != expected_allowed:
        fail("authorization allowed actions drifted")
    if not isinstance(value.get("approval_digest"), str) or not FINGERPRINT.fullmatch(
        str(value["approval_digest"])
    ):
        fail("authorization receipt requires an approval digest")
    if fingerprint and value.get("fingerprint") != fingerprint:
        fail("authorization receipt does not match the approved PLAN fingerprint")
    if value.get("stop_before") != STOP_BEFORE:
        fail("authorization stop boundary drifted")
    return str(value["mode"])


def command_check(args: argparse.Namespace) -> None:
    repo = repo_path(args.repo)
    plan = plan_path(repo, args.plan)
    mode = validate_execution(repo, plan, args.fingerprint)
    print(f"execution-evidence: PASS plan={plan} mode={mode}")


def command_authorize_protected(args: argparse.Namespace) -> None:
    repo = repo_path(args.repo)
    plan = plan_path(repo, args.plan)
    plan_text = plan.read_text(encoding="utf-8")
    fingerprint_match = re.findall(
        r"(?m)^- approval_fingerprint = (sha256:[0-9a-f]{64})$", plan_text
    )
    if len(fingerprint_match) != 1 or "- approval_status = approved" not in plan_text:
        fail("protected action requires an approved active PLAN")
    fingerprint = fingerprint_match[0]
    validate_execution(repo, plan, fingerprint)
    if not AFFIRMATIVE.search(args.approval_reply):
        fail("protected action requires a clear affirmative reply")
    try:
        tool_input = json.loads(args.tool_input_json)
    except json.JSONDecodeError as error:
        fail(f"protected tool input is invalid JSON: {error}")
    if not isinstance(tool_input, dict):
        fail("protected tool input must be a JSON object")
    if not args.target.strip():
        fail("protected action requires an exact target")
    value: dict[str, object] = {
        "action_digest": action_digest(args.tool_name, tool_input),
        "approval_digest": "sha256:"
        + hashlib.sha256(args.approval_reply.encode("utf-8")).hexdigest(),
        "fingerprint": fingerprint,
        "kind": args.kind,
        "plan_id": plan_id(plan),
        "schema_version": 1,
        "target": args.target.strip(),
    }
    atomic_json(receipt_path(plan, "protected-action.json"), value)
    print(f"protected-action: PASS plan={plan} kind={args.kind} target={value['target']}")


def command_start_direct(args: argparse.Namespace) -> None:
    repo = repo_path(args.repo)
    if not args.session_id.strip():
        fail("direct route requires a runtime session id")
    if not FINGERPRINT.fullmatch(args.request_digest):
        fail("direct route requires the current request digest")
    intended: list[dict[str, str]] = []
    for item in dict.fromkeys(args.intended_path):
        raw = Path(item)
        if raw.is_absolute() or ".." in raw.parts:
            fail(f"direct intended path must be repository-relative: {item}")
        path = (repo / raw).resolve()
        try:
            relative = path.relative_to(repo).as_posix()
        except ValueError:
            fail(f"direct intended path escaped the repository: {item}")
        if relative in {"", "."}:
            fail("direct intended path cannot be the whole repository")
        scope = "tree" if item.endswith("/") or path.is_dir() else "file"
        intended.append({"path": relative, "scope": scope})
    if not intended:
        fail("direct route requires at least one intended path")
    sources = list(dict.fromkeys(args.source))
    try:
        fresh_until = date.fromisoformat(args.fresh_until)
    except ValueError:
        fail("fresh-until must use YYYY-MM-DD")
    if fresh_until < date.today():
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
            raw = Path(item)
            if raw.is_absolute() or ".." in raw.parts:
                fail(f"local direct research source is invalid: {item}")
            path = (repo / raw).resolve()
            if not path.is_file() or path.is_symlink() or repo not in path.parents:
                fail(f"local direct research source is invalid: {item}")
            versions.append("sha256:" + hashlib.sha256(path.read_bytes()).hexdigest())
    if not sources or not args.verified or not args.question.strip() or not args.decision.strip():
        fail("direct route requires question, decision, source, and verified result")
    head = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"], cwd=repo, text=True,
        capture_output=True, check=False, env=git_env(),
    )
    session_digest = "sha256:" + hashlib.sha256(args.session_id.encode("utf-8")).hexdigest()
    value: dict[str, object] = {
        "allowed": ["reversible-local-work"]
        + (["parallel-subagents"] if args.allow_subagents else []),
        "checked_at": date.today().isoformat(),
        "decision": args.decision.strip(),
        "fresh_until": fresh_until.isoformat(),
        "intended_paths": intended,
        "question": args.question.strip(),
        "request_digest": args.request_digest,
        "repository_head": head.stdout.strip() if head.returncode == 0 else "unborn",
        "route": "direct",
        "schema_version": 1,
        "scope": args.scope,
        "session_digest": session_digest,
        "source_versions": versions,
        "sources": sources,
        "stop_before": STOP_BEFORE,
        "unknown": [] if args.unknown == ["none"] else args.unknown,
        "verified": args.verified,
    }
    atomic_json(git_private_path(repo, "current-direct.json"), value)
    print(f"direct-route: PASS repo={repo} paths={len(intended)}")


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
    protected.add_argument("--repo", required=True)
    protected.add_argument("--plan", required=True)
    protected.add_argument("--kind", choices=EXACT_APPROVAL_KINDS, required=True)
    protected.add_argument("--target", required=True)
    protected.add_argument("--tool-name", required=True)
    protected.add_argument("--tool-input-json", required=True)
    protected.add_argument("--approval-reply", required=True)
    protected.set_defaults(action=command_authorize_protected)
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
    for name, action in (("authorize", command_authorize), ("check", command_check)):
        command = commands.add_parser(name)
        command.add_argument("--repo", required=True)
        command.add_argument("--plan", required=True)
        if name == "authorize":
            command.add_argument("--fingerprint", required=True)
            command.add_argument("--approval-reply", required=True)
        else:
            command.add_argument("--fingerprint")
        command.set_defaults(action=action)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        args.action(args)
    except (EvidenceError, OSError, UnicodeError, subprocess.SubprocessError) as error:
        print(f"execution-evidence: FAIL: {error}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
