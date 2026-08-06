#!/usr/bin/env python3
"""Regression contract for the shared agent guard hooks.

Proves the guard never stands between an agent and a write it was asked to
make: shell commands are never pre-denied, edits are answered with codebase-map
context instead of a refusal, the git revert net still puts back writes no map
query covered, each runtime's injection dialect is spoken, and the registrars
converge without evicting hook entries owned by anyone else.

The one surviving denial is the ripgrep flag typo, which costs nothing to retry.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "scripts" / "hooks" / "agent-hook.sh"
REGISTRAR = ROOT / "scripts" / "setup" / "agent-hooks.py"
RECEIPTS = ROOT / "receipts" / "agent-hooks.json"
RECEIPT_RUNTIMES = ("claude", "codex", "copilot")
RECEIPT_FIELDS = ("version", "version_command", "command", "observed", "proven_on")
MAP_CLI = "codebase-memory-mcp"
# Fixture repositories must not inherit the caller's git identity or config.
GIT_ENV = dict(
    os.environ,
    GIT_CONFIG_GLOBAL=os.devnull,
    GIT_CONFIG_SYSTEM=os.devnull,
    GIT_AUTHOR_NAME="contract",
    GIT_AUTHOR_EMAIL="contract@example.test",
    GIT_COMMITTER_NAME="contract",
    GIT_COMMITTER_EMAIL="contract@example.test",
)
FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        FAILURES.append(f"{name}: {detail}" if detail else name)


def run_hook(state: Path, runtime: str, event: str, payload: dict) -> dict | None:
    environment = dict(os.environ, HARD_ENG_HOOK_STATE=str(state))
    result = subprocess.run(
        ["bash", str(HOOK), runtime, event],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )
    if result.returncode != 0:
        FAILURES.append(f"hook exited {result.returncode}: {result.stderr.strip()}")
    out = result.stdout.strip()
    return json.loads(out) if out else None


def denial_reason(response: dict | None, runtime: str) -> str | None:
    if response is None:
        return None
    body = response if runtime == "copilot" else response.get("hookSpecificOutput", {})
    if body.get("permissionDecision") != "deny":
        return None
    return body.get("permissionDecisionReason", "")


def git_fixture(root: Path) -> Path:
    repo = root / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / ".git").mkdir()
    (repo / "src" / "owner.py").write_text("value = 1\n", encoding="utf-8")
    (repo / "src" / "other.py").write_text("value = 2\n", encoding="utf-8")
    (repo / "notes.md").write_text("prose\n", encoding="utf-8")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "tool").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    return repo


def check_rg_rule(state: Path) -> None:
    for runtime in ("claude", "codex", "copilot"):
        blocked = denial_reason(
            run_hook(
                state,
                runtime,
                "pretooluse",
                {"tool_name": "Bash", "tool_input": {"command": "rg -rn thing src/"}},
            ),
            runtime,
        )
        check(f"rg rule blocks -rn on {runtime}", blocked is not None)
        check(
            f"rg rule explains itself on {runtime}",
            bool(blocked) and "--replace" in blocked,
            repr(blocked),
        )
    allowed = run_hook(
        state,
        "claude",
        "pretooluse",
        {"tool_name": "Bash", "tool_input": {"command": "rg -n thing src/"}},
    )
    check("rg rule allows -n", allowed is None, repr(allowed))
    wrapped = denial_reason(
        run_hook(
            state,
            "claude",
            "pretooluse",
            {"tool_name": "Bash", "tool_input": {"command": "ls && sudo rg -rl thing"}},
        ),
        "claude",
    )
    check("rg rule reads past wrappers and separators", wrapped is not None)
    unrelated = run_hook(
        state,
        "claude",
        "pretooluse",
        {"tool_name": "Bash", "tool_input": {"command": "grep -rn thing src/"}},
    )
    check("rg rule ignores other commands", unrelated is None, repr(unrelated))


def edit_payload(repo: Path, name: str, tool: str = "Edit") -> dict:
    return {
        "session_id": name,
        "cwd": str(repo),
        "tool_name": tool,
        "tool_input": {"file_path": str(repo / "src" / "owner.py")},
    }


def repository_is_indexed() -> bool:
    """Whether the codebase map knows this repository.

    Injection can only be proved against a project the map actually holds, so the
    positive assertions below are skipped with a note rather than faked.
    """
    if shutil.which(MAP_CLI) is None:
        return False
    try:
        result = subprocess.run(
            [MAP_CLI, "cli", "search_code"],
            input=json.dumps({"project": str(ROOT), "pattern": "def ", "limit": 1}),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            answer = json.loads(line)
        except ValueError:
            continue
        return bool(answer.get("results"))
    return False


def check_impact_rule(state: Path, repo: Path) -> None:
    """An edit is never refused; what the map knows arrives as context instead."""
    fresh = run_hook(state, "claude", "pretooluse", edit_payload(repo, "fresh"))
    check(
        "an uncovered edit is not denied",
        denial_reason(fresh, "claude") is None,
        repr(fresh),
    )

    if not repository_is_indexed():
        print("agent-hook-contract: NOTE: this repository is not indexed; injection not rechecked")
    else:
        live = run_hook(
            state,
            "claude",
            "pretooluse",
            {
                "session_id": "mapped",
                "cwd": str(ROOT),
                "tool_name": "Edit",
                "tool_input": {"file_path": str(Path(__file__).resolve())},
            },
        )
        message = context_message(live)
        check("a mapped edit injects map context", bool(message), repr(live))
        check(
            "the injected context says nothing is blocked",
            "Nothing is blocked" in message,
            repr(message),
        )
        check(
            "the injected context names where the symbols live",
            ".py:" in message,
            repr(message),
        )
        check("injection carries no decision", denial_reason(live, "claude") is None, repr(live))

    exempt = run_hook(
        state,
        "claude",
        "pretooluse",
        {
            "session_id": "fresh",
            "cwd": str(repo),
            "tool_name": "Write",
            "tool_input": {"file_path": str(repo / "notes.md")},
        },
    )
    check("impact rule exempts prose", exempt is None, repr(exempt))

    new_file = run_hook(
        state,
        "claude",
        "pretooluse",
        {
            "session_id": "fresh",
            "cwd": str(repo),
            "tool_name": "Write",
            "tool_input": {"file_path": str(repo / "src" / "brand-new.py")},
        },
    )
    check("impact rule exempts a file with no callers yet", new_file is None, repr(new_file))

    outside = run_hook(
        state,
        "claude",
        "pretooluse",
        {
            "session_id": "fresh",
            "cwd": str(repo.parent),
            "tool_name": "Write",
            "tool_input": {"file_path": str(repo.parent / "loose.py")},
        },
    )
    check("impact rule ignores files outside a repository", outside is None, repr(outside))


def shell_payload(repo: Path, name: str, command: str) -> dict:
    return {
        "session_id": name,
        "cwd": str(repo),
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def check_shell_never_blocked(state: Path, repo: Path) -> None:
    """The guard used to guess a shell command's write targets and deny on a match.

    Guessing cost more than it bought: every read below was denied in practice
    because of one indirection substring, and the retry produced the same denial,
    which is how a session stalls. Nothing here may be pre-denied; a write that
    no map query covered is caught afterwards by the revert net instead.
    """
    commands = {
        # Writes. Real, and deliberately allowed.
        "in-place perl": "perl -0pi -e 's/1/2/' src/owner.py",
        "in-place sed": "sed -i '' 's/1/2/' src/owner.py",
        "truncating redirect": "echo 'def compute(): return 2' > src/owner.py",
        "appending redirect": "printf 'x\\n' >> src/owner.py",
        "tee": "echo x | tee src/owner.py",
        "copy over": "cp /etc/hostname src/owner.py",
        "move over": "mv other.py src/owner.py",
        "inline python write": "python3 -c \"open('src/owner.py','w').write('x')\"",
        "glob in place": "sed -i '' 's/1/2/' src/*.py",
        "piped through xargs": "echo src/owner.py | xargs perl -0pi -e 's/1/2/'",
        "behind eval": "eval \"sed -i '' 's/1/2/' src/owner.py\"",
        "behind substitution": "$(echo sed) -i '' 's/1/2/' src/owner.py",
        "behind backticks": "`echo sed` -i '' 's/1/2/' src/owner.py",
        "redirect inside an interpreter": "bash -c \"echo x > src/owner.py\"",
        "unknown tool": "codemod --write src/owner.py",
        "repository script": "./scripts/tool --write src/owner.py",
        "shell heredoc patch": (
            "apply_patch <<'EOF'\n*** Begin Patch\n"
            "*** Update File: src/owner.py\n*** End Patch\nEOF"
        ),
        "write after cd": f"cd {repo} && perl -0pi -e 's/1/2/' src/owner.py",
        # Reads the old parser denied. These are the reported stalls.
        "ripgrep counting matches": "rg -c 'def test|assert' src/owner.py",
        "ripgrep piped into python": "rg -l thing src | python3 -c 'import sys; print(len(sys.stdin.read()))'",
        "command substitution in a read": "wc -l $(ls src/*.py)",
        "xargs over a read": "ls src | xargs wc -l",
        # Discards with nothing to discard. The guard measures loss, so a clean
        # tree costs nothing; check_discard_guard covers the dirty case.
        "git checkout on a clean tree": "git checkout -- src/owner.py",
        "git restore on a clean tree": "git restore src/owner.py",
        "git checkout switching branch": "git checkout main",
        # Plain reads.
        "cat": "cat src/owner.py",
        "rg": "rg -n compute src",
        "git diff": "git diff src/owner.py",
        "sed print range": "sed -n '1,5p' src/owner.py",
        "head": "head -3 src/owner.py",
        "find without an action": "find src -name '*.py'",
        "running the file": "python3 src/owner.py",
        "package script": "npm test",
    }
    for label, command in commands.items():
        response = run_hook(state, "claude", "pretooluse", shell_payload(repo, "shell", command))
        check(
            f"shell command is not pre-denied: {label}",
            denial_reason(response, "claude") is None,
            f"{command} -> {response!r}",
        )

    # A denial that repeats byte for byte is the stall: the agent has no move left.
    first = run_hook(state, "claude", "pretooluse", shell_payload(repo, "loop", "sed -i '' s/1/2/ src/owner.py"))
    second = run_hook(state, "claude", "pretooluse", shell_payload(repo, "loop", "sed -i '' s/1/2/ src/owner.py"))
    check("a repeated command cannot deny-loop", first is None and second is None, repr((first, second)))


def check_discard_guard(state: Path, root: Path) -> None:
    """A discard is the one write nothing downstream can undo.

    The revert net restores a file by asking git what changed; a discard leaves the
    file matching HEAD, so by the time the net looks there is nothing to see and the
    work is gone. Blocking is the only place this can be caught, and it fires only
    when git confirms real content is at risk.
    """
    repo = live_git_fixture(root, "discard")
    if repo is None:
        print("agent-hook-contract: NOTE: git unavailable, discard guard not checked")
        return
    (repo / "src" / "owner.py").write_text("value = 99\n", encoding="utf-8")

    blocked = {
        "named path": "git checkout -- src/owner.py",
        "restore": "git restore src/owner.py",
        "whole tree": "git checkout .",
        "hard reset": "git reset --hard HEAD",
        "clean": "git clean -fd",
        "stash drop": "git stash drop",
        "behind a wrapper": "cd . && git restore src/owner.py",
        # This one escaped the guard live and really destroyed the file: the paths
        # were resolved against the tool's cwd, not the directory the line cd'd to.
        "after cd into the repository": f"cd {repo} && git restore src/owner.py",
        "after cd into a subdirectory": f"cd {repo}/src && git checkout -- owner.py",
        # Options in front of the subcommand: every one of these read as the
        # subcommand itself until the parser learned to step over them.
        "-C elsewhere": f"git -C {repo} checkout -- src/owner.py",
        "-c config first": "git -c core.pager=cat restore src/owner.py",
        "--git-dir and --work-tree": (
            f"git --git-dir={repo}/.git --work-tree={repo} checkout -- src/owner.py"
        ),
        "a boolean flag first": "git --no-pager restore src/owner.py",
        # Path spellings that reach the same file.
        "absolute path": f"git checkout -- {repo}/src/owner.py",
        "the directory above it": "git restore src",
    }
    for label, command in blocked.items():
        reason = denial_reason(
            run_hook(state, "claude", "pretooluse", shell_payload(repo, f"d-{label}", command)),
            "claude",
        )
        check(
            f"a discard of uncommitted work is refused: {label}",
            reason is not None and "stash" in reason,
            f"{command} -> {reason!r}",
        )

    named = denial_reason(
        run_hook(state, "claude", "pretooluse", shell_payload(repo, "d-msg", "git restore src/owner.py")),
        "claude",
    )
    check(
        "the refusal names the file that would be lost",
        named is not None and "src/owner.py" in named,
        repr(named),
    )

    allowed = {
        "a clean file": "git restore src/other.py",
        "a clean file from elsewhere": f"git -C {repo} restore src/other.py",
        "a clean file after cd": f"cd {repo} && git restore src/other.py",
        "reset without --hard": "git reset HEAD",
        "branch switch": "git checkout main",
        "reading the change": "git diff src/owner.py",
        "keeping the work": "git stash push -m wip",
        # The rebase flow: blocking this was the guard's own false positive.
        "restoring a stash": "git stash pop",
    }
    for label, command in allowed.items():
        reason = denial_reason(
            run_hook(state, "claude", "pretooluse", shell_payload(repo, f"a-{label}", command)),
            "claude",
        )
        check(f"a git call that loses nothing is allowed: {label}", reason is None, f"{command} -> {reason!r}")


def live_git_fixture(root: Path, name: str = "live") -> Path | None:
    """A real repository: the revert net asks git what changed, so a stub .git is useless.

    One per scenario: the net stands down when a second session has been active in
    the same checkout, so scenarios that shared a repository would mask each other.
    """
    repo = root / name
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "owner.py").write_text("value = 1\n", encoding="utf-8")
    (repo / "src" / "other.py").write_text("value = 2\n", encoding="utf-8")
    for extra in ("one", "two", "three", "four"):
        (repo / "src" / f"{extra}.py").write_text("value = 0\n", encoding="utf-8")
    (repo / "notes.md").write_text("prose\n", encoding="utf-8")
    (repo / "src" / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\nbefore")
    for argv in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "base"]):
        result = subprocess.run(
            ["git", "-C", str(repo), *argv],
            capture_output=True,
            text=True,
            env=GIT_ENV,
            timeout=30,
        )
        if result.returncode != 0:
            return None
    return repo


def context_message(response: dict | None) -> str:
    if not isinstance(response, dict):
        return ""
    body = response.get("hookSpecificOutput", response)
    return str(body.get("additionalContext") or "")


def net_cycle(state: Path, repo: Path, session: str, before: object = None) -> str:
    """One command's worth of hook traffic: snapshot, whatever happened, then the net."""
    run_hook(state, "claude", "pretooluse", shell_payload(repo, session, "bash run.sh"))
    if callable(before):
        before()
    response = run_hook(
        state,
        "claude",
        "posttooluse",
        dict(shell_payload(repo, session, "bash run.sh"), tool_response='{"stdout":"done"}'),
    )
    return context_message(response)


