"""Judge the root .gitleaksignore: an entry passes only when a scan run now finds it and its finding is in the past or in generated output."""

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from challenge import known
from gate_config import generated_sources

COMMIT_ENTRY = re.compile(r"([0-9a-f]{40}|[0-9a-f]{64}):(.+):([\w.-]+):\d+")
CURRENT_ENTRY = re.compile(r"(.+):([\w.-]+):\d+")


def entry_lines(root: Path) -> list[tuple[int, str]]:
    path = root / ".gitleaksignore"
    if not path.is_file() or path.is_symlink():
        return []
    return [
        (number, line.strip())
        for number, line in enumerate(path.read_text(errors="replace").splitlines(), 1)
        if line.strip() and not line.strip().startswith("#")
    ]


def scan(
    command: list[str], cwd: Path, report: Path, config: list[str], timeout: float
) -> list[dict[str, str]]:
    """Run Gitleaks where no .gitleaksignore reaches it; the report keeps no secret value."""
    done = subprocess.run(
        [
            "gitleaks",
            *command,
            *config,
            "--redact=100",
            "--no-banner",
            "--ignore-gitleaks-allow",
            "--report-format",
            "json",
            "--report-path",
            str(report),
        ],
        cwd=cwd,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if done.returncode not in (0, 1):
        raise RuntimeError(
            f"gitleaks failed while judging .gitleaksignore: {done.stderr.decode(errors='replace')}"
        )
    return json.loads(report.read_text() or "[]") if report.is_file() else []


def past_findings(
    root: Path, work: Path, commits: list[str], config: list[str], timeout: float
) -> set[str]:
    """Fingerprints of the named commits, scanned in a bare shared clone that holds no ignore file."""
    clone = work / "clone"
    subprocess.run(
        ["git", "clone", "-q", "--bare", "--shared", str(root), str(clone)],
        check=True,
        capture_output=True,
    )
    found = scan(
        ["git", str(clone), f"--log-opts=--no-walk {' '.join(commits)}"],
        work,
        work / "history.json",
        config,
        timeout,
    )
    return {item["Fingerprint"] for item in found}


def entry_paths(entries: list[tuple[int, str]]) -> list[str]:
    """The files that the entries name; a finding of one file does not depend on another file."""
    named: set[str] = set()
    for _, entry in entries:
        if commit := COMMIT_ENTRY.fullmatch(entry):
            named.add(commit[2])
        elif current := CURRENT_ENTRY.fullmatch(entry):
            named.add(current[1])
    return sorted(named)


def current_findings(
    root: Path, work: Path, config: list[str], timeout: float, paths: list[str]
) -> list[dict[str, str]]:
    snapshot = work / "snapshot"
    snapshot.mkdir()
    for path in paths:
        source = root / path
        if (
            source.is_file()
            and not source.is_symlink()
            and ".." not in Path(path).parts
        ):
            (snapshot / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, snapshot / path)
    return scan(["dir", "."], snapshot, work / "current.json", config, timeout)


def ensure_gitleaks(timeout: float) -> None:
    if shutil.which("gitleaks") is None:
        from tool_setup import PACKAGES, provision_batch

        provision_batch([PACKAGES["gitleaks"] + "@latest"], timeout)


def validate_entries(root: Path, timeout: float = 900.0) -> None:
    """Refuse each root entry that hides a finding a scan run now would not hide; the full check runs it after the tools are installed."""
    if (root / ".gitleaksignore").is_symlink():
        from comments import SWITCH_OFF_HEADER

        raise ValueError(
            f"{SWITCH_OFF_HEADER}\n  .gitleaksignore:1 is a link, which Gitleaks reads and no check can judge; make it a regular file"
        )
    entries = entry_lines(root)
    if not entries:
        return
    ensure_gitleaks(timeout)
    config = [".gitleaks.toml"] if (root / ".gitleaks.toml").is_file() else []
    config = ["--config", str((root / config[0]).resolve())] if config else []
    commits = sorted({m[1] for _, e in entries if (m := COMMIT_ENTRY.fullmatch(e))})
    present = [commit for commit in commits if known(root, commit)]
    refused: list[str] = []
    with tempfile.TemporaryDirectory(prefix="hard-eng-entries-") as temporary:
        work = Path(temporary)
        past = past_findings(root, work, present, config, timeout) if present else set()
        current = current_findings(root, work, config, timeout, entry_paths(entries))
        paths = {item["File"] for item in current} | {
            m[2] for _, e in entries if (m := COMMIT_ENTRY.fullmatch(e))
        }
        names = sorted({m[1] for _, e in entries if (m := CURRENT_ENTRY.fullmatch(e))})
        generated = generated_sources(
            root, sorted(paths | set(names)), generated_only=True
        )
    now = {item["Fingerprint"] for item in current}
    in_tree = {(item["File"], item["RuleID"]) for item in current}
    for number, entry in entries:
        reason = entry_reason(entry, present, past, now, in_tree, generated)
        if reason:
            refused.append(f".gitleaksignore:{number} holds {entry!r}: {reason}")
    if refused:
        from comments import SWITCH_OFF_HEADER

        raise ValueError(
            "\n".join([SWITCH_OFF_HEADER, *(f"  {line}" for line in refused)])
        )


def entry_reason(
    entry: str,
    present: list[str],
    past: set[str],
    now: set[str],
    in_tree: set[tuple[str, str]],
    generated: set[str],
) -> str:
    """Why an entry is refused, or an empty string when it passes."""
    if commit := COMMIT_ENTRY.fullmatch(entry):
        if commit[1] not in present:
            return "the commit is not in this clone: fetch it, or remove the entry"
        if entry not in past:
            return "stale: a scan finds no such finding; remove the entry"
        if commit[2] in generated or (commit[2], commit[3]) not in in_tree:
            return ""
        return "the finding is still in the current tree: fix it there, then keep the entry only for the history"
    if (path := CURRENT_ENTRY.fullmatch(entry)) is None or entry not in now:
        return "stale: a scan finds no such finding; remove the entry"
    if path[1] in generated:
        return ""
    return "the finding is not in a linguist-generated file: fix it at its cause"
