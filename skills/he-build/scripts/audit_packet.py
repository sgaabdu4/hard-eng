#!/usr/bin/env python3
"""Construct bounded, secret-safe evidence packets for Hard Eng audits."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from audit_contract import PLAN_PATH, AuditError
from generated_evidence import generated_diff, generated_file
import related_context as related_context_api
from related_context import RelatedContextError, current_plan_intent, related_context
from repository_index import RepositoryIndex, repository_source_index
from repository_snapshot import SnapshotError, snapshot_id as repository_snapshot_id
from secret_scanner import EncodedTextError, decode_text_bytes, secret_marker, sensitive_path


SCRIPT_DIR = Path(__file__).resolve().parent
AGENTS_ROOT = SCRIPT_DIR.parents[2]
E2E_SCRIPT_DIR = AGENTS_ROOT / "skills/e2e/scripts"
if str(E2E_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(E2E_SCRIPT_DIR))
STATE_SCRIPT_DIR = AGENTS_ROOT / "skills/he/scripts"
if str(STATE_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(STATE_SCRIPT_DIR))
from plan_items import closed_plan_authority  # noqa: E402
from visual_evidence import EvidenceError, parent_provenance  # noqa: E402

DEFAULT_MAX_PACKET_BYTES = 800 * 1024
STRUCTURAL_DIFF_CONTEXT = 8
DIAGNOSTIC_MAX_RELATED_SECTIONS = 4096
DIAGNOSTIC_MAX_RELATED_BYTES = 8 * 1024 * 1024
DIAGNOSTIC_MAX_PACKET_BYTES = 8 * 1024 * 1024
SCANNED_HISTORY: set[tuple[str, str, str]] = set()


@dataclass(frozen=True)
class ReviewScope:
    primary_paths: tuple[str, ...]
    coverage_paths: tuple[str, ...]
    packet: str
    related_units: tuple[tuple[str, int], ...]
    packet_units: tuple[tuple[str, int], ...]
    related_sections: int
    related_bytes: int
    packet_bytes: int
    citation_paths: tuple[str, ...] = ()


class ReviewScopeOverflow(AuditError):
    def __init__(self, scope: ReviewScope):
        super().__init__(f"single-path review scope exceeds fixed limits: {scope.primary_paths[0]}")
        self.scope = scope


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


@lru_cache(maxsize=64)
def visual_provenance_packet(
    root_value: str, relative: str, repository_snapshot: str
) -> str:
    root = Path(root_value)
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise AuditError(f"visual evidence receipt is not a regular file: {relative}")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
        record = parent_provenance(
            receipt, root, repository_snapshot, relative
        )
    except (EvidenceError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"invalid visual evidence receipt: {relative}: {exc}") from exc
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def add_packet_section(
    sections: list[str], label: str, content: str, relative: str | None = None
) -> None:
    marker = secret_marker(content, relative)
    if marker:
        raise AuditError(f"{marker} content blocks audit: {label}")
    sections.extend((label, content))


def add_required_related_context(
    sections: list[str], context: tuple[tuple[str, str, str], ...], max_packet_bytes: int | None = None
) -> None:
    limit = DEFAULT_MAX_PACKET_BYTES if max_packet_bytes is None else max_packet_bytes
    for relative, label, content in context:
        candidate = "\n\n".join((*sections, label, content))
        if len(candidate.encode("utf-8", "surrogateescape")) > limit:
            raise AuditError(f"review packet has no room for required related context: {label}")
        add_packet_section(sections, label, content, relative)


def safe_payload(data: bytes) -> tuple[str, bool]:
    try:
        text = decode_text_bytes(data)
    except EncodedTextError as exc:
        raise AuditError(str(exc)) from exc
    if text is not None:
        return text, True
    kind = "binary" if b"\0" in data else "non-utf8"
    return f"<{kind} bytes={len(data)} sha256={hashlib.sha256(data).hexdigest()}>", False


def require_safe_bytes(data: bytes, label: str, relative: str | None = None) -> None:
    try:
        decoded = decode_text_bytes(data)
    except EncodedTextError as exc:
        raise AuditError(f"malformed encoded text blocks audit: {label}") from exc
    for text in (data.decode("latin-1"), decoded):
        if text is not None and (marker := secret_marker(text, relative)):
            raise AuditError(f"{marker} raw bytes block audit: {label}")


def packet_file(path: Path, relative: str | None = None) -> str:
    if path.is_symlink():
        return "<symlink>"
    data = path.read_bytes()
    require_safe_bytes(data, str(path), relative)
    return safe_payload(data)[0]


def required_packet_file(path: Path, label: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise AuditError(f"review packet requires regular file: {label}")
    return packet_file(path, label)


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
        require_safe_bytes(data, f"diff:{'/'.join(revisions)}:{relative}", relative)
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


def plan_base_sha(root: Path, plan: Path) -> str:
    match = re.search(r"(?m)^- base_sha = ([0-9a-f]{40})$", plan.read_text(encoding="utf-8"))
    if not match:
        raise AuditError("PLAN base_sha is missing or invalid")
    base = match.group(1)
    resolved = git(root, "rev-parse", "--verify", f"{base}^{{commit}}", check=False).decode().strip()
    ancestor = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", base, "HEAD"],
        capture_output=True,
        check=False,
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
                require_safe_bytes(data, relative, relative)
                seen.add(digest)


def commit_paths(root: Path, parent: str, commit: str) -> tuple[str, ...]:
    raw = git(
        root, "diff", "--name-only", "-z", parent, commit, "--", ".",
        ":(exclude,glob)features/*/PLAN.md",
    )
    return tuple(sorted(part.decode("utf-8", "surrogateescape") for part in raw.split(b"\0") if part))


def scan_commit_history(root: Path, base: str) -> None:
    head = git(root, "rev-parse", "HEAD").decode().strip()
    cache_key = (str(root), base, head)
    if cache_key in SCANNED_HISTORY:
        return
    commits = tuple(
        line for line in git(root, "rev-list", "--reverse", f"{base}..HEAD").decode().splitlines() if line
    )
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
                require_safe_bytes(
                    git(root, "show", f"{commit}:{relative}"), f"{relative}@{commit}", relative
                )
    SCANNED_HISTORY.add(cache_key)


def reject_changed_symlinks(root: Path, changed: tuple[str, ...], base: str) -> None:
    for relative in changed:
        modes = [git(root, "ls-tree", revision, "--", relative, check=False) for revision in (base, "HEAD")]
        modes.append(git(root, "ls-files", "--stage", "--", relative, check=False))
        if (root / relative).is_symlink() or any(data.startswith(b"120000 ") for data in modes):
            raise AuditError(f"changed symlink blocks audit: {relative}")


def review_packet_parts(
    repo: Path, plan: Path, *, related_max_sections: int | None = None,
    related_max_bytes: int | None = None, max_packet_bytes: int | None = None,
    changed_paths_override: tuple[str, ...] | None = None,
    full_file_paths: tuple[str, ...] = (),
    planned_unit: tuple[str, tuple[str, ...], tuple[str, ...]] | None = None,
    repository_index: RepositoryIndex | None = None,
    defer_related_packet_limit: bool = False,
) -> tuple[list[str], list[tuple[str, str]], tuple[tuple[str, str, str], ...]]:
    root = repository_root(repo.resolve())
    repository_snapshot = snapshot_id(root)
    sections = ["# Review packet", f"snapshot = {repository_snapshot}"]
    base = plan_base_sha(root, plan)
    tracked = tuple(
        part.decode("utf-8", "surrogateescape")
        for part in git(root, "ls-files", "-z").split(b"\0")
        if part
    )
    changed = changed_paths(root, base) if changed_paths_override is None else changed_paths_override
    scoped = (*changed, plan.resolve().relative_to(root).as_posix())
    for relative in applicable_rule_paths(tracked, scoped):
        add_packet_section(sections, f"## Rules: {relative}", required_packet_file(root / relative, relative))
    plan_text = packet_file(plan.resolve(), plan.resolve().relative_to(root).as_posix())
    context_paths = ["PRODUCT.md"]
    if not re.search(r"(?m)^- build_axes = .*\bui-design:na(?:,|$)", plan_text):
        context_paths.append("DESIGN.md")
    for relative in context_paths:
        path = root / relative
        add_packet_section(
            sections, f"## Context: {relative}", required_packet_file(path, relative), relative
        )
    visual_receipts = tuple(
        relative for relative in changed
        if Path(relative).name == "visual-review-receipt.json"
        and (root / relative).is_file()
    )
    review_contracts = [
        "skills/code-review/SKILL.md",
        "skills/code-review/references/spec.md",
    ]
    if visual_receipts:
        review_contracts.append("skills/e2e/references/visual-evidence.md")
    for relative in review_contracts:
        path = AGENTS_ROOT / relative
        if path.is_symlink() or not path.is_file():
            raise AuditError(f"review packet missing contract: {relative}")
        add_packet_section(
            sections, f"## Review contract: {relative}", packet_file(path, relative), relative
        )
    for relative in visual_receipts:
        add_packet_section(
            sections,
            f"## Parent visual provenance: {relative}",
            visual_provenance_packet(str(root), relative, repository_snapshot),
            relative,
        )
    resolved_plan = plan.resolve()
    add_packet_section(
        sections,
        f"## Intent: {resolved_plan.relative_to(root).as_posix()}",
        current_plan_intent(plan_text),
    )
    add_packet_section(
        sections, "## Closed PLAN authority", closed_plan_authority(plan_text)
    )
    for relative in changed:
        if sensitive_path(relative):
            raise AuditError(f"sensitive path blocks audit: {relative}")
    reject_changed_symlinks(root, changed, base)
    scan_changed_bytes(root, changed, base)
    if planned_unit is None:
        scan_commit_history(root, base)
        commit_log = git(root, "log", "--oneline", f"{base}..HEAD", check=False).decode("utf-8", "replace")
        final_units = scoped_diff_units(root, (base,), changed, STRUCTURAL_DIFF_CONTEXT)
        add_packet_section(
            sections, "## Commit provenance (non-authoritative)", commit_log or "<none>"
        )
        units = []
        if final_units:
            units.extend((f"## Authoritative final base-to-worktree diff: {relative}", content)
                         for relative, content in final_units)
        else:
            units.append(("## Authoritative final base-to-worktree diff", "<none>"))
        for relative in untracked_paths(root):
            normalized = Path(relative).as_posix()
            if PLAN_PATH.fullmatch(normalized):
                continue
            if changed_paths_override is not None and normalized not in changed:
                continue
            if sensitive_path(normalized):
                raise AuditError(f"sensitive untracked path blocks audit: {normalized}")
            content = generated_file(root / relative, normalized)
            units.append((
                f"## Untracked: {normalized}", content or packet_file(root / relative, normalized)
            ))
    else:
        unit_id, planned_paths, unresolved = planned_unit
        absent = set(unresolved)
        manifest = "\n".join(
            f"{relative} | {'absent' if relative in absent else 'existing-full-file'}"
            for relative in planned_paths
        )
        units = [(f"## Planned unit estimate: {unit_id}", manifest)]
    try:
        section_limit = related_context_api.MAX_SECTIONS if related_max_sections is None else related_max_sections
        byte_limit = related_context_api.MAX_BYTES if related_max_bytes is None else related_max_bytes
        context = related_context(root, changed, base, max_sections=section_limit,
                                  max_bytes=byte_limit, full_file_paths=full_file_paths,
                                  repository_index=repository_index)
    except RelatedContextError as exc:
        raise AuditError(str(exc)) from exc
    if defer_related_packet_limit:
        for relative, label, content in context:
            marker = secret_marker(content, relative)
            if marker:
                raise AuditError(f"{marker} content blocks audit: {label}")
            units.append((label, content))
    else:
        combined = [*sections, *(value for unit in units for value in unit)]
        before = len(combined)
        add_required_related_context(combined, context, max_packet_bytes)
        appended = combined[before:]
        units.extend((appended[index], appended[index + 1]) for index in range(0, len(appended), 2))
    return sections, units, context


def review_packet(repo: Path, plan: Path, *, max_packet_bytes: int | None = None) -> str:
    limit = DEFAULT_MAX_PACKET_BYTES if max_packet_bytes is None else max_packet_bytes
    sections, units, _ = review_packet_parts(repo, plan, max_packet_bytes=limit)
    packet = "\n\n".join([*sections, *(value for unit in units for value in unit)])
    packet = packet.replace(str(repository_root(repo.resolve())), "<repo-root>")
    if len(packet.encode("utf-8", "surrogateescape")) > limit:
        raise AuditError(f"review packet exceeds {limit} bytes")
    return packet


def packet_measurements(sections, units) -> tuple[int, tuple[tuple[str, int], ...]]:
    packet = "\n\n".join([*sections, *(value for unit in units for value in unit)])
    measured: list[tuple[str, int]] = [
        ("Review packet header", len("\n\n".join(sections[:2]).encode("utf-8", "surrogateescape")))
    ]
    for index in range(2, len(sections), 2):
        label, content = sections[index], sections[index + 1]
        measured.append((label, 4 + len((label + "\n\n" + content).encode("utf-8", "surrogateescape"))))
    for label, content in units:
        measured.append((label, 4 + len((label + "\n\n" + content).encode("utf-8", "surrogateescape"))))
    return len(packet.encode("utf-8", "surrogateescape")), tuple(measured)


def citation_paths(
    sections: list[str], primary_paths: tuple[str, ...], context: tuple[tuple[str, str, str], ...],
) -> tuple[str, ...]:
    paths = set(primary_paths)
    for index in range(2, len(sections), 2):
        label = sections[index]
        for prefix in ("## Rules: ", "## Context: ", "## Review contract: "):
            if label.startswith(prefix):
                paths.add(label.removeprefix(prefix))
    paths.update(relative for relative, _, _ in context)
    return tuple(sorted(paths))


def _measure_review_scope(
    repo: Path, plan: Path, primary_paths: tuple[str, ...], *,
    full_files: bool, planned_unit_id: str | None, repository_index: RepositoryIndex,
) -> ReviewScope:
    existing = tuple(path for path in primary_paths if (repo / path).is_file())
    planned = None
    changed = primary_paths
    if planned_unit_id is not None:
        unresolved = tuple(path for path in primary_paths if not (repo / path).exists())
        planned = (planned_unit_id, primary_paths, unresolved)
        changed = existing
    sections, units, context = review_packet_parts(
        repo, plan, related_max_sections=DIAGNOSTIC_MAX_RELATED_SECTIONS,
        related_max_bytes=DIAGNOSTIC_MAX_RELATED_BYTES,
        max_packet_bytes=DIAGNOSTIC_MAX_PACKET_BYTES, changed_paths_override=changed,
        full_file_paths=existing if full_files else (), planned_unit=planned,
        repository_index=repository_index,
    )
    packet_bytes, packet_units = packet_measurements(sections, units)
    related_units = tuple((entry[1], sum(len(value.encode("utf-8", "surrogateescape"))
                                         for value in entry)) for entry in context)
    packet = "\n\n".join([*sections, *(value for unit in units for value in unit)])
    packet = packet.replace(str(repository_root(repo.resolve())), "<repo-root>")
    return ReviewScope(
        primary_paths=primary_paths, coverage_paths=primary_paths, packet=packet,
        related_units=related_units,
        packet_units=packet_units, related_sections=len(context),
        related_bytes=sum(size for _, size in related_units), packet_bytes=packet_bytes,
        citation_paths=citation_paths(sections, primary_paths, context),
    )


def _context_size(entry: tuple[str, str, str]) -> int:
    return sum(len(value.encode("utf-8", "surrogateescape")) for value in entry)


def _split_text(text: str, limit: int) -> tuple[str, ...]:
    if limit < 4:
        raise AuditError("review shard has no room for UTF-8 context")
    parts: list[str] = []
    current: list[str] = []
    size = 0
    for character in text:
        width = len(character.encode("utf-8", "surrogateescape"))
        if current and size + width > limit:
            parts.append("".join(current))
            current, size = [], 0
        current.append(character)
        size += width
    if current or not parts:
        parts.append("".join(current))
    return tuple(parts)


def _split_context_entry(
    entry: tuple[str, str, str], common_bytes: int, *,
    max_related_bytes: int, max_packet_bytes: int,
) -> tuple[tuple[str, str, str], ...]:
    path, label, content = entry
    packet_size = 4 + len((label + "\n\n" + content).encode("utf-8", "surrogateescape"))
    if _context_size(entry) <= max_related_bytes and common_bytes + packet_size <= max_packet_bytes:
        return (entry,)
    reserve = 64
    content_limit = min(
        max_related_bytes - len((path + label).encode("utf-8", "surrogateescape")) - reserve,
        max_packet_bytes - common_bytes
        - len((label + "\n\n").encode("utf-8", "surrogateescape")) - reserve,
    )
    parts = _split_text(content, content_limit)
    return tuple((path, f"{label} [part {index}/{len(parts)}]", part)
                 for index, part in enumerate(parts, 1))


def _build_review_scopes(
    repo: Path, plan: Path, primary_paths: tuple[str, ...], *,
    max_related_sections: int, max_related_bytes: int, max_packet_bytes: int,
    full_files: bool, planned_unit_id: str | None, repository_index: RepositoryIndex,
) -> tuple[ReviewScope, ...]:
    existing = tuple(path for path in primary_paths if (repo / path).is_file())
    planned = None
    changed = primary_paths
    if planned_unit_id is not None:
        unresolved = tuple(path for path in primary_paths if not (repo / path).exists())
        planned = (planned_unit_id, primary_paths, unresolved)
        changed = existing
    sections, units, context = review_packet_parts(
        repo, plan, related_max_sections=DIAGNOSTIC_MAX_RELATED_SECTIONS,
        related_max_bytes=DIAGNOSTIC_MAX_RELATED_BYTES,
        changed_paths_override=changed, full_file_paths=existing if full_files else (),
        planned_unit=planned, repository_index=repository_index,
        defer_related_packet_limit=True,
    )
    base_units = units[:-len(context)] if context else units
    common_bytes, common_units = packet_measurements(sections, base_units)
    common_limit = max_packet_bytes if len(primary_paths) == 1 else max_packet_bytes // 2
    if common_bytes > common_limit:
        raise ReviewScopeOverflow(ReviewScope(
            primary_paths, primary_paths, "", (), common_units, 0, 0, common_bytes,
        ))
    try:
        pieces = tuple(piece for entry in context for piece in _split_context_entry(
            entry, common_bytes, max_related_bytes=max_related_bytes,
            max_packet_bytes=max_packet_bytes,
        ))
    except AuditError as exc:
        raise ReviewScopeOverflow(ReviewScope(
            primary_paths, primary_paths, "", (), common_units, 1,
            max_related_bytes + 1, max_packet_bytes + 1,
        )) from exc
    chunks: list[tuple[tuple[str, str, str], ...]] = []
    current: list[tuple[str, str, str]] = []

    def within_limits(entries: tuple[tuple[str, str, str], ...]) -> bool:
        trial_units = [*base_units, *((label, content) for _, label, content in entries)]
        packet_bytes, _ = packet_measurements(sections, trial_units)
        return (
            len(entries) <= max_related_sections
            and sum(_context_size(entry) for entry in entries) <= max_related_bytes
            and packet_bytes <= max_packet_bytes
        )

    for piece in pieces:
        trial = (*current, piece)
        if within_limits(trial):
            current.append(piece)
            continue
        if not current:
            raise ReviewScopeOverflow(ReviewScope(
                primary_paths, primary_paths, "", ((piece[1], _context_size(piece)),),
                common_units, 1, _context_size(piece), max_packet_bytes + 1,
            ))
        chunks.append(tuple(current))
        if not within_limits((piece,)):
            raise ReviewScopeOverflow(ReviewScope(
                primary_paths, primary_paths, "", ((piece[1], _context_size(piece)),),
                common_units, 1, _context_size(piece), max_packet_bytes + 1,
            ))
        current = [piece]
    if current or not chunks:
        chunks.append(tuple(current))
    scopes = []
    root = repository_root(repo.resolve())
    for index, chunk in enumerate(chunks):
        shard_units = [*base_units, *((label, content) for _, label, content in chunk)]
        packet_bytes, packet_units = packet_measurements(sections, shard_units)
        packet = "\n\n".join([*sections, *(value for unit in shard_units for value in unit)])
        packet = packet.replace(str(root), "<repo-root>")
        related_units = tuple((entry[1], _context_size(entry)) for entry in chunk)
        scopes.append(ReviewScope(
            primary_paths=primary_paths,
            coverage_paths=primary_paths if index == 0 else (),
            packet=packet, related_units=related_units, packet_units=packet_units,
            related_sections=len(chunk), related_bytes=sum(size for _, size in related_units),
            packet_bytes=packet_bytes, citation_paths=citation_paths(sections, primary_paths, chunk),
        ))
    return tuple(scopes)


def partition_review_scopes(
    repo: Path, plan: Path, primary_paths: tuple[str, ...], *,
    max_related_sections: int, max_related_bytes: int, max_packet_bytes: int,
    full_files: bool = False, planned_unit_id: str | None = None,
    repository_index: RepositoryIndex | None = None,
) -> tuple[ReviewScope, ...]:
    if not primary_paths:
        raise AuditError("review scope requires at least one primary path")
    root = repository_root(repo.resolve())
    index = repository_source_index(root) if repository_index is None else repository_index
    cache: dict[tuple[str, ...], tuple[ReviewScope, ...] | None] = {}
    failures: dict[tuple[str, ...], ReviewScopeOverflow] = {}

    def built(paths: tuple[str, ...]) -> tuple[ReviewScope, ...] | None:
        if paths not in cache:
            try:
                cache[paths] = _build_review_scopes(
                    root, plan, paths, max_related_sections=max_related_sections,
                    max_related_bytes=max_related_bytes, max_packet_bytes=max_packet_bytes,
                    full_files=full_files, planned_unit_id=planned_unit_id,
                    repository_index=index,
                )
            except ReviewScopeOverflow as exc:
                cache[paths], failures[paths] = None, exc
            except AuditError as exc:
                message = str(exc)
                diagnostic = (
                    f"exceeds {DIAGNOSTIC_MAX_RELATED_SECTIONS} sections" in message
                    or f"exceeds {DIAGNOSTIC_MAX_RELATED_BYTES} bytes" in message
                )
                if not diagnostic:
                    raise
                scope = ReviewScope(
                    paths, paths, "", (), ((paths[0], max_packet_bytes + 1),),
                    max_related_sections + 1, max_related_bytes + 1, max_packet_bytes + 1,
                )
                cache[paths], failures[paths] = None, ReviewScopeOverflow(scope)
        return cache[paths]

    remaining = primary_paths
    scopes: list[ReviewScope] = []
    while remaining:
        first = built(remaining[:1])
        if first is None:
            raise failures[remaining[:1]]
        best = 1
        probe = 2
        while probe <= len(remaining) and built(remaining[:probe]) is not None:
            best = probe
            probe *= 2
        low, high = best + 1, min(len(remaining), probe - 1)
        while low <= high:
            middle = (low + high) // 2
            if built(remaining[:middle]) is not None:
                best = middle
                low = middle + 1
            else:
                high = middle - 1
        scopes.extend(built(remaining[:best]) or ())
        remaining = remaining[best:]
    covered = tuple(path for scope in scopes for path in scope.coverage_paths)
    if covered != primary_paths or len(set(covered)) != len(covered):
        raise AuditError("review scope coverage is incomplete or duplicated")
    return tuple(scopes)
