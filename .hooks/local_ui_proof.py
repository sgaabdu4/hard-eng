"""Fast local Complete-stage UI proof checks: pure file-record checks before ship, skipped in CI and --quick."""

import fnmatch
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import cast

from gate_config import ALL_ZERO_OBJECT_ID
from plans import _is_test as is_test_path

PLAN_PATH_TOKEN = re.compile(
    r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.*-]+)+/?|[A-Za-z0-9_.-]+/"
)
PLAN_ROUTE_TOKEN = re.compile(
    r"(?:^|[\s`(])(/(?:[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*/?))(?=$|[\s`),.;:?#])"
    r"|^(/)(?=$|[\s`),.;:?#])"
    r"|`(/)(?=`)"
    r"|\b(?:route|page|path|url)\s+(/)(?=$|[\s`),.;:?#])",
    re.IGNORECASE,
)
from ui_proof import (
    UNCHANGED_LINE,
    Change,
    _stem,
    browser_record_files,
    capture_set_problem,
    guideline_problem,
    is_native,
    look_base_problem,
    matches,
    merge_base,
    reference_problem,
    reference_section,
    surface_route,
    unchanged_problem,
    visible_files,
)


def in_ci() -> bool:
    return bool(os.environ.get("GITHUB_ACTIONS") or os.environ.get("CI"))


def _shipping_ui(root: Path) -> tuple[list[str], str] | None:
    try:
        data = json.loads((root / "hard-eng.gates.json").read_text())
        shipping = data.get("shipping")
        if not isinstance(shipping, dict):
            return None
        patterns = shipping.get("ui_paths")
        base = shipping.get("base")
        if (
            isinstance(patterns, list)
            and patterns
            and all(isinstance(item, str) for item in patterns)
            and isinstance(base, str)
            and base
        ):
            return list(patterns), base
    except (OSError, ValueError, TypeError):
        return None
    return None


def evidence_root(root: Path) -> Path:
    """The checkout holding local browser and look records; inside a pre-push snapshot, that is its owner."""
    from tool_setup import TOOL_OWNER

    snapshot, _, owner = os.environ.get(TOOL_OWNER, "").partition(os.pathsep)
    if snapshot and owner and Path(snapshot).resolve() == root.resolve():
        candidate = Path(owner)
        if candidate.is_dir():
            return candidate
    return root


def _git_stdout(root: Path, *args: str) -> str | None:
    done = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )
    return done.stdout if done.returncode == 0 else None


def _parse_patches(raw: str) -> dict[str, str | None]:
    from comments import header_path

    patches: dict[str, str | None] = {}
    current = ""
    lines: list[str] = []
    binary_file = False
    for line in raw.splitlines():
        if line.startswith("diff --git "):
            if current:
                patches[current] = None if binary_file else "\n".join(lines)
            current = ""
            lines = []
            binary_file = False
        elif (
            line.startswith("+++ ") or (line.startswith("--- ") and not current)
        ) and line[4:] != "/dev/null":
            current = header_path(line[4:])
        elif line.startswith("Binary files ") or line == "GIT binary patch":
            binary_file = True
        elif current:
            lines.append(line)
    if current:
        patches[current] = None if binary_file else "\n".join(lines)
    return patches


def _local_changes(root: Path, point: str, names: list[str]) -> list[Change]:
    from comments import DIFF

    raw = (
        _git_stdout(
            root,
            *DIFF[1:],
            "--no-renames",
            point,
            "--",
            *(f":(literal){name}" for name in names),
        )
        or ""
    )
    patches = _parse_patches(raw)
    changes: list[Change] = []
    for name in names:
        local = root / name
        text: str | None = None
        if local.is_file() and not local.is_symlink():
            data = local.read_bytes()
            if b"\0" not in data[:8000]:
                text = data.decode(errors="replace")
        if name in patches:
            patch = patches[name]
        else:
            patch = (
                "\n".join(f"+{line}" for line in text.splitlines())
                if text is not None
                else None
            )
        changes.append(Change(name, patch, text))
    return changes


def _path_mtime_ns(root: Path, name: str) -> int:
    target = root / name
    if target.exists():
        return target.stat().st_mtime_ns
    for parent in target.parents:
        if parent.exists():
            return parent.stat().st_mtime_ns
        if parent == root:
            break
    return 0


def _git_index_mtime_ns(root: Path) -> int:
    index = (_git_stdout(root, "rev-parse", "--git-path", "index") or "").strip()
    if not index:
        return 0
    path = root / index
    return path.stat().st_mtime_ns if path.is_file() else 0


def _dirty_ui_paths(root: Path, patterns: list[str], visible: list[str]) -> list[str]:
    raw = _git_stdout(
        root, "-c", "core.quotepath=off", "status", "--porcelain", "-uall", "-z"
    )
    if not raw:
        return []
    candidates: list[str] = []
    entries = iter(raw.split("\0"))
    for entry in entries:
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        paths = [path]
        if code[0] in ("R", "C"):
            paths.append(next(entries, ""))
        for item in paths:
            if (
                item
                and matches(item, patterns)
                and not is_test_path(PurePosixPath(item))
            ):
                candidates.append(item)
    visible_set = set(visible)
    extra = [item for item in candidates if item not in visible_set]
    extra_visible = (
        set(visible_files(_local_changes(root, "HEAD", extra))) if extra else set()
    )
    return [item for item in candidates if item in visible_set or item in extra_visible]


