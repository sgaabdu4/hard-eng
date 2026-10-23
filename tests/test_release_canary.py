"""`release_canary.py`: which releases need a try on installed projects, and what it publishes."""

import fcntl
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import yaml
from gate_config import validate_documents

import release_canary


def test_only_changes_to_installed_files_need_a_canary_run() -> None:
    assert not release_canary.needs_canary(
        ["README.md", "release_canary.py", "features/x/PLAN.md", "docs/a.md"]
    )
    for installed in (
        ".hooks/update.py",
        "setup.py",
        "AGENTS.md",
        ".agents/skill-sources/building-flutter-apps",
        ".github/workflows/hard-eng.yml",
    ):
        assert release_canary.needs_canary(["README.md", installed])


def test_published_status_names_no_project() -> None:
    """The source repository is public; most installed projects are private."""
    results = {
        "owner/private-app": (True, "update and check passed"),
        "owner/other-app": (False, "check failed; log /cache/owner__other-app.log"),
    }
    text = release_canary.status_text(results)
    assert text == "1 of 2 canary runs passed"
    assert "owner" not in text


def full_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, projects: list[str]
) -> list[tuple[str, str]]:
    """A posting run of a release that changes an installed file; returns each status."""
    monkeypatch.setattr(release_canary, "LOCK", tmp_path / "canary.lock")
    monkeypatch.setattr(release_canary, "CACHE", tmp_path / "cache")
    posted: list[tuple[str, str]] = []
    replies = {"rev-parse": "a" * 40, "diff": ".hooks/update.py"}

    def output(command: list[str], cwd: Path = release_canary.SOURCE) -> str:
        return replies.get(command[1], "")

    def installed_projects(_: object) -> list[str]:
        return projects

    def post_status(revision: str, state: str, description: str) -> None:
        posted.append((state, description))

    monkeypatch.setattr(release_canary, "output", output)
    monkeypatch.setattr(release_canary, "repositories", list)
    monkeypatch.setattr(release_canary, "public_text", str)
    monkeypatch.setattr(release_canary, "installed_projects", installed_projects)
    monkeypatch.setattr(release_canary, "post_status", post_status)
    monkeypatch.setattr(sys, "argv", ["release_canary.py", "HEAD", "--post-status"])
    assert release_canary.main() == 1
    return posted


def test_a_run_that_finds_no_project_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty search must not certify a release."""
    posted = full_run(tmp_path, monkeypatch, [])
    assert [state for state, _ in posted] == ["pending", "failure"]


def test_a_step_past_its_limit_stops_every_process_it_started(tmp_path: Path) -> None:
    """Hung tests and installers must not outlive the step."""
    pid_file = tmp_path / "child.pid"
    spawn = (
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "open(sys.argv[1], 'w').write(str(child.pid))\n"
        "time.sleep(60)\n"
    )
    with (tmp_path / "step.log").open("w") as log:
        command = [sys.executable, "-c", spawn, str(pid_file)]
        assert not release_canary.step(command, tmp_path, log, 2)
    child = pid_file.read_text()
    time.sleep(0.5)
    # A killed orphan stays a zombie where the container's first process never reaps it.
    state = subprocess.run(
        ["ps", "-o", "stat=", "-p", child], check=False, capture_output=True, text=True
    )
    assert state.stdout.strip() in {"", "Z"}


def test_projects_with_dotted_names_keep_their_own_log_and_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cloned: list[str] = []

    def step(command: list[str], cwd: Path, log: object, limit: int) -> bool:
        cloned.append(command[-1])
        return False

    monkeypatch.setattr(release_canary, "step", step)
    messages = []
    for name in ("owner/app.api", "owner/app.web", "owner/app.log"):
        trial = release_canary.Trial(("installed", name), tmp_path, ())
        assert trial.prepare("a" * 40, tmp_path) == []
        messages.append(trial.results[f"installed {name}"][1])
    logs = [message.rsplit("log ", 1)[1] for message in messages]
    assert len(set(logs)) == 3
    assert not set(logs) & set(cloned)


def test_an_install_without_the_update_runner_uses_its_older_entry_point(
    tmp_path: Path,
) -> None:
    hooks = tmp_path / ".hooks"
    hooks.mkdir()
    (hooks / "update.py").write_text(
        "def latest_verified(previous):\n    return None\n\n\n"
        "def update(root):\n    return f'updated to {latest_verified(None)}'\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", release_canary.UPDATE, "a" * 40],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout == f"updated to {'a' * 40}\n"


def test_a_second_run_waits_and_keeps_the_active_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Parallel agents must not delete each other's checkouts and logs."""
    active = tmp_path / "cache/run-active/project.log"
    active.parent.mkdir(parents=True)
    active.write_text("running\n")
    lock = tmp_path / "canary.lock"
    monkeypatch.setattr(release_canary, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(release_canary, "LOCK", lock)
    monkeypatch.setattr(sys, "argv", ["release_canary.py", "HEAD"])
    with lock.open("a") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX)
        assert release_canary.main() == 1
    assert active.read_text() == "running\n"


