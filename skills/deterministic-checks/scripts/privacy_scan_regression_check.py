#!/usr/bin/env python3
"""Regression proof: privacy_scan.py catches home paths, off-allowlist emails, and denylist words without leaking them."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "skills/deterministic-checks/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from git_env import scrub_environ
from regression_fixture import checker, git
from script_runner import ScriptResult, run_script

scrub_environ(ceiling=tempfile.gettempdir())

SCAN_SCRIPT = SCRIPTS / "privacy_scan.py"
DENY_ENV = "HARD_ENG_PRIVACY_DENYLIST"


fail, require = checker("privacy-scan-check")


def scan(repo: Path, *args: str) -> ScriptResult:
    inherited = {key: value for key, value in os.environ.items() if key != DENY_ENV}
    return run_script(SCAN_SCRIPT, ["--repo", str(repo), *args], cwd=repo, env=inherited)


def make_repo(base: Path) -> Path:
    repo = base / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("hello world\n", encoding="utf-8")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    return repo


def check_clean_tree_passes(repo: Path) -> None:
    result = scan(repo)
    require(result.returncode == 0, f"a clean tree passes: {result.output}")
    require("privacy: PASS" in result.output, f"clean tree prints PASS: {result.output}")


def commit_file(repo: Path, name: str, text: str) -> None:
    (repo / name).write_text(text, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", name)


def check_home_paths(repo: Path) -> None:
    commit_file(repo, "notes-bad.txt", "config at " + "/Users/" + "someone" + "/project\n")
    bad = scan(repo)
    require(bad.returncode == 1, f"a non-allowlisted home path fails: {bad.output}")
    require("home-path" in bad.output, f"finding is labeled home-path: {bad.output}")
    git(repo, "rm", "-q", "notes-bad.txt")
    git(repo, "commit", "-q", "-m", "remove bad home path")
    commit_file(repo, "notes-good.txt", "config at /home/example/project\n")
    good = scan(repo)
    require(good.returncode == 0, f"/home/example/ passes: {good.output}")
    git(repo, "rm", "-q", "notes-good.txt")
    git(repo, "commit", "-q", "-m", "remove good home path")


def check_emails(repo: Path) -> None:
    commit_file(repo, "contacts.txt", "person" + "@" + "corp.example.net\n")
    bad = scan(repo)
    require(bad.returncode == 1, f"a non-allowlisted domain fails: {bad.output}")
    require("email" in bad.output, f"finding is labeled email: {bad.output}")
    git(repo, "rm", "-q", "contacts.txt")
    git(repo, "commit", "-q", "-m", "remove bad email")
    commit_file(repo, "allowed.txt", "fixture@example.invalid\n41898282+github-actions[bot]@users.noreply.github.com\n")
    good = scan(repo)
    require(good.returncode == 0, f"allowlisted domains pass: {good.output}")
    git(repo, "rm", "-q", "allowed.txt")
    git(repo, "commit", "-q", "-m", "remove allowed emails")


def check_git_private_denylist(repo: Path) -> None:
    deny_dir = repo / ".git" / "hard-eng"
    deny_dir.mkdir(parents=True)
    (deny_dir / "privacy-denylist.txt").write_text("# comment\nsecretword\n", encoding="utf-8")
    commit_file(repo, "leak.txt", "this line has SecretWord in it\n")
    result = scan(repo)
    require(result.returncode == 1, f"a denylist word fails: {result.output}")
    require("denylist word #" in result.output, f"finding names a denylist slot: {result.output}")
    require("secretword" not in result.output.lower(), f"the denylist word never leaks: {result.output}")
    git(repo, "rm", "-q", "leak.txt")
    git(repo, "commit", "-q", "-m", "remove denylist leak")
    (deny_dir / "privacy-denylist.txt").unlink()
    deny_dir.rmdir()


def check_env_denylist(repo: Path) -> None:
    commit_file(repo, "leak-env.txt", "this line has ENVWORD present\n")
    inherited = {key: value for key, value in os.environ.items() if key != DENY_ENV}
    result = run_script(SCAN_SCRIPT, ["--repo", str(repo)], cwd=repo, env={**inherited, DENY_ENV: "otherword,envword"})
    require(result.returncode == 1, f"the env denylist catches a hit: {result.output}")
    require("envword" not in result.output.lower(), f"the env denylist word never leaks: {result.output}")
    clean = run_script(SCAN_SCRIPT, ["--repo", str(repo)], cwd=repo, env=inherited)
    require(clean.returncode == 0, f"without the env var the same line passes: {clean.output}")
    git(repo, "rm", "-q", "leak-env.txt")
    git(repo, "commit", "-q", "-m", "remove env denylist leak")


def check_staged_uncommitted(repo: Path) -> None:
    path = repo / "staged-only.txt"
    path.write_text("reachable at " + "/Users/" + "nobody" + "/work\n", encoding="utf-8")
    git(repo, "add", "staged-only.txt")
    path.write_text("reachable at /home/example/work\n", encoding="utf-8")
    unstaged_mode = scan(repo)
    require(unstaged_mode.returncode == 0, f"a plain scan reads the clean working tree copy: {unstaged_mode.output}")
    staged_mode = scan(repo, "--staged")
    require(staged_mode.returncode == 1, f"--staged catches a staged-but-uncommitted hit: {staged_mode.output}")
    require("home-path" in staged_mode.output, f"the staged finding is labeled home-path: {staged_mode.output}")
    git(repo, "reset", "-q", "HEAD", "--", "staged-only.txt")
    path.unlink()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="privacy-scan-check-") as directory:
        repo = make_repo(Path(directory).resolve())
        check_clean_tree_passes(repo)
        check_home_paths(repo)
        check_emails(repo)
        check_git_private_denylist(repo)
        check_env_denylist(repo)
        check_staged_uncommitted(repo)
    print("privacy-scan regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
