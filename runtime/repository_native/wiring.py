"""Repository-local native adapters with exact ownership and rollback."""

from __future__ import annotations

import base64
import json
import os
import re
import shlex
import stat
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:
    fcntl = None

from .errors import ConfigurationError

STATE_SCHEMA = 1
START = "# >>> hard-eng repository fallback >>>"
END = "# <<< hard-eng repository fallback <<<"
MAX_SNAPSHOT_BYTES = 1024 * 1024
MAX_STATE_BYTES = 16 * 1024 * 1024
LOCK_TIMEOUT_SECONDS = 30
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _write_all(descriptor: int, data: bytes) -> None:
    remaining = memoryview(data)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError("file write made no progress")
        remaining = remaining[written:]


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


def _git_exclude(repository: Path) -> Path:
    result = _run_git(repository, "rev-parse", "--path-format=absolute", "--git-path", "info/exclude")
    if result.returncode != 0 or not result.stdout.strip():
        raise ConfigurationError("Git private exclude path could not be resolved")
    return Path(result.stdout.strip())


@contextmanager
def _wiring_lock(repository: Path) -> Iterator[None]:
    if fcntl is None:
        raise ConfigurationError("repository fallback is supported only on macOS and Linux")
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
    lock = root / ".wiring.lock"
    flags = os.O_CREAT | os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    handle: int | None = None
    try:
        handle = os.open(lock, flags, 0o600)
        metadata = os.fstat(handle)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ConfigurationError("fallback wiring lock is unsafe")
    except ConfigurationError:
        if handle is not None:
            os.close(handle)
        raise
    except OSError as error:
        if handle is not None:
            os.close(handle)
        raise ConfigurationError(f"fallback wiring lock could not be opened: {error}") from error
    assert handle is not None
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.monotonic() >= deadline:
                os.close(handle)
                raise ConfigurationError("another Hard Eng wiring update did not finish within 30 seconds")
            time.sleep(0.1)
        except OSError as error:
            os.close(handle)
            raise ConfigurationError(f"fallback wiring lock failed: {error}") from error
    try:
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        os.close(handle)


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


def _atomic_write(path: Path, raw: bytes, mode: int) -> None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ConfigurationError(f"refusing to replace unsafe path: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode)
        try:
            _write_all(descriptor, raw)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary, path)
        os.chmod(path, mode)
    except BaseException:
        if temporary.is_file() and not temporary.is_symlink():
            temporary.unlink()
        raise


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
    _atomic_write(path, base64.b64decode(data, validate=True), mode)


def _relative(repository: Path, path: Path) -> str:
    try:
        return path.relative_to(repository).as_posix()
    except ValueError as error:
        raise ConfigurationError(f"managed path escaped the repository: {path}") from error