def _dirty_ui_mtime_ns(
    root: Path, patterns: list[str], visible: list[str]
) -> tuple[bool, int]:
    dirty_ui = _dirty_ui_paths(root, patterns, visible)
    if not dirty_ui:
        return False, 0
    existing_visible = [name for name in visible if (root / name).exists()]
    mtimes = [_path_mtime_ns(root, name) for name in {*dirty_ui, *existing_visible}]
    if any(not (root / name).exists() for name in dirty_ui):
        mtimes.append(_git_index_mtime_ns(root))
    return True, max(mtimes, default=0)


def _local_browser_proof(
    evidence: Path, head: str, route: str, dirty_tree: bool, min_mtime_ns: int
) -> tuple[set[str], str | None]:
    items = browser_record_files(evidence)
    by_image = {str(rec["image"]): (path, rec) for path, rec in items}
    stems = list(
        dict.fromkeys(_stem(rec) for _, rec in items if rec.get("commit") == head)
    )
    if not stems:
        return (
            set(),
            (
                f"no measured capture at {head[:12]} in .hard-eng/browser; run "
                "`python3 .hooks/hard-eng.py browser capture <url> --session <name> --name after` "
                "(or `browser measure`), never a scratch screenshot script"
            ),
        )
    clean_hashes: set[str] = set()
    first_problem: str | None = None
    for stem in stems:
        problem, hashes = capture_set_problem(
            by_image,
            stem,
            head,
            route,
            allow_dirty=dirty_tree,
            min_mtime_ns=min_mtime_ns,
        )
        if problem is None:
            clean_hashes |= hashes
        elif first_problem is None:
            first_problem = problem
    return (clean_hashes, None) if clean_hashes else (set(), first_problem)


def _single_local_look_problem(
    record: dict[str, object],
    path: Path,
    head: str,
    expected_design: str,
    wanted: list[str],
    route_hashes: list[set[str]],
    native: bool,
    min_mtime_ns: int,
) -> tuple[str | None, set[str]]:
    if problem := look_base_problem(record, head, expected_design, wanted):
        return problem, set()
    images = cast(list[dict[str, object]], record.get("images", []))
    opened = {str(item["sha256"]) for item in images if item.get("read") is True}
    if not opened:
        return (
            "Look review: the record opened no After image; run `look` on the After images",
            set(),
        )
    if min_mtime_ns and path.stat().st_mtime_ns < min_mtime_ns:
        return (
            "Look review: the record predates the latest UI edit; run `look` again",
            set(),
        )
    if not native and not any(opened & hashes for hashes in route_hashes):
        return (
            "Look review: the record does not cover any clean measured capture at this head; run `look` on the After images",
            set(),
        )
    return None, opened


def _local_look_problem(
    root: Path,
    evidence: Path,
    head: str,
    route_hashes: list[set[str]],
    native: bool,
    min_mtime_ns: int,
) -> str | None:
    import look
    from challenge import store
    from plans import usability_rules

    folder = store(evidence, head, look.STORE).parent
    paths: list[Path] = sorted(folder.glob(f"{head}-*.json")) if folder.is_dir() else []
    if not paths:
        return f"Look review: no record for {head[:12]}; run `python3 .hooks/hard-eng.py look <After images>`"
    expected_design = look.design_hash(root)
    wanted = [name for name, _ in usability_rules()]
    covered: set[str] = set()
    first_problem: str | None = None
    for path in paths:
        try:
            record = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        problem, opened = _single_local_look_problem(
            record,
            path,
            head,
            expected_design,
            wanted,
            route_hashes,
            native,
            min_mtime_ns,
        )
        if problem is None:
            if native:
                return None
            covered |= opened
        elif first_problem is None:
            first_problem = problem
    if not native and route_hashes and all(covered & hashes for hashes in route_hashes):
        return None
    if not native and covered:
        return "Look review: clean look records do not cover every changed route's capture; run `look` on each route's After images"
    return (
        first_problem
        or f"Look review: no clean record for {head[:12]}; run `python3 .hooks/hard-eng.py look <After images>`"
    )


def _active_plan_texts(root: Path, base: str | None, changed: set[str]) -> list[str]:
    from change_size import judged_plans
    from plan_parent import named_parents
    from plans import plan_status

    _, _, applicable = judged_plans(root, base, changed)
    texts = {
        str(path.relative_to(root)): path.read_text()
        for path in applicable
        if path.is_file()
    }
    parents = named_parents(texts)
    return [
        text
        for name, text in texts.items()
        if name not in parents and plan_status(text) == "Complete"
    ]


