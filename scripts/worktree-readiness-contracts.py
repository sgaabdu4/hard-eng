#!/usr/bin/env python3
"""Focused `.worktreeinclude` and read/write readiness regressions."""

from __future__ import annotations

import importlib.util
import io
import stat
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from typing import NoReturn


ROOT = Path(__file__).resolve().parents[1]
GIT_ENV_SCRIPTS = ROOT / "skills/deterministic-checks/scripts"
if str(GIT_ENV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GIT_ENV_SCRIPTS))

from git_env import scrub_environ

scrub_environ(ceiling=tempfile.gettempdir())


def fail(message: str) -> NoReturn:
    raise SystemExit(f"worktree-readiness-contracts: FAIL: {message}")


def load():
    path = ROOT / "skills/deterministic-checks/scripts/worktree.py"
    spec = importlib.util.spec_from_file_location("worktree_ready", path)
    if spec is None or spec.loader is None:
        fail("worktree.py unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inspect(module, root: Path, intent: str, choice: str | None = None) -> tuple[int, str]:
    output = io.StringIO()
    with redirect_stdout(output):
        result = module.inspect(str(root), intent, choice)
    return result, output.getvalue()


def run(*argv: str) -> None:
    subprocess.run(list(argv), check=True, capture_output=True)


def check_rebase_contract(module, temporary: Path) -> None:
    """A push that is not a fast-forward is the thing rebasing prevents.

    Proven against a local bare remote: the rule is about what the branch is going
    onto, and a file:// remote answers that without a network.
    """
    remote = temporary / "remote.git"
    clone = temporary / "clone"
    other = temporary / "other"
    run("git", "init", "-q", "--bare", "-b", "main", str(remote))
    for repo in (clone, other):
        run("git", "clone", "-q", str(remote), str(repo))
        run("git", "-C", str(repo), "config", "user.name", "Fixture")
        run("git", "-C", str(repo), "config", "user.email", "fixture@example.com")
    (clone / "README.md").write_text("first\n", encoding="utf-8")
    run("git", "-C", str(clone), "add", "README.md")
    run("git", "-C", str(clone), "commit", "-q", "-m", "first")
    run("git", "-C", str(clone), "push", "-q", "-u", "origin", "main")
    if inspect(module, clone, "publish")[0] != 0:
        fail("a branch level with its upstream was rejected for publish")

    (clone / "LOCAL.md").write_text("ahead\n", encoding="utf-8")
    run("git", "-C", str(clone), "add", "LOCAL.md")
    run("git", "-C", str(clone), "commit", "-q", "-m", "ahead")
    if inspect(module, clone, "publish")[0] != 0:
        fail("a branch ahead of its upstream was rejected for publish")

    run("git", "-C", str(other), "fetch", "-q", "origin")
    run("git", "-C", str(other), "checkout", "-q", "-B", "main", "origin/main")
    (other / "REMOTE.md").write_text("second\n", encoding="utf-8")
    run("git", "-C", str(other), "add", "REMOTE.md")
    run("git", "-C", str(other), "commit", "-q", "-m", "second")
    run("git", "-C", str(other), "push", "-q", "origin", "main")
    result, output = inspect(module, clone, "publish")
    if result != 4 or "diverged" not in output or "rebase" not in output:
        fail(f"a branch diverged from its upstream was accepted for publish: {output}")

    run("git", "-C", str(clone), "fetch", "-q", "origin")
    run("git", "-C", str(clone), "rebase", "-q", "origin/main")
    result, output = inspect(module, clone, "publish")
    if result != 0:
        fail(f"a rebased branch was still rejected for publish: {output}")

    run("git", "-C", str(clone), "remote", "remove", "origin")
    result, output = inspect(module, clone, "publish")
    if result != 4 or "no remote" not in output:
        fail("a repository with no remote was accepted for publish")
    run("git", "-C", str(clone), "remote", "add", "origin", str(temporary / "missing.git"))
    result, output = inspect(module, clone, "publish")
    if result != 4 or "unproven" not in output:
        fail("a failed remote fetch was accepted for publish")


def main() -> int:
    module = load()
    with tempfile.TemporaryDirectory(prefix="hard-eng-worktree-") as temporary:
        source = Path(temporary) / "source"
        linked = Path(temporary) / "linked"
        if inspect(module, source, "read")[0] != 4:
            fail("non-Git checkout accepted")
        subprocess.run(["git", "init", "-q", "-b", "main", str(source)], check=True)
        subprocess.run(["git", "-C", str(source), "config", "user.name", "Fixture"], check=True)
        subprocess.run(["git", "-C", str(source), "config", "user.email", "fixture@example.com"], check=True)
        for intent in ("read", "write"):
            result, output = inspect(module, source, intent)
            if result != 0 or "head_sha=UNBORN" not in output:
                fail(f"unborn repository rejected for {intent}")
        if inspect(module, source, "publish")[0] != 4:
            fail("unborn repository accepted for publish")
        (source / ".gitignore").write_text(".env\n.worktree-setup-ran\n", encoding="utf-8")
        (source / ".worktreeinclude").write_text(".env\n", encoding="utf-8")
        (source / ".env").write_text("fixture=true\n", encoding="utf-8")
        (source / "README.md").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(source), "add", ".gitignore", ".worktreeinclude", "README.md"], check=True)
        subprocess.run(["git", "-C", str(source), "commit", "-q", "-m", "fixture"], check=True)
        if inspect(module, source, "read")[0] != 0 or inspect(module, source, "write")[0] != 0:
            fail("clean primary checkout rejected")
        odd = source / "odd\nname.txt"
        odd.write_text("odd\n", encoding="utf-8")
        result, output = inspect(module, source, "read")
        if result != 0 or "dirty_count=1" not in output:
            fail("newline-bearing Git path corrupted dirty-state parsing")
        odd.unlink()
        subprocess.run(
            ["git", "-C", str(source), "config", "core.hooksPath", ".githooks"],
            check=True,
        )
        result, output = inspect(module, source, "write")
        if result != 4 or "post-checkout" not in output:
            fail("repository hook override without worktree provisioning was accepted")
        hook = source / ".githooks/post-checkout"
        hook.parent.mkdir()
        hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        hook.chmod(0o755)
        subprocess.run(["git", "-C", str(source), "add", ".githooks/post-checkout"], check=True)
        subprocess.run(["git", "-C", str(source), "commit", "-q", "-m", "invalid hook"], check=True)
        result, output = inspect(module, source, "write")
        if result != 4 or "global post-checkout dispatcher" not in output:
            fail("no-op repository post-checkout hook was accepted")
        repair_result, repair_output = inspect(module, source, "repair")
        if repair_result != 0 or "repair_issue_" not in repair_output:
            fail("invalid worktree owner could not enter scoped repair")
        (source / "scripts").mkdir(exist_ok=True)
        (source / "scripts/worktree_setup_test.py").write_text(
            "raise SystemExit(0)\n", encoding="utf-8"
        )
        if inspect(module, source, "repair")[0] != 0:
            fail("worktree repair rejected its setup regression owner")
        (source / "scripts/worktree_setup_test.py").unlink()
        (source / "README.md").write_text("out of scope\n", encoding="utf-8")
        result, output = inspect(module, source, "repair")
        if result != 4 or "out-of-scope changes" not in output:
            fail("worktree repair accepted product dirt")
        (source / "README.md").write_text("fixture\n", encoding="utf-8")
        hook.write_text(module.PROJECT_POST_CHECKOUT, encoding="utf-8")
        subprocess.run(["git", "-C", str(source), "add", ".githooks/post-checkout"], check=True)
        subprocess.run(["git", "-C", str(source), "commit", "-q", "-m", "delegating hook"], check=True)
        if inspect(module, source, "write")[0] != 0:
            fail("canonical repository post-checkout delegation was rejected")
        setup = source / "scripts/worktree-setup.sh"
        setup.parent.mkdir(exist_ok=True)
        setup.write_text(
            "#!/bin/sh\n"
            "set -eu\n"
            "printf 'ran\\n' >> .worktree-setup-ran\n",
            encoding="utf-8",
        )
        result, output = inspect(module, source, "write")
        if result != 4 or "tracked regular executable" not in output:
            fail("untracked non-executable worktree setup was accepted")
        setup.chmod(0o755)
        subprocess.run(["git", "-C", str(source), "add", "scripts/worktree-setup.sh"], check=True)
        subprocess.run(["git", "-C", str(source), "commit", "-q", "-m", "setup"], check=True)
        if inspect(module, source, "write")[0] != 0:
            fail("tracked executable worktree setup was rejected")
        (source / ".gitignore").write_text(
            ".env\n.husky/_/\n.worktree-setup-ran\n",
            encoding="utf-8",
        )
        (source / ".worktreeinclude").write_text(".env\n", encoding="utf-8")
        husky_owner = source / ".husky/post-checkout"
        husky_runtime = source / ".husky/_/post-checkout"
        husky_runtime.parent.mkdir(parents=True)
        husky_owner.write_text(module.PROJECT_POST_CHECKOUT, encoding="utf-8")
        husky_runtime.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        husky_owner.chmod(0o755)
        husky_runtime.chmod(0o755)
        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "add",
                ".gitignore",
                ".worktreeinclude",
                ".husky/post-checkout",
            ],
            check=True,
        )
        subprocess.run(["git", "-C", str(source), "commit", "-q", "-m", "husky owner"], check=True)
        subprocess.run(
            ["git", "-C", str(source), "config", "core.hooksPath", ".husky/_"],
            check=True,
        )
        if inspect(module, source, "write")[0] != 0:
            fail("rebuildable hook-manager runtime with canonical tracked owner was rejected")
        (source / ".worktreeinclude").write_text(".env\n.husky/_/*\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(source), "add", ".worktreeinclude"],
            check=True,
        )
        subprocess.run(["git", "-C", str(source), "commit", "-q", "-m", "copied runtime"], check=True)
        result, output = inspect(module, source, "write")
        if result != 4 or "must be rebuilt" not in output:
            fail("copied hook-manager runtime was accepted")
        (source / ".worktreeinclude").write_text(".env\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(source), "add", ".worktreeinclude"],
            check=True,
        )
        subprocess.run(["git", "-C", str(source), "commit", "-q", "-m", "rebuilt runtime"], check=True)
        subprocess.run(
            ["git", "-C", str(source), "config", "core.hooksPath", ".githooks"],
            check=True,
        )
        (source / ".gitignore").write_text(".env\n.worktree-setup-ran\n", encoding="utf-8")
        (source / ".worktreeinclude").write_text(".env\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(source), "add", ".gitignore", ".worktreeinclude"],
            check=True,
        )
        subprocess.run(["git", "-C", str(source), "commit", "-q", "-m", "fixture reset"], check=True)
        (source / "README.md").write_text("dirty\n", encoding="utf-8")
        result, output = inspect(module, source, "write")
        if result != 3 or "choice-required" not in output or inspect(module, source, "write", "current")[0] != 0:
            fail("dirty primary choice contract broken")
        (source / "README.md").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(source), "-c", "core.hooksPath=/dev/null", "worktree", "add", "-q", "--detach", str(linked)], check=True)
        if inspect(module, linked, "read")[0] != 4:
            fail("linked checkout missing included input accepted")
        (linked / ".env").write_text("fixture=true\n", encoding="utf-8")
        (linked / ".env").chmod(0o644)
        if inspect(module, linked, "read")[0] != 0 or inspect(module, linked, "write")[0] != 0:
            fail("ready linked checkout rejected")
        setup_runs = linked / ".worktree-setup-ran"
        if setup_runs.read_text(encoding="utf-8").splitlines() != ["ran"]:
            fail("hookless linked checkout did not run its tracked setup owner exactly once")
        if stat.S_IMODE((linked / ".env").stat().st_mode) != 0o600:
            fail("hookless linked checkout left its included input exposed")
        receipt = module.setup_receipt_path(
            module.git_path(linked, "--git-dir")
        )
        if not receipt.is_file() or stat.S_IMODE(receipt.stat().st_mode) != 0o600:
            fail("hookless linked checkout did not write a private setup receipt")
        if inspect(module, linked, "write")[0] != 0:
            fail("current linked checkout setup receipt was rejected")
        if setup_runs.read_text(encoding="utf-8").splitlines() != ["ran"]:
            fail("current linked checkout reran setup unnecessarily")
        (linked / ".env").chmod(0o644)
        result, output = inspect(module, linked, "write")
        if result != 0 or stat.S_IMODE((linked / ".env").stat().st_mode) != 0o600:
            fail("current receipt did not repair an exposed included input")
        if setup_runs.read_text(encoding="utf-8").splitlines() != ["ran"]:
            fail("permission repair reran current setup unnecessarily")
        (linked / ".worktreeinclude").write_text("*\n", encoding="utf-8")
        if inspect(module, linked, "read")[0] != 4:
            fail("universal include pattern accepted")
        (linked / ".worktreeinclude").write_text(":(glob)**\n", encoding="utf-8")
        if inspect(module, linked, "read")[0] != 4:
            fail("Git pathspec magic accepted")
        (linked / ".worktreeinclude").write_text("README.md\n", encoding="utf-8")
        if inspect(module, linked, "read")[0] != 4:
            fail("tracked include entry accepted")
        subprocess.run(["git", "-C", str(linked), "rm", "-q", "--cached", "-f", ".worktreeinclude"], check=True)
        (linked / ".worktreeinclude").write_text(".env\n", encoding="utf-8")
        if inspect(module, linked, "read")[0] != 4:
            fail("untracked include owner accepted")
        check_rebase_contract(module, Path(temporary))
    print("worktree-readiness-contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
