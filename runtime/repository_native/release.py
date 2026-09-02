"""Verified GitHub Release selection and atomic repository activation."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

try:
    import fcntl
except ImportError:
    fcntl = None

from . import LAUNCHER_SCHEMA, SUPPORTED_AGENTS
from .errors import ReleaseError, ReleaseUnavailable
from .models import MarkerPolicy

PRERELEASE = re.compile(r"^v0\.1\.0-alpha\.g([0-9a-f]{40})$")
STABLE = re.compile(r"^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
STATE_SCHEMA = 1
LOCK_TIMEOUT_SECONDS = 30
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_EXPANDED_BYTES = 256 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_ARCHIVE_MEMBERS = 20_000
PYTHON_REQUIREMENT = ">=3.12.0"
NODE_REQUIREMENT = ">=26.0.0"
VERSION = re.compile(r"^v?([0-9]+)\.([0-9]+)\.([0-9]+)(?:[-+].*)?$")


@dataclass(frozen=True)
class Candidate:
    tag: str
    commit: str
    release: dict[str, object]


@dataclass(frozen=True)
class ActiveRelease:
    root: Path
    version: str
    source_commit: str
    newest_allowed_version: str
    last_check: str


def _write_all(descriptor: int, data: bytes) -> None:
    remaining = memoryview(data)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError("file write made no progress")
        remaining = remaining[written:]


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda value: value.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise ReleaseError(f"installed release contains a symlink: {relative}")
        if stat.S_ISDIR(metadata.st_mode):
            kind = b"directory"
        elif stat.S_ISREG(metadata.st_mode):
            kind = b"file"
        else:
            raise ReleaseError(f"installed release contains an unsupported path: {relative}")
        digest.update(kind + b"\0" + relative.encode() + b"\0")
        digest.update(f"{stat.S_IMODE(metadata.st_mode):04o}".encode() + b"\0")
        if kind == b"file":
            digest.update(str(metadata.st_size).encode() + b"\0")
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
    return digest.hexdigest()


def _command_env() -> dict[str, str]:
    return {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}


def _run(command: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True, env=_command_env(), timeout=timeout)
    except FileNotFoundError as error:
        failure = ReleaseUnavailable if command[0] == "gh" else ReleaseError
        raise failure(f"required command is missing: {command[0]}") from error
    except subprocess.TimeoutExpired as error:
        failure = ReleaseUnavailable if command[0] == "gh" else ReleaseError
        raise failure(f"command did not finish within {timeout}s: {command[0]}") from error
    except subprocess.CalledProcessError as error:
        message = (error.stderr or error.stdout or "command failed").strip().splitlines()[-1]
        network_failures = (
            "api rate limit exceeded",
            "connection refused",
            "could not resolve host",
            "failed to connect",
            "network is unreachable",
            "service unavailable",
            "timed out",
            "tls handshake timeout",
        )
        if command[0] == "gh" and any(fragment in message.lower() for fragment in network_failures):
            raise ReleaseUnavailable(f"gh failed: {message}") from error
        raise ReleaseError(f"{command[0]} failed: {message}") from error


def _gh_json(*arguments: str) -> object:
    result = _run(["gh", *arguments], timeout=60)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ReleaseError("GitHub CLI returned invalid JSON") from error


def _platform_id() -> str:
    system = {"darwin": "darwin", "linux": "linux", "win32": "windows"}.get(sys.platform)
    machine = platform.machine().lower()
    architecture = {"amd64": "x64", "x86_64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(machine)
    if system is None or architecture is None:
        raise ReleaseError(f"unsupported platform: {sys.platform}-{machine}")
    return f"{system}-{architecture}"


def require_runtime() -> None:
    if sys.version_info < (3, 12):
        raise ReleaseError(f"release requires Python {PYTHON_REQUIREMENT}")
    node_version = _run(["node", "--version"], timeout=10).stdout.strip()
    match = VERSION.fullmatch(node_version)
    if match is None or tuple(int(part) for part in match.groups()) < (26, 0, 0):
        raise ReleaseError(f"release requires Node.js {NODE_REQUIREMENT}")


def _candidate(value: object, channel: str) -> Candidate | None:
    if not isinstance(value, dict) or value.get("draft") is not False or value.get("immutable") is not True:
        return None
    tag = value.get("tag_name")
    commit = value.get("target_commitish")
    prerelease = value.get("prerelease")
    if not isinstance(tag, str) or not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        return None
    if channel == "stable":
        if prerelease is not False or not STABLE.fullmatch(tag):
            return None
    elif not ((prerelease is True and PRERELEASE.fullmatch(tag)) or (prerelease is False and STABLE.fullmatch(tag))):
        return None
    return Candidate(tag, commit, value)


def _compare(repository: str, base: str, head: str) -> str:
    value = _gh_json("api", f"repos/{repository}/compare/{base}...{head}")
    if not isinstance(value, dict) or value.get("status") not in {"ahead", "behind", "identical", "diverged"}:
        raise ReleaseError("GitHub compare response is missing a valid status")
    return str(value["status"])


def _newest_by_ancestry(repository: str, candidates: list[Candidate]) -> Candidate:
    if not candidates:
        raise ReleaseError("no compatible immutable release exists on the selected channel")
    selected = candidates[0]
    for candidate in candidates[1:]:
        status = _compare(repository, selected.commit, candidate.commit)
        if status == "ahead":
            selected = candidate
        elif status == "diverged":
            raise ReleaseError("published Hard Eng releases have incomparable source commits")
    for candidate in candidates:
        if candidate == selected:
            continue
        if _compare(repository, candidate.commit, selected.commit) not in {"ahead", "identical"}:
            raise ReleaseError("no single newest Hard Eng release exists on the default-branch ancestry")
    return selected


def release_by_tag(repository: str, tag: str) -> Candidate:
    value = _gh_json("api", f"repos/{repository}/releases/tags/{tag}")
    candidate = _candidate(value, "prerelease")
    if candidate is None or candidate.tag != tag:
        raise ReleaseError(f"minimum Hard Eng release is not eligible: {tag}")
    return candidate


def select_release(policy: MarkerPolicy) -> Candidate:
    if policy.channel is None:
        raise ReleaseError("no global Hard Eng exists and hard_eng.channel is missing; set it to stable or prerelease")
    value = _gh_json("api", "--method", "GET", f"repos/{policy.release_repository}/releases", "-f", "per_page=100")
    if not isinstance(value, list):
        raise ReleaseError("GitHub releases response is not a list")
    candidates = [candidate for item in value if (candidate := _candidate(item, policy.channel))]
    if policy.minimum_version:
        minimum = release_by_tag(policy.release_repository, policy.minimum_version)
        candidates = [
            candidate
            for candidate in candidates
            if _compare(policy.release_repository, minimum.commit, candidate.commit) in {"ahead", "identical"}
        ]
    return _newest_by_ancestry(policy.release_repository, candidates)


def _asset(release: dict[str, object], name: str) -> dict[str, object]:
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise ReleaseError("release assets are missing")
    matches = [entry for entry in assets if isinstance(entry, dict) and entry.get("name") == name]
    if len(matches) != 1:
        raise ReleaseError(f"release must contain exactly one {name} asset")
    return matches[0]


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_asset_digest(path: Path, asset: dict[str, object]) -> None:
    digest = asset.get("digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise ReleaseError(f"GitHub did not publish a SHA-256 digest for {path.name}")
    expected = digest.removeprefix("sha256:")
    if not SHA256.fullmatch(expected) or file_sha(path) != expected:
        raise ReleaseError(f"GitHub asset digest does not match {path.name}")


def download_release(candidate: Candidate, repository: str, destination: Path) -> tuple[Path, Path, dict[str, object]]:
    archive_name = f"hard-eng-{candidate.tag}.tar.gz"
    manifest_name = f"hard-eng-{candidate.tag}.manifest.json"
    archive_asset = _asset(candidate.release, archive_name)
    manifest_asset = _asset(candidate.release, manifest_name)
    archive_size = archive_asset.get("size")
    manifest_size = manifest_asset.get("size")
    if not isinstance(archive_size, int) or archive_size <= 0 or archive_size > MAX_ARCHIVE_BYTES:
        raise ReleaseError("GitHub release archive size is missing or unsafe")
    if not isinstance(manifest_size, int) or manifest_size <= 0 or manifest_size > MAX_MANIFEST_BYTES:
        raise ReleaseError("GitHub release manifest size is missing or unsafe")
    _run(
        [
            "gh",
            "release",
            "download",
            candidate.tag,
            "--repo",
            repository,
            "--pattern",
            archive_name,
            "--pattern",
            manifest_name,
            "--dir",
            str(destination),
        ],
        timeout=180,
    )
    verification = _run(
        ["gh", "release", "verify", candidate.tag, "--repo", repository, "--format", "json"], timeout=120
    )
    try:
        verification_receipt = json.loads(verification.stdout)
    except json.JSONDecodeError as error:
        raise ReleaseError("GitHub release verification returned an invalid receipt") from error
    if not verification_receipt:
        raise ReleaseError("GitHub release verification returned an empty receipt")
    archive = destination / archive_name
    manifest_path = destination / manifest_name
    if not archive.is_file() or not manifest_path.is_file():
        raise ReleaseError("GitHub release download did not produce both required assets")
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ReleaseError("release archive exceeds the 64 MiB safety limit")
    if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ReleaseError("release manifest exceeds the 1 MiB safety limit")
    _verify_asset_digest(archive, archive_asset)
    _verify_asset_digest(manifest_path, manifest_asset)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseError("release manifest is invalid JSON") from error
    if not isinstance(manifest, dict):
        raise ReleaseError("release manifest is not an object")
    return archive, manifest_path, manifest


def validate_manifest(candidate: Candidate, archive: Path, manifest: dict[str, object], *, agent: str) -> None:
    if manifest.get("schema_version") != 3 or manifest.get("product") != "hard-eng":
        raise ReleaseError("release manifest is not repository-native Hard Eng schema 3")
    if manifest.get("version") != candidate.tag or manifest.get("source_commit") != candidate.commit:
        raise ReleaseError("release manifest identity does not match the GitHub Release")
    if manifest.get("launcher_schema") != LAUNCHER_SCHEMA:
        raise ReleaseError("release launcher compatibility does not match this launcher")
    compatibility = manifest.get("compatibility")
    if not isinstance(compatibility, dict):
        raise ReleaseError("release compatibility is missing")
    agents = compatibility.get("agents")
    platforms = compatibility.get("platforms")
    if agent not in SUPPORTED_AGENTS or not isinstance(agents, list) or agent not in agents:
        raise ReleaseError(f"release does not support {agent}")
    if not isinstance(platforms, list) or _platform_id() not in platforms:
        raise ReleaseError(f"release does not support {_platform_id()}")
    if compatibility.get("python") != PYTHON_REQUIREMENT:
        raise ReleaseError(f"release must declare Python {PYTHON_REQUIREMENT}")
    if compatibility.get("node") != NODE_REQUIREMENT:
        raise ReleaseError(f"release must declare Node.js {NODE_REQUIREMENT}")
    archive_value = manifest.get("archive")
    if not isinstance(archive_value, dict):
        raise ReleaseError("release manifest archive identity is missing")
    if archive_value.get("name") != archive.name or archive_value.get("sha256") != file_sha(archive):
        raise ReleaseError("release archive checksum does not match the manifest")
    if archive_value.get("size") != archive.stat().st_size:
        raise ReleaseError("release archive size does not match the manifest")


def _safe_member(member: tarfile.TarInfo) -> None:
    path = PurePosixPath(member.name)
    if path.is_absolute() or not path.parts or ".." in path.parts or path.parts[0] in {"", "."}:
        raise ReleaseError(f"unsafe release archive path: {member.name}")
    if member.issym() or member.islnk() or member.isdev() or member.isfifo():
        raise ReleaseError(f"unsupported release archive entry: {member.name}")
    if not (member.isdir() or member.isfile()):
        raise ReleaseError(f"unknown release archive entry: {member.name}")
    if member.size < 0:
        raise ReleaseError(f"release archive entry has a negative size: {member.name}")


def _extract(archive: Path, destination: Path) -> None:
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            members = bundle.getmembers()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise ReleaseError("release archive contains too many entries")
            expanded_bytes = sum(member.size for member in members if member.isfile())
            if expanded_bytes > MAX_EXPANDED_BYTES:
                raise ReleaseError("release archive exceeds the 256 MiB expanded safety limit")
            for member in members:
                _safe_member(member)
            prefixes = {PurePosixPath(member.name).parts[0] for member in members}
            if len(prefixes) != 1:
                raise ReleaseError("release archive must have one top-level directory")
            prefix = prefixes.pop()
            for member in members:
                parts = PurePosixPath(member.name).parts
                if parts[0] != prefix or len(parts) == 1:
                    continue
                relative = Path(*parts[1:])
                target = destination / relative
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                source = bundle.extractfile(member)
                if source is None:
                    raise ReleaseError(f"release file has no content: {member.name}")
                descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, member.mode & 0o755)
                try:
                    with source:
                        while block := source.read(1024 * 1024):
                            _write_all(descriptor, block)
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
    except (OSError, tarfile.TarError) as error:
        raise ReleaseError(f"release archive could not be extracted: {error}") from error


def payload_health(root: Path) -> tuple[str, str]:
    identity = root / ".hard-eng-release.json"
    required = (
        root / "AGENTS.md",
        root / "agents/he-learn/claude.md",
        root / "agents/he-learn/codex.toml",
        root / "agents/he-learn/copilot.agent.md",
        root / "output-styles/plain-english.md",
        root / "skills/plain-english/SKILL.md",
        root / "scripts/hooks/agent-hook.sh",
        root / "runtime/repository_native/__init__.py",
        root / "runtime/repository_native/adapters.py",
        root / "runtime/repository_native/cli.py",
        root / "runtime/repository_native/errors.py",
        root / "runtime/repository_native/installer.py",
        root / "runtime/repository_native/locking.py",
        root / "runtime/repository_native/models.py",
        root / "runtime/repository_native/prepare.py",
        root / "runtime/repository_native/release.py",
        root / "runtime/repository_native/repository.py",
        root / "runtime/repository_native/shared.py",
        root / "runtime/repository_native/wiring.py",
    )
    for path in required:
        if path.is_symlink() or not path.is_file():
            raise ReleaseError(f"installed release is missing {path.relative_to(root)}")
    if identity.is_symlink() or not identity.is_file():
        raise ReleaseError("installed release identity is missing or unsafe")
    try:
        value = json.loads(identity.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseError("installed release identity is invalid") from error
    version = value.get("version") if isinstance(value, dict) else None
    commit = value.get("source_commit") if isinstance(value, dict) else None
    if not isinstance(version, str) or not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        raise ReleaseError("installed release identity is incomplete")
    return version, commit


def stage_release(candidate: Candidate, repository: str, parent: Path, *, agents: tuple[str, ...]) -> Path:
    """Download, verify, and extract one release into a fresh directory under parent."""
    require_runtime()
    stage = Path(tempfile.mkdtemp(prefix=".hard-eng-install-", dir=parent))
    try:
        with tempfile.TemporaryDirectory(prefix="hard-eng-release-") as temporary:
            archive, _, manifest = download_release(candidate, repository, Path(temporary))
            for agent in agents:
                validate_manifest(candidate, archive, manifest, agent=agent)
            _extract(archive, stage)
            write_json(stage / ".hard-eng-release.json", manifest)
        payload_health(stage)
        for relative in ("setup.sh", "bin/hard-eng"):
            path = stage / relative
            if path.is_symlink() or not path.is_file() or not path.stat().st_mode & 0o111:
                raise ReleaseError(f"release file is missing or not executable: {relative}")
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return stage


@contextmanager
def activation_lock(root: Path) -> Iterator[None]:
    if fcntl is None:
        raise ReleaseError("repository fallback is supported only on macOS and Linux")
    parent = root.parent
    try:
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ReleaseError(f"fallback parent is unsafe: {parent}")
        parent.mkdir(mode=0o700, exist_ok=True)
        if root.is_symlink() or (root.exists() and not root.is_dir()):
            raise ReleaseError(f"fallback root is unsafe: {root}")
        root.mkdir(mode=0o700, exist_ok=True)
    except OSError as error:
        raise ReleaseError(f"fallback root could not be prepared: {error}") from error
    lock = root / ".update.lock"
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    flags = os.O_CREAT | os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    handle: int | None = None
    try:
        handle = os.open(lock, flags, 0o600)
        metadata = os.fstat(handle)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ReleaseError("fallback update lock is unsafe")
    except ReleaseError:
        if handle is not None:
            os.close(handle)
        raise
    except OSError as error:
        if handle is not None:
            os.close(handle)
        raise ReleaseError(f"fallback update lock could not be opened: {error}") from error
    assert handle is not None
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.monotonic() >= deadline:
                os.close(handle)
                raise ReleaseError("another Hard Eng update did not finish within 30 seconds")
            time.sleep(0.1)
        except OSError as error:
            os.close(handle)
            raise ReleaseError(f"fallback update lock failed: {error}") from error
    try:
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        os.close(handle)


def read_current(root: Path) -> Path | None:
    current = root / "current"
    if not current.exists() and not current.is_symlink():
        return None
    if not current.is_symlink():
        raise ReleaseError("fallback current path is not a symlink")
    try:
        resolved = current.resolve(strict=True)
    except OSError as error:
        raise ReleaseError("fallback current link is broken") from error
    releases_path = root / "releases"
    if releases_path.is_symlink() or not releases_path.is_dir():
        raise ReleaseError("fallback release directory is unsafe")
    releases = releases_path.resolve()
    if resolved.parent != releases:
        raise ReleaseError("fallback current link points outside the release directory")
    return resolved


def _cached(root: Path, policy: MarkerPolicy, marker_digest: str) -> ActiveRelease | None:
    state_path = root / "last-check.json"
    current = read_current(root)
    if current is None or not state_path.is_file() or state_path.is_symlink():
        return None
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(state, dict) or state.get("schema_version") != STATE_SCHEMA:
        return None
    if (
        state.get("marker_digest") != marker_digest
        or state.get("channel") != policy.channel
        or state.get("minimum_version") != policy.minimum_version
        or state.get("release_repository") != policy.release_repository
    ):
        return None
    version, commit = payload_health(current)
    payload_digest = state.get("payload_digest")
    if (
        state.get("active_version") != version
        or state.get("source_commit") != commit
        or not isinstance(payload_digest, str)
        or not SHA256.fullmatch(payload_digest)
        or tree_digest(current) != payload_digest
    ):
        return None
    return ActiveRelease(current, version, commit, version, "offline-cache")


def write_json(path: Path, value: dict[str, object], mode: int = 0o600) -> None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ReleaseError(f"refusing to replace unsafe release state: {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode)
        try:
            _write_all(descriptor, data)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary, path)
    except BaseException:
        if temporary.is_file() and not temporary.is_symlink():
            temporary.unlink()
        raise


def activate(
    local_root: Path,
    candidate: Candidate,
    archive: Path,
    manifest: dict[str, object],
    policy: MarkerPolicy,
    marker_digest: str,
    extra: dict[str, object] | None = None,
) -> ActiveRelease:
    releases = local_root / "releases"
    if releases.is_symlink() or (releases.exists() and not releases.is_dir()):
        raise ReleaseError("fallback release directory is unsafe")
    releases.mkdir(mode=0o700, exist_ok=True)
    target = releases / candidate.tag
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise ReleaseError(f"existing release path is unsafe: {target}")
    stage = Path(tempfile.mkdtemp(prefix=".installing-", dir=releases))
    try:
        _extract(archive, stage)
        write_json(stage / ".hard-eng-release.json", manifest)
        payload_health(stage)
        payload_digest = tree_digest(stage)
        if target.exists():
            version, commit = payload_health(target)
            if version != candidate.tag or commit != candidate.commit or tree_digest(target) != payload_digest:
                raise ReleaseError(f"existing release directory does not match the verified release: {target}")
        else:
            os.replace(stage, target)
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
    current = local_root / "current"
    if current.exists() and not current.is_symlink():
        raise ReleaseError("fallback current path is not a symlink")
    previous_current = os.readlink(current) if current.is_symlink() else None
    state_path = local_root / "last-check.json"
    if state_path.is_symlink() or (state_path.exists() and not state_path.is_file()):
        raise ReleaseError(f"refusing to replace unsafe release state: {state_path}")
    temporary_link = local_root / f".current.{os.getpid()}"
    try:
        temporary_link.symlink_to(Path("releases") / candidate.tag)
        os.replace(temporary_link, current)
        write_json(
            state_path,
            {
                "active_version": candidate.tag,
                "channel": policy.channel,
                "last_result": "online-verified",
                "marker_digest": marker_digest,
                "minimum_version": policy.minimum_version,
                "newest_allowed_version": candidate.tag,
                "payload_digest": payload_digest,
                "release_repository": policy.release_repository,
                "schema_version": STATE_SCHEMA,
                "source_commit": candidate.commit,
                **(extra or {}),
            },
        )
    except BaseException:
        if temporary_link.is_symlink():
            temporary_link.unlink()
        if previous_current is None:
            if current.is_symlink():
                current.unlink()
        else:
            temporary_link.symlink_to(previous_current)
            os.replace(temporary_link, current)
        raise
    return ActiveRelease(target, candidate.tag, candidate.commit, candidate.tag, "online-verified")


def installed_status(root: Path, policy: MarkerPolicy, marker_digest: str) -> ActiveRelease | None:
    cached = _cached(root, policy, marker_digest)
    if cached is None:
        return None
    state_path = root / "last-check.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    newest = state.get("newest_allowed_version") if isinstance(state, dict) else None
    result = state.get("last_result") if isinstance(state, dict) else None
    return ActiveRelease(
        cached.root,
        cached.version,
        cached.source_commit,
        newest if isinstance(newest, str) else cached.version,
        result if isinstance(result, str) else "installed-not-checked",
    )


def prepare_release(repository: Path, policy: MarkerPolicy, marker_digest: str, *, agent: str) -> ActiveRelease:
    local_root = repository / ".agents/hard-eng"
    with activation_lock(local_root):
        require_runtime()
        try:
            candidate = select_release(policy)
        except ReleaseUnavailable as error:
            cached = _cached(local_root, policy, marker_digest)
            if cached is not None:
                return cached
            raise ReleaseError(
                f"Hard Eng release check failed and no allowed verified cache exists: {error}"
            ) from error
        try:
            with tempfile.TemporaryDirectory(prefix="hard-eng-release-") as temporary:
                archive, _, manifest = download_release(candidate, policy.release_repository, Path(temporary))
                validate_manifest(candidate, archive, manifest, agent=agent)
                return activate(local_root, candidate, archive, manifest, policy, marker_digest)
        except ReleaseError as error:
            cached = _cached(local_root, policy, marker_digest)
            if cached is not None:
                return ActiveRelease(
                    cached.root,
                    cached.version,
                    cached.source_commit,
                    candidate.tag,
                    f"update-failed-using-verified-cache: {error}",
                )
            raise ReleaseError(
                f"Hard Eng release update failed and no allowed verified cache exists: {error}"
            ) from error