def test_a_release_that_names_a_private_project_fails_without_publishing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The source repository is public; private project names must not reach it."""
    monkeypatch.setattr(release_canary, "LOCK", tmp_path / "canary.lock")
    posted: list[str] = []
    found = [("owner/secret-app", True, False), ("owner/open-tool", False, False)]

    def output(command: list[str], cwd: Path = release_canary.SOURCE) -> str:
        return "a" * 40

    def post_status(revision: str, state: str, description: str) -> None:
        posted.append(description)

    monkeypatch.setattr(release_canary, "output", output)
    monkeypatch.setattr(release_canary, "repositories", lambda: found)
    monkeypatch.setattr(release_canary, "public_text", "Seen in secret-app {}.".format)
    monkeypatch.setattr(release_canary, "post_status", post_status)
    monkeypatch.setattr(sys, "argv", ["release_canary.py", "HEAD", "--post-status"])
    assert release_canary.main() == 1
    assert posted == ["The release names a private project"]


def test_only_whole_private_names_count_as_leaks() -> None:
    private = ["owner/secret-app"]
    for text in ("see owner/secret-app", "in secret-app.", "SECRET-APP fails"):
        assert release_canary.leaked_names(text, private), text
    for text in ("secret-apps", "my-secret-app", "secret-app.py", "x/secret-app/y"):
        assert not release_canary.leaked_names(text, private), text


def test_a_cut_github_reply_is_retried_before_reading_release_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GitHub sometimes cuts a reply short; one cut reply must not stop a full run."""
    failed: set[str] = set()

    def output(command: list[str], cwd: Path = release_canary.SOURCE) -> str:
        if command[0] == "gh":
            if command[2] not in failed:
                failed.add(command[2])
                raise subprocess.CalledProcessError(1, command)
            return f"PR for {command[2]}"
        return "c1 c2" if command[1] == "rev-list" else ""

    monkeypatch.setattr(release_canary, "output", output)
    monkeypatch.setattr(time, "sleep", float)
    text = release_canary.public_text("HEAD")
    assert "commits/c1/pulls" in text
    assert "commits/c2/pulls" in text


