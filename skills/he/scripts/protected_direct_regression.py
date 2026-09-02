#!/usr/bin/env python3
"""Regression proof: direct-route protected approvals mint and consume deterministically."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "skills/he/scripts"
GIT_ENV_SCRIPTS = ROOT / "skills/deterministic-checks/scripts"
for entry in (SCRIPTS, GIT_ENV_SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from git_env import scrub_environ

scrub_environ(ceiling=tempfile.gettempdir())

EVIDENCE = SCRIPTS / "execution_evidence.py"
KIND = "data-deletion-or-destructive-schema"


def fail(message: str) -> NoReturn:
    raise SystemExit(f"protected-direct-check: {message}")


def load_lib():
    specification = importlib.util.spec_from_file_location("pd_evidence_lib", SCRIPTS / "evidence_lib.py")
    if specification is None or specification.loader is None:
        fail("cannot load evidence_lib.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def run_cli(*arguments: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(EVIDENCE), *arguments], input=stdin, capture_output=True, text=True, check=False
    )


def make_repo(root: Path, slug: str) -> Path:
    repo = root / slug
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    (repo / "owner.txt").write_text("fixture\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@example.invalid", "-c", "user.name=T", "add", "-A"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@example.invalid", "-c", "user.name=T", "commit", "-qm", "init"],
        check=True,
        capture_output=True,
    )
    return repo


def receipt_file(repo: Path) -> Path:
    return repo / ".git" / "hard-eng" / "protected-action.json"


def authorize(repo: Path, digest: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return run_cli(
        "authorize-protected",
        "--repo",
        str(repo),
        "--plan",
        "direct",
        "--kind",
        KIND,
        "--target",
        "fixture stash entry",
        "--effect",
        "permanently drop the fixture stash entry",
        "--tool-name",
        "Bash",
        "--action-digest",
        digest,
        "--approval-reply",
        "yes pls",
        *extra,
    )


def consume(repo: Path, digest: str) -> subprocess.CompletedProcess[str]:
    return run_cli(
        "consume-protected",
        "--repo",
        str(repo),
        "--plan",
        "direct",
        "--kind",
        KIND,
        "--tool-name",
        "Bash",
        "--action-digest",
        digest,
    )


def check_action_digest_recipe(lib) -> str:
    tool_input = {"command": "true", "description": "fixture"}
    result = run_cli("action-digest", "--tool-name", "Bash", stdin=json.dumps(tool_input))
    if result.returncode != 0:
        fail(f"action-digest must succeed on object stdin: {result.stderr}")
    digest = result.stdout.strip()
    if digest != lib.action_digest("Bash", tool_input):
        fail("action-digest output must match evidence_lib.action_digest")
    malformed = run_cli("action-digest", "--tool-name", "Bash", stdin="not json")
    if malformed.returncode == 0:
        fail("action-digest must reject non-JSON stdin")
    return digest


def check_mint_and_single_consume(lib, root: Path) -> None:
    repo = make_repo(root, "mint")
    digest = check_action_digest_recipe(lib)
    empty_reply = authorize(repo, digest)
    assert empty_reply.returncode == 0
    blank = run_cli(
        "authorize-protected",
        "--repo",
        str(repo),
        "--plan",
        "direct",
        "--kind",
        KIND,
        "--target",
        "t",
        "--effect",
        "e",
        "--tool-name",
        "Bash",
        "--action-digest",
        digest,
        "--approval-reply",
        "   ",
    )
    if blank.returncode == 0 or "literal approval reply" not in blank.stderr:
        fail(f"blank approval reply must be rejected: {blank.stderr}")
    if not receipt_file(repo).is_file():
        fail("direct authorization must land in the Git-private store without any PLAN or direct receipt")
    if (repo / "features").exists() or (repo / "research.json").exists():
        fail("direct authorization fixture must stay free of lifecycle files")
    first = consume(repo, digest)
    if first.returncode != 0 or "protected-action-consume: PASS" not in first.stdout:
        fail(f"exact consume must pass: {first.stderr}")
    if receipt_file(repo).exists():
        fail("consume must remove the one-use authorization")
    second = consume(repo, digest)
    if second.returncode == 0:
        fail("second consume must fail after the receipt is consumed")


def check_binding_rejections(root: Path) -> None:
    repo = make_repo(root, "binding")
    digest = "sha256:" + "b" * 64
    assert authorize(repo, digest).returncode == 0
    wrong_action = consume(repo, "sha256:" + "c" * 64)
    if wrong_action.returncode == 0:
        fail("changed action digest must be rejected")
    wrong_kind = run_cli(
        "consume-protected",
        "--repo",
        str(repo),
        "--plan",
        "direct",
        "--kind",
        "force-or-history-rewrite",
        "--tool-name",
        "Bash",
        "--action-digest",
        digest,
    )
    if wrong_kind.returncode == 0:
        fail("changed approval kind must be rejected")
    wrong_tool = run_cli(
        "consume-protected",
        "--repo",
        str(repo),
        "--plan",
        "direct",
        "--kind",
        KIND,
        "--tool-name",
        "Read",
        "--action-digest",
        digest,
    )
    if wrong_tool.returncode == 0:
        fail("changed tool name must be rejected")
    survivor = consume(repo, digest)
    if survivor.returncode != 0:
        fail(f"a receipt must survive rejected consume attempts against it: {survivor.stderr}")

    forgeable = "sha256:" + "e" * 64
    assert authorize(repo, forgeable).returncode == 0
    path = receipt_file(repo)
    value = json.loads(path.read_text(encoding="utf-8"))
    value["target"] = "forged target"
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    forged = consume(repo, forgeable)
    if forged.returncode == 0:
        fail("field tampering must break the binding digest")


def check_reauthorize_after_consume(root: Path) -> None:
    repo = make_repo(root, "reauthorize")
    digest = "sha256:" + "9" * 64
    if authorize(repo, digest).returncode != 0:
        fail("initial authorize must succeed")
    if consume(repo, digest).returncode != 0:
        fail("initial consume must succeed")
    reauthorized = authorize(repo, digest)
    if reauthorized.returncode != 0:
        fail(f"re-authorizing from the same reply after a consumed receipt must succeed: {reauthorized.stderr}")
    reconsumed = consume(repo, digest)
    if reconsumed.returncode != 0:
        fail(f"consuming a re-authorized receipt must succeed: {reconsumed.stderr}")


def main() -> int:
    lib = load_lib()
    with tempfile.TemporaryDirectory(prefix="protected-direct-") as scratch:
        root = Path(scratch)
        check_mint_and_single_consume(lib, root)
        check_binding_rejections(root)
        check_reauthorize_after_consume(root)
    print("protected-direct-check: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