def check_revert_net(state: Path, root: Path) -> None:
    """A command can write through a script the guard never parses, so the file is
    compared against git afterwards and put back when no query covered it."""
    for name in ("net", "dirty", "stale", "bulk", "hidden", "merging", "staged", "rescue", "company"):
        repo = live_git_fixture(root, name)
        if repo is None:
            FAILURES.append(f"could not build a git repository for the {name} scenario")
            return
        owner = repo / "src" / "owner.py"

        if name == "net":
            other, notes, fresh = repo / "src" / "other.py", repo / "notes.md", repo / "src" / "new.py"
            shot = repo / "src" / "shot.png"
            run_hook(
                state,
                "claude",
                "posttooluse",
                {
                    "session_id": "net",
                    "cwd": str(repo),
                    "tool_name": "Bash",
                    "tool_input": {"command": "codebase-memory-mcp cli search_graph '{}'"},
                    "tool_response": '{"stdout":"{\\"file_path\\":\\"src/other.py\\"}"}',
                },
            )

            def wrote() -> None:
                owner.write_text("value = 99\n", encoding="utf-8")
                other.write_text("value = 99\n", encoding="utf-8")
                notes.write_text("changed\n", encoding="utf-8")
                fresh.write_text("value = 3\n", encoding="utf-8")
                shot.write_bytes(b"\x89PNG\r\n\x1a\nafter")

            message = net_cycle(state, repo, "net", wrote)
            check("revert net restores an unmapped source file", owner.read_text() == "value = 1\n")
            check("revert net names what it undid", "src/owner.py" in message, repr(message))
            check("revert net keeps a file a query covered", other.read_text() == "value = 99\n")
            check("revert net keeps prose", notes.read_text() == "changed\n")
            check("revert net leaves a new file alone", fresh.exists())
            # An undone screenshot or built asset cannot be regenerated from git.
            check("revert net keeps media it cannot recreate", shot.read_bytes().endswith(b"after"))

        elif name == "dirty":
            # An edit that predates the command is somebody else's, not this one's.
            owner.write_text("value = 7\n", encoding="utf-8")
            net_cycle(state, repo, "dirty", lambda: owner.write_text("value = 8\n", encoding="utf-8"))
            check(
                "revert net leaves edits that predate the command",
                owner.read_text() == "value = 8\n",
            )

        elif name == "stale":
            # Dirty during the command is not proof this command wrote it: an editor
            # autosave or a neighbouring session lands the same way in git status.
            def elsewhere() -> None:
                owner.write_text("value = 21\n", encoding="utf-8")
                old = time.time() - 3600
                os.utime(owner, (old, old))

            net_cycle(state, repo, "stale", elsewhere)
            check(
                "revert net leaves a file this command never wrote",
                owner.read_text() == "value = 21\n",
            )

        elif name == "bulk":
            # A generator or a formatter writes a batch; putting half of one back
            # leaves a tree nobody wrote, and that is worse than the write itself.
            batch = [repo / "src" / f"{stem}.py" for stem in ("one", "two", "three", "four")]

            def generated() -> None:
                for path in batch:
                    path.write_text("value = 5\n", encoding="utf-8")

            message = net_cycle(state, repo, "bulk", generated)
            check(
                "revert net leaves a bulk change in place",
                all(path.read_text() == "value = 5\n" for path in batch),
            )
            check(
                "leaving a bulk change is still reported",
                "src/one.py" in message and "codebase-map" in message,
                repr(message),
            )

        elif name == "hidden":
            # The bypass the pre-check cannot see: a write inside an executed script.
            (repo / "run.sh").write_text("printf 'value = 5\\n' > src/owner.py\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repo), "add", "-A"], env=GIT_ENV, capture_output=True, timeout=30
            )
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
                 "commit", "-qm", "script"],
                env=GIT_ENV,
                capture_output=True,
                timeout=30,
            )
            allowed = run_hook(
                state, "claude", "pretooluse", shell_payload(repo, "hidden", "bash run.sh")
            )
            check("a script write is not pre-blocked", allowed is None, repr(allowed))
            subprocess.run(["bash", "run.sh"], cwd=str(repo), capture_output=True, timeout=30)
            check("the script really wrote the file", owner.read_text() == "value = 5\n")
            after = run_hook(
                state,
                "claude",
                "posttooluse",
                dict(
                    shell_payload(repo, "hidden", "bash run.sh"),
                    tool_response='{"stdout":"done"}',
                ),
            )
            check("revert net undoes a write it never parsed", owner.read_text() == "value = 1\n")
            check(
                "revert net explains the undo",
                "search_code" in context_message(after),
                repr(context_message(after)),
            )

        elif name == "merging":
            # A conflict being resolved is not this command's write, and restoring
            # it would throw away work nobody can reproduce.
            merge_head = repo / ".git" / "MERGE_HEAD"

            def conflict() -> None:
                merge_head.write_text("0" * 40 + "\n", encoding="utf-8")
                owner.write_text("value = 42\n", encoding="utf-8")

            net_cycle(state, repo, "merging", conflict)
            check("revert net stands down mid-merge", owner.read_text() == "value = 42\n")

        elif name == "staged":
            # Another agent staging its own work is not this command's write, and
            # restoring from that same index would help nobody.
            def stage() -> None:
                owner.write_text("value = 11\n", encoding="utf-8")
                subprocess.run(
                    ["git", "-C", str(repo), "add", "src/owner.py"],
                    env=GIT_ENV,
                    capture_output=True,
                    timeout=30,
                )

            message = net_cycle(state, repo, "staged", stage)
            check("revert net leaves staged work alone", owner.read_text() == "value = 11\n")
            check(
                "revert net does not claim staged work",
                "owner.py" not in message,
                repr(message),
            )

        elif name == "company":
            # Two sessions in one checkout: git can say a file changed, never who
            # changed it, so an undo would land on the other session's edit.
            run_hook(
                state,
                "claude",
                "pretooluse",
                edit_payload(repo, "neighbour"),
            )
            message = net_cycle(
                state, repo, "company", lambda: owner.write_text("value = 33\n", encoding="utf-8")
            )
            check(
                "revert net stands down while another session is here",
                owner.read_text() == "value = 33\n",
            )
            check(
                "standing down is still reported",
                "src/owner.py" in message and "another agent session" in message.lower(),
                repr(message),
            )

        else:  # rescue — an undo nobody can undo is worse than the write it undoes.
            message = net_cycle(
                state, repo, "rescue", lambda: owner.write_text("value = 77\n", encoding="utf-8")
            )
            check("revert net restores the file", owner.read_text() == "value = 1\n")
            kept = [
                line.split("kept at ")[1].split(" ")[0]
                for line in message.splitlines()
                if "kept at " in line
            ]
            check("revert net says where the bytes went", bool(kept), repr(message))
            if kept:
                copy = Path(kept[0]) / "src" / "owner.py"
                check(
                    "the discarded bytes are recoverable",
                    copy.is_file() and copy.read_text() == "value = 77\n",
                    str(copy),
                )


