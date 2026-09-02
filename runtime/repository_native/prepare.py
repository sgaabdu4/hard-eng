"""Prepare one repository for one agent: a healthy global Hard Eng or one verified fallback."""

from __future__ import annotations

import shutil
import stat
from dataclasses import replace
from pathlib import Path

from .adapters import composable_files, hook_owners, shared_files, strip_hooks
from .errors import ConfigurationError, HardEngError
from .models import GlobalState, PreparedState, RepositoryState
from .release import installed_status, prepare_release
from .repository import inspect_global, inspect_repository, require_claude_owner
from .shared import (
    BOOTSTRAP,
    ensure_pinned_release,
    global_guard_agents,
    pin_release,
    pinned_cache,
    replace_file,
    set_global_guard,
    write_policy,
)
from .wiring import install_wiring, preflight_wiring, uninstall_wiring, verify_wiring


def _pass_through(root: Path) -> PreparedState:
    return PreparedState("pass-through", root, None, None, None, None, None, "not-marked")


OWNED_ENTRIES = (
    "current",
    "last-check.json",
    "wiring.json",
    ".wiring.lock",
    ".update.lock",
    "releases",
    "global-guard",
)


def remove_fallback(repository: Path) -> bool:
    local = repository / ".agents/hard-eng"
    current = local / "current"
    if not current.is_symlink():
        return False
    uninstall_wiring(repository, current)
    if local.is_symlink() or not local.is_dir():
        raise ConfigurationError(f"fallback root is unsafe: {local}")
    if not current.is_symlink():
        raise ConfigurationError("fallback current link changed during removal")
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


def _discard_fallback(repository: Path, *, existed: bool) -> None:
    local = repository / ".agents/hard-eng"
    if local.is_symlink() or not local.is_dir():
        return
    if existed:
        for name in ("current", "last-check.json"):
            path = local / name
            if path.is_symlink() or path.is_file():
                path.unlink()
        return
    shutil.rmtree(local)
    try:
        local.parent.rmdir()
    except OSError:
        pass


def _prepare_shared(repository: RepositoryState, global_state: GlobalState, agent: str) -> PreparedState:
    policy = repository.policy
    if policy is None or policy.pin is None:
        raise ConfigurationError("shared wiring needs hard_eng.pin in hard-eng.gates.json")
    local = repository.root / ".agents/hard-eng"
    existed = local.is_dir()
    fresh = not (local / "current").is_symlink()
    try:
        active = ensure_pinned_release(repository.root, policy, agent=agent)
        install_wiring(repository.root, local / "current", shared=True)
    except HardEngError:
        if fresh:
            _discard_fallback(repository.root, existed=existed)
        raise
    deferring = global_state.mode == "global"
    set_global_guard(repository.root, agent, deferring)
    last_check = active.last_check
    if deferring:
        last_check += "; the global Hard Eng guard checks tool calls"
    elif global_state.mode == "broken":
        last_check += "; global Hard Eng is broken: " + "; ".join(global_state.problems)
    return PreparedState(
        "shared",
        repository.root,
        active.root,
        active.version,
        active.source_commit,
        policy.channel,
        active.newest_allowed_version,
        last_check,
    )


def prepare(start: Path, home: Path, agent: str) -> PreparedState:
    repository = inspect_repository(start)
    if not repository.marked:
        return _pass_through(repository.root)
    if agent == "claude":
        require_claude_owner(repository.root)
    global_state = inspect_global(home, agent)
    if repository.policy is not None and repository.policy.shared:
        return _prepare_shared(repository, global_state, agent)
    if global_state.mode == "broken":
        details = "\n  - ".join(global_state.problems)
        raise ConfigurationError(
            "a partial or broken global Hard Eng install was found; fallback was not activated.\n"
            f"  - {details}\nRun `npx -y github:sgaabdu4/hard-eng --global` to repair it."
        )
    channel = repository.policy.channel if repository.policy else None
    if global_state.mode == "global":
        removed = remove_fallback(repository.root)
        last_check = "global-health-verified" + ("; stale repository fallback removed" if removed else "")
        return PreparedState(
            "global", repository.root, global_state.root, global_state.identity, None, channel, None, last_check
        )
    if repository.policy is None:
        raise ConfigurationError("no global Hard Eng exists and hard-eng.gates.json has no hard_eng release policy")
    preflight_wiring(repository.root)
    local = repository.root / ".agents/hard-eng"
    existed = local.is_dir()
    fresh = not (local / "current").is_symlink()
    active = prepare_release(repository.root, repository.policy, repository.marker_digest or "", agent=agent)
    try:
        install_wiring(repository.root, local / "current")
    except HardEngError:
        if fresh:
            _discard_fallback(repository.root, existed=existed)
        raise
    return PreparedState(
        "fallback",
        repository.root,
        active.root,
        active.version,
        active.source_commit,
        repository.policy.channel,
        active.newest_allowed_version,
        active.last_check,
    )