def test_release_text_holds_added_lines_but_not_lines_main_already_published(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A release that deletes an old mention must not fail for publishing it."""
    diff = "--- a/plan.md\n+++ b/plan.md\n-old secret-app note\n+new text\n context"

    def output(command: list[str], cwd: Path = release_canary.SOURCE) -> str:
        return diff if command[1] == "diff" else ""

    monkeypatch.setattr(release_canary, "output", output)
    text = release_canary.public_text("HEAD")
    assert "new text" in text
    assert "secret-app" not in text


def test_new_targets_get_the_project_documents_the_check_requires(
    tmp_path: Path,
) -> None:
    """A fresh install fails its check until PRODUCT.md and DESIGN.md are filled."""
    release_canary.add_documents(tmp_path)
    validate_documents(tmp_path)


def test_a_target_folder_is_a_valid_cloudflare_project_name() -> None:
    """create-cloudflare names the project after the folder and rejects underscores."""
    assert re.fullmatch(r"[a-z0-9-]+", release_canary.folder("scaffold opennext"))


def test_a_private_repository_named_after_a_public_owner_is_no_leak() -> None:
    private = ["school/sgaabdu4"]
    assert not release_canary.leaked_names('"github_login":"sgaabdu4"', private)
    assert release_canary.leaked_names("see school/sgaabdu4", private)


def test_a_private_repository_named_with_a_common_word_leaks_only_by_full_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(release_canary, "WORDS", frozenset({"starter"}))
    private = ["owner/starter", "owner/zorblax"]
    assert not release_canary.leaked_names("The starter tests pass.", private)
    assert release_canary.leaked_names("see owner/starter", private)
    assert release_canary.leaked_names("the zorblax app", private)


def agent_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, session: dict[str, object]
) -> Path:
    work = tmp_path / "target"
    work.mkdir()
    for command in (
        ["git", "init", "-q"],
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "base",
        ],
    ):
        subprocess.run(command, cwd=work, check=True)
    agent = (
        "import json, pathlib, sys\n"
        "pathlib.Path('sum.py').write_text('def add(a, b):\\n    return a + b\\n')\n"
        "state = pathlib.Path('.hard-eng/sessions/s.json')\n"
        "state.parent.mkdir(parents=True)\n"
        "state.write_text(sys.argv[1])\n"
    )

    def agent_command(name: str, copy: Path) -> list[str]:
        return [sys.executable, "-c", agent, json.dumps(session)]

    monkeypatch.setattr(release_canary, "agent_command", agent_command)
    return work


@pytest.mark.parametrize(
    ("session", "expected"),
    [
        ({"base": "x", "verified": {}}, (True, "codex passed")),
        ({"base": "x"}, (False, "codex ended without a passing Hard Eng check")),
    ],
)
def test_an_agent_run_passes_only_when_hard_eng_recorded_a_passing_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    session: dict[str, object],
    expected: tuple[bool, str],
) -> None:
    """Agent exit status alone cannot prove the hooks loaded and the gate passed."""
    work = agent_target(tmp_path, monkeypatch, session)
    with (tmp_path / "agent.log").open("w") as log:
        assert release_canary.try_agent("codex", work, log) == expected
    assert sorted(path.name for path in tmp_path.iterdir()) == ["agent.log", "target"]


def test_git_locks_in_the_target_never_reach_the_agent_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Background git maintenance holds and drops lock files while the target is copied."""
    work = agent_target(tmp_path, monkeypatch, {"base": "x", "verified": {}})
    (work / ".git/index.lock").touch()
    with (tmp_path / "agent.log").open("w") as log:
        assert release_canary.try_agent("codex", work, log) == (True, "codex passed")


def test_project_lock_files_reach_the_agent_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dependency lock files such as pubspec.lock are project files the checks need."""
    work = agent_target(tmp_path, monkeypatch, {"base": "x", "verified": {}})
    (work / "pubspec.lock").write_text("packages: {}\n")
    command = release_canary.agent_command

    def agent_command(name: str, copy: Path) -> list[str]:
        assert (copy / "pubspec.lock").is_file()
        return command(name, copy)

    monkeypatch.setattr(release_canary, "agent_command", agent_command)
    with (tmp_path / "agent.log").open("w") as log:
        assert release_canary.try_agent("codex", work, log) == (True, "codex passed")


def test_a_step_log_shows_when_each_command_started_and_how_long_it_took(
    tmp_path: Path,
) -> None:
    """Without times nobody can tell which part of a nine-hour run is slow."""
    with (tmp_path / "step.log").open("w") as log:
        assert release_canary.step(["true"], tmp_path, log, 60)
    text = (tmp_path / "step.log").read_text()
    assert re.search(r"^\[\d\d:\d\d:\d\d\] \$ true$", text, re.MULTILINE)
    assert "Exit 0 after 0 seconds." in text


def test_agent_units_of_a_prepared_target_run_before_the_next_target_is_prepared() -> (
    None
):
    """Agents of one target are separate units, and they keep at most a few targets on disk."""
    ran: list[str] = []

    def prepare(name: str) -> list[release_canary.Unit]:
        ran.append(name)
        return [
            lambda: ran.append(f"{name} claude") or [],
            lambda: ran.append(f"{name} codex") or [],
        ]

    release_canary.run_units([lambda: prepare("a"), lambda: prepare("b")], 1)
    assert ran == ["a", "a claude", "a codex", "b", "b claude", "b codex"]


def test_agents_of_one_target_run_at_the_same_time() -> None:
    """Claude and Codex work on their own copies, so neither waits for the other."""
    both = threading.Barrier(2, timeout=10)

    def agent() -> list[release_canary.Unit]:
        both.wait()
        return []

    release_canary.run_units([lambda: [agent, agent]], 2)


def test_a_unit_that_crashes_stops_the_run() -> None:
    """A canary fault must stop the run, not turn into a verdict on a release."""
    ran: list[str] = []

    def broken() -> list[release_canary.Unit]:
        raise RuntimeError("broken")

    with pytest.raises(RuntimeError, match="broken"):
        release_canary.run_units([broken, lambda: ran.append("other") or []], 1)
    assert ran == []


def test_new_projects_start_before_installed_ones() -> None:
    """They always run both agents and take longest, so they must not form the tail."""
    found = [
        ("installed", "o/a"),
        ("installed", "o/b"),
        ("scaffold", "vite"),
        ("brownfield", "x"),
    ]
    assert release_canary.longest_first(found) == [
        ("scaffold", "vite"),
        ("brownfield", "x"),
        ("installed", "o/a"),
        ("installed", "o/b"),
    ]


def test_a_target_is_kept_until_its_last_agent_ends_and_only_when_one_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each agent writes its own log; the shared target goes once every run passed."""
    verdicts = {"claude": (True, "claude passed")}

    def try_agent(agent: str, work: Path, log: object) -> tuple[bool, str]:
        assert work.is_dir()
        return verdicts[agent]

    def prepare(*_: object) -> list[tuple[str, list[str]]]:
        return []

    monkeypatch.setattr(release_canary, "try_agent", try_agent)
    monkeypatch.setattr(release_canary, "prepare", prepare)
    for failing, kept in ((True, True), (False, False)):
        verdicts["codex"] = (not failing, "codex result")
        run = tmp_path / str(kept)
        run.mkdir()
        trial = release_canary.Trial(("scaffold", "vite"), run, ("claude", "codex"))
        trial.work.mkdir()
        units = trial.prepare("a" * 40, tmp_path)
        assert [unit() for unit in units] == [[], []]
        assert trial.work.exists() == kept
        assert trial.log(".claude").exists()
        assert trial.log(".codex").exists()
        assert [stage for stage, _, _ in trial.times] == ["prepare", "claude", "codex"]


def test_a_failed_clone_falls_back_to_a_full_copy_without_git_locks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lock that Git's maintenance drops mid-clone must not fail the agent run."""
    work = tmp_path / "target"
    (work / ".git").mkdir(parents=True)
    (work / ".git/index.lock").touch()
    (work / "pubspec.lock").touch()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "cp").write_text('#!/bin/sh\nmkdir -p "$5/partial"\nexit 1\n')
    (bin_dir / "cp").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    monkeypatch.setattr(sys, "platform", "darwin")
    copy = tmp_path / "copy"
    release_canary.copy_target(work, copy)
    assert sorted(path.name for path in copy.rglob("*")) == [".git", "pubspec.lock"]


