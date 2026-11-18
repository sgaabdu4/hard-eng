"""A merge goes through ship: the shell hook and the Codex rule file refuse every other route."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import shipping
from conftest import SOURCE, git, init
from test_shipping import (
    _PR_URL,
    FakeGitHub,
    _check,
    _fixture,
    _patch_gh,
    _pull,
)

HOOK = SOURCE / ".hooks/polling.py"
HEAD = "d" * 40


def hook(payload: dict[str, object]) -> str:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def bash(repo: Path, command: str, **extra: object) -> dict[str, object]:
    return {
        "tool_name": "Bash",
        "cwd": str(repo),
        "tool_input": {"command": command, **extra},
    }


def record_ship(repo: Path, number: int, head: str, method: str) -> None:
    folder = repo / ".git/hard-eng/ship"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{number}.json").write_text(
        json.dumps(
            {
                "head": head,
                "method": method,
                "result": "passed",
                "time": "2026-11-17T10:00:00Z",
            }
        )
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    init(root)
    (root / "a.txt").write_text("a\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "first")
    return root


REFUSED = [
    "gh pr merge 12 --rebase",
    "gh pr merge 12 --rebase --match-head-commit " + "e" * 40,
    "gh pr merge --rebase",
    "gh pr merge feature-branch --rebase --match-head-commit " + HEAD,
    "gh pr merge 12 --rebase && echo done",
    "cd /tmp && gh pr merge 12 --rebase",
    "bash -c 'gh pr merge 12 --rebase'",
    "/opt/homebrew/bin/gh pr merge https://github.com/o/r/pull/12 --rebase",
    "gh api -X PUT repos/o/r/pulls/12/merge",
    "gh api --method PUT /repos/o/r/pulls/12/merge -f merge_method=rebase",
    "gh api graphql -f query='mutation { mergePullRequest(input: {pullRequestId: \"x\"}) { clientMutationId } }'",
    "gh -R o/r pr merge 12 --rebase",
    "gh --repo o/r pr merge 12 --rebase",
    "gh pr --repo o/r merge 12 --rebase",
    "gh pr -R o/r merge 12 --rebase",
    "N=12; gh api -X PUT repos/o/r/pulls/$N/merge",
    "gh api graphql -F query=@m.graphql",
    "gh api graphql -F query=@- < m.graphql",
    "gh api graphql -f query=@m.graphql",
    "gh api graphql --input q.json",
    "GH pr merge 12 --rebase",
    "gh pr mer\\\nge 12 --rebase",
    "gh pr mer{g..g}e 12 --rebase",
    "gh pr $'\\x6d'erge 12 --rebase",
    "gh api -X POST repos/o/r/merges -f base=develop -f head=feature",
    "gh api graphql -f query='mutation { mergeBranch(input: {}) { clientMutationId } }'",
    "gh api graphql -f query='mutation { enqueuePullRequest(input: {}) { clientMutationId } }'",
    "gh alias set ship-it 'pr merge' && gh ship-it 12",
    "echo 12 | xargs gh pr merge --rebase",
    "eval 'gh pr merge 12 --rebase'",
    "python3 -c \"import subprocess; subprocess.run(['gh', 'pr', 'merge', '12'])\"",
    "node -e \"require('child_process').execSync('gh pr merge 12')\"",
    "f(){ gh pr merge 12 --rebase; }; f",
    "{ gh pr merge 12 --rebase; }",
    "if true; then gh pr merge 12 --rebase; fi",
    "for n in 12; do gh pr merge $n --rebase; done",
    "! gh pr merge 12 --rebase",
    "G=gh; $G pr merge 12 --rebase",
    "echo 'gh pr merge 12 --rebase' | bash",
    "command gh pr merge 12 --rebase --match-head-commit " + HEAD,
    'sh -c "gh pr merge 12 --rebase"',
    'bash -c "gh pr merge 12 --rebase"',
    "env gh pr merge 12 --rebase --match-head-commit " + HEAD,
    "gh --repo=o/r pr merge 12 --rebase --match-head-commit " + HEAD,
    "gh pr 'me'rge 12 --rebase",
    'gh pr "mer"ge 12 --rebase',
    "g'h' pr merge 12 --rebase",
    "gh pr me\\rge 12 --rebase",
    "bash <<< 'gh pr merge 12 --rebase'",
    "bash -c -- 'gh pr merge 12 --rebase'",
    "echo `gh pr merge 12`",
    "nice gh pr merge 12 --rebase",
    "timeout 60 gh pr merge 12 --rebase",
    "caffeinate -i gh pr merge 12 --rebase",
    "xargs -n1 gh pr merge --rebase < f",
    "echo 12 | xargs -I{} gh pr merge {} --rebase",
    "P=pulls/12/merge; gh api -X PUT repos/o/r/$P",
    "gh alias import merge-aliases.yml",
    "gh pr merge 12 --rebase --admin --match-head-commit " + HEAD,
    "gh pr merge 12 --rebase --auto --match-head-commit " + HEAD,
    "GH_REPO=o/r gh pr merge 12 --rebase --match-head-commit " + HEAD,
    "gh pr merge 12 --rebase --match-head-commit " + HEAD + " && echo ok",
    "gh pr $(echo merge) 12 --rebase",
    "gh pr `echo merge` 12 --rebase",
    "gh $(echo pr) merge 12 --rebase",
    "gh api -X PUT repos/o/r/pulls/12/$(echo merge)",
    "$(which gh) pr merge 12 --rebase",
    "`which gh` pr merge 12 --rebase",
    '"$(which gh)" pr merge 12 --rebase',
    "$(command -v gh) pr merge 12 --rebase",
    "find . -maxdepth 0 -exec gh pr merge 12 --rebase \\;",
    "arch -arm64 gh pr merge 12 --rebase",
    "script -q /dev/null gh pr merge 12 --rebase",
    "git -c alias.x='!gh pr merge 12 --rebase' x",
    "source <(echo gh pr merge 12 --rebase)",
    "alias m='gh pr merge'\nm 12 --rebase",
    "shopt -s expand_aliases; alias m='gh pr merge'\nm 12 --rebase",
    'gh api graphql -f query="$(cat m.graphql)"',
    'gh api graphql -F query="$(<m.graphql)"',
    "Q='mutation{mergePullRequest(x)}'; gh api graphql -f query=\"$Q\"",
    "echo gh pr merge 12",
    "/usr/bin/time gh pr merge 12 --rebase",
    "gh api repos/o/r/pulls/12/$(echo merge) -X PUT",
    'gh api graphql --field=query="$(cat m.graphql)"',
    'gh api graphql -fquery="$(cat m.graphql)"',
    "Q='mutation{mergePullRequest(x)}'; gh api graphql --field=query=\"$Q\"",
    "git config alias.m '!gh pr merge'",
    "git config --global alias.m '!gh pr merge'",
    "git config alias.m '!gh pr merge'; git m 12 --rebase",
    'gh api graphql -f a="x\\"\'" -f query="$Q"',
]
ALLOWED = [
    "gh pr view 12",
    "git merge main",
    'git commit -m "merge notes"',
    "gh api repos/o/r/pulls/12",
    "gh pr view 12 --json mergeStateStatus,mergeCommit",
    'gh pr create --body "Undo: revert the merge commit"',
    'gh pr comment 12 --body "ready to merge"',
    "rg -n 'gh pr merge' .hooks",
    "gh pr checks 12; git merge --ff-only origin/develop",
    "gh run list --branch merge-queue",
    'gh pr view 12 --json "mergeStateStatus"',
    "gh pr merge 12 --rebase --match-head-commit " + HEAD,
    "gh pr merge https://github.com/o/r/pull/12 --rebase --match-head-commit " + HEAD,
    "ls",
    "gh -R o/r pr view 12",
    "gh api graphql -f query='query { viewer { login } }'",
    "python3 -c 'print(1)'",
    "gh alias list",
    "echo 12 | xargs echo",
    'gh pr create --title "Merge the guard" --body-file body.md',
    "gh pr view 12 --json mergeStateStatus,mergeable",
    "grep -rn 'gh pr merge' docs",
    "gh pr list --search 'merge guard'",
    "gh issue create --title 'merge guard misses a form' --body 'see the merge hook'",
    "gh pr edit 12 --body 'Merge with ship'",
    'gh pr create --base develop --head feature/merge-guard --title "x" --body "y"',
    "gh pr view 12 --json title -q .title",
    "gh api repos/o/r/pulls/12 --jq '.mergeable'",
    "gh pr checks 12 --watch=false",
    "git log --oneline | grep -i merge; gh pr view 12",
    "gh pr view 12 > merge.txt",
    "gh run view 123 --log | grep merge",
    'git commit -m "$(cat msg.txt)" && gh pr view 12',
    "gh search prs 'merge' --repo o/r",
    "python3 .hooks/hard-eng.py ship --pr https://github.com/o/r/pull/12 --stage merge",
    'gh run view "$RUN" --log-failed',
    'gh pr view "$PR" --json state',
    'gh release create "v${VERSION}" dist/app.zip --notes-file notes.md',
    'gh api graphql -f query=\'query{repository(owner:"o",name:"r"){pullRequest(number:1){mergeable merged}}}\'',
    'gh pr create --title "Merge guard" --body "$(cat b.md)"',
    "gh api repos/o/r/pulls/12 --jq .merged",
    "man gh",
    "which gh",
    "gh api repos/{owner}/{repo}/pulls/12/comments",
    'gh api "repos/$REPO/pulls/$PR" --jq .body',
    "gh api repos/o/r/pulls/$PR/reviews",
    "gh api graphql -F owner=o -F name=r -f query='query($owner:String!,$name:String!){repository(owner:$owner,name:$name){name}}'",
    "gh api graphql -f query='mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{isResolved}}}' -f id=T1",
    'gh api graphql -f query=\'query($n:Int!){repository(owner:"o",name:"r"){pullRequest(number:$n){title}}}\' -F n=12',
    "gh api repos/{owner}/{repo}/releases",
    "gh api repos/{owner}/{repo}/issues/123/comments -f body='Hi from CLI'",
    'gh api repos/{owner}/{repo}/issues/12/comments -f body="$(cat reply.md)"',
    'gh api -X PATCH repos/{owner}/{repo}/pulls/12 -f body="$BODY"',
    "gh api repos/{owner}/{repo}/pulls/12/comments -f body='Fixed' -F in_reply_to=99",
    'gh api repos/o/r/issues/12/comments -f body="$MSG"',
    'gh api repos/o/r/issues/12/labels -f labels[]="$LABEL"',
]


def denied(output: str) -> bool:
    if not output:
        return False
    decision = json.loads(output)["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    return bool(decision["permissionDecision"] == "deny")


@pytest.mark.parametrize("command", REFUSED)
@pytest.mark.parametrize(
    "extra", [{}, {"run_in_background": True}], ids=["foreground", "background"]
)
@pytest.mark.parametrize("agent", [None, "agent-1"], ids=["main", "subagent"])
def test_direct_merge_needs_a_passed_ship_record(
    repo: Path, command: str, extra: dict[str, object], agent: str | None
) -> None:
    record_ship(repo, 12, HEAD, "rebase")
    payload = bash(repo, command, **extra)
    if agent:
        payload["agent_id"] = agent
    assert denied(hook(payload)), command


@pytest.mark.parametrize("command", ALLOWED)
def test_near_misses_and_a_recorded_merge_stay_allowed(
    repo: Path, command: str
) -> None:
    record_ship(repo, 12, HEAD, "rebase")
    assert not denied(hook(bash(repo, command)))


@pytest.mark.parametrize(
    "command",
    [
        "gh pr view 12",
        "gh api repos/o/r/pulls/12/comments",
        "gh pr create --title x --body-file body.md",
        "gh pr view 12 --json mergeStateStatus,mergeable",
    ],
)
def test_a_gh_command_that_is_not_a_merge_loads_no_module(
    command: str,
) -> None:
    script = (
        "import json, sys; sys.path.insert(0, sys.argv[1]); import polling; "
        "before = set(sys.modules); "
        "polling.decision({'tool_name': 'Bash', 'cwd': '.', "
        "'tool_input': {'command': sys.argv[2]}}); "
        "print(json.dumps(sorted(set(sys.modules) - before)))"
    )
    done = subprocess.run(
        [sys.executable, "-c", script, str(SOURCE / ".hooks"), command],
        capture_output=True,
        text=True,
        check=True,
    )
    loaded = set(json.loads(done.stdout))
    assert {"merge_guard", "shlex", "subprocess", "pathlib"}.isdisjoint(loaded)


def test_a_merge_with_no_record_is_refused_even_with_the_flag(repo: Path) -> None:
    command = "gh pr merge 12 --rebase --match-head-commit " + HEAD
    assert denied(hook(bash(repo, command)))
    record_ship(repo, 12, HEAD, "rebase")
    assert not denied(hook(bash(repo, command)))
    record_ship(repo, 12, "f" * 40, "rebase")
    assert denied(hook(bash(repo, command)))


@pytest.mark.parametrize(
    ("method", "flag"), [("merge", "--merge"), ("squash", "--squash")]
)
def test_release_and_squash_only_merges_stay_possible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repo: Path, method: str, flag: str
) -> None:
    record_ship(repo, 7, HEAD, method)
    allowed = f"gh pr merge 7 {flag} --match-head-commit {HEAD}"
    assert not denied(hook(bash(repo, allowed)))
    other = "--rebase" if method != "rebase" else "--merge"
    assert denied(hook(bash(repo, f"gh pr merge 7 {other} --match-head-commit {HEAD}")))

    (tmp_path / "ship").mkdir()
    fixture = _fixture(tmp_path / "ship")
    fake = FakeGitHub(_pull(fixture, rebaseable=False), [_check(fixture.head)])
    fake.rebase_merge_allowed = False
    fake.squash_merge_allowed = method == "squash"
    fake.merge_commit_allowed = method == "merge"
    _patch_gh(monkeypatch, fake)
    shipment = shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    assert shipment.method == method
    written = json.loads((fixture.root / ".git/hard-eng/ship/1.json").read_text())
    assert written["head"] == fixture.head
    assert written["method"] == method
    assert written["result"] == "passed"


def test_ship_ready_records_a_rebase_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    _patch_gh(monkeypatch, FakeGitHub(_pull(fixture), [_check(fixture.head)]))
    assert (
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready").method == "rebase"
    )
    record = json.loads((fixture.root / ".git/hard-eng/ship/1.json").read_text())
    assert (record["head"], record["method"]) == (fixture.head, "rebase")


HOMES = ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin")


def test_setup_installs_the_codex_merge_rule(tmp_path: Path) -> None:
    import setup

    root = tmp_path / "project"
    init(root)
    changes: dict[str, str] = {}
    setup.configure_hooks(root, changes)
    rules = changes[".codex/rules/hard-eng.rules"]
    patterns = [json.loads(m) for m in re.findall(r"pattern = (\[.*\]),", rules)]
    wanted = [["gh", "pr", "merge"]]
    wanted += [
        [word, "gh", "pr", "merge"] for word in ("env", "command", "xargs", "exec")
    ]
    wanted += [[f"{folder}/gh", "pr", "merge"] for folder in HOMES]
    assert sorted(map(str, patterns)) == sorted(map(str, wanted))
    assert rules.count('decision = "forbidden"') == len(wanted)
    assert rules.count("--stage merge") == len(wanted)


def test_ship_merge_uses_the_recorded_method(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ship_actions

    for method in ("merge", "squash", "rebase"):
        (tmp_path / method).mkdir()
        fixture = _fixture(tmp_path / method)
        shipment = shipping.Shipment(
            root=fixture.root,
            plan=fixture.plan,
            pr_url=_PR_URL,
            repository="acme/widget",
            remote="origin",
            remote_url="https://github.com/acme/widget.git",
            branch="feature/shipping",
            head_sha=fixture.head,
            base="main",
            merged_sha=None,
            delivery_target="Merge",
            method=method,
        )
        calls: list[tuple[str, ...]] = []

        def gh(_root: Path, *args: str, sink: list[tuple[str, ...]] = calls) -> str:
            sink.append(args)
            return ""

        def delivered(
            _root: Path, _plan: Path | None, found: shipping.Shipment, _stage: str
        ) -> shipping.Shipment:
            return found

        monkeypatch.setattr(ship_actions, "gh", gh)
        monkeypatch.setattr(ship_actions, "verify", delivered)
        ship_actions.merge(fixture.root, fixture.plan, shipment, shipment.method)
        assert f"--{method}" in calls[0]
        assert calls[0][-2:] == ("--match-head-commit", fixture.head)


@pytest.mark.parametrize("behind", [0, 3], ids=["current", "three-commits-behind"])
def test_a_release_pull_request_records_a_merge_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, behind: int
) -> None:
    fixture = _fixture(tmp_path)
    git(fixture.root, "branch", "-M", "develop")
    gates = json.loads((fixture.root / "hard-eng.gates.json").read_text())
    gates["shipping"]["base"] = "develop"
    (fixture.root / "hard-eng.gates.json").write_text(json.dumps(gates))
    git(fixture.root, "commit", "-qam", "base is develop")
    head = git(fixture.root, "rev-parse", "HEAD")
    pull = _pull(
        fixture,
        head={"ref": "develop", "sha": head, "repo": {"full_name": "acme/widget"}},
    )
    pull["base"] = {
        "ref": "main",
        "sha": "a" * 40,
        "repo": {"full_name": "acme/widget"},
    }
    fake = FakeGitHub(pull, [_check(head)])
    fake.comparison = {"behind_by": behind}
    _patch_gh(monkeypatch, fake)
    shipment = shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    assert shipment.method == "merge"
    record = json.loads((fixture.root / ".git/hard-eng/ship/1.json").read_text())
    assert (record["head"], record["method"]) == (head, "merge")
