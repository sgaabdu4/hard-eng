"""Repository-local native adapters with exact ownership, healing, and rollback."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .adapters import (
    EMPTY_COMPOSABLE,
    MAX_SNAPSHOT_BYTES,
    composable_files,
    exclusive_files,
    expected_files,
    expected_links,
    shared_files,
    strip_composable,
)
from .errors import ConfigurationError
from .locking import exclusive_lock
from .shared import GENERATED, replace_file

STATE_SCHEMA = 2
START = "# >>> hard-eng repository fallback >>>"
END = "# <<< hard-eng repository fallback <<<"
MAX_STATE_BYTES = 16 * 1024 * 1024
LOCK_TIMEOUT_SECONDS = 30
IGNORED = (
    "AGENTS.override.md",
    "CLAUDE.local.md",
    ".agents/hard-eng/",
    ".codex/hooks.json",
    ".codex/config.toml",
    ".claude/settings.local.json",
    ".github/hooks/hard-eng.json",
    ".github/instructions/hard-eng.instructions.md",
)
IGNORED_SHARED = ("CLAUDE.local.md", ".agents/hard-eng/")
STATE_FIELDS = {
    "created_directories",
    "created_paths",
    "exclude_block",
    "exclude_installed",
    "exclude_path",
    "exclude_snapshot",
    "generated",
    "repository",
    "schema_version",
    "shared",
    "snapshots",
}
EDITED_BY_HAND = (
    "generated Hard Eng file was edited by hand: {relative}. Move the edits into the repository AGENTS.md, "
    "then rerun `npx -y github:sgaabdu4/hard-eng --repo`, or run `hard-eng uninstall` first."
)


def _run_git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    try:
        return subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ConfigurationError(f"Git could not inspect repository ownership: {error}") from error


def _tracked(repository: Path, relative: Path) -> bool:
    result = _run_git(repository, "ls-files", "--error-unmatch", "--", relative.as_posix())
    return result.returncode == 0


def _foreign_tracked(repository: Path, relative: Path, shared: bool) -> bool:
    """Tracked files are off limits, except the generated set a shared repository commits on purpose."""
    if shared and repository / relative in shared_files(repository):
        return False
    return _tracked(repository, relative)


def _healable(path: Path, expected: bytes) -> bool:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_SNAPSHOT_BYTES:
        return False
    actual = path.read_bytes()
    return actual == expected or GENERATED.encode() in actual[:4096]


def _ignored(shared: bool, created_paths: list[str]) -> list[str]:
    return [*(IGNORED_SHARED if shared else IGNORED), *created_paths]


def _git_exclude(repository: Path) -> Path:
    result = _run_git(repository, "rev-parse", "--path-format=absolute", "--git-path", "info/exclude")
    if result.returncode != 0 or not result.stdout.strip():
        raise ConfigurationError("Git private exclude path could not be resolved")
    return Path(result.stdout.strip())


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@contextmanager
def _wiring_lock(repository: Path) -> Iterator[None]:
    parent = repository / ".agents"
    root = parent / "hard-eng"
    try:
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ConfigurationError(f"fallback parent is unsafe: {parent}")
        parent.mkdir(mode=0o700, exist_ok=True)
        if root.is_symlink() or (root.exists() and not root.is_dir()):
            raise ConfigurationError(f"fallback root is unsafe: {root}")
        root.mkdir(mode=0o700, exist_ok=True)
    except OSError as error:
        raise ConfigurationError(f"fallback root could not be prepared: {error}") from error
    with exclusive_lock(root / ".wiring.lock", timeout=LOCK_TIMEOUT_SECONDS, holder="another Hard Eng wiring update"):
        yield


def _snapshot(path: Path) -> dict[str, object]:
    if path.is_symlink():
        return {"kind": "symlink", "target": os.readlink(path)}
    if path.exists():
        metadata = path.stat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ConfigurationError(f"cannot compose non-file provider state: {path}")
        raw = path.read_bytes()
        if len(raw) > MAX_SNAPSHOT_BYTES:
            raise ConfigurationError(f"provider state is too large to compose safely: {path}")
        return {"data": base64.b64encode(raw).decode("ascii"), "kind": "file", "mode": stat.S_IMODE(metadata.st_mode)}
    return {"kind": "absent"}


def _restore(path: Path, snapshot: dict[str, object]) -> None:
    kind = snapshot.get("kind")
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        raise ConfigurationError(f"managed path changed type and cannot be restored: {path}")
    if kind == "absent":
        return
    if kind == "symlink":
        target = snapshot.get("target")
        if not isinstance(target, str):
            raise ConfigurationError("stored symlink snapshot is invalid")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target)
        return
    data = snapshot.get("data")
    mode = snapshot.get("mode")
    if kind != "file" or not isinstance(data, str) or not isinstance(mode, int):
        raise ConfigurationError("stored file snapshot is invalid")
    replace_file(path, base64.b64decode(data, validate=True), mode)


def _relative(repository: Path, path: Path) -> str:
    try:
        return path.relative_to(repository).as_posix()
    except ValueError as error:
        raise ConfigurationError(f"managed path escaped the repository: {path}") from error


def _inside(repository: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative or relative.startswith("/") or ".." in Path(relative).parts:
        raise ConfigurationError("fallback ownership state names an unsafe path")
    return repository / relative


def _exclude_block(paths: list[str]) -> str:
    rows = [START, *[f"/{path}" for path in sorted(set(paths))], END]
    return "\n".join(rows) + "\n"


def _compose_exclude(current: str, managed_paths: list[str]) -> bytes:
    lines = current.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == START]
    ends = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == END]
    block = _exclude_block(managed_paths)
    if not starts and not ends:
        prefix = current
        if prefix and not prefix.endswith(("\n", "\r")):
            prefix += "\n"
        if prefix and not prefix.endswith("\n\n"):
            prefix += "\n"
        return (prefix + block).encode()
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise ConfigurationError("Git private exclude has malformed Hard Eng markers")
    return ("".join(lines[: starts[0]]) + block + "".join(lines[ends[0] + 1 :])).encode()


def _remove_exclude_block(current: str, expected: str) -> bytes:
    lines = current.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == START]
    ends = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == END]
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise ConfigurationError("Git private exclude has malformed Hard Eng markers")
    actual = "".join(lines[starts[0] : ends[0] + 1])
    if actual != expected:
        raise ConfigurationError("Git private exclude Hard Eng block changed")
    return ("".join(lines[: starts[0]]) + "".join(lines[ends[0] + 1 :])).encode()


def _ensure_parent(path: Path, created_directories: list[str], repository: Path) -> None:
    missing: list[Path] = []
    parent = path.parent
    while parent != repository and not parent.exists():
        missing.append(parent)
        parent = parent.parent
    if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
        raise ConfigurationError(f"managed parent is unsafe: {parent}")
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
        relative = _relative(repository, directory)
        if relative not in created_directories:
            created_directories.append(relative)


def _create_link(
    repository: Path, path: Path, target: Path, created_paths: list[str], created_directories: list[str]
) -> None:
    relative = Path(_relative(repository, path))
    if _tracked(repository, relative):
        raise ConfigurationError(f"fallback would replace tracked repository state: {relative}")
    _ensure_parent(path, created_directories, repository)
    if path.is_symlink():
        if path.resolve(strict=False) != target.resolve(strict=False):
            raise ConfigurationError(f"fallback link has another owner: {relative}")
    elif path.exists():
        raise ConfigurationError(f"fallback link path has another owner: {relative}")
    else:
        path.symlink_to(os.path.relpath(target, path.parent), target_is_directory=target.is_dir())
    if relative.as_posix() not in created_paths:
        created_paths.append(relative.as_posix())


def _write_managed(
    repository: Path,
    path: Path,
    raw: bytes,
    mode: int,
    snapshots: dict[str, dict[str, object]],
    *,
    shared: bool = False,
) -> None:
    relative = Path(_relative(repository, path))
    if _foreign_tracked(repository, relative, shared):
        raise ConfigurationError(f"fallback would replace tracked repository state: {relative}")
    snapshots.setdefault(relative.as_posix(), _snapshot(path))
    replace_file(path, raw, mode)


def preflight_wiring(repository: Path) -> None:
    if _load_state(repository / ".agents/hard-eng/wiring.json") is not None:
        return
    exclusive = set(exclusive_files(repository))
    for path in exclusive | composable_files(repository):
        relative = Path(_relative(repository, path))
        if _tracked(repository, relative):
            raise ConfigurationError(
                f"fallback would replace tracked repository state: {relative}; install Hard Eng globally instead"
            )
        if path in exclusive and (path.exists() or path.is_symlink()):
            raise ConfigurationError(f"fallback generated file has another owner: {relative}")


def _load_state(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise ConfigurationError(f"fallback ownership state is unsafe: {path}")
    if path.stat().st_size > MAX_STATE_BYTES:
        raise ConfigurationError("fallback ownership state is too large")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ConfigurationError("fallback ownership state is invalid") from error
    if not isinstance(value, dict) or value.get("schema_version") != STATE_SCHEMA:
        raise ConfigurationError(
            "fallback ownership state has an unsupported schema; remove .agents/hard-eng and the generated "
            "AGENTS.override.md, CLAUDE.local.md, and hook files, then rerun the setup"
        )
    if not STATE_FIELDS - {"shared"} <= set(value) <= STATE_FIELDS:
        raise ConfigurationError("fallback ownership state has unsupported fields")
    value["shared"] = value.get("shared") is True
    return value


def _write_state(path: Path, state: dict[str, object]) -> None:
    replace_file(path, (json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n").encode(), 0o600)


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigurationError(f"fallback {label} ownership state is invalid")
    if len(value) != len(set(value)):
        raise ConfigurationError(f"fallback {label} ownership state is invalid")
    return list(value)


def _same_json(left: bytes, right: bytes) -> bool:
    try:
        return json.loads(left) == json.loads(right)
    except (UnicodeError, json.JSONDecodeError):
        return False


def _reconcile(repository: Path, payload: Path, state: dict[str, object], *, heal: bool) -> list[str]:
    """Compare the generated wiring with what this release expects; heal untouched drift when asked."""
    if state.get("repository") != str(repository):
        raise ConfigurationError("fallback ownership state belongs to another repository")
    generated = state.get("generated")
    snapshots = state.get("snapshots")
    if not isinstance(generated, dict) or not isinstance(snapshots, dict):
        raise ConfigurationError("fallback file ownership state is invalid")
    created_paths = _string_list(state.get("created_paths"), "link")
    created_directories = _string_list(state.get("created_directories"), "directory")
    shared = state["shared"] is True
    files = expected_files(repository, payload, shared=shared)
    links = expected_links(repository, payload)
    composable = composable_files(repository, shared=shared)
    stale: list[str] = []
    changed = False
    for path, (expected, mode) in files.items():
        relative = _relative(repository, path)
        if _foreign_tracked(repository, Path(relative), shared):
            raise ConfigurationError(f"fallback would replace tracked repository state: {relative}")
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ConfigurationError(f"generated Hard Eng file changed type: {relative}")
        actual = path.read_bytes() if path.is_file() else None
        if actual == expected or (actual is not None and path in composable and _same_json(actual, expected)):
            continue
        if actual is not None and path not in composable and _digest(actual) != generated.get(relative):
            raise ConfigurationError(EDITED_BY_HAND.format(relative=relative))
        if not heal:
            stale.append(f"{relative} is out of date")
            continue
        _ensure_parent(path, created_directories, repository)
        snapshots.setdefault(relative, _snapshot(path))
        replace_file(path, expected, mode)
        generated[relative] = _digest(expected)
        changed = True
    link_names = {_relative(repository, link) for link in links}
    for link, target in links.items():
        relative = _relative(repository, link)
        if link.is_symlink():
            if link.resolve(strict=False) != target.resolve(strict=False):
                raise ConfigurationError(f"fallback link has another owner: {relative}")
            continue
        if link.exists():
            raise ConfigurationError(f"fallback link path has another owner: {relative}")
        if not heal:
            stale.append(f"{relative} link is missing")
            continue
        _create_link(repository, link, target, created_paths, created_directories)
        changed = True
    for relative in list(created_paths):
        if relative in link_names:
            continue
        if not heal:
            stale.append(f"{relative} link is no longer needed")
            continue
        path = _inside(repository, relative)
        if path.is_symlink():
            path.unlink()
        elif path.exists():
            raise ConfigurationError(f"generated link path changed type: {relative}")
        created_paths.remove(relative)
        changed = True
    exclude = _git_exclude(repository)
    if state.get("exclude_path") != str(exclude):
        raise ConfigurationError("fallback Git exclude ownership path changed")
    if exclude.is_symlink() or (exclude.exists() and not exclude.is_file()):
        raise ConfigurationError("fallback Git exclude ownership state is invalid")
    ignored = _ignored(shared, created_paths)
    block = _exclude_block(ignored)
    current = exclude.read_text(encoding="utf-8") if exclude.is_file() else ""
    try:
        _remove_exclude_block(current, block)
        present = True
    except ConfigurationError:
        present = False
    if not present:
        if not heal:
            stale.append("Git private exclude block is out of date")
        else:
            installed = _compose_exclude(current, ignored)
            mode = stat.S_IMODE(exclude.stat().st_mode) if exclude.is_file() else 0o600
            replace_file(exclude, installed, mode)
            state["exclude_block"] = block
            state["exclude_installed"] = base64.b64encode(installed).decode("ascii")
            changed = True
    if heal and changed:
        state["created_paths"] = created_paths
        state["created_directories"] = created_directories
        _write_state(repository / ".agents/hard-eng/wiring.json", state)
    return stale


def _install_wiring(repository: Path, payload: Path, *, shared: bool) -> None:
    state_path = repository / ".agents/hard-eng/wiring.json"
    snapshots: dict[str, dict[str, object]] = {}
    generated: dict[str, str] = {}
    created_paths: list[str] = []
    created_directories: list[str] = []
    exclude = _git_exclude(repository)
    exclude_snapshot: dict[str, object] | None = None
    try:
        files = expected_files(repository, payload, shared=shared)
        composable = composable_files(repository, shared=shared)
        for path, (raw, _) in files.items():
            if path in composable or not (path.exists() or path.is_symlink()):
                continue
            if not (shared and _healable(path, raw)):
                raise ConfigurationError(f"fallback generated file has another owner: {_relative(repository, path)}")
        for path, (raw, mode) in files.items():
            _ensure_parent(path, created_directories, repository)
            _write_managed(repository, path, raw, mode, snapshots, shared=shared)
            generated[_relative(repository, path)] = _digest(raw)
        for path, target in expected_links(repository, payload).items():
            _create_link(repository, path, target, created_paths, created_directories)
        exclude_snapshot = _snapshot(exclude)
        current_exclude = exclude.read_text(encoding="utf-8") if exclude.is_file() else ""
        ignored = _ignored(shared, created_paths)
        installed_exclude = _compose_exclude(current_exclude, ignored)
        exclude_mode = stat.S_IMODE(exclude.stat().st_mode) if exclude.is_file() else 0o600
        replace_file(exclude, installed_exclude, exclude_mode)
        _write_state(
            state_path,
            {
                "created_directories": created_directories,
                "created_paths": created_paths,
                "exclude_block": _exclude_block(ignored),
                "exclude_installed": base64.b64encode(installed_exclude).decode("ascii"),
                "exclude_path": str(exclude),
                "exclude_snapshot": exclude_snapshot,
                "generated": generated,
                "repository": str(repository),
                "schema_version": STATE_SCHEMA,
                "shared": shared,
                "snapshots": snapshots,
            },
        )
    except BaseException:
        if state_path.is_file() and not state_path.is_symlink():
            state_path.unlink()
        if exclude_snapshot is not None:
            _restore(exclude, exclude_snapshot)
        for relative, snapshot in reversed(tuple(snapshots.items())):
            _restore(repository / relative, snapshot)
        for relative in reversed(created_paths):
            path = repository / relative
            if path.is_symlink():
                path.unlink()
        for relative in reversed(created_directories):
            try:
                (repository / relative).rmdir()
            except OSError:
                pass
        raise


def _release_composable(
    repository: Path, payload: Path, relative: str, snapshot: dict[str, object], *, shared: bool
) -> None:
    path = _inside(repository, relative)
    if not path.is_file() or path.is_symlink():
        return
    stripped = strip_composable(repository, payload, path, shared=shared)
    if stripped is None:
        return
    if stripped in EMPTY_COMPOSABLE and (shared or snapshot.get("kind") == "absent"):
        path.unlink()
        return
    replace_file(path, stripped, stat.S_IMODE(path.stat().st_mode))


def _uninstall_wiring(repository: Path, payload: Path) -> None:
    state_path = repository / ".agents/hard-eng/wiring.json"
    state = _load_state(state_path)
    if state is None:
        return
    if state.get("repository") != str(repository):
        raise ConfigurationError("fallback ownership state belongs to another repository")
    shared = state["shared"] is True
    committed = set(shared_files(repository)) if shared else set()
    snapshots = state.get("snapshots")
    generated = state.get("generated")
    exclude_path = state.get("exclude_path")
    exclude_block = state.get("exclude_block")
    exclude_installed = state.get("exclude_installed")
    exclude_snapshot = state.get("exclude_snapshot")
    if (
        not isinstance(snapshots, dict)
        or not isinstance(generated, dict)
        or not isinstance(exclude_path, str)
        or not isinstance(exclude_block, str)
        or not isinstance(exclude_installed, str)
        or not isinstance(exclude_snapshot, dict)
    ):
        raise ConfigurationError("fallback ownership state is incomplete")
    created_paths = _string_list(state.get("created_paths"), "link")
    created_directories = _string_list(state.get("created_directories"), "directory")
    composable = {_relative(repository, path) for path in composable_files(repository, shared=shared)}
    for relative, snapshot in snapshots.items():
        path = _inside(repository, relative)
        if not isinstance(snapshot, dict):
            raise ConfigurationError("fallback file snapshot is invalid")
        if relative not in composable and path.is_file() and _digest(path.read_bytes()) != generated.get(relative):
            raise ConfigurationError(EDITED_BY_HAND.format(relative=relative))
    exclude = Path(exclude_path)
    current_exclude = exclude.read_bytes() if exclude.is_file() else b""
    restore_exclude = current_exclude == base64.b64decode(exclude_installed, validate=True)
    updated_exclude = b"" if restore_exclude else _remove_exclude_block(current_exclude.decode("utf-8"), exclude_block)
    exclude_mode = stat.S_IMODE(exclude.stat().st_mode) if exclude.is_file() else 0o600
    for relative, snapshot in snapshots.items():
        path = _inside(repository, relative)
        if (
            relative in composable
            and path.is_file()
            and (shared or _digest(path.read_bytes()) != generated.get(relative))
        ):
            _release_composable(repository, payload, relative, snapshot, shared=shared)
        elif path in committed:
            if path.is_file() or path.is_symlink():
                path.unlink()
        else:
            _restore(path, snapshot)
    for relative in reversed(created_paths):
        path = _inside(repository, relative)
        if path.is_symlink():
            path.unlink()
        elif path.exists():
            raise ConfigurationError(f"generated link path changed type: {relative}")
    if restore_exclude:
        _restore(exclude, exclude_snapshot)
    else:
        replace_file(exclude, updated_exclude, exclude_mode)
    if state_path.is_file() and not state_path.is_symlink():
        state_path.unlink()
    for relative in reversed(created_directories):
        try:
            _inside(repository, relative).rmdir()
        except OSError:
            pass


def install_wiring(repository: Path, payload: Path, *, shared: bool = False) -> None:
    with _wiring_lock(repository):
        state = _load_state(repository / ".agents/hard-eng/wiring.json")
        if state is not None and state["shared"] is not shared:
            _uninstall_wiring(repository, payload)
            state = None
        if state is None:
            _install_wiring(repository, payload, shared=shared)
        else:
            _reconcile(repository, payload, state, heal=True)


def uninstall_wiring(repository: Path, payload: Path) -> None:
    with _wiring_lock(repository):
        _uninstall_wiring(repository, payload)


def verify_wiring(repository: Path, payload: Path) -> list[str]:
    state = _load_state(repository / ".agents/hard-eng/wiring.json")
    if state is None:
        raise ConfigurationError("fallback ownership state is missing")
    return _reconcile(repository, payload, state, heal=False)
