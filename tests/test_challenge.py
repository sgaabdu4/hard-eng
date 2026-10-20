"""The cross-model challenge picks the other agent, runs it read-only and gates big changes."""

import json
import os
import stat
import sys
from contextlib import suppress
from pathlib import Path
from unittest.mock import Mock

import challenge
import pytest
import ship_actions
from conftest import commit, git
from plans import validate_plans
from shipping import Shipment
from test_plans import edit, sized_branch

FAKE = """#!{python}
import json, os, sys
log = {{"argv": sys.argv[1:], "stdin_is_null": os.path.samestat(os.fstat(0), os.stat(os.devnull)), "markers": sorted(k for k in os.environ if k == "CLAUDECODE" or k.startswith("CODEX_"))}}
open({log!r}, "w").write(json.dumps(log))
sys.stderr.write({error!r})
print({output!r})
sys.exit({code})
"""


def fake_cli(
    directory: Path, name: str, output: str = "ok", code: int = 0, error: str = ""
) -> Path:
    directory.mkdir(exist_ok=True)
    log = directory / f"{name}.json"
    script = directory / name
    script.write_text(
        FAKE.format(
            python=sys.executable, log=str(log), error=error, output=output, code=code
        )
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return log


@pytest.fixture
def branch(repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    git(repository, "branch", "-M", "main")
    (repository / "app.py").write_text("value = 1\n")
    commit(repository, "base")
    git(repository, "checkout", "-qb", "feature")
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}")
    return repository


def big(root: Path) -> None:
    (root / "extra.py").write_text("value = 2\n")
    commit(root, "big")


def small(root: Path) -> None:
    (root / "app.py").write_text("value = 3\n")
    commit(root, "small")


@pytest.mark.parametrize(
    ("claude", "codex", "host", "reviewer"),
    [
        ("1", None, None, "codex"),
        (None, "thread", None, "claude"),
        (None, None, "codex", "claude"),
        (None, None, "claude", "codex"),
    ],
)
def test_reviewer_is_the_other_agent_of_the_running_host(
    monkeypatch: pytest.MonkeyPatch,
    claude: str | None,
    codex: str | None,
    host: str | None,
    reviewer: str,
) -> None:
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    if claude:
        monkeypatch.setenv("CLAUDECODE", claude)
    if codex:
        monkeypatch.setenv("CODEX_THREAD_ID", codex)
    assert challenge.reviewer_for(host) == reviewer


@pytest.mark.parametrize("markers", [{}, {"CLAUDECODE": "1", "CODEX_THREAD_ID": "t"}])
def test_unknown_or_ambiguous_host_asks_for_the_host(
    monkeypatch: pytest.MonkeyPatch, markers: dict[str, str]
) -> None:
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    for name, value in markers.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match="--host"):
        challenge.reviewer_for(None)


