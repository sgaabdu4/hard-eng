"""Load host model roles, challenge fallback order, and CLI flags from .agents/models.json."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import TypedDict

MODELS_FILE = ".agents/models.json"
SHIPPED_MODELS = Path(__file__).resolve().parents[1] / MODELS_FILE
HOSTS = ("claude", "codex", "agy")
ROLES = ("reasoning", "implementation", "lookup")
OVERFLOW_ROLES = ("reasoning", "implementation")
EFFORTS = frozenset({"low", "medium", "high", "xhigh", "max"})
SAFE_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]*$")
SAFE_TIER = re.compile(r"^[a-z][a-z0-9_-]*$")
TOML_LITERALS = frozenset({"true", "false", "inf", "nan"})
ROLE_FIELDS = frozenset({"model", "effort", "service_tier"})
TOP_FIELDS = frozenset({"hosts", "challenge_order", "subagent_overflow"})


RoleConfig = TypedDict(
    "RoleConfig", {"model": str, "effort": str, "service_tier": str}, total=False
)
ModelsConfig = TypedDict(
    "ModelsConfig",
    {
        "hosts": dict[str, dict[str, RoleConfig]],
        "challenge_order": dict[str, list[str]],
        "subagent_overflow": dict[str, list[str]],
    },
)


def local_override_path() -> Path:
    """Optional machine-local override outside the repository."""
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / ".config"
    return base / "hard-eng/models.json"


def base_models_path(root: Path | None = None) -> Path:
    if root is not None:
        candidate = root / MODELS_FILE
        if candidate.exists() or candidate.is_symlink():
            return candidate
    return SHIPPED_MODELS


def _parse_object(text: str, label: str) -> dict[str, object]:
    try:
        raw = json.loads(text)
    except ValueError as error:
        raise ValueError(f"{label}: unreadable JSON ({error})") from error
    if not isinstance(raw, dict):
        raise TypeError(f"{label}: expected a JSON object")
    return raw


def _read_object(path: Path, label: str) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"{label}: unreadable JSON ({error})") from error
    return _parse_object(text, label)


def _git_stdout(root: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def _git_blob_if_present(root: Path, ref: str, path: str) -> str | None:
    """Read ref:path; return None only when ls-tree proves the path is absent in ref."""
    spec = f"{ref}:{path}"
    shown = subprocess.run(
        ["git", "show", spec],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if shown.returncode == 0:
        return shown.stdout
    listed = _git_stdout(root, "ls-tree", ref, "--", path)
    if listed == "":
        return None
    reason = shown.stderr.strip() or "git read failed"
    raise ValueError(f"{ref}:{path}: unreadable trusted base ({reason})")


def _policy_base(raw: str) -> str | None:
    try:
        config = json.loads(raw)
    except ValueError:
        return None
    if isinstance(config, dict) and isinstance(config.get("shipping"), dict):
        base = config["shipping"].get("base")
        if isinstance(base, str) and base.strip():
            return base.strip()
    return None


def _exact_ref_sha(root: Path, full_ref: str) -> str | None:
    """Resolve an exact branch or remote-tracking ref without ever matching tags."""
    sha = (_git_stdout(root, "show-ref", "--verify", "--hash", full_ref) or "").strip()
    return sha or None


def _symbolic_origin_head(root: Path) -> str | None:
    target = (
        _git_stdout(root, "symbolic-ref", "-q", "refs/remotes/origin/HEAD") or ""
    ).strip()
    if not target.startswith("refs/remotes/origin/"):
        return None
    return _exact_ref_sha(root, target)


def _is_shallow(root: Path) -> bool:
    return (
        _git_stdout(root, "rev-parse", "--is-shallow-repository") or ""
    ).strip() == "true"


def _anchor_point(
    root: Path, sha: str, *, allow_shallow_tip: bool
) -> tuple[str, str] | None:
    if point := _git_stdout(root, "merge-base", "HEAD", sha):
        return sha, point.strip()
    if allow_shallow_tip and _is_shallow(root):
        return sha, sha
    return None


def _remote_anchor_shas(root: Path) -> list[str]:
    return list(
        dict.fromkeys(
            sha
            for name in ("main", "master", "develop", "HEAD")
            if (sha := _exact_ref_sha(root, f"refs/remotes/origin/{name}"))
        )
    )


def _policy_merge_base(root: Path, ref_sha: str, *, remote_only: bool) -> str | None:
    raw = _git_blob_if_present(root, ref_sha, "hard-eng.gates.json")
    if raw is None or (base := _policy_base(raw)) is None:
        return None
    refs = (
        (f"refs/remotes/origin/{base}",)
        if remote_only
        else (f"refs/remotes/origin/{base}", f"refs/heads/{base}")
    )
    for full_ref in refs:
        if (sha := _exact_ref_sha(root, full_ref)) and (
            found := _anchor_point(root, sha, allow_shallow_tip=remote_only)
        ):
            return found[1]
    return None


def _local_anchor_shas(root: Path) -> list[str]:
    local = (
        _git_stdout(root, "config", "--get", "init.defaultBranch") or ""
    ).strip() or "master"
    return list(
        dict.fromkeys(
            sha
            for name in dict.fromkeys(("main", "master", local, "develop"))
            if (sha := _exact_ref_sha(root, f"refs/heads/{name}"))
        )
    )


def trusted_base_ref(root: Path | None) -> str | None:
    """Resolve the merge-base commit from the default base ref, never trusting unmerged branch policies."""
    if root is None or not _git_stdout(root, "rev-parse", "--verify", "HEAD^{commit}"):
        return None
    if sym := _symbolic_origin_head(root):
        if resolved := _policy_merge_base(root, sym, remote_only=True):
            return resolved
        found = _anchor_point(root, sym, allow_shallow_tip=True)
        return found[1] if found else sym
    remote_shas = _remote_anchor_shas(root)
    candidates, remote_only = (
        (remote_shas, True) if remote_shas else (_local_anchor_shas(root), False)
    )
    for sha in candidates:
        if found := _anchor_point(root, sha, allow_shallow_tip=remote_only):
            return (
                _policy_merge_base(root, found[0], remote_only=remote_only) or found[1]
            )
    return None


def _read_trusted_base(root: Path | None, trusted_ref: str | None) -> dict[str, object]:
    if root is not None and trusted_ref is not None:
        raw = _git_blob_if_present(root, trusted_ref, MODELS_FILE)
        if raw is not None:
            return _parse_object(raw, f"{trusted_ref}:{MODELS_FILE}")
        return _read_object(SHIPPED_MODELS, MODELS_FILE)
    return _read_object(base_models_path(root), MODELS_FILE)


def _check_role_field(key: str, value: object, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{where}.{key}: must be a nonempty string")
    if key == "model" and not SAFE_MODEL.fullmatch(value):
        raise ValueError(f"{where}.model: invalid model identifier {value!r}")
    if key == "effort" and value not in EFFORTS:
        raise ValueError(f"{where}.effort: must be one of {sorted(EFFORTS)}")
    if key == "service_tier" and (
        not SAFE_TIER.fullmatch(value) or value in TOML_LITERALS
    ):
        raise ValueError(f"{where}.service_tier: invalid service tier {value!r}")
    return value


def _validate_role(
    host: str, role: str, raw: object, label: str, *, partial: bool
) -> RoleConfig:
    where = f"{label} hosts.{host}.{role}"
    if not isinstance(raw, dict):
        raise TypeError(f"{where}: expected an object")
    if unknown := sorted(set(raw) - ROLE_FIELDS):
        raise ValueError(f"{where}: unknown fields {', '.join(unknown)}")
    if "service_tier" in raw and host != "codex":
        raise ValueError(f"{where}: service_tier is supported only for codex")
    if not partial and (missing := [k for k in ("model", "effort") if k not in raw]):
        raise ValueError(f"{where}: missing required fields {', '.join(missing)}")
    result: RoleConfig = {}
    if "model" in raw:
        result["model"] = _check_role_field("model", raw["model"], where)
    if "effort" in raw:
        result["effort"] = _check_role_field("effort", raw["effort"], where)
    if "service_tier" in raw:
        result["service_tier"] = _check_role_field(
            "service_tier", raw["service_tier"], where
        )
    return result


def _validate_host_list(
    where: str,
    raw: object,
    *,
    excluded: str | None = None,
    require_all_other: bool = False,
) -> list[str]:
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{where}: must be a nonempty list of hosts")
    seen: list[str] = []
    for item in raw:
        if not isinstance(item, str) or item not in HOSTS:
            raise ValueError(f"{where}: unknown host {item!r}")
        if item == excluded:
            raise ValueError(f"{where}: cannot include {excluded!r} itself")
        if item in seen:
            raise ValueError(f"{where}: duplicate host {item!r}")
        seen.append(item)
    if require_all_other and excluded is not None and len(seen) != len(HOSTS) - 1:
        missing = sorted(set(HOSTS) - {excluded} - set(seen))
        raise ValueError(
            f"{where}: must include all other hosts (missing {', '.join(missing)})"
        )
    return seen


def _validate_hosts(
    raw: object, label: str, *, partial: bool
) -> dict[str, dict[str, RoleConfig]]:
    if not isinstance(raw, dict):
        raise TypeError(f"{label} hosts: expected an object")
    allowed = set(HOSTS)
    if unknown := sorted(set(raw) - allowed):
        raise ValueError(f"{label} hosts: unknown hosts {', '.join(unknown)}")
    if not partial and (missing := sorted(allowed - set(raw))):
        raise ValueError(f"{label} hosts: missing hosts {', '.join(missing)}")
    parsed: dict[str, dict[str, RoleConfig]] = {}
    for host, roles in raw.items():
        if not isinstance(roles, dict):
            raise TypeError(f"{label} hosts.{host}: expected an object")
        role_set = set(ROLES)
        if bad_roles := sorted(set(roles) - role_set):
            raise ValueError(
                f"{label} hosts.{host}: unknown roles {', '.join(bad_roles)}"
            )
        if not partial and (missing_roles := sorted(role_set - set(roles))):
            raise ValueError(
                f"{label} hosts.{host}: missing roles {', '.join(missing_roles)}"
            )
        parsed[host] = {
            role: _validate_role(host, role, cfg, label, partial=partial)
            for role, cfg in roles.items()
        }
    return parsed


def _validate_order_map(
    section: str,
    keys: tuple[str, ...],
    raw: object,
    label: str,
    *,
    partial: bool,
    exclude_self: bool,
) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        raise TypeError(f"{label} {section}: expected an object")
    allowed = set(keys)
    if unknown := sorted(set(raw) - allowed):
        raise ValueError(f"{label} {section}: unknown keys {', '.join(unknown)}")
    if not partial and (missing := sorted(allowed - set(raw))):
        raise ValueError(f"{label} {section}: missing keys {', '.join(missing)}")
    return {
        key: _validate_host_list(
            f"{label} {section}.{key}",
            value,
            excluded=key if exclude_self else None,
            require_all_other=exclude_self,
        )
        for key, value in raw.items()
    }


def _validate_base(raw: dict[str, object], label: str) -> ModelsConfig:
    if unknown := sorted(set(raw) - TOP_FIELDS):
        raise ValueError(f"{label}: unknown sections {', '.join(unknown)}")
    if missing := sorted(TOP_FIELDS - set(raw)):
        raise ValueError(f"{label}: missing sections {', '.join(missing)}")
    return {
        "hosts": _validate_hosts(raw["hosts"], label, partial=False),
        "challenge_order": _validate_order_map(
            "challenge_order",
            HOSTS,
            raw["challenge_order"],
            label,
            partial=False,
            exclude_self=True,
        ),
        "subagent_overflow": _validate_order_map(
            "subagent_overflow",
            OVERFLOW_ROLES,
            raw["subagent_overflow"],
            label,
            partial=False,
            exclude_self=False,
        ),
    }


def _merge_overlay(
    base: ModelsConfig, raw: dict[str, object], label: str
) -> ModelsConfig:
    if unknown := sorted(set(raw) - TOP_FIELDS):
        raise ValueError(f"{label}: unknown sections {', '.join(unknown)}")
    merged: ModelsConfig = {
        "hosts": {
            host: {role: cfg.copy() for role, cfg in roles.items()}
            for host, roles in base["hosts"].items()
        },
        "challenge_order": {
            host: list(order) for host, order in base["challenge_order"].items()
        },
        "subagent_overflow": {
            role: list(order) for role, order in base["subagent_overflow"].items()
        },
    }
    if "hosts" in raw:
        for host, roles in _validate_hosts(raw["hosts"], label, partial=True).items():
            for role, patch in roles.items():
                merged["hosts"][host][role].update(patch)
    if "challenge_order" in raw:
        merged["challenge_order"].update(
            _validate_order_map(
                "challenge_order",
                HOSTS,
                raw["challenge_order"],
                label,
                partial=True,
                exclude_self=True,
            )
        )
    if "subagent_overflow" in raw:
        merged["subagent_overflow"].update(
            _validate_order_map(
                "subagent_overflow",
                OVERFLOW_ROLES,
                raw["subagent_overflow"],
                label,
                partial=True,
                exclude_self=False,
            )
        )
    return merged


def load_models(
    root: Path | None = None, *, trusted_ref: str | None = None
) -> ModelsConfig:
    """Load validated model settings from .agents/models.json plus optional local overlay."""
    config = _validate_base(_read_trusted_base(root, trusted_ref), MODELS_FILE)
    override = local_override_path()
    if override.exists() or override.is_symlink():
        config = _merge_overlay(
            config, _read_object(override, str(override)), str(override)
        )
    return config


def challenge_order_for(
    host: str, root: Path | None = None, *, trusted_ref: str | None = None
) -> tuple[str, ...]:
    if host not in HOSTS:
        raise ValueError(f"Unknown host {host!r}; expected one of {', '.join(HOSTS)}")
    return tuple(load_models(root, trusted_ref=trusted_ref)["challenge_order"][host])


def role_config(
    host: str, role: str, root: Path | None = None, *, trusted_ref: str | None = None
) -> RoleConfig:
    if host not in HOSTS:
        raise ValueError(f"Unknown host {host!r}; expected one of {', '.join(HOSTS)}")
    if role not in ROLES:
        raise ValueError(f"Unknown role {role!r}; expected one of {', '.join(ROLES)}")
    return load_models(root, trusted_ref=trusted_ref)["hosts"][host][role]


def cli_flags(
    host: str,
    role: str = "reasoning",
    root: Path | None = None,
    *,
    trusted_ref: str | None = None,
) -> list[str]:
    """CLI model, effort, and service-tier flags verified for the given host binary."""
    cfg = role_config(host, role, root, trusted_ref=trusted_ref)
    model = cfg["model"]
    effort = cfg["effort"]
    if host == "codex":
        flags = ["-m", model, "-c", f"model_reasoning_effort={effort}"]
        if "service_tier" in cfg:
            flags.extend(["-c", f"service_tier={cfg['service_tier']}"])
        return flags
    return ["--model", model, "--effort", effort]


def session_note(root: Path, agent: str) -> str:
    """Surface model-role config to hosts that do not auto-load .claude/rules/."""
    if agent in {"codex", "agy"} and (root / MODELS_FILE).is_file():
        return (
            f"\nSubagent models/efforts: {MODELS_FILE} "
            "(rules: .claude/rules/model-roles.md)."
        )
    return ""
