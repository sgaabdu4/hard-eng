#!/usr/bin/env python3
"""Regression checks that kill the surviving mutants of plan_cleanup.py."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills/deterministic-checks/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from regression_fixture import checker, git

fail, require = checker("plan-cleanup-survivors")

import plan_cleanup as pc
from plan_sections import PlanError, token_for

from scripts.setup import safe_file

SABOTAGE: dict[str, tuple[Path, bytes]] = {}
RENDER_STATE_CALLS: list[dict] = []
RENDER_TEMPLATE_CALLS: list[tuple[str, str]] = []
VALIDATE_CALLS: list[object] = []


def none_lock_path() -> Path:
    identity = hashlib.sha256(b"None").hexdigest()
    return Path(tempfile.gettempdir()) / f"hard-eng-plan-cleanup-{identity}.lock"


_REPO_COUNTER = [0]


def make_repo(base: Path) -> Path:
    _REPO_COUNTER[0] += 1
    repo = base / f"repo-{_REPO_COUNTER[0]}"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def base_plan_text(status: str = "building", tag: str = "demo") -> str:
    return f"# PLAN: {tag}\n\n{pc.STATE_START}\n- lifecycle_status = {status}\n- plan_id = {tag}-plan\n{pc.STATE_END}\n"


def stub_validate_plan(text, *, ready=True, allow_legacy_missing_ux_reference=False):
    VALIDATE_CALLS.append(allow_legacy_missing_ux_reference)
    sabotage = SABOTAGE.get(text)
    if sabotage is not None:
        SABOTAGE.pop(text)
        sabotage[0].write_bytes(sabotage[1])
    if "INVALID-MARKER" in text:
        raise PlanError("stub: invalid plan content")
    match = pc.STATUS.search(text)
    if match is None:
        raise PlanError("stub: missing lifecycle_status")
    return {"lifecycle_status": match.group(1)}


def stub_render_template(slug: str, plan_id: str) -> str:
    RENDER_TEMPLATE_CALLS.append((slug, plan_id))
    return f"# PLAN: {slug}\n\n{pc.STATE_START}\n- lifecycle_status = building\n- plan_id = {plan_id}\n{pc.STATE_END}\n"


def stub_render_state(text: str, changes: dict) -> str:
    RENDER_STATE_CALLS.append(dict(changes))
    start = text.index(pc.STATE_START)
    end = text.index(pc.STATE_END, start) + len(pc.STATE_END)
    before, after = text[:start], text[end:]
    base = {"lifecycle_status": "building", "plan_id": "demo-plan"}
    base.update(changes)
    lines = "\n".join(f"- {key} = {value}" for key, value in base.items())
    return f"{before}{pc.STATE_START}\n{lines}\n{pc.STATE_END}{after}"


def write_plan(repo: Path, slug: str, text: str, *, commit: bool) -> Path:
    directory = repo / "features" / slug
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "PLAN.md"
    path.write_bytes(text.encode("utf-8"))
    relative = str(path.relative_to(repo))
    if commit:
        git(repo, "add", relative)
        git(repo, "commit", "-q", "-m", f"plan {slug}")
    return path


def expect_error(message_prefix: str, func, *args, **kwargs) -> None:
    try:
        func(*args, **kwargs)
    except PlanError as error:
        if not str(error).startswith(message_prefix):
            fail(f"expected error starting with {message_prefix!r}, got {error!r}")
        return
    fail(f"expected PlanError starting with {message_prefix!r}, nothing raised")


def check_digest_and_action_digest() -> None:
    data = b"hello world"
    if pc._digest(data) != "sha256:" + __import__("hashlib").sha256(data).hexdigest():
        fail("_digest must be sha256-prefixed hex")
    repo = Path("/tmp/repo-a")
    items = [(Path("features/a/PLAN.md"), "sha256:" + "1" * 64)]
    first = pc._action_digest(repo, "cancel now", items)
    if not first.startswith("sha256:") or len(first) != len("sha256:") + 64:
        fail("_action_digest must be a sha256-prefixed 64-hex digest")
    if pc._action_digest(repo, "cancel now", items) != first:
        fail("_action_digest must be deterministic for identical inputs")
    if pc._action_digest(repo, "cancel later", items) == first:
        fail("_action_digest must change when decision changes")
    other_items = [(Path("features/a/PLAN.md"), "sha256:" + "2" * 64)]
    if pc._action_digest(repo, "cancel now", other_items) == first:
        fail("_action_digest must change when item hash changes")
    other_path_items = [(Path("features/b/PLAN.md"), "sha256:" + "1" * 64)]
    if pc._action_digest(repo, "cancel now", other_path_items) == first:
        fail("_action_digest must change when item path changes")
    if pc._action_digest(Path("/tmp/repo-b"), "cancel now", items) == first:
        fail("_action_digest must change when repo changes")
    two_items = [(Path("features/a/PLAN.md"), "sha256:" + "1" * 64), (Path("features/b/PLAN.md"), "sha256:" + "2" * 64)]
    reversed_items = list(reversed(two_items))
    if pc._action_digest(repo, "cancel now", two_items) == pc._action_digest(repo, "cancel now", reversed_items):
        fail("_action_digest must be order-sensitive over items")
    payload = {
        "decision": "cancel now",
        "items": [{"path": "features/a/PLAN.md", "sha256": "sha256:" + "1" * 64}],
        "operation": "hard-eng-plan-cleanup-v1",
        "repo": str(repo),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    if first != pc._digest(encoded):
        fail("_action_digest payload shape drifted from expected schema")


def check_parse_items() -> None:
    parsed = pc._parse_items(["features/demo-slug/PLAN.md=" + "a" * 64])
    if parsed != [(Path("features/demo-slug/PLAN.md"), "sha256:" + "a" * 64)]:
        fail(f"_parse_items produced unexpected tuple: {parsed}")
    prefixed = pc._parse_items(["features/demo-slug/PLAN.md=sha256:" + "b" * 64])
    if prefixed != [(Path("features/demo-slug/PLAN.md"), "sha256:" + "b" * 64)]:
        fail("_parse_items must accept an already-prefixed sha256 value identically")
    item_format_message = "--item must be features/<slug>/PLAN.md=SHA256"
    expect_error(item_format_message, pc._parse_items, ["not-a-valid-item"])
    expect_error(item_format_message, pc._parse_items, ["features/Demo/PLAN.md=" + "a" * 64])
    dup_items = ["features/demo-slug/PLAN.md=" + "a" * 64, "features/demo-slug/PLAN.md=" + "b" * 64]
    expect_error("duplicate cleanup item: ", pc._parse_items, dup_items)
    two = pc._parse_items(["features/a/PLAN.md=" + "a" * 64, "features/b/PLAN.md=" + "b" * 64])
    if len(two) != 2:
        fail("_parse_items must keep every distinct item")


def check_lock(tmp: Path) -> None:
    repo_one = tmp / "lock-repo-1"
    repo_one.mkdir()
    repo_two = tmp / "lock-repo-2"
    repo_two.mkdir()

    identity_one = hashlib.sha256(str(repo_one).encode()).hexdigest()
    expected_path = Path(tempfile.gettempdir()) / f"hard-eng-plan-cleanup-{identity_one}.lock"
    if expected_path.exists():
        expected_path.unlink()
    descriptor = pc._lock(repo_one)
    try:
        if not expected_path.exists():
            fail("_lock must create its deterministic lock path")
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            fail("_lock file must be a regular file")
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            fail("_lock file must be created with mode 0o600")
        descriptor_two = pc._lock(repo_two)
        try:
            identity_two = hashlib.sha256(str(repo_two).encode()).hexdigest()
            if identity_two == identity_one:
                fail("distinct repos must not collide on lock identity")
        finally:
            os.close(descriptor_two)
        reopened = pc._lock(repo_one)
        os.close(reopened)
    finally:
        os.close(descriptor)
        expected_path.unlink()
    symlink_target = tmp / "lock-target"
    symlink_target.write_bytes(b"x")
    expected_path.symlink_to(symlink_target)
    try:
        pc._lock(repo_one)
    except OSError:
        pass
    else:
        fail("_lock must refuse to follow a symlink at its lock path (O_NOFOLLOW)")
    finally:
        expected_path.unlink()
    fifo_repo = tmp / "lock-repo-fifo"
    fifo_repo.mkdir()
    fifo_identity = hashlib.sha256(str(fifo_repo).encode()).hexdigest()
    fifo_path = Path(tempfile.gettempdir()) / f"hard-eng-plan-cleanup-{fifo_identity}.lock"
    if fifo_path.exists():
        fifo_path.unlink()
    os.mkfifo(fifo_path, 0o600)
    try:
        expect_error("cleanup lock is not a private current-user file", pc._lock, fifo_repo)
    finally:
        fifo_path.unlink()


def check_git_common_dir(tmp: Path) -> None:
    repo = make_repo(tmp)
    plain = pc._git_common_dir(repo)
    if plain != (repo / ".git").resolve():
        fail(f"_git_common_dir must resolve a plain repo's relative .git dir, got {plain}")
    worktree = tmp / "linked-worktree"
    git(repo, "worktree", "add", "-q", "-b", "wt-branch", str(worktree))
    linked = pc._git_common_dir(worktree)
    if linked != (repo / ".git").resolve():
        fail(f"_git_common_dir must resolve a linked worktree's absolute common dir, got {linked}")


def check_note_path_and_bytes(tmp: Path) -> None:
    repo = make_repo(tmp)
    action = "sha256:" + "c" * 64
    note_path = pc._note_path(repo, action)
    owner = pc._git_common_dir(repo) / "hard-eng"
    if note_path.parent != owner:
        fail("_note_path must live under <git-common-dir>/hard-eng")
    if stat.S_IMODE(os.lstat(owner).st_mode) != 0o700:
        fail("_note_path owner directory must be mode 0o700")
    if note_path.name != f"plan-cleanup-{'c' * 20}.json":
        fail(f"_note_path filename must use the first 20 hex chars after sha256:, got {note_path.name}")
    again = pc._note_path(repo, action)
    if again != note_path:
        fail("_note_path must be idempotent for the same action digest")
    unprefixed = pc._note_path(repo, "d" * 64)
    if unprefixed.name != f"plan-cleanup-{'d' * 20}.json":
        fail("_note_path must tolerate an action digest without the sha256: prefix")
    if pc._note_path(repo, "sha256:" + "e" * 64).name == pc._note_path(repo, "sha256:" + "f" * 64).name:
        fail("_note_path must vary its filename with the action digest")

    note: dict[str, object] = {"b": 2, "a": 1}
    encoded = pc._note_bytes(note)
    if encoded != (json.dumps(note, indent=2, sort_keys=True) + "\n").encode():
        fail("_note_bytes must match sorted, 2-indent json plus trailing newline")
    if not encoded.endswith(b"\n"):
        fail("_note_bytes must end with a trailing newline")
    if encoded.index(b'"a"') > encoded.index(b'"b"'):
        fail("_note_bytes must sort keys")
    if b"\n  " not in encoded:
        fail("_note_bytes must use two-space indentation")

    unsafe_owner_repo = tmp / "unsafe-owner-repo"
    unsafe_owner_repo.mkdir()
    git(unsafe_owner_repo, "init", "-q")
    unsafe_owner = pc._git_common_dir(unsafe_owner_repo) / "hard-eng"
    elsewhere = tmp / "elsewhere"
    elsewhere.mkdir()
    unsafe_owner.symlink_to(elsewhere)
    expect_error("Git-private recovery directory is unsafe", pc._note_path, unsafe_owner_repo, action)
    unsafe_owner.unlink()

    file_owner_repo = tmp / "file-owner-repo"
    file_owner_repo.mkdir()
    git(file_owner_repo, "init", "-q")
    file_owner = pc._git_common_dir(file_owner_repo) / "hard-eng"
    file_owner.write_bytes(b"not a directory")
    expect_error("Git-private recovery directory is unsafe", pc._note_path, file_owner_repo, action)


def check_write_note(tmp: Path) -> None:
    path = tmp / "note.json"
    note: dict[str, object] = {"status": "running"}
    written = pc._write_note(path, note)
    if not path.exists():
        fail("_write_note must create the file when previous is None")
    if path.read_bytes() != written:
        fail("_write_note must persist exactly the bytes it returns")
    expect_error("recovery note already exists", pc._write_note, path, note)
    updated: dict[str, object] = {"status": "completed"}
    replaced = pc._write_note(path, updated, written)
    if path.read_bytes() != replaced or replaced == written:
        fail("_write_note must replace the file when given a matching preimage")
    try:
        pc._write_note(path, {"status": "stale"}, written)
    except safe_file.SafeFileError:
        pass
    else:
        fail("_write_note must reject a stale preimage")


def check_head_preimage(tmp: Path) -> None:
    repo = make_repo(tmp)
    untracked = repo / "untracked.txt"
    untracked.write_bytes(b"anything")
    pc._head_preimage(repo, Path("untracked.txt"), b"does not matter")

    tracked = repo / "tracked.txt"
    tracked.write_bytes(b"tracked content")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-q", "-m", "add tracked")
    pc._head_preimage(repo, Path("tracked.txt"), b"tracked content")
    preimage_message = "tracked HEAD preimage mismatch"
    expect_error(preimage_message, pc._head_preimage, repo, Path("tracked.txt"), b"different content")

    staged_only = repo / "staged.txt"
    staged_only.write_bytes(b"")
    git(repo, "add", "staged.txt")
    expect_error(preimage_message, pc._head_preimage, repo, Path("staged.txt"), b"non-empty-mismatch")
    expect_error(preimage_message, pc._head_preimage, repo, Path("staged.txt"), b"")


def check_read_draft(tmp: Path) -> None:
    repo = make_repo(tmp).resolve()
    outside = tmp / "outside"
    outside.mkdir()

    expect_error("--candidate must be an absolute staging path", pc._read_draft, "relative/path.md", repo)

    inside = repo / "candidate.md"
    inside.write_text("hi", encoding="utf-8")
    expect_error("--candidate must stay outside the repository", pc._read_draft, str(inside), repo)

    good = outside / "candidate.md"
    good.write_text("hello draft", encoding="utf-8")
    if pc._read_draft(str(good), repo) != "hello draft":
        fail("_read_draft must return the exact decoded contents")

    as_directory = outside / "a-directory"
    as_directory.mkdir()
    expect_error("draft candidate must be a current-user regular file", pc._read_draft, str(as_directory), repo)

    symlink_path = outside / "candidate-link.md"
    symlink_target = outside / "candidate-target.md"
    symlink_target.write_text("target text", encoding="utf-8")
    symlink_path.symlink_to(symlink_target)
    try:
        pc._read_draft(str(symlink_path), repo)
    except OSError:
        pass
    else:
        fail("_read_draft must refuse to follow a symlink candidate (O_NOFOLLOW)")

    at_limit = outside / "at-limit.md"
    at_limit.write_bytes(b"a" * pc.MAX_DRAFT_BYTES)
    if len(pc._read_draft(str(at_limit), repo)) != pc.MAX_DRAFT_BYTES:
        fail("_read_draft must accept a candidate exactly at MAX_DRAFT_BYTES")

    over_limit = outside / "over-limit.md"
    over_limit.write_bytes(b"a" * (pc.MAX_DRAFT_BYTES + 1))
    expect_error("draft candidate exceeds 1 MiB", pc._read_draft, str(over_limit), repo)

    invalid_utf8 = outside / "invalid.md"
    invalid_utf8.write_bytes(b"\xff\xfe not utf-8")
    expect_error("draft candidate must be UTF-8", pc._read_draft, str(invalid_utf8), repo)


def check_state_block() -> None:
    text = f"before\n{pc.STATE_START}\nbody\n{pc.STATE_END}\nafter\n"
    block = pc._state_block(text)
    if block != f"{pc.STATE_START}\nbody\n{pc.STATE_END}":
        fail(f"_state_block must return exactly the marked block, got {block!r}")
    if not block.startswith(pc.STATE_START) or not block.endswith(pc.STATE_END):
        fail("_state_block bounds must include both markers exactly once")

    one_block_message = "draft requires exactly one v1 State block"
    no_markers = "no markers here"
    expect_error(one_block_message, pc._state_block, no_markers)

    two_starts = f"{pc.STATE_START}\n{pc.STATE_START}\nbody\n{pc.STATE_END}\n"
    expect_error(one_block_message, pc._state_block, two_starts)

    two_ends = f"{pc.STATE_START}\nbody\n{pc.STATE_END}\n{pc.STATE_END}\n"
    expect_error(one_block_message, pc._state_block, two_ends)

    end_before_start = f"before\n{pc.STATE_END}\nmiddle\n{pc.STATE_START}\nafter\n"
    try:
        pc._state_block(end_before_start)
    except ValueError:
        pass
    else:
        fail("_state_block must not silently accept an END marker preceding START")


def run_draft(repo: Path, **overrides) -> None:
    args = SimpleNamespace(repo=str(repo), plan="", expect_token="", candidate="")
    for key, value in overrides.items():
        setattr(args, key, value)
    pc.draft(args, stub_validate_plan, overrides["emit_plan"])


def check_draft(tmp: Path) -> None:
    repo = make_repo(tmp)
    guard_lock = none_lock_path()
    guard_lock.unlink(missing_ok=True)
    text = base_plan_text("building", "draft-demo")
    plan_path = write_plan(repo, "draft-demo", text, commit=True)
    outside = tmp / "draft-outside"
    outside.mkdir()
    candidate_text = text + "\nExtra body note.\n"
    candidate_path = outside / "candidate.md"
    candidate_path.write_text(candidate_text, encoding="utf-8")
    emitted = []

    def emit_plan(path, candidate, updated):
        emitted.append((path, candidate, updated))

    def expect_draft_error(message, plan_path, token, candidate_path):
        expect_error(
            message,
            run_draft,
            repo,
            plan=str(plan_path),
            expect_token=token,
            candidate=str(candidate_path),
            emit_plan=emit_plan,
        )

    run_draft(
        repo, plan=str(plan_path), expect_token=token_for(text), candidate=str(candidate_path), emit_plan=emit_plan
    )
    if guard_lock.exists():
        fail("draft() must lock using the real repo identity, not None")
    if plan_path.read_text(encoding="utf-8") != candidate_text:
        fail("draft() must persist the candidate text on success")
    if len(emitted) != 1 or emitted[0][0] != plan_path.resolve() or emitted[0][1] != candidate_text:
        fail("draft() must call emit_plan with the written path and candidate text")

    terminal_text = base_plan_text("shipped", "draft-terminal")
    terminal_path = write_plan(repo, "draft-terminal", terminal_text, commit=True)
    expect_draft_error("terminal PLAN content is immutable", terminal_path, token_for(terminal_text), candidate_path)

    stale_text = base_plan_text("building", "draft-stale")
    stale_path = write_plan(repo, "draft-stale", stale_text, commit=True)
    expect_draft_error("stale plan token", stale_path, "sha256:" + "0" * 64, candidate_path)

    title_text = base_plan_text("building", "draft-title")
    title_path = write_plan(repo, "draft-title", title_text, commit=True)
    bad_title_candidate = outside / "bad-title.md"
    bad_title_candidate.write_text("# PLAN: different-title\n\n" + pc._state_block(title_text) + "\n", encoding="utf-8")
    title_block_message = "draft candidate must preserve the exact title and State block"
    expect_draft_error(title_block_message, title_path, token_for(title_text), bad_title_candidate)
    if title_path.read_text(encoding="utf-8") != title_text:
        fail("draft() must not persist anything when the candidate title mismatches")

    state_text = base_plan_text("building", "draft-state")
    state_path = write_plan(repo, "draft-state", state_text, commit=True)
    bad_state_candidate = outside / "bad-state.md"
    bad_state_candidate.write_text(
        state_text.splitlines()[0] + "\n\n" + pc.STATE_START + "\nchanged\n" + pc.STATE_END + "\n", encoding="utf-8"
    )
    expect_draft_error(title_block_message, state_path, token_for(state_text), bad_state_candidate)


def run_cleanup(repo: Path, decision: str, item_strings, *, apply=False, confirm_delete=False, confirm_cancel=False):
    args = SimpleNamespace(
        repo=str(repo),
        decision=decision,
        item=item_strings,
        apply=apply,
        confirm_delete=confirm_delete,
        confirm_cancel=confirm_cancel,
    )
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        pc.run(args, stub_validate_plan, stub_render_template, stub_render_state)
    return buffer.getvalue()


def item_string(repo: Path, path: Path) -> str:
    digest = pc._digest(path.read_bytes())
    return f"{path.relative_to(repo)}={digest.removeprefix('sha256:')}"


def check_run_decision_validation(tmp: Path) -> None:
    repo = make_repo(tmp)
    slug = "decision-demo"
    text = base_plan_text("building")
    path = write_plan(repo, slug, text, commit=True)
    item = item_string(repo, path)
    for bad_decision in ("", "   ", "line one\nline two", "carriage\rreturn"):
        expect_error("--decision must be one nonempty line", run_cleanup, repo, bad_decision, [item])
    output = run_cleanup(repo, "  cancel it  ", [item])
    if "result=preview" not in output.splitlines():
        fail("run() preview must print result=preview exactly")


def check_run_hash_and_utf8(tmp: Path) -> None:
    repo = make_repo(tmp)
    slug = "hash-demo"
    text = base_plan_text("building")
    path = write_plan(repo, slug, text, commit=True)
    relative = path.relative_to(repo)
    wrong_item = f"{relative}={'0' * 64}"
    expect_error("cleanup hash mismatch", run_cleanup, repo, "cancel", [wrong_item])

    binary_slug = "binary-demo"
    binary_path = repo / "features" / binary_slug / "PLAN.md"
    binary_path.parent.mkdir(parents=True)
    binary_path.write_bytes(b"\xff\xfe not utf-8")
    git(repo, "add", str(binary_path.relative_to(repo)))
    git(repo, "commit", "-q", "-m", "binary plan")
    binary_item = item_string(repo, binary_path)
    expect_error("PLAN is not UTF-8", run_cleanup, repo, "cancel", [binary_item])

    drift_path = write_plan(repo, "preimage-drift", base_plan_text(tag="preimage-drift"), commit=True)
    drift_path.write_bytes(b"uncommitted drift that no longer matches HEAD\n")
    drift_item = item_string(repo, drift_path)
    expect_error("tracked HEAD preimage mismatch", run_cleanup, repo, "cancel", [drift_item])


def check_run_preview_routes(tmp: Path) -> None:
    repo = make_repo(tmp)
    terminal_path = write_plan(repo, "preview-terminal", base_plan_text("shipped"), commit=True)
    nonterminal_path = write_plan(repo, "preview-nonterminal", base_plan_text("building"), commit=True)
    invalid_path = write_plan(repo, "preview-invalid", "# PLAN: preview-invalid\n\nINVALID-MARKER\n", commit=True)
    terminal_item = item_string(repo, terminal_path)
    output_terminal = run_cleanup(repo, "cancel", [terminal_item])
    if "terminal->removed" not in output_terminal or "requires_confirm_cancel=no" not in output_terminal:
        fail(f"preview for an already-terminal PLAN must not require cancel confirmation: {output_terminal!r}")
    if "requires_confirm_delete=yes" not in output_terminal.splitlines():
        fail("preview must always require delete confirmation exactly")

    nonterminal_item = item_string(repo, nonterminal_path)
    output_nonterminal = run_cleanup(repo, "cancel", [nonterminal_item])
    if (
        "nonterminal->cancelled->removed" not in output_nonterminal
        or "requires_confirm_cancel=yes" not in output_nonterminal
    ):
        fail(
            f"preview for a nonterminal PLAN must route through cancel and require confirmation: {output_nonterminal!r}"
        )

    invalid_item = item_string(repo, invalid_path)
    output_invalid = run_cleanup(repo, "cancel", [invalid_item])
    if "invalid->cancelled->removed" not in output_invalid or "requires_confirm_cancel=yes" not in output_invalid:
        fail(f"preview for an invalid legacy PLAN must route through cancel: {output_invalid!r}")

    next_action = "Cancelled by exact user decision: cancel"
    nonterminal_changes = {
        "lifecycle_status": "cancelled",
        "green_artifact": "none",
        "active_slice": "none",
        "next_action": next_action,
    }
    if RENDER_STATE_CALLS[-2] != nonterminal_changes:
        fail(f"nonterminal cancel render_state changes drifted: {RENDER_STATE_CALLS[-2]}")
    invalid_changes = {
        "lifecycle_status": "cancelled",
        "approval_status": "pending",
        "approval_fingerprint": "none",
        "approval_provenance": "none",
        "green_artifact": "none",
        "active_slice": "none",
        "completed_slices": "none",
        "next_action": next_action,
        "replan_reason": "none",
    }
    if RENDER_STATE_CALLS[-1] != invalid_changes:
        fail(f"invalid legacy render_state changes drifted: {RENDER_STATE_CALLS[-1]}")
    if RENDER_TEMPLATE_CALLS[-1][0] != "preview-invalid":
        fail(f"render_template must receive the item's own slug: {RENDER_TEMPLATE_CALLS[-1]}")
    expected_actual = pc._digest(invalid_path.read_bytes())
    if RENDER_TEMPLATE_CALLS[-1][1] != f"legacy-cleanup-{expected_actual[-12:]}":
        fail(f"render_template plan_id must use the last 12 chars of the item hash: {RENDER_TEMPLATE_CALLS[-1]}")
    if not any(call is True for call in VALIDATE_CALLS):
        fail("run() must validate candidates with allow_legacy_missing_ux_reference=True")

    if terminal_path.read_bytes() != base_plan_text("shipped").encode("utf-8"):
        fail("preview mode must never modify PLAN files")
    action_line = next(line for line in output_terminal.splitlines() if line.startswith("action_digest="))
    item_line = next(line for line in output_terminal.splitlines() if line.startswith("item="))
    expected_hash = pc._digest(terminal_path.read_bytes())
    if item_line != f"item={terminal_path.relative_to(repo)}|{expected_hash}|terminal->removed":
        fail(f"preview item line format drifted: {item_line!r}")
    if not action_line.split("=", 1)[1].startswith("sha256:"):
        fail("preview action_digest must be sha256-prefixed")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="plan-cleanup-survivors-") as raw:
        tmp = Path(raw)
        check_digest_and_action_digest()
        check_parse_items()
        check_lock(tmp)
        check_git_common_dir(tmp)
        check_note_path_and_bytes(tmp)
        check_write_note(tmp)
        check_head_preimage(tmp)
        check_read_draft(tmp)
        check_state_block()
        check_draft(tmp)
        check_run_decision_validation(tmp)
        check_run_hash_and_utf8(tmp)
        check_run_preview_routes(tmp)
    print("plan-cleanup-survivors: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