def test_a_clone_drops_git_locks_and_keeps_project_lock_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "target"
    (work / ".git/modules/skill").mkdir(parents=True)
    (work / ".git/modules/skill/index.lock").touch()
    (work / "pubspec.lock").touch()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # GNU cp has no clone flag; drop it so the clone path runs here too.
    (bin_dir / "cp").write_text('#!/bin/sh\nshift\nexec /bin/cp "$@"\n')
    (bin_dir / "cp").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    monkeypatch.setattr(sys, "platform", "darwin")
    copy = tmp_path / "copy"
    release_canary.copy_target(work, copy)
    assert (copy / "pubspec.lock").is_file()
    assert not list(copy.rglob("index.lock"))
    assert (work / ".git/modules/skill/index.lock").is_file()


def test_the_time_summary_names_each_stage_with_its_runs_total_and_longest() -> None:
    times = [
        ("prepare", "installed o/a", 120.0),
        ("claude", "scaffold vite", 3600.0),
        ("claude", "installed o/a", 900.0),
    ]
    assert release_canary.time_summary(times, 5430.0) == [
        "Time: 1h30m from start to end.",
        "prepare: 1 runs, 2m in all, longest 2m (installed o/a)",
        "claude: 2 runs, 1h15m in all, longest 1h00m (scaffold vite)",
    ]