def _plan_owns_visible(text: str, visible: list[str]) -> list[str]:
    tokens = set(PLAN_PATH_TOKEN.findall(text))
    owned: list[str] = []
    for name in visible:
        if name in text or any(
            (token.endswith("/") and name.startswith(token))
            or fnmatch.fnmatchcase(name, token)
            for token in tokens
        ):
            owned.append(name)
    return owned


def _unchanged_route(plan_text: str, reference: str) -> str:
    if route := surface_route(plan_text):
        return route
    tail = reference.rpartition(" — ")[2].strip()
    if match := PLAN_ROUTE_TOKEN.search(tail):
        return match[1] or match[2] or match[3] or match[4] or ""
    return ""


def _plans_reference_problem(plans: list[str], visible: list[str]) -> str | None:
    if not plans:
        return None
    for text in plans:
        owned = _plan_owns_visible(text, visible)
        if (len(plans) == 1 or owned) and (
            problem := reference_problem(text, owned or visible, "", False)
        ):
            return problem
    problems = [reference_problem(text, visible, "", False) for text in plans]
    return None if None in problems else problems[0]


def _local_visible_context(
    root: Path, base: str | None, changed_names: set[str] | None = None
) -> tuple[str, str, list[str], set[str], list[str]] | None:
    if in_ci():
        return None
    policy = _shipping_ui(root)
    if policy is None:
        return None
    patterns, base_branch = policy
    if changed_names is not None:
        changed = changed_names
        point = base
    else:
        from gate_config import changed_files
        from plans import default_branch_point

        point = (
            base
            if base and not ALL_ZERO_OBJECT_ID.fullmatch(base)
            else default_branch_point(root) or "HEAD"
        )
        changed = changed_files(root, point) or set()
    candidates = sorted(
        name
        for name in changed
        if matches(name, patterns) and not is_test_path(PurePosixPath(name))
    )
    if not candidates:
        return None
    head = (_git_stdout(root, "rev-parse", "--verify", "--quiet", "HEAD") or "").strip()
    if not head:
        return None
    if not point or ALL_ZERO_OBJECT_ID.fullmatch(point):
        from plans import default_branch_point

        point = default_branch_point(root) or "HEAD"
    from gate_config import generated_sources

    visible = visible_files(_local_changes(root, point, candidates))
    visible = [name for name in visible if name not in generated_sources(root, visible)]
    return (head, base_branch, patterns, changed, visible) if visible else None


def _unchanged_plans_problem(
    root: Path,
    evidence: Path,
    items: list[tuple[str, str]],
    head: str,
    base_branch: str,
    dirty_ui: bool,
    min_mtime_ns: int,
) -> str | None:
    base_sha = merge_base(root, base_branch, head=head)
    for ref, route in items:
        if problem := unchanged_problem(
            evidence,
            ref,
            head,
            base_sha,
            route=route,
            allow_dirty_after=dirty_ui,
            min_mtime_ns=min_mtime_ns,
        ):
            return problem
    return None


def local_ui_proof_problem(
    root: Path, base: str | None, changed_names: set[str] | None = None
) -> str | None:
    """Fast local check (zero extra git calls on the non-UI fast path) for visible UI changes at Complete."""
    context = _local_visible_context(root, base, changed_names)
    if context is None:
        return None
    head, base_branch, patterns, changed, visible = context
    plans = _active_plan_texts(root, base, changed)
    if problem := _plans_reference_problem(plans, visible):
        return problem
    if problem := guideline_problem(
        root, [name for name in visible if (root / name).is_file()]
    ):
        return problem
    evidence = evidence_root(root)
    dirty_ui, min_mtime_ns = _dirty_ui_mtime_ns(root, patterns, visible)
    unchanged = [
        (ref, _unchanged_route(text, ref))
        for text in plans
        if UNCHANGED_LINE.match(ref := reference_section(text))
    ]
    visual_plans = [
        text
        for text in plans
        if reference_section(text)
        and not UNCHANGED_LINE.match(reference_section(text))
        and reference_problem(text, visible, "", False) is None
    ]
    if unchanged:
        if problem := _unchanged_plans_problem(
            root, evidence, unchanged, head, base_branch, dirty_ui, min_mtime_ns
        ):
            return problem
        if not visual_plans:
            return None
    routes = list(
        dict.fromkeys(r for text in visual_plans if (r := surface_route(text)))
    )
    native = is_native(visible)
    route_hashes: list[set[str]] = []
    if not native:
        for route in routes or [""]:
            hashes, problem = _local_browser_proof(
                evidence, head, route, dirty_ui, min_mtime_ns
            )
            if problem:
                return problem
            route_hashes.append(hashes)
    return _local_look_problem(root, evidence, head, route_hashes, native, min_mtime_ns)


def validate_local_ui_proof(
    root: Path, base: str | None, changed_names: set[str] | None = None
) -> None:
    if problem := local_ui_proof_problem(root, base, changed_names):
        raise ValueError(f"UI evidence: {problem}")