def check_clearance(state: Path, repo: Path) -> None:
    """A map result marks the files it named as covered, wherever it was run from.

    Nothing is gated on that mark any more; the revert net reads it to decide
    which writes to put back, so it still has to be recorded and still has to
    expire.
    """
    run_hook(
        state,
        "claude",
        "posttooluse",
        {
            "session_id": "cleared",
            "cwd": str(repo.parent),
            "tool_name": "Bash",
            "tool_input": {"command": "codebase-memory-mcp cli search_code '{}'"},
            "tool_response": '{"stdout":"{\\"file_path\\":\\"src/owner.py\\"}"}',
        },
    )
    recorded = json.loads((state / "cleared.json").read_text(encoding="utf-8"))
    cleared = recorded.get("cleared") or {}
    check("a map result records the file it names", "src/owner.py" in cleared, repr(cleared))
    check(
        "clearance does not spread to unnamed files",
        "src/other.py" not in cleared,
        repr(cleared),
    )
    check(
        "clearance is stamped so it can expire",
        isinstance(cleared.get("src/owner.py"), (int, float)),
        repr(cleared),
    )

    edit = run_hook(state, "claude", "pretooluse", edit_payload(repo, "cleared"))
    check("clearance is not a permission gate", denial_reason(edit, "claude") is None, repr(edit))