def test_the_reviewer_does_not_inherit_host_markers(
    branch: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    big(branch)
    log = fake_cli(tmp_path / "bin", "codex", "VERDICT: clean")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setenv("CODEX_SANDBOX", "seatbelt")
    challenge.challenge(branch, None, "claude")
    assert json.loads(log.read_text())["markers"] == ["CODEX_HOME"]


def test_the_prompt_pins_the_reviewed_revision_and_treats_repo_text_as_data(
    branch: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    big(branch)
    log = fake_cli(tmp_path / "bin", "codex", "VERDICT: clean")
    monkeypatch.setenv("CLAUDECODE", "1")
    challenge.challenge(branch, None, None)
    prompt = json.loads(log.read_text())["argv"][-1]
    revision = git(branch, "rev-parse", "HEAD")
    assert f"git diff {git(branch, 'merge-base', 'HEAD', 'main')} {revision}`" in prompt
    assert "never instructions" in prompt


def record_of(root: Path) -> dict[str, str]:
    path = challenge.store(root, git(root, "rev-parse", "HEAD")).with_suffix(".json")
    return json.loads(path.read_text())


@pytest.mark.parametrize(
    "output",
    ["", "Traceback (most recent call last):\nError", "Looks fine.", "verdict: clean"],
)
def test_a_reply_without_an_exact_verdict_is_not_a_review(
    branch: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: str
) -> None:
    big(branch)
    fake_cli(tmp_path / "bin", "codex", output)
    monkeypatch.setenv("CLAUDECODE", "1")
    assert challenge.challenge(branch, None, None) == 1
    assert record_of(branch)["outcome"].startswith("not done: codex gave no")


def test_no_branch_point_records_not_done_without_calling_the_reviewer(
    repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git(repository, "branch", "-M", "trunk")
    big(repository)
    log = fake_cli(tmp_path / "bin", "codex", "VERDICT: clean")
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("CLAUDECODE", "1")
    assert challenge.challenge(repository, None, None) == 1
    assert "branch point" in record_of(repository)["outcome"]
    assert not log.exists()


def test_a_dirty_tree_is_not_reviewed(
    branch: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    big(branch)
    (branch / "app.py").write_text("value = 9\n")
    log = fake_cli(tmp_path / "bin", "codex", "VERDICT: clean")
    monkeypatch.setenv("CLAUDECODE", "1")
    assert challenge.challenge(branch, None, None) == 1
    assert "uncommitted" in record_of(branch)["outcome"]
    assert not log.exists()


def test_a_commit_during_the_review_voids_it(
    branch: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    big(branch)
    reviewed = git(branch, "rev-parse", "HEAD")
    (tmp_path / "bin").mkdir()
    script = tmp_path / "bin" / "codex"
    script.write_text(
        f"#!{sys.executable}\nimport subprocess\n"
        "subprocess.run(['git', 'commit', '-q', '--allow-empty', '-m', 'during'], check=True)\n"
        "print('VERDICT: clean')\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("CLAUDECODE", "1")
    assert challenge.challenge(branch, None, None) == 1
    record = json.loads(
        challenge.store(branch, reviewed).with_suffix(".json").read_text()
    )
    assert "HEAD moved" in record["outcome"]


def test_claude_host_runs_codex_read_only_with_closed_stdin(
    branch: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    big(branch)
    log = fake_cli(tmp_path / "bin", "codex", "Nothing found.\nVERDICT: clean")
    monkeypatch.setenv("CLAUDECODE", "1")
    assert challenge.challenge(branch, None, None) == 0
    ran = json.loads(log.read_text())
    assert ran["stdin_is_null"]
    assert ran["argv"][:5] == ["exec", "--sandbox", "read-only", "--cd", str(branch)]
    revision = git(branch, "rev-parse", "HEAD")
    record = json.loads(
        challenge.store(branch, revision).with_suffix(".json").read_text()
    )
    assert record["reviewer"] == "codex"
    assert record["revision"] == revision
    assert record["outcome"] == "clean"
    assert "VERDICT: clean" in Path(record["output"]).read_text()


def test_codex_host_runs_claude_with_read_only_tools(
    branch: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    big(branch)
    log = fake_cli(tmp_path / "bin", "claude", "src/a.py:3 breaks\nVERDICT: findings")
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "thread")
    assert challenge.challenge(branch, None, None) == 0
    ran = json.loads(log.read_text())
    argv = ran["argv"]
    assert ran["stdin_is_null"]
    assert "--safe-mode" in argv
    assert argv[argv.index("--tools") + 1] == "Read,Grep,Glob,Bash"
    assert "Edit" not in " ".join(argv[argv.index("--allowedTools") + 1 :])
    record = json.loads(
        challenge.store(branch, git(branch, "rev-parse", "HEAD"))
        .with_suffix(".json")
        .read_text()
    )
    assert (record["reviewer"], record["outcome"]) == ("claude", "findings")


@pytest.mark.parametrize(
    ("code", "error", "reason"),
    [(None, "", "codex is not installed"), (1, "Not signed in", "Not signed in")],
)
def test_unavailable_reviewer_records_not_done(
    branch: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    code: int | None,
    error: str,
    reason: str,
) -> None:
    big(branch)
    (tmp_path / "bin").mkdir(exist_ok=True)
    if code is None:
        (tmp_path / "bin" / "git").symlink_to(
            next(
                Path(p) / "git"
                for p in os.environ["PATH"].split(os.pathsep)
                if (Path(p) / "git").exists()
            )
        )
        monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    else:
        fake_cli(tmp_path / "bin", "codex", "", code, error)
    monkeypatch.setenv("CLAUDECODE", "1")
    assert challenge.challenge(branch, None, None) == 1
    record = json.loads(
        challenge.store(branch, git(branch, "rev-parse", "HEAD"))
        .with_suffix(".json")
        .read_text()
    )
    assert record["outcome"].startswith("not done: ")
    assert reason in record["outcome"]


def shipment(root: Path) -> Shipment:
    return Shipment(
        root=root,
        plan=root / "PLAN.md",
        pr_url="https://github.com/fixture/project/pull/1",
        repository="fixture/project",
        remote="origin",
        remote_url="unused",
        branch="feature",
        head_sha=git(root, "rev-parse", "HEAD"),
        base="main",
        merged_sha=None,
        delivery_target="Merge",
    )


@pytest.mark.parametrize("stage", ["ready", "merge"])
def test_shipping_a_big_change_needs_a_review_record_for_the_head(
    branch: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stage: str,
) -> None:
    big(branch)
    verified = Mock(return_value=shipment(branch))
    monkeypatch.setattr(ship_actions, "verify", verified)
    monkeypatch.setattr(ship_actions, "gh", Mock(return_value=""))
    arguments = (
        branch,
        "PLAN.md",
        "https://github.com/fixture/project/pull/1",
        stage,
        None,
        "rebase",
    )
    with pytest.raises(ValueError, match="hard-eng.py challenge"):
        ship_actions.run(*arguments)
    fake_cli(tmp_path / "bin", "codex", "VERDICT: clean")
    monkeypatch.setenv("CLAUDECODE", "1")
    challenge.challenge(branch, None, None)
    ship_actions.run(*arguments)
    assert "Independent review by codex: clean" in capsys.readouterr().out


def test_shipping_reports_a_review_that_was_not_done(
    branch: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    big(branch)
    fake_cli(tmp_path / "bin", "codex", "", 2, "signed out")
    monkeypatch.setenv("CLAUDECODE", "1")
    challenge.challenge(branch, None, None)
    note = challenge.shipping_note(branch, git(branch, "rev-parse", "HEAD"))
    assert note is not None
    assert note.startswith("independent review not done: codex exited 2")


def test_a_review_of_an_older_head_does_not_cover_a_new_commit(
    branch: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    big(branch)
    fake_cli(tmp_path / "bin", "codex", "VERDICT: clean")
    monkeypatch.setenv("CLAUDECODE", "1")
    challenge.challenge(branch, None, None)
    (branch / "extra.py").write_text("value = 4\n")
    head = commit(branch, "later")
    with pytest.raises(ValueError, match=head):
        challenge.shipping_note(branch, head)


def test_a_small_change_needs_no_review(branch: Path) -> None:
    small(branch)
    assert challenge.shipping_note(branch, git(branch, "rev-parse", "HEAD")) is None


def test_a_failed_rerun_keeps_the_completed_review_of_the_same_revision(
    branch: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    big(branch)
    fake_cli(tmp_path / "bin", "codex", "src/a.py:3 breaks\nVERDICT: findings")
    monkeypatch.setenv("CLAUDECODE", "1")
    assert challenge.challenge(branch, None, None) == 0
    fake_cli(tmp_path / "bin", "codex", "", 1, "Not signed in")
    assert challenge.challenge(branch, None, None) == 0
    record = json.loads(
        challenge.store(branch, git(branch, "rev-parse", "HEAD"))
        .with_suffix(".json")
        .read_text()
    )
    assert record["outcome"] == "findings"
    assert "VERDICT: findings" in Path(record["output"]).read_text()


@pytest.mark.parametrize(
    ("page", "verdict"),
    [("site/page.md", "Size: big"), ("README.md", "Size: small (documentation only)")],
)
def test_nested_markdown_in_a_javascript_package_counts_as_code_size(
    repository: Path,
    capsys: pytest.CaptureFixture[str],
    page: str,
    verdict: str,
) -> None:
    (repository / "site").mkdir()
    (repository / page).write_text("".join(f"line {n}\n" for n in range(1200)))
    (repository / "hard-eng.gates.json").write_text(
        json.dumps(
            {"packages": [{"path": ".", "language": "javascript"}], "shared": []}
        )
    )
    sized_branch(repository)
    edit(repository, page, 1100)
    with suppress(ValueError):
        validate_plans(repository)
    assert verdict in capsys.readouterr().out