def _load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    if path.is_symlink() or not path.is_file():
        raise ConfigurationError(f"provider configuration is not a regular file: {path}")
    if path.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ConfigurationError(f"provider configuration is too large to compose safely: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ConfigurationError(f"provider configuration is invalid JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise ConfigurationError(f"provider configuration must be a JSON object: {path}")
    return value


def _owned_hook(value: object, expected: dict[str, object]) -> bool:
    if not isinstance(value, dict):
        return False
    return any(
        isinstance(expected.get(key), str) and value.get(key) == expected[key]
        for key in ("command", "bash", "powershell")
    )


def _compose_nested_hook(
    path: Path, event: str, hook: dict[str, object], settings: dict[str, object] | None = None
) -> bytes:
    value = _load_json(path)
    for key, expected in (settings or {}).items():
        if key in value and value[key] != expected:
            raise ConfigurationError(f"{key} has another owner: {path}")
        value[key] = expected
    hooks = value.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ConfigurationError(f"hooks must be a JSON object: {path}")
    entries = hooks.setdefault(event, [])
    if not isinstance(entries, list):
        raise ConfigurationError(f"hooks.{event} must be an array: {path}")
    kept: list[object] = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
            raise ConfigurationError(f"hooks.{event} contains an unsupported entry: {path}")
        inner = [item for item in entry["hooks"] if not _owned_hook(item, hook)]
        if inner:
            kept.append({**entry, "hooks": inner})
    kept.append({"hooks": [hook]})
    hooks[event] = kept
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _compose_flat_hook(path: Path, event: str, hook: dict[str, object]) -> bytes:
    value = _load_json(path)
    value["version"] = 1
    hooks = value.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ConfigurationError(f"hooks must be a JSON object: {path}")
    entries = hooks.setdefault(event, [])
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        raise ConfigurationError(f"hooks.{event} must be an object array: {path}")
    hooks[event] = [entry for entry in entries if not _owned_hook(entry, hook)] + [hook]
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _instruction_bridge() -> bytes:
    return (
        b"# Hard Eng repository bridge\n\n"
        b"Read and follow `./AGENTS.md` first.\n"
        b"Then read and follow `.agents/hard-eng/current/AGENTS.md`.\n\n"
        b"@AGENTS.md\n"
        b"@.agents/hard-eng/current/AGENTS.md\n"
    )


def _mcp_config(repository: Path, payload: Path) -> bytes:
    value = {
        "mcpServers": {
            "hard-eng": {
                "args": [str(payload / "runtime/repository_native/mcp_server.py"), "--repo", str(repository)],
                "command": "python3",
            }
        }
    }
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


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
        created_directories.append(_relative(repository, directory))


def _create_link(
    repository: Path, path: Path, target: Path, created_paths: list[str], created_directories: list[str]
) -> None:
    relative = Path(_relative(repository, path))
    if _tracked(repository, relative):
        raise ConfigurationError(f"fallback would replace tracked repository state: {relative}")
    _ensure_parent(path, created_directories, repository)
    if path.is_symlink():
        if path.resolve(strict=False) == target.resolve(strict=False):
            return
        raise ConfigurationError(f"fallback link has another owner: {relative}")
    if path.exists():
        raise ConfigurationError(f"fallback link path has another owner: {relative}")
    path.symlink_to(os.path.relpath(target, path.parent), target_is_directory=target.is_dir())
    created_paths.append(relative.as_posix())


def _write_managed(
    repository: Path, path: Path, raw: bytes, mode: int, snapshots: dict[str, dict[str, object]]
) -> None:
    relative = Path(_relative(repository, path))
    if _tracked(repository, relative):
        raise ConfigurationError(f"fallback would replace tracked repository state: {relative}")
    snapshots.setdefault(relative.as_posix(), _snapshot(path))
    _atomic_write(path, raw, mode)


def _skills(payload: Path) -> list[str]:
    root = payload / "skills"
    if root.is_symlink() or not root.is_dir():
        raise ConfigurationError("fallback release skills directory is missing")
    names = sorted(path.name for path in root.iterdir() if path.is_dir() and (path / "SKILL.md").is_file())
    if "plain-english" not in names:
        raise ConfigurationError("fallback release is missing the plain-english skill")
    return names


def _links(repository: Path, payload: Path) -> dict[Path, Path]:
    links: dict[Path, Path] = {}
    for name in _skills(payload):
        target = payload / "skills" / name
        links[repository / ".agents/skills" / name] = target
        links[repository / ".claude/skills" / name] = target
    agents = payload / "agents"
    if agents.is_dir() and not agents.is_symlink():
        adapters = {
            "claude.md": repository / ".claude/agents",
            "codex.toml": repository / ".codex/agents",
            "copilot.agent.md": repository / ".github/agents",
        }
        for package in sorted(agents.iterdir()):
            if not package.is_dir() or package.is_symlink() or not NAME.fullmatch(package.name):
                continue
            for source_name, destination in adapters.items():
                source = package / source_name
                if source.is_file() and not source.is_symlink():
                    suffix = {"claude.md": ".md", "codex.toml": ".toml", "copilot.agent.md": ".agent.md"}[source_name]
                    links[destination / f"{package.name}{suffix}"] = source
    styles = payload / "output-styles"
    if styles.is_dir() and not styles.is_symlink():
        for source in sorted(styles.glob("*.md")):
            if source.is_file() and not source.is_symlink():
                links[repository / ".claude/output-styles" / source.name] = source
    return links


def _expected_files(repository: Path, payload: Path) -> dict[Path, tuple[bytes, int]]:
    hook_path = payload / "scripts/hooks/agent-hook.sh"
    command = f"bash {shlex.quote(str(hook_path))}"
    codex = repository / ".codex/hooks.json"
    claude = repository / ".claude/settings.local.json"
    copilot = repository / ".github/hooks/hard-eng.json"
    return {
        repository / "AGENTS.override.md": (_instruction_bridge(), 0o644),
        repository / "CLAUDE.local.md": (b"@AGENTS.override.md\n", 0o644),
        codex: (
            _compose_nested_hook(
                codex, "PreToolUse", {"command": f"{command} codex pretooluse", "timeout": 2, "type": "command"}
            ),
            0o600,
        ),
        claude: (
            _compose_nested_hook(
                claude,
                "PreToolUse",
                {
                    "matcher": "Bash|Edit|Write|MultiEdit|NotebookEdit|Agent|mcp__.*",
                    "command": f"{command} claude pretooluse",
                    "type": "command",
                },
                {"outputStyle": "plain-english"},
            ),
            0o600,
        ),
        copilot: (
            _compose_flat_hook(
                copilot, "preToolUse", {"bash": f"{command} copilot pretooluse", "timeoutSec": 2, "type": "command"}
            ),
            0o600,
        ),
        repository / ".agents/hard-eng/mcp.json": (_mcp_config(repository, payload), 0o600),
        repository / ".agents/hard-eng/copilot-instructions/AGENTS.md": (_instruction_bridge(), 0o644),
    }


def _composable_files(repository: Path) -> set[Path]:
    return {
        repository / ".codex/hooks.json",
        repository / ".claude/settings.local.json",
        repository / ".github/hooks/hard-eng.json",
    }


def preflight_wiring(repository: Path) -> None:
    state_path = repository / ".agents/hard-eng/wiring.json"
    if _load_state(state_path) is not None:
        return
    exclusive = {
        repository / "AGENTS.override.md",
        repository / "CLAUDE.local.md",
        repository / ".agents/hard-eng/mcp.json",
        repository / ".agents/hard-eng/copilot-instructions/AGENTS.md",
    }
    for path in exclusive | _composable_files(repository):
        relative = Path(_relative(repository, path))
        if _tracked(repository, relative):
            raise ConfigurationError(f"fallback would replace tracked repository state: {relative}")
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
        raise ConfigurationError("fallback ownership state has an unsupported schema")
    return value


def _verify_existing(repository: Path, payload: Path, state: dict[str, object]) -> None:
    if state.get("repository") != str(repository):
        raise ConfigurationError("fallback ownership state belongs to another repository")
    allowed_state = {
        "created_directories",
        "created_paths",
        "exclude_block",
        "exclude_installed",
        "exclude_path",
        "exclude_snapshot",
        "repository",
        "schema_version",
        "snapshots",
    }
    if set(state) != allowed_state:
        raise ConfigurationError("fallback ownership state has unsupported fields")
    expected_files = _expected_files(repository, payload)
    expected_links = _links(repository, payload)
    expected_file_names = {_relative(repository, path) for path in expected_files}
    expected_link_names = {_relative(repository, path) for path in expected_links}
    snapshots = state.get("snapshots")
    created_paths = state.get("created_paths")
    created_directories = state.get("created_directories")
    if not isinstance(snapshots, dict) or set(snapshots) != expected_file_names:
        raise ConfigurationError("fallback file ownership state is incomplete")
    if not isinstance(created_paths, list) or len(created_paths) != len(set(map(str, created_paths))):
        raise ConfigurationError("fallback link ownership state is invalid")
    if not all(isinstance(value, str) and value in expected_link_names for value in created_paths):
        raise ConfigurationError("fallback link ownership state escaped its allowed paths")
    allowed_directories: set[str] = set()
    for path in (*expected_files, *expected_links):
        parent = path.parent
        while parent != repository:
            allowed_directories.add(_relative(repository, parent))
            parent = parent.parent
    if not isinstance(created_directories, list) or len(created_directories) != len(set(map(str, created_directories))):
        raise ConfigurationError("fallback directory ownership state is invalid")
    if not all(isinstance(value, str) and value in allowed_directories for value in created_directories):
        raise ConfigurationError("fallback directory ownership state escaped its allowed paths")
    for path, (expected, _) in expected_files.items():
        if not path.is_file() or path.is_symlink() or path.read_bytes() != expected:
            raise ConfigurationError(f"generated Hard Eng file drifted: {_relative(repository, path)}")
    for link, target in expected_links.items():
        if not link.is_symlink() or link.resolve(strict=False) != target.resolve(strict=False):
            raise ConfigurationError(f"generated Hard Eng link drifted: {_relative(repository, link)}")
    exclude = _git_exclude(repository)
    if state.get("exclude_path") != str(exclude):
        raise ConfigurationError("fallback Git exclude ownership path changed")
    exclude_block = state.get("exclude_block")
    exclude_installed = state.get("exclude_installed")
    if (
        not isinstance(exclude_block, str)
        or not isinstance(exclude_installed, str)
        or not exclude.is_file()
        or exclude.is_symlink()
    ):
        raise ConfigurationError("fallback Git exclude ownership state is invalid")
    try:
        base64.b64decode(exclude_installed, validate=True)
    except ValueError as error:
        raise ConfigurationError("fallback Git exclude installed state is invalid") from error
    _remove_exclude_block(exclude.read_text(encoding="utf-8"), exclude_block)


def _install_wiring(repository: Path, payload: Path) -> Path:
    state_path = repository / ".agents/hard-eng/wiring.json"
    existing = _load_state(state_path)
    if existing is not None:
        _verify_existing(repository, payload, existing)
        return repository / ".agents/hard-eng/mcp.json"
    snapshots: dict[str, dict[str, object]] = {}
    created_paths: list[str] = []
    created_directories: list[str] = []
    exclude = _git_exclude(repository)
    exclude_snapshot: dict[str, object] | None = None
    try:
        expected_files = _expected_files(repository, payload)
        composable_files = _composable_files(repository)
        for path in expected_files:
            if path not in composable_files and (path.exists() or path.is_symlink()):
                raise ConfigurationError(f"fallback generated file has another owner: {_relative(repository, path)}")
        for path, (raw, mode) in expected_files.items():
            _ensure_parent(path, created_directories, repository)
            _write_managed(repository, path, raw, mode, snapshots)
        for path, target in _links(repository, payload).items():
            _create_link(repository, path, target, created_paths, created_directories)
        exclude_snapshot = _snapshot(exclude)
        current_exclude = exclude.read_text(encoding="utf-8") if exclude.is_file() else ""
        ignored = [
            "AGENTS.override.md",
            "CLAUDE.local.md",
            ".agents/hard-eng/",
            ".codex/hooks.json",
            ".claude/settings.local.json",
            ".github/hooks/hard-eng.json",
            *created_paths,
        ]
        exclude_block = _exclude_block(ignored)
        installed_exclude = _compose_exclude(current_exclude, ignored)
        _atomic_write(exclude, installed_exclude, 0o600)
        _atomic_write(
            state_path,
            (
                json.dumps(
                    {
                        "created_directories": created_directories,
                        "created_paths": created_paths,
                        "exclude_block": exclude_block,
                        "exclude_installed": base64.b64encode(installed_exclude).decode("ascii"),
                        "exclude_path": str(exclude),
                        "exclude_snapshot": exclude_snapshot,
                        "repository": str(repository),
                        "schema_version": STATE_SCHEMA,
                        "snapshots": snapshots,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode(),
            0o600,
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
    return repository / ".agents/hard-eng/mcp.json"


def _uninstall_wiring(repository: Path, payload: Path) -> None:
    state_path = repository / ".agents/hard-eng/wiring.json"
    state = _load_state(state_path)
    if state is None:
        return
    _verify_existing(repository, payload, state)
    snapshots = state.get("snapshots")
    created_paths = state.get("created_paths")
    created_directories = state.get("created_directories")
    exclude_path = state.get("exclude_path")
    exclude_block = state.get("exclude_block")
    exclude_installed = state.get("exclude_installed")
    exclude_snapshot = state.get("exclude_snapshot")
    if (
        not isinstance(snapshots, dict)
        or not isinstance(created_paths, list)
        or not isinstance(created_directories, list)
        or not isinstance(exclude_path, str)
        or not isinstance(exclude_block, str)
        or not isinstance(exclude_installed, str)
        or not isinstance(exclude_snapshot, dict)
    ):
        raise ConfigurationError("fallback ownership state is incomplete")
    exclude = Path(exclude_path)
    current_exclude = exclude.read_bytes()
    installed_exclude = base64.b64decode(exclude_installed, validate=True)
    restore_exclude = current_exclude == installed_exclude
    updated_exclude = b"" if restore_exclude else _remove_exclude_block(current_exclude.decode("utf-8"), exclude_block)
    exclude_mode = stat.S_IMODE(exclude.stat().st_mode)
    for relative, snapshot in snapshots.items():
        if not isinstance(relative, str) or not isinstance(snapshot, dict):
            raise ConfigurationError("fallback file snapshot is invalid")
        _restore(repository / relative, snapshot)
    for relative in reversed(created_paths):
        path = repository / str(relative)
        if path.is_symlink():
            path.unlink()
        elif path.exists():
            raise ConfigurationError(f"generated link path changed type: {relative}")
    if restore_exclude:
        _restore(exclude, exclude_snapshot)
    else:
        _atomic_write(exclude, updated_exclude, exclude_mode)
    if state_path.is_file() and not state_path.is_symlink():
        state_path.unlink()
    for relative in reversed(created_directories):
        try:
            (repository / str(relative)).rmdir()
        except OSError:
            pass


def install_wiring(repository: Path, payload: Path) -> Path:
    with _wiring_lock(repository):
        return _install_wiring(repository, payload)


def uninstall_wiring(repository: Path, payload: Path) -> None:
    with _wiring_lock(repository):
        _uninstall_wiring(repository, payload)


def verify_wiring(repository: Path, payload: Path) -> None:
    state = _load_state(repository / ".agents/hard-eng/wiring.json")
    if state is None:
        raise ConfigurationError("fallback ownership state is missing")
    _verify_existing(repository, payload, state)