def check_dialects(state: Path, repo: Path) -> None:
    """Each runtime hears the same context in its own envelope.

    Proved against this repository because injection needs an indexed project;
    the fixture repo only proves that no runtime is handed a denial.
    """
    for runtime, payload in (
        ("claude", {"session_id": "d", "cwd": str(repo), "tool_name": "Edit",
                    "tool_input": {"file_path": str(repo / "src" / "owner.py")}}),
        ("codex", {"session_id": "d", "cwd": str(repo), "tool_name": "apply_patch",
                   "tool_input": {"input": "*** Begin Patch\n*** Update File: src/owner.py\n"}}),
        ("copilot", {"sessionId": "d", "cwd": str(repo), "toolName": "str_replace",
                     "toolArgs": {"path": "src/owner.py"}}),
    ):
        response = run_hook(state, runtime, "pretooluse", payload)
        check(
            f"{runtime} edits are never denied",
            denial_reason(response, runtime) is None,
            repr(response),
        )

    if not repository_is_indexed():
        print("agent-hook-contract: NOTE: this repository is not indexed; dialects not rechecked")
        return

    here = str(Path(__file__).resolve())
    relative = str(Path(here).relative_to(ROOT))
    claude = run_hook(
        state,
        "claude",
        "pretooluse",
        {"session_id": "dc", "cwd": str(ROOT), "tool_name": "Edit",
         "tool_input": {"file_path": here}},
    )
    check(
        "Claude context is wrapped in hookSpecificOutput",
        isinstance(claude, dict) and "hookSpecificOutput" in claude
        and bool(claude["hookSpecificOutput"].get("additionalContext")),
        repr(claude),
    )
    check(
        "Claude context names the event it answers",
        isinstance(claude, dict)
        and claude.get("hookSpecificOutput", {}).get("hookEventName") == "PreToolUse",
        repr(claude),
    )

    # Codex sends the patch body, not a path: the target is read out of the patch.
    codex = run_hook(
        state,
        "codex",
        "pretooluse",
        {"session_id": "dx", "cwd": str(ROOT), "tool_name": "apply_patch",
         "tool_input": {"input": f"*** Begin Patch\n*** Update File: {relative}\n*** End Patch\n"}},
    )
    check(
        "Codex apply_patch targets are read from the patch body",
        relative in context_message(codex),
        repr(codex),
    )

    # Copilot encodes arguments as a string: JSON for most tools, and the bare
    # patch body for apply_patch. Its envelope is flat.
    encoded = run_hook(
        state,
        "copilot",
        "pretooluse",
        {"sessionId": "dp", "cwd": str(ROOT), "toolName": "str_replace",
         "toolArgs": json.dumps({"path": here})},
    )
    check(
        "Copilot context is flat and its string arguments are decoded",
        isinstance(encoded, dict)
        and "hookSpecificOutput" not in encoded
        and relative in str(encoded.get("additionalContext") or ""),
        repr(encoded),
    )
    patch_body = run_hook(
        state,
        "copilot",
        "pretooluse",
        {"sessionId": "dq", "cwd": str(ROOT), "toolName": "apply_patch",
         "toolArgs": f"*** Begin Patch\n*** Update File: {here}\n*** End Patch\n"},
    )
    check(
        "Copilot bare patch bodies are read",
        relative in str((patch_body or {}).get("additionalContext") or ""),
        repr(patch_body),
    )


