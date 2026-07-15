#!/usr/bin/env python3
"""Run one exact-snapshot, read-only Codex final audit for Hard Eng build."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
SCRIPT_DIR = Path(__file__).resolve().parent
AGENTS_ROOT = SCRIPT_DIR.parents[2]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
STATE_SCRIPT_DIR = SCRIPT_DIR.parents[1] / "he/scripts"
if str(STATE_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(STATE_SCRIPT_DIR))
from audit_contract import (  # noqa: E402
    PLAN_PATH,
    AuditError,
    RetryableAuditError,
    finding_issue,
    output_schema,
    parse_usage,
    validate_result,
)
from audit_result import (  # noqa: E402
    assign_finding_ids,
    audit_prompt,
    bounded_timeout,
    load_audit_result,
    one_infrastructure_retry,
)
from audit_entry import validate_audit_entry, validate_audit_state  # noqa: E402
from generated_evidence import GeneratedEvidenceError, generated_diff, generated_file  # noqa: E402
from related_context import RelatedContextError, current_plan_intent, related_context  # noqa: E402
from repository_snapshot import (  # noqa: E402
    SnapshotError,
    artifact_id as repository_artifact_id,
    snapshot_id as repository_snapshot_id,
)
from secret_scanner import (  # noqa: E402
    EncodedTextError,
    GENERIC_SECRET_ASSIGNMENT,
    SECRET_ASSIGNMENT,
    decode_text_bytes,
    secret_marker,
    sensitive_path,
)
MAX_PACKET_BYTES = 800 * 1024
MAX_TOOL_CALLS = 0
DEFAULT_TIMEOUT = 600
TOOL_IDLE_TIMEOUT = 180
SYNTHESIS_IDLE_TIMEOUT = 360
HEARTBEAT_SECONDS = 30
ALLOWED_ITEM_TYPES = {"agent_message", "reasoning", "error"}
ITEM_EVENTS = {"item.started", "item.updated", "item.completed"}
DISABLED_TOOL_FEATURES = (
    "apps", "auth_elicitation", "browser_use", "browser_use_external", "browser_use_full_cdp_access",
    "code_mode_host", "computer_use", "default_mode_request_user_input", "goals", "hooks", "image_generation",
    "in_app_browser", "multi_agent", "plugins", "remote_plugin", "request_permissions_tool", "shell_tool",
    "skill_mcp_dependency_install", "tool_call_mcp_elicitation", "tool_suggest", "unified_exec", "workspace_dependencies",
)
def git(root: Path, *args: str, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
    )
    if check and result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise AuditError(detail or f"git {' '.join(args)} failed")
    return result.stdout
def repository_root(repo: Path) -> Path:
    value = git(repo, "rev-parse", "--show-toplevel").decode("utf-8", "strict").strip()
    return Path(value).resolve()
def untracked_paths(root: Path) -> tuple[str, ...]:
    raw = git(root, "ls-files", "--others", "--exclude-standard", "-z")
    return tuple(sorted(part.decode("utf-8", "surrogateescape") for part in raw.split(b"\0") if part))
def snapshot_id(repo: Path) -> str:
    try:
        return repository_snapshot_id(repo)
    except SnapshotError as exc:
        raise AuditError(str(exc)) from exc
def add_packet_section(sections: list[str], label: str, content: str) -> None:
    marker = secret_marker(content)
    if marker:
        raise AuditError(f"{marker} content blocks audit: {label}")
    sections.extend((label, content))
def add_required_related_context(
    sections: list[str], context: tuple[tuple[str, str, str], ...]
) -> None:
    for _, label, content in context:
        candidate = "\n\n".join((*sections, label, content))
        if len(candidate.encode("utf-8", "surrogateescape")) > MAX_PACKET_BYTES:
            raise AuditError(f"review packet has no room for required related context: {label}")
        add_packet_section(sections, label, content)
def safe_payload(data: bytes) -> tuple[str, bool]:
    try:
        text = decode_text_bytes(data)
    except EncodedTextError as exc:
        raise AuditError(str(exc)) from exc
    if text is not None:
        return text, True
    kind = "binary" if b"\0" in data else "non-utf8"
    return f"<{kind} bytes={len(data)} sha256={hashlib.sha256(data).hexdigest()}>", False
def require_safe_bytes(data: bytes, label: str) -> None:
    try:
        decoded = decode_text_bytes(data)
    except EncodedTextError as exc:
        raise AuditError(f"malformed encoded text blocks audit: {label}") from exc
    for text in (data.decode("latin-1"), decoded):
        if text is not None and (marker := secret_marker(text)):
            raise AuditError(f"{marker} raw bytes block audit: {label}")
def packet_file(path: Path) -> str:
    if path.is_symlink():
        return "<symlink>"
    data = path.read_bytes()
    require_safe_bytes(data, str(path))
    return safe_payload(data)[0]
def required_packet_file(path: Path, label: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise AuditError(f"review packet requires regular file: {label}")
    return packet_file(path)
def scoped_diff(
    root: Path, revisions: tuple[str, ...], changed: tuple[str, ...], context: int = 0
) -> str:
    return "\n".join(
        f"file -- {relative}\n{content}"
        for relative, content in scoped_diff_units(root, revisions, changed, context)
    )
def scoped_diff_units(
    root: Path, revisions: tuple[str, ...], changed: tuple[str, ...], context: int = 0
) -> tuple[tuple[str, str], ...]:
    units = []
    for relative in changed:
        generated = generated_diff(root, relative, revisions)
        if generated is not None:
            if generated:
                units.append((relative, generated))
            continue
        data = git(
            root,
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            f"--unified={context}",
            *revisions,
            "--",
            relative,
            check=False,
        )
        if not data:
            continue
        require_safe_bytes(data, f"diff:{'/'.join(revisions)}:{relative}")
        content, is_text = safe_payload(data)
        if not is_text:
            units.append((relative, content))
            continue
        compact = []
        in_hunk = False
        for line in content.splitlines():
            in_hunk = in_hunk or line.startswith("@@")
            if not in_hunk and line.startswith(("diff --git ", "index ", "--- ", "+++ ")):
                continue
            compact.append(line)
        units.append((relative, "\n".join(compact)))
    return tuple(units)
def cached_evidence(root: Path, changed: tuple[str, ...]) -> str:
    raw = git(root, "diff", "--cached", "--diff-filter=A", "--name-only", "-z", "--", ".",
              ":(exclude,glob)features/*/PLAN.md", check=False)
    added = {part.decode("utf-8", "surrogateescape") for part in raw.split(b"\0") if part}
    sections = [scoped_diff(root, ("--cached",), tuple(path for path in changed if path not in added), 0)]
    for relative in sorted(added):
        content = generated_diff(root, relative, ("--cached",))
        if content is None:
            content = safe_payload(git(root, "show", f":{relative}", check=False))[0]
        sections.append(f"file -- {relative}\n{content}")
    return "\n".join(section for section in sections if section)
def plan_base_sha(root: Path, plan: Path) -> str:
    match = re.search(r"(?m)^- base_sha = ([0-9a-f]{40})$", plan.read_text(encoding="utf-8"))
    if not match:
        raise AuditError("PLAN base_sha is missing or invalid")
    base = match.group(1)
    resolved = git(root, "rev-parse", "--verify", f"{base}^{{commit}}", check=False).decode().strip()
    ancestor = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", base, "HEAD"], capture_output=True, check=False
    )
    if resolved != base or ancestor.returncode != 0:
        raise AuditError("PLAN base_sha is not an ancestor of HEAD")
    return base
def changed_paths(root: Path, base: str = "HEAD") -> tuple[str, ...]:
    exclude = ":(exclude,glob)features/*/PLAN.md"
    final = git(root, "diff", "--name-only", "-z", base, "--", ".", exclude, check=False)
    cached = git(root, "diff", "--cached", "--name-only", "-z", "--", ".", exclude, check=False)
    paths = {
        part.decode("utf-8", "surrogateescape")
        for part in (*final.split(b"\0"), *cached.split(b"\0"))
        if part
    }
    paths.update(relative for relative in untracked_paths(root) if not PLAN_PATH.fullmatch(Path(relative).as_posix()))
    return tuple(sorted(paths))
def applicable_rule_paths(tracked: tuple[str, ...], scoped: tuple[str, ...]) -> tuple[str, ...]:
    rules = []
    for relative in tracked:
        path = Path(relative)
        if path.name not in {"AGENTS.md", "AGENTS.override.md"}:
            continue
        parent = path.parent.as_posix()
        if parent == "." or any(item == parent or item.startswith(parent + "/") for item in scoped):
            rules.append(relative)
    return tuple(sorted(rules, key=lambda value: (len(Path(value).parts), value)))
def scan_changed_bytes(root: Path, changed: tuple[str, ...], base: str) -> None:
    for relative in changed:
        versions = [git(root, "show", f"{revision}:{relative}", check=False) for revision in (base, "HEAD")]
        versions.append(git(root, "show", f":{relative}", check=False))
        path = root / relative
        if path.is_file() and not path.is_symlink():
            versions.append(path.read_bytes())
        seen = set()
        for data in versions:
            digest = hashlib.sha256(data).digest()
            if data and digest not in seen:
                require_safe_bytes(data, relative)
                seen.add(digest)
def commit_paths(root: Path, parent: str, commit: str) -> tuple[str, ...]:
    raw = git(
        root, "diff", "--name-only", "-z", parent, commit, "--", ".",
        ":(exclude,glob)features/*/PLAN.md",
    )
    return tuple(sorted(part.decode("utf-8", "surrogateescape") for part in raw.split(b"\0") if part))
def commit_history_units(root: Path, base: str) -> tuple[tuple[str, str], ...]:
    commits = tuple(
        line for line in git(root, "rev-list", "--reverse", f"{base}..HEAD").decode().splitlines() if line
    )
    sections = []
    for commit in commits:
        ancestry = git(root, "rev-list", "--parents", "-n", "1", commit).decode().split()
        parents = tuple(ancestry[1:])
        if not parents:
            raise AuditError(f"commit range contains parentless commit: {commit}")
        parent_paths = {parent: commit_paths(root, parent, commit) for parent in parents}
        paths = tuple(sorted({path for values in parent_paths.values() for path in values}))
        for relative in paths:
            if sensitive_path(relative):
                raise AuditError(f"sensitive historical path blocks audit: {relative}@{commit}")
            tree = git(root, "ls-tree", commit, "--", relative, check=False)
            if tree.startswith(b"120000 "):
                raise AuditError(f"historical symlink blocks audit: {relative}@{commit}")
            if tree:
                require_safe_bytes(git(root, "show", f"{commit}:{relative}"), f"{relative}@{commit}")
        patches = []
        for parent, relative_paths in parent_paths.items():
            for relative in relative_paths:
                direct = scoped_diff(root, (parent, commit), (relative,)) or "<empty parent patch>"
                patches.append(
                    f"parent = {parent}\npath = {relative}\n#### Parent-to-commit patch\n{direct}",
                )
        if patches:
            sections.append((f"### Commit {commit}", "\n\n".join(patches)))
    return tuple(sections)
def commit_history_evidence(root: Path, base: str) -> str:
    return "\n\n".join(f"{label}\n{content}" for label, content in commit_history_units(root, base)) or "<none>"
def reject_changed_symlinks(root: Path, changed: tuple[str, ...], base: str) -> None:
    for relative in changed:
        modes = [git(root, "ls-tree", revision, "--", relative, check=False) for revision in (base, "HEAD")]
        modes.append(git(root, "ls-files", "--stage", "--", relative, check=False))
        if (root / relative).is_symlink() or any(data.startswith(b"120000 ") for data in modes):
            raise AuditError(f"changed symlink blocks audit: {relative}")
def review_packet_parts(repo: Path, plan: Path) -> tuple[list[str], list[tuple[str, str]]]:
    root = repository_root(repo.resolve())
    sections = ["# Review packet", f"snapshot = {snapshot_id(root)}"]
    base = plan_base_sha(root, plan)
    tracked = tuple(
        part.decode("utf-8", "surrogateescape")
        for part in git(root, "ls-files", "-z").split(b"\0")
        if part
    )
    changed = changed_paths(root, base)
    scoped = (*changed, plan.resolve().relative_to(root).as_posix())
    for relative in applicable_rule_paths(tracked, scoped):
        add_packet_section(sections, f"## Rules: {relative}", required_packet_file(root / relative, relative))
    plan_text = packet_file(plan.resolve())
    context_paths = ["PRODUCT.md"]
    if not re.search(r"(?m)^- build_axes = .*\bui-design:na(?:,|$)", plan_text):
        context_paths.append("DESIGN.md")
    for relative in context_paths:
        path = root / relative
        add_packet_section(sections, f"## Context: {relative}", required_packet_file(path, relative))
    for relative in ("skills/code-review/SKILL.md", "skills/code-review/references/spec.md"):
        path = AGENTS_ROOT / relative
        if path.is_symlink() or not path.is_file():
            raise AuditError(f"review packet missing contract: {relative}")
        add_packet_section(sections, f"## Review contract: {relative}", packet_file(path))
    resolved_plan = plan.resolve()
    add_packet_section(
        sections,
        f"## Intent: {resolved_plan.relative_to(root).as_posix()}",
        current_plan_intent(plan_text),
    )
    for relative in changed:
        if sensitive_path(relative):
            raise AuditError(f"sensitive path blocks audit: {relative}")
    reject_changed_symlinks(root, changed, base)
    scan_changed_bytes(root, changed, base)
    commit_log = git(root, "log", "--oneline", f"{base}..HEAD", check=False).decode("utf-8", "replace")
    commit_units = commit_history_units(root, base)
    final_units = scoped_diff_units(root, ("HEAD",), changed)
    staged_divergence = cached_evidence(root, changed)
    add_packet_section(sections, "## Commit range", commit_log or "<none>")
    units = [("## Staged divergence", staged_divergence or "<none>"), *commit_units]
    if not commit_units:
        units.append(("## Per-commit patch reconstruction", "<none>"))
    if final_units:
        units.extend(
            (f"## Final HEAD-to-worktree diff: {relative}", content)
            for relative, content in final_units
        )
    else:
        units.append(("## Final HEAD-to-worktree diff", "<none>"))
    for relative in untracked_paths(root):
        normalized = Path(relative).as_posix()
        if PLAN_PATH.fullmatch(normalized):
            continue
        if sensitive_path(normalized):
            raise AuditError(f"sensitive untracked path blocks audit: {normalized}")
        content = generated_file(root / relative, normalized)
        units.append((f"## Untracked: {normalized}", content or packet_file(root / relative)))
    try:
        context = related_context(root, changed, base)
    except RelatedContextError as exc:
        raise AuditError(str(exc)) from exc
    combined = [*sections, *(value for unit in units for value in unit)]
    before = len(combined)
    add_required_related_context(combined, context)
    appended = combined[before:]
    units.extend((appended[index], appended[index + 1]) for index in range(0, len(appended), 2))
    return sections, units
def review_packet(repo: Path, plan: Path) -> str:
    sections, units = review_packet_parts(repo, plan)
    packet = "\n\n".join([*sections, *(value for unit in units for value in unit)])
    packet = packet.replace(str(repository_root(repo.resolve())), "<repo-root>")
    if len(packet.encode("utf-8", "surrogateescape")) > MAX_PACKET_BYTES:
        raise AuditError(f"review packet exceeds {MAX_PACKET_BYTES} bytes")
    return packet
def set_workspace_writable(root: Path, writable: bool) -> None:
    paths = [root, *root.rglob("*")]
    for path in reversed(paths):
        if path.is_symlink():
            continue
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IWUSR if writable else mode & ~0o222)
def isolated_environment(directory: Path, controller_codex: Path | None = None) -> tuple[dict[str, str], tuple[str, ...]]:
    original_home = Path.home().resolve()
    original_codex = (controller_codex or Path(os.environ.get("CODEX_HOME", original_home / ".codex"))).resolve()
    auth = original_codex / "auth.json"
    if auth.is_symlink() or not auth.is_file():
        raise AuditError("audit controller requires Codex auth.json")
    home = directory / "home"
    home.mkdir()
    allowed = ("PATH", "TMPDIR", "LANG", "LC_ALL", "TERM", "NO_COLOR")
    environment = {
        "HOME": str(home),
        "CODEX_HOME": str(original_codex),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "PYTHONDONTWRITEBYTECODE": "1",
        **{name: os.environ[name] for name in allowed if name in os.environ},
    }
    return environment, (str(original_home), str(original_codex))
def require_unchanged_snapshot(repo: Path, expected: str) -> None:
    if snapshot_id(repo) != expected:
        raise AuditError("repository changed during audit")
def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()
def require_unchanged_file(path: Path, expected: str, label: str) -> None:
    if file_digest(path) != expected:
        raise AuditError(f"{label} changed during audit")
@dataclass
class EventState:
    stage: str = "starting"
    action: str = "none"
    tool_calls: int = 0
    completed_items: int = 0
    usage: dict[str, int] | None = None
    forbidden_paths: tuple[str, ...] = ()
def new_event_state(forbidden_paths: tuple[str, ...] = ()) -> EventState:
    return EventState(forbidden_paths=forbidden_paths)
def emit_status(stage: str, **details: object) -> None:
    payload = {"type": "he.audit.status", "stage": stage, **details}
    print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), file=sys.stderr, flush=True)
def progress(state: EventState) -> None:
    emit_status(
        state.stage,
        action=state.action,
        tool_calls=state.tool_calls,
        tool_budget=MAX_TOOL_CALLS,
        completed_items=state.completed_items,
    )
def consume_event(line: str, state: EventState, emit_progress: bool) -> None:
    try:
        event = json.loads(line)
    except json.JSONDecodeError as exc:
        raise AuditError("codex audit event stream is not valid JSONL") from exc
    if not isinstance(event, dict):
        raise AuditError("codex audit event is invalid")
    event_type = event.get("type")
    item = event.get("item")
    item_type = item.get("type") if isinstance(item, dict) else None
    if event_type in ITEM_EVENTS and item_type == "error":
        state.stage = "transport-recovering"
        if emit_progress:
            progress(state)
        return
    if event_type in ITEM_EVENTS and item_type not in ALLOWED_ITEM_TYPES:
        raise AuditError(f"codex audit emitted unapproved item type: {item_type}")
    if event_type == "thread.started":
        state.stage = "packet-review"
    elif event_type == "item.started":
        state.stage = "synthesizing" if item_type == "agent_message" else "packet-review"
    elif event_type == "item.completed":
        state.completed_items += int(item_type == "agent_message")
        state.stage = "synthesizing" if item_type == "agent_message" else state.stage
    elif event_type == "turn.completed":
        state.usage = parse_usage(event.get("usage"))
        state.stage = "synthesizing"
    if emit_progress and event_type in {"thread.started", "item.started", "item.completed", "turn.completed"}:
        progress(state)
def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=3)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if process.poll() is None:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                return
def run_codex_stream(
    command: list[str],
    prompt: str,
    timeout: int,
    environment_overrides: dict[str, str] | None = None,
    forbidden_paths: tuple[str, ...] = (),
) -> tuple[dict[str, int], int]:
    environment = dict(environment_overrides or {})
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=os.name == "posix",
        env=environment,
    )
    if process.stdin is None or process.stdout is None:
        stop_process(process)
        raise AuditError("codex audit stream unavailable")
    selector = selectors.DefaultSelector()
    state = new_event_state(forbidden_paths)
    started = last_event = last_heartbeat = time.monotonic()
    buffered = b""
    progress(state)
    try:
        process.stdin.write(prompt.encode("utf-8"))
        process.stdin.close()
        os.set_blocking(process.stdout.fileno(), False)
        selector.register(process.stdout, selectors.EVENT_READ)
        while True:
            now = time.monotonic()
            elapsed = now - started
            idle = now - last_event
            idle_limit = (
                timeout if state.stage in {"starting", "packet-review"}
                else min(timeout, TOOL_IDLE_TIMEOUT if state.stage == "targeted-inspection" else SYNTHESIS_IDLE_TIMEOUT)
            )
            if elapsed >= timeout:
                error = RetryableAuditError if state.completed_items == 0 else AuditError
                raise error(f"codex audit timed out after {timeout}s")
            if idle >= idle_limit:
                raise AuditError(f"codex audit stalled after {idle_limit}s without event")
            if now - last_heartbeat >= HEARTBEAT_SECONDS:
                emit_status(
                    state.stage,
                    action=state.action,
                    heartbeat=True,
                    elapsed_s=int(elapsed),
                    idle_s=int(idle),
                    tool_calls=state.tool_calls,
                    tool_budget=MAX_TOOL_CALLS,
                    completed_items=state.completed_items,
                )
                last_heartbeat = now
            ready = selector.select(timeout=min(1.0, timeout - elapsed, idle_limit - idle))
            for key, _ in ready:
                while True:
                    try:
                        chunk = os.read(key.fileobj.fileno(), 65536)
                    except BlockingIOError:
                        break
                    if not chunk:
                        selector.unregister(key.fileobj)
                        break
                    buffered += chunk
                while b"\n" in buffered:
                    line, buffered = buffered.split(b"\n", 1)
                    last_event = time.monotonic()
                    try:
                        decoded = line.decode("utf-8")
                    except UnicodeError as exc:
                        raise AuditError("codex audit event stream is not UTF-8") from exc
                    consume_event(decoded, state, emit_progress=True)
            if process.poll() is not None:
                if buffered:
                    raise AuditError("codex audit event stream ended with a partial record")
                break
        if process.returncode != 0:
            raise (RetryableAuditError if state.completed_items == 0 else AuditError)(f"codex audit exited {process.returncode}")
        if state.usage is None:
            raise (RetryableAuditError if state.completed_items == 0 else AuditError)("codex audit produced no usage event")
        return state.usage, state.completed_items
    except BrokenPipeError as exc:
        stop_process(process)
        raise AuditError("codex audit input pipe closed") from exc
    except AuditError:
        stop_process(process)
        raise
    except BaseException:
        stop_process(process)
        raise
    finally:
        selector.close()
        process.stdout.close()
def codex_command(
    repo: Path, schema_path: Path, result_path: Path, denied_paths: tuple[str, ...] = ()
) -> list[str]:
    denied_rules = ", ".join(f"{json.dumps(path)} = \"deny\"" for path in denied_paths)
    denied = ["-c", f"permissions.hard-eng-audit.filesystem={{ {denied_rules} }}"]
    disabled = [argument for feature in DISABLED_TOOL_FEATURES for argument in ("--disable", feature)]
    return [
        "codex",
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--strict-config",
        "-c",
        'approval_policy="never"',
        "-c",
        'default_permissions="hard-eng-audit"',
        "-c",
        'permissions.hard-eng-audit.extends=":read-only"',
        *denied,
        *disabled,
        "-c",
        'web_search="disabled"',
        "--model",
        "gpt-5.6-sol",
        "-c",
        'model_reasoning_effort="medium"',
        "--cd",
        str(repo),
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(result_path),
        "--json",
        "--color",
        "never",
        "-",
    ]
def resolve_plan(root: Path, plan_arg: Path) -> Path:
    plan = (plan_arg if plan_arg.is_absolute() else root / plan_arg).resolve()
    try:
        relative = plan.relative_to(root).as_posix()
    except ValueError as exc:
        raise AuditError("PLAN is outside repository") from exc
    if not PLAN_PATH.fullmatch(relative) or not plan.is_file():
        raise AuditError("PLAN must be features/<feature>/PLAN.md")
    return plan
def run_audit(repo: Path, plan_arg: Path, timeout: int, controller_codex: Path | None = None) -> dict[str, object]:
    if timeout <= 0:
        raise AuditError("audit timeout must be positive")
    root = repository_root(repo.resolve())
    plan = resolve_plan(root, plan_arg)
    snapshot = snapshot_id(root)
    validate_audit_entry(plan, root, snapshot, AuditError)
    plan_token = file_digest(plan)
    packet = review_packet(root, plan)
    with tempfile.TemporaryDirectory(prefix="hard-eng-audit-") as temporary:
        directory = Path(temporary)
        workspace = directory / "workspace"
        schema_path = directory / "schema.json"
        schema_path.write_text(json.dumps(output_schema(), separators=(",", ":")), encoding="utf-8")
        workspace.mkdir()
        initialized = subprocess.run(
            ["git", "-C", str(workspace), "init", "-q", "-b", "audit"], capture_output=True, check=False
        )
        if initialized.returncode != 0:
            raise AuditError("cannot initialize empty audit workspace")
        environment, forbidden_paths = isolated_environment(directory, controller_codex)
        try:
            set_workspace_writable(workspace, False)
            deadline = time.monotonic() + timeout
            result_path = directory / "result.json"
            emit_status("audit-starting")
            attempt = 0
            def action():
                nonlocal attempt
                attempt += 1
                result_path.unlink(missing_ok=True)
                usage, completed_items = run_codex_stream(
                    codex_command(workspace, schema_path, result_path, forbidden_paths),
                    audit_prompt(snapshot, plan_token, packet),
                    bounded_timeout(
                        deadline, timeout, AuditError, reserve_retry=attempt == 1
                    ), environment, forbidden_paths,
                )
                return usage, load_audit_result(result_path, snapshot, completed_items)
            usage, validated = one_infrastructure_retry(
                action, RetryableAuditError,
                lambda: emit_status("audit-retrying", reason="invalid-review-item"),
            )
        finally:
            set_workspace_writable(workspace, True)
    require_unchanged_snapshot(root, snapshot)
    require_unchanged_file(plan, plan_token, "PLAN")
    validated["usage"] = usage
    emit_status(
        "completed",
        verdict=validated["verdict"],
        findings=len(validated["findings"]),
        unknowns=len(validated["unknowns"]),
    )
    return validated


def self_test() -> None:
    validate_result(
        {"snapshot_id": "sha256:" + "0" * 64, "verdict": "pass", "findings": [], "unknowns": [], "summary": "clean"},
        "sha256:" + "0" * 64,
    )
    json.dumps(output_schema())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--plan")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--snapshot-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        if args.self_test:
            self_test()
            print("audit-self-test: PASS")
            return 0
        root = repository_root(Path(args.repo).expanduser().resolve())
        if args.snapshot_only:
            print(snapshot_id(root))
            return 0
        if not args.plan:
            raise AuditError("--plan is required")
        result = run_audit(root, Path(args.plan).expanduser(), args.timeout)
        print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
        return 0
    except (AuditError, GeneratedEvidenceError, OSError, UnicodeError) as exc:
        stage = "timed-out" if "timed out" in str(exc) or "stalled" in str(exc) else "blocked"
        emit_status(stage, reason=str(exc))
        print(f"audit: FAIL | {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