def share(start: Path, home: Path, agent: str, *, repin: bool = False) -> PreparedState:
    """Pin the newest allowed release into the repository so every clone bootstraps the same Hard Eng."""
    repository = inspect_repository(start)
    if not repository.marked or repository.policy is None:
        raise ConfigurationError("hard-eng.gates.json needs a hard_eng policy before shared wiring")
    if agent == "claude":
        require_claude_owner(repository.root)
    if repository.policy.shared and not repin:
        return prepare(start, home, agent)
    local = repository.root / ".agents/hard-eng"
    existed = local.is_dir()
    fresh = not (local / "current").is_symlink()
    try:
        _, pin = pin_release(repository.root, repository.policy, repository.marker_digest or "")
        install_wiring(repository.root, local / "current", shared=True)
        write_policy(repository.root, replace(repository.policy, shared=True, pin=pin))
    except HardEngError:
        if fresh:
            _discard_fallback(repository.root, existed=existed)
        raise
    return prepare(start, home, agent)


def remove_shared(start: Path) -> bool:
    """Remove the committed shared wiring: generated files, Hard Eng hook entries, the pin, and the private cache."""
    repository = inspect_repository(start)
    if not repository.marked or repository.policy is None or not repository.policy.shared:
        return False
    root = repository.root
    remove_fallback(root)
    owners = hook_owners(root, root / ".agents/hard-eng/current", shared=True)
    composable = composable_files(root, shared=True)
    for path in shared_files(root):
        if path.is_symlink() or not path.exists():
            continue
        if path in composable:
            stripped = strip_hooks(path, [owner for owner in owners if owner.path == path])
            if stripped == b"{}\n":
                path.unlink()
            else:
                replace_file(path, stripped, stat.S_IMODE(path.stat().st_mode))
        else:
            path.unlink()
    write_policy(root, replace(repository.policy, shared=False, pin=None))
    try:
        (root / ".hard-eng").rmdir()
    except OSError:
        pass
    return True


def _status_shared(repository: RepositoryState, agent: str) -> PreparedState:
    policy = repository.policy
    if policy is None or policy.pin is None:
        raise ConfigurationError("shared wiring needs hard_eng.pin in hard-eng.gates.json")
    local = repository.root / ".agents/hard-eng"
    cached = pinned_cache(local, policy.pin)
    if cached is None:
        wiring = f"not downloaded: run bash {BOOTSTRAP} {agent}"
        return PreparedState(
            "shared",
            repository.root,
            None,
            policy.pin.tag,
            None,
            policy.channel,
            policy.pin.tag,
            "not-prepared",
            wiring,
        )
    stale = verify_wiring(repository.root, local / "current")
    wiring = "verified" if not stale else "stale: " + "; ".join(stale)
    if agent in global_guard_agents(repository.root):
        wiring += "; the global Hard Eng guard checks tool calls"
    return PreparedState(
        "shared",
        repository.root,
        cached.root,
        cached.version,
        cached.source_commit,
        policy.channel,
        cached.newest_allowed_version,
        cached.last_check,
        wiring,
    )


def status(start: Path, home: Path, agent: str) -> PreparedState:
    repository = inspect_repository(start)
    if not repository.marked:
        return _pass_through(repository.root)
    if repository.policy is not None and repository.policy.shared:
        return _status_shared(repository, agent)
    global_state = inspect_global(home, agent)
    channel = repository.policy.channel if repository.policy else None
    if global_state.mode == "broken":
        raise ConfigurationError("global Hard Eng is broken: " + "; ".join(global_state.problems))
    current = repository.root / ".agents/hard-eng/current"
    if global_state.mode == "global":
        wiring = "stale repository fallback present" if current.is_symlink() else "verified"
        return PreparedState(
            "global",
            repository.root,
            global_state.root,
            global_state.identity,
            None,
            channel,
            None,
            "global-health-verified",
            wiring,
        )
    if not current.is_symlink():
        return PreparedState("unprotected", repository.root, None, None, None, channel, None, "not-prepared")
    if repository.policy is None or repository.marker_digest is None:
        raise ConfigurationError("fallback release policy is missing")
    active = installed_status(repository.root / ".agents/hard-eng", repository.policy, repository.marker_digest)
    if active is None:
        raise ConfigurationError("fallback release state is incomplete or changed")
    stale = verify_wiring(repository.root, current)
    wiring = "verified" if not stale else "stale: " + "; ".join(stale)
    return PreparedState(
        "fallback",
        repository.root,
        active.root,
        active.version,
        active.source_commit,
        channel,
        active.newest_allowed_version,
        active.last_check,
        wiring,
    )