def check_resilience(state: Path) -> None:
    for payload in ("not json", "[]", ""):
        result = subprocess.run(
            ["bash", str(HOOK), "claude", "pretooluse"],
            input=payload,
            capture_output=True,
            text=True,
            env=dict(os.environ, HARD_ENG_HOOK_STATE=str(state)),
            timeout=30,
        )
        check(
            f"unusable input {payload!r} allows the call",
            result.returncode == 0 and not result.stdout.strip(),
            result.stdout.strip() or result.stderr.strip(),
        )


def registrar(path: Path, runtime: str, mode: str) -> int:
    return subprocess.run(
        [sys.executable, str(REGISTRAR), runtime, mode],
        capture_output=True,
        text=True,
        env=dict(
            os.environ,
            HARD_ENG_HOOK_COMMAND='bash "/canonical/agent-hook.sh"',
            CODEX_HOOKS=str(path),
            COPILOT_HOOKS=str(path),
        ),
        timeout=30,
    ).returncode


def check_registrars(root: Path) -> None:
    codex = root / "codex-hooks.json"
    foreign = {
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": "bash other.sh session"}]}
            ]
        }
    }
    codex.write_text(json.dumps(foreign), encoding="utf-8")
    check("Codex drift is reported", registrar(codex, "codex", "check") == 5)
    check("Codex converges", registrar(codex, "codex", "install") == 0)
    converged = json.loads(codex.read_text(encoding="utf-8"))
    check(
        "Codex keeps hook entries owned by others",
        converged["hooks"]["SessionStart"] == foreign["hooks"]["SessionStart"],
        json.dumps(converged["hooks"].get("SessionStart")),
    )
    for event in ("PreToolUse", "PostToolUse"):
        check(f"Codex registers {event}", len(converged["hooks"].get(event, [])) == 1)
    check("Codex convergence is idempotent", registrar(codex, "codex", "check") == 0)
    check("Codex install is idempotent", registrar(codex, "codex", "install") == 0)
    check(
        "Codex does not stack duplicates",
        len(json.loads(codex.read_text(encoding="utf-8"))["hooks"]["PreToolUse"]) == 1,
    )

    codex_hook = converged["hooks"]["PreToolUse"][0]["hooks"][0]
    check(
        "Codex names its command and timeout keys",
        codex_hook.get("timeout") == 10 and "agent-hook.sh" in codex_hook.get("command", ""),
        json.dumps(codex_hook),
    )

    copilot = root / "copilot-hooks.json"
    # A hook written under Claude's key names is invisible to Copilot, so a
    # stale entry in that shape must be replaced, not kept alongside.
    copilot.write_text(
        json.dumps(
            {
                "version": 1,
                "hooks": {
                    "preToolUse": [
                        {
                            "type": "command",
                            "command": 'bash "/canonical/agent-hook.sh" copilot pretooluse',
                            "timeout": 10,
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    check("Copilot converges", registrar(copilot, "copilot", "install") == 0)
    written = json.loads(copilot.read_text(encoding="utf-8"))
    check("Copilot declares its schema version", written.get("version") == 1)
    check(
        "Copilot uses camelCase events",
        {"preToolUse", "postToolUse"} <= set(written.get("hooks", {})),
        json.dumps(list(written.get("hooks", {}))),
    )
    for event in ("preToolUse", "postToolUse"):
        entries = written["hooks"][event]
        check(f"Copilot registers one {event} hook", len(entries) == 1, json.dumps(entries))
        hook = entries[0] if entries else {}
        check(
            f"Copilot {event} runs the guard under the bash key",
            "agent-hook.sh" in hook.get("bash", ""),
            json.dumps(hook),
        )
        check(
            f"Copilot {event} states its timeout in seconds",
            hook.get("timeoutSec") == 10 and "timeout" not in hook,
            json.dumps(hook),
        )
        check(
            f"Copilot {event} drops the key Copilot ignores",
            "command" not in hook,
            json.dumps(hook),
        )
    check("Copilot convergence is idempotent", registrar(copilot, "copilot", "check") == 0)


def installed_version(argv: list[str]) -> str | None:
    """First line the runtime itself prints, or None when it is not installed."""
    if shutil.which(argv[0]) is None:
        return None
    # These runtimes fork helpers that outlive the version print, so the probe
    # owns a process group it can reap; a stray descendant fails the bounded runner.
    try:
        process = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            start_new_session=True,
        )
    except OSError:
        return ""
    try:
        out, err = process.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        out, err = "", ""
    finally:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
        process.wait()
    output = (out or err).strip().splitlines()
    return output[0].strip() if output else ""


def check_receipts() -> None:
    """Every runtime the guard claims to block must name the version it was proven on.

    The contract check below only proves the guard's own logic; whether a
    third-party runtime honours a deny is that runtime's behaviour, and it
    changes between releases. A receipt older than the installed release is
    an unproven claim, so it fails here until someone runs the guard live again.
    """
    try:
        receipts = json.loads(RECEIPTS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        FAILURES.append(f"live-run receipts are unreadable: {RECEIPTS}: {error}")
        return
    if not isinstance(receipts, dict):
        FAILURES.append(f"live-run receipts are not a JSON object: {RECEIPTS}")
        return
    for runtime in RECEIPT_RUNTIMES:
        receipt = receipts.get(runtime)
        if not isinstance(receipt, dict):
            FAILURES.append(f"{runtime} has no live-run receipt in {RECEIPTS}")
            continue
        missing = [
            field
            for field in RECEIPT_FIELDS
            if not str(receipt.get(field) or "").strip()
            and not isinstance(receipt.get(field), list)
        ]
        if missing:
            FAILURES.append(f"{runtime} receipt is missing: {', '.join(missing)}")
            continue
        argv = receipt["version_command"]
        if not isinstance(argv, list) or not argv:
            FAILURES.append(f"{runtime} receipt has no version command")
            continue
        found = installed_version([str(item) for item in argv])
        if found is None:
            print(f"agent-hook-contract: NOTE: {runtime} is not installed; receipt not rechecked")
            continue
        if found != receipt["version"]:
            FAILURES.append(
                f"{runtime} guard proof is stale: proven against {receipt['version']!r}, "
                f"installed {found!r}. Run the guard live against the installed release "
                f"and record what it did in {RECEIPTS}."
            )


def main() -> int:
    if not HOOK.exists() or not os.access(HOOK, os.X_OK):
        print(f"agent-hook-contract: FAIL: guard hook is not executable: {HOOK}")
        return 1
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        repo = git_fixture(root)
        state = root / "state"
        check_rg_rule(state)
        check_impact_rule(state, repo)
        check_shell_never_blocked(state, repo)
        check_discard_guard(state, root)
        check_revert_net(state, root)
        check_clearance(state, repo)
        check_dialects(state, repo)
        check_resilience(state)
        check_registrars(root)
    check_receipts()
    if FAILURES:
        for failure in FAILURES:
            print(f"agent-hook-contract: FAIL: {failure}")
        return 1
    print("agent-hook-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