def test_only_new_projects_get_agent_sessions() -> None:
    """Installed projects prove the release with their checks; new ones prove the agents."""
    agents = ("claude", "codex")
    assert release_canary.agents_for(("installed", "o/a"), agents) == ()
    for kind in ("scaffold", "greenfield", "brownfield"):
        assert release_canary.agents_for((kind, "x"), agents) == agents


def test_the_public_canary_workflow_needs_no_canary_run() -> None:
    """The workflow only checks new projects; a project never installs it."""
    assert not release_canary.needs_canary([".github/workflows/canary.yml"])


def test_ci_names_every_new_project_without_a_newest_passing_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        "new project (scaffold-flutter, ubuntu-latest)\tsuccess",
        "new project (scaffold-flutter, macos-latest)\tsuccess",
        "new project (scaffold-vite, macos-latest)\tfailure",
        "new project (scaffold-vite, ubuntu-latest)\tsuccess",
        "new project (greenfield-python, ubuntu-latest)\t",
        "new project (scaffold-nextjs, ubuntu-latest)\tsuccess",
        "new project (scaffold-opennext, ubuntu-latest)\tsuccess",
        "new project (brownfield-itsdangerous, ubuntu-latest)\tsuccess",
        "hard-eng\tsuccess",
    ]

    def output(command: list[str]) -> str:
        return "\n".join(rows)

    monkeypatch.setattr(release_canary, "output", output)
    assert release_canary.ci_failures("a" * 40) == [
        "scaffold-vite",
        "greenfield-python",
    ]
    rows[:] = ["hard-eng\tsuccess"]
    assert release_canary.ci_failures("a" * 40) == [
        release_canary.folder(" ".join(target)) for target in release_canary.NEW_TARGETS
    ]


def test_the_workflow_job_names_are_the_ones_the_mac_canary_reads() -> None:
    workflow = yaml.safe_load(
        (release_canary.SOURCE / ".github/workflows/canary.yml").read_text()
    )
    name = workflow["jobs"]["new-project"]["name"]
    for os_name in workflow["jobs"]["new-project"]["strategy"]["matrix"]["os"]:
        job = name.replace("${{ matrix.target }}", "scaffold-vite")
        found = release_canary.CI_JOB.fullmatch(
            job.replace("${{ matrix.os }}", os_name)
        )
        assert found and found[1] == "scaffold-vite"


def test_a_new_project_gets_its_full_check_only_in_ci(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On the Mac the agents' Stop check runs it; CI proved it first."""

    def install_new(*_: object) -> None:
        pass

    monkeypatch.setattr(release_canary, "install_new", install_new)
    with (tmp_path / "log").open("w") as log:
        for target in release_canary.NEW_TARGETS:
            args = (target, "a" * 40, tmp_path, tmp_path / "work", log)
            assert release_canary.prepare(*args) == []
            checks = release_canary.prepare(*args, check_new=True)
            assert [name for name, _ in checks] == ["full check"]


def test_ci_and_reruns_pick_only_the_named_new_projects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["release_canary.py", "HEAD", "--ci", "--target", "scaffold-vite"]
    )
    assert release_canary.targets(release_canary.arguments(), ["o/a"]) == [
        ("scaffold", "vite")
    ]
    monkeypatch.setattr(sys, "argv", ["release_canary.py", "HEAD", "--ci"])
    found = release_canary.targets(release_canary.arguments(), ["o/a"])
    assert found == list(release_canary.NEW_TARGETS)
    monkeypatch.setattr(sys, "argv", ["release_canary.py", "HEAD"])
    found = release_canary.targets(release_canary.arguments(), ["o/a"])
    assert found == [("installed", "o/a"), *release_canary.NEW_TARGETS]


def test_new_projects_that_failed_ci_stop_the_run_before_any_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A scaffold that fails in minutes on CI must not start hours of agent runs."""

    def ci_failures(_: str) -> list[str]:
        return ["scaffold-vite"]

    monkeypatch.setattr(release_canary, "ci_failures", ci_failures)
    posted = full_run(tmp_path, monkeypatch, ["o/a"])
    assert posted[-1] == ("failure", "New projects have not passed CI")
    assert not (tmp_path / "cache").exists()
