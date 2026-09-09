"""Prepare one repository for one agent: the global Hard Eng, or the repository copy every clone fetches."""

from __future__ import annotations

import shutil
import stat
from pathlib import Path

from .adapters import EMPTY_COMPOSABLE, composable_files, shared_files, strip_composable
from .errors import ConfigurationError, HardEngError
from .models import GlobalState, PreparedState, RepositoryState
from .repository import inspect_global, inspect_repository, require_claude_owner
from .shared import BOOTSTRAP, ensure_checkout, global_guard_agents, replace_file, set_global_guard, write_policy
from .source import read_checkout
from .wiring import install_wiring, uninstall_wiring, verify_wiring

OWNED_ENTRIES = (
    "current",
    "wiring.json",
    ".wiring.lock",
    ".update.lock",
    "checkouts",
    "global-guard",
    "releases",
    "last-check.json",
)


def _pass_through(root: Path) -> PreparedState:
    return PreparedState("pass-through", root, None, None, "not-marked")


def remove_copy(repository: Path) -> bool:
    local = repository / ".agents/hard-eng"
    current = local / "current"
    if not current.is_symlink():
        return False
    uninstall_wiring(repository, current)
    if local.is_symlink() or not local.is_dir():
        raise ConfigurationError(f"Hard Eng copy root is unsafe: {local}")
    if not current.is_symlink():
        raise ConfigurationError("Hard Eng current link changed during removal")
    for name in OWNED_ENTRIES:
        path = local / name
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
    for directory in (local, local.parent):
        try:
            directory.rmdir()
        except OSError:
            break
    return True


def _discard_copy(repository: Path, *, existed: bool) -> None:
    local = repository / ".agents/hard-eng"
    if local.is_symlink() or not local.is_dir():
        return
    if existed:
        current = local / "current"
        if current.is_symlink():
            current.unlink()
        shutil.rmtree(local / "checkouts", ignore_errors=True)
        return
    shutil.rmtree(local)
    try:
        local.parent.rmdir()
    except OSError:
        pass


def _guard_note(global_state: GlobalState) -> str:
    if global_state.mode == "global":
        return "; the global Hard Eng guard checks tool calls"
    if global_state.mode == "broken":
        return "; global Hard Eng is broken: " + "; ".join(global_state.problems)
    return ""


def _prepare_shared(
    repository: RepositoryState, global_state: GlobalState, agent: str, *, fetch: bool
) -> PreparedState:
    local = repository.root / ".agents/hard-eng"
    existed = local.is_dir()
    fresh = not (local / "current").is_symlink()
    try:
        checkout = ensure_checkout(repository.root, fetch=fetch)
        install_wiring(repository.root, local / "current", shared=True)
    except HardEngError:
        if fresh:
            _discard_copy(repository.root, existed=existed)
        raise
    set_global_guard(repository.root, agent, global_state.mode == "global")
    return PreparedState(
        "shared", repository.root, checkout.root, checkout.commit, "verified" + _guard_note(global_state)
    )


def prepare(start: Path, home: Path, agent: str) -> PreparedState:
    repository = inspect_repository(start)
    if not repository.marked:
        return _pass_through(repository.root)
    if agent == "claude":
        require_claude_owner(repository.root)
    global_state = inspect_global(home, agent)
    if repository.shared:
        return _prepare_shared(repository, global_state, agent, fetch=False)
    if global_state.mode == "broken":
        details = "\n  - ".join(global_state.problems)
        raise ConfigurationError(
            "a partial or broken global Hard Eng install was found.\n"
            f"  - {details}\nRun `npx -y github:sgaabdu4/hard-eng --global` to repair it."
        )
    if global_state.mode == "global":
        removed = remove_copy(repository.root)
        wiring = "verified" + ("; stale repository copy removed" if removed else "")
        return PreparedState("global", repository.root, global_state.root, global_state.identity, wiring)
    raise ConfigurationError(
        "no global Hard Eng exists; run `hard-eng install --repo` so this repository carries its own copy"
    )


def share(start: Path, home: Path, agent: str) -> PreparedState:
    """Fetch the newest Hard Eng into the repository and stage the wiring every clone needs to fetch it too."""
    repository = inspect_repository(start)
    if not repository.marked:
        raise ConfigurationError(
            "hard-eng.gates.json is missing; run `hard-eng install --repo` from the repository root"
        )
    if agent == "claude":
        require_claude_owner(repository.root)
    global_state = inspect_global(home, agent)
    state = _prepare_shared(repository, global_state, agent, fetch=True)
    if not repository.shared:
        write_policy(repository.root, shared=True)
    return state


def remove_shared(start: Path) -> bool:
    """Remove the committed shared wiring: generated files, Hard Eng hook entries, the marker, and the copy."""
    repository = inspect_repository(start)
    if not repository.marked or not repository.shared:
        return False
    root = repository.root
    payload = root / ".agents/hard-eng/current"
    remove_copy(root)
    composable = composable_files(root, shared=True)
    for path in shared_files(root):
        if path.is_symlink() or not path.exists():
            continue
        if path in composable:
            stripped = strip_composable(root, payload, path, shared=True)
            if stripped is None:
                continue
            if stripped in EMPTY_COMPOSABLE:
                path.unlink()
            else:
                replace_file(path, stripped, stat.S_IMODE(path.stat().st_mode))
        else:
            path.unlink()
    write_policy(root, shared=False)
    try:
        (root / ".hard-eng").rmdir()
    except OSError:
        pass
    return True


def _status_shared(repository: RepositoryState, agent: str) -> PreparedState:
    local = repository.root / ".agents/hard-eng"
    checkout = read_checkout(local)
    if checkout is None:
        wiring = f"not fetched: run bash {BOOTSTRAP} {agent}"
        return PreparedState("shared", repository.root, None, None, wiring)
    stale = verify_wiring(repository.root, local / "current")
    wiring = "verified" if not stale else "stale: " + "; ".join(stale)
    if agent in global_guard_agents(repository.root):
        wiring += "; the global Hard Eng guard checks tool calls"
    return PreparedState("shared", repository.root, checkout.root, checkout.commit, wiring)


def status(start: Path, home: Path, agent: str) -> PreparedState:
    repository = inspect_repository(start)
    if not repository.marked:
        return _pass_through(repository.root)
    if repository.shared:
        return _status_shared(repository, agent)
    global_state = inspect_global(home, agent)
    if global_state.mode == "broken":
        raise ConfigurationError("global Hard Eng is broken: " + "; ".join(global_state.problems))
    current = repository.root / ".agents/hard-eng/current"
    if global_state.mode == "global":
        wiring = "stale repository copy present" if current.is_symlink() else "verified"
        return PreparedState("global", repository.root, global_state.root, global_state.identity, wiring)
    return PreparedState("unprotected", repository.root, None, None, "not-prepared")
