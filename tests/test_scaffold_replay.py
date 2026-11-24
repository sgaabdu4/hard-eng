"""A verified update is proven from its tree, even when the base held edited scaffold files."""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import change_size
import gate_config
import pytest
import shipping
import tool_setup
import update
from conftest import SOURCE, commit, default_policy, git, load_module
from coverage_sources import require_listed_sources
from gate_config import parse_config, repository_files
from test_update_pr_refusal import loading_project
from test_updates import fixed_revision

SKILL_LOCK = ".agents/skills/marketing-video/bun.lock"
WORKFLOW = ".github/workflows/hard-eng.yml"
GENERATED_RUNNER = (
    "${{ vars.CI_RUNS_ON && fromJSON(vars.CI_RUNS_ON) || 'ubuntu-latest' }}"
)


def edited_base(target: Path) -> tuple[str, str]:
    """A base that carries a project's own copy of a shipped file and an older workflow."""
    workflow = target / WORKFLOW
    original = workflow.read_text()
    assert GENERATED_RUNNER in original
    workflow.write_text(original.replace(GENERATED_RUNNER, "ubuntu-latest"))
    lock = target / SKILL_LOCK
    shipped = lock.read_text()
    lock.write_text(shipped.replace("1.", "2.", 1))
    assert lock.read_text() != shipped
    return commit(target, "project copy of a skill file"), shipped


def test_update_that_restores_edited_skill_files_is_proven(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = release
    base, shipped = edited_base(target)
    (target / SKILL_LOCK).write_text(shipped)
    commit(target, "restore the shipped skill file")
    revision = commit(source, "verified update")
    monkeypatch.setattr(update, "latest_verified", fixed_revision(revision))
    update.update(target)
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    assert git(target, "diff", "--name-only", base, "--", SKILL_LOCK) == SKILL_LOCK
    assert update.check_scaffold_update(target, base)
    assert GENERATED_RUNNER in (target / WORKFLOW).read_text()


COORDINATOR = ".agents/skills/trello-coordinator/"
RUN = COORDINATOR + "references/run.md"
SCRIPT = COORDINATOR + "scripts/trello_board/commands.py"
LOCAL_RULE = "- Project rule: reply in the card's language.\n"
LOCAL_CODE = "\n\ndef project_command() -> str:\n    return 'project'\n"


def release_now(source: Path, monkeypatch: pytest.MonkeyPatch, message: str) -> str:
    git(source, "add", ".")
    git(source, "commit", "-q", "--allow-empty", "-m", message)
    revision = git(source, "rev-parse", "HEAD")
    monkeypatch.setattr(update, "latest_verified", fixed_revision(revision))
    return revision


def edited_coordinator(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    """A project with the coordinator installed and its own committed lines in it."""
    source, target, _ = release
    (target / "trello.json").write_text('{"board": "https://trello.com/b/abc"}')
    commit(target, "connect the board")
    release_now(source, monkeypatch, "release one")
    update.update(target)
    with (target / RUN).open("a") as rules:
        rules.write(LOCAL_RULE)
    with (target / SCRIPT).open("a") as script:
        script.write(LOCAL_CODE)
    commit(target, "project coordinator edits")
    return source, target


def change_first_line(path: Path, line: str) -> None:
    lines = path.read_text().splitlines(keepends=True)
    path.write_text(line + "".join(lines[1:]))


def test_update_merges_local_coordinator_edits(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target = edited_coordinator(release, monkeypatch)
    base = git(target, "rev-parse", "HEAD")
    change_first_line(source / RUN, "# One coordinator run, release two\n")
    change_first_line(source / SCRIPT, 'import argparse\nRELEASE = "release two"\n')
    release_now(source, monkeypatch, "release two")
    update.update(target)
    for name, local, new in (
        (RUN, LOCAL_RULE, "release two"),
        (SCRIPT, LOCAL_CODE, "release two"),
    ):
        text = (target / name).read_text()
        assert local in text and new in text
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    assert update.check_scaffold_update(target, base)


def test_local_coordinator_edits_survive_two_releases(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target = edited_coordinator(release, monkeypatch)
    for number in ("two", "three"):
        change_first_line(source / RUN, f"# One coordinator run, release {number}\n")
        release_now(source, monkeypatch, f"release {number}")
        update.update(target)
        text = (target / RUN).read_text()
        assert text.startswith(f"# One coordinator run, release {number}\n")
        assert text.endswith(LOCAL_RULE)


def test_untouched_coordinator_file_keeps_local_edits(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target = edited_coordinator(release, monkeypatch)
    before = git(target, "rev-parse", "HEAD")
    release_now(source, monkeypatch, "release without coordinator changes")
    update.update(target)
    assert (target / RUN).read_text().endswith(LOCAL_RULE)
    assert RUN not in git(target, "diff", "--name-only", before, "HEAD").splitlines()


def test_overlapping_coordinator_edit_is_refused(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target = edited_coordinator(release, monkeypatch)
    change_first_line(target / RUN, "# Our coordinator run\n")
    commit(target, "project heading")
    head = git(target, "rev-parse", "HEAD")
    change_first_line(source / RUN, "# One coordinator run, release two\n")
    release_now(source, monkeypatch, "release two")
    with pytest.raises(ValueError, match=f"{RUN} has local edits on the same lines"):
        update.update(target)
    assert git(target, "rev-parse", "HEAD") == head
    assert git(target, "status", "--porcelain") == ""


def test_merged_coordinator_script_must_compile(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target = edited_coordinator(release, monkeypatch)
    head = git(target, "rev-parse", "HEAD")
    change_first_line(source / SCRIPT, "def broken(:\n")
    release_now(source, monkeypatch, "release two")
    with pytest.raises(ValueError, match=f"{SCRIPT} does not compile"):
        update.update(target)
    assert git(target, "rev-parse", "HEAD") == head


def update_beside_code_outside_the_sources(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, str]:
    source, target, _ = release
    for name in ("src/index.ts", "scripts/build.mjs"):
        (target / name).parent.mkdir(exist_ok=True)
        (target / name).write_text("export const a = 1;\n")
    manifest = target / "package.json"
    package = json.loads(manifest.read_text())
    package["scripts"] |= {
        "lint:boundaries": "bun run boundaries",
        "boundaries": "bun test boundaries",
    }
    manifest.write_text(json.dumps(package))
    commit(target, "code outside the listed sources")
    release_now(source, monkeypatch, "release one")
    update.update(target)
    assert '"sources": ["src"]' in (target / "hard-eng.gates.json").read_text()
    base = git(target, "rev-parse", "HEAD")
    release_now(source, monkeypatch, "release two")
    update.update(target)
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    return target, base


def after_the_gate_check(spy: Mock) -> list[str]:
    """The Git commands started after the last start that is not Git."""
    words = [call.args[0] for call in spy.call_args_list]
    last = max(
        (n for n, command in enumerate(words) if command[0] != "git"), default=-1
    )
    return [command[3 if command[1] == "-c" else 1] for command in words[last + 1 :]]


@pytest.mark.parametrize("hosted", [True, False])
def test_scaffold_update_check_refuses_code_outside_the_sources(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch, hosted: bool
) -> None:
    target, base = update_beside_code_outside_the_sources(release, monkeypatch)
    spy = Mock(side_effect=subprocess.Popen)
    monkeypatch.setattr(subprocess, "Popen", spy)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    if hosted:
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(ValueError, match="outside its sources: scripts"):
        update.check_scaffold_update(target, base)
    assert after_the_gate_check(spy) == ["ls-files", "check-attr"]


def test_a_quick_check_of_a_verified_update_leaves_the_sources_rule_to_the_full_check(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target, base = update_beside_code_outside_the_sources(release, monkeypatch)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("CI", raising=False)
    runner = load_module("runner", SOURCE / ".hooks/gate_runner.py")
    runner.__dict__["ROOT"] = target
    spy = Mock(side_effect=subprocess.Popen)
    monkeypatch.setattr(subprocess, "Popen", spy)
    assert runner.check(base=base, quick=True) == 0
    assert after_the_gate_check(spy) == []
    with pytest.raises(ValueError, match="outside its sources: scripts"):
        runner.check(base=base)


def test_the_step_of_the_update_refusal_works_on_the_update_branch(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target, base = update_beside_code_outside_the_sources(release, monkeypatch)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    gates = target / "hard-eng.gates.json"
    gates.write_text(
        gates.read_text().replace('"sources": ["src"]', '"sources": ["scripts", "src"]')
    )
    commit(target, "list the scripts folder")
    assert not update.check_scaffold_update(target, base)
    packages = parse_config(gates.read_text())["packages"]
    require_listed_sources(
        target, packages, repository_files(target), python_only=False
    )


def test_an_update_adds_the_biome_entry_and_stays_an_update(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = release
    (target / "biome.json").write_text(
        '{\n  "files": {\n    "includes": ["**"]\n  }\n}\n'
    )
    base = commit(target, "project Biome settings")
    release_now(source, monkeypatch, "release one")
    update.update(target)
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    assert '"!.hooks"' in (target / "biome.json").read_text()
    changed = set(git(target, "diff", "--name-only", base).splitlines())
    assert "biome.json" in changed
    assert change_size.update_only(target, base, changed)


def web_project(target: Path, **extra: object) -> str:
    """A project with screens in `src` and a shared folder `src/ui`, whose shipping policy has no `ui_library`."""
    gates = target / "hard-eng.gates.json"
    config = json.loads(gates.read_text())
    config["shipping"] = {
        key: value for key, value in default_policy().items() if key != "ui_library"
    } | {"ui_paths": ["src/**"], **extra}
    gates.write_text(json.dumps(config))
    (target / "src/ui").mkdir(parents=True)
    (target / "src/ui/Button.tsx").write_text(
        "export const Button = () => <button>Go</button>;\n"
    )
    (target / "src/App.tsx").write_text("export const App = () => <p>Hi</p>;\n")
    return commit(target, "a web project with no ui_library")


def test_an_update_adds_the_ui_library_key_in_the_same_commit(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = release
    base = web_project(target)
    release_now(source, monkeypatch, "release one")
    update.update(target)
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    saved = json.loads((target / "hard-eng.gates.json").read_text())["shipping"]
    assert saved["ui_library"] == ["src/ui/*"]
    assert git(target, "rev-list", "--count", f"{base}..HEAD") == "1"
    changed = set(git(target, "show", "--name-only", "--format=", "HEAD").splitlines())
    assert {"hard-eng.gates.json", ".hooks/hard-eng-source.json"} <= changed
    assert change_size.update_only(target, base, changed)
    policy = shipping.load_policy(target)
    assert policy is not None and policy["ui_library"] == ["src/ui/*"]
    assert gate_config.load_groups(target)


def test_an_update_leaves_an_existing_ui_library_key_alone(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = release
    base = web_project(target, ui_library=["src/shared/*"])
    release_now(source, monkeypatch, "release one")
    update.update(target)
    saved = json.loads((target / "hard-eng.gates.json").read_text())["shipping"]
    assert saved["ui_library"] == ["src/shared/*"]
    assert "hard-eng.gates.json" not in git(target, "diff", "--name-only", base)


@pytest.mark.parametrize(
    "deployment", [["python3", "-c", "print('DEPLOY')"], ["trivy", "config", "."]]
)
def test_the_full_check_of_an_update_loads_the_gates_file_with_its_release(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    deployment: list[str],
) -> None:
    source, target, _ = release
    base = loading_project(target, deployment)
    revision = commit(source, "next release")
    monkeypatch.setattr(update, "latest_verified", fixed_revision(revision))
    assert revision in update.update(target)
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    monkeypatch.setitem(tool_setup.ROLE_TOOLS["shared"], "deployment", ("trivy",))

    assert update.check_scaffold_update(target, base, sources=False)
    if deployment[0] == "trivy":
        assert update.check_scaffold_update(target, base)
    else:
        with pytest.raises(ValueError, match="the deployment check must run `trivy`"):
            update.check_scaffold_update(target, base)


def test_an_update_that_adds_codex_rules_stays_a_verified_scaffold_update(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = release
    rules = target / ".codex/rules/hard-eng.rules"
    assert rules.is_file()
    rules.unlink()
    base = commit(target, "installed before codex rules existed")
    release_now(source, monkeypatch, "next release")

    update.update(target)

    changed = set(git(target, "diff", "--name-only", base).splitlines())
    assert ".codex/rules/hard-eng.rules" in changed
    assert all(update.maybe_installed(name) for name in changed)
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    assert update.check_scaffold_update(target, base)
    assert update.installed_update_paths(target, base) == changed
    assert change_size.update_only(target, base, changed)
    expected = rules.read_text()
    rules.write_text("# tampered\n")
    commit(target, "tampered codex rules")
    assert not update.check_scaffold_update(target, base)
    copy = target.parent / "elsewhere.rules"
    copy.write_text(expected)
    rules.unlink()
    rules.symlink_to(copy)
    commit(target, "symlinked codex rules")
    with pytest.raises(ValueError, match=r"\.codex/rules/hard-eng\.rules is a symlink"):
        update.check_scaffold_update(target, base)


def test_update_that_changes_the_project_rules_file_does_not_prove_the_project_checks(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Escaped bug: a root AGENTS.md change in a verified update skipped every project check that reads that file."""
    source, target, _ = release
    base = git(target, "rev-parse", "HEAD")
    with (source / "AGENTS.md").open("a") as rules:
        rules.write("- A new shared rule.\n")
    release_now(source, monkeypatch, "release with a rule")
    update.update(target)
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    assert "AGENTS.md" in git(target, "diff", "--name-only", base).splitlines()
    assert update.check_scaffold_update(target, base)
    assert not update.check_scaffold_update(target, base, rules_proven=False)


def test_the_runner_takes_an_update_as_proof_unless_it_changes_the_rules_file(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = release
    runner = load_module("runner_proof", SOURCE / ".hooks/gate_runner.py")
    runner.__dict__["ROOT"] = target
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    base = git(target, "rev-parse", "HEAD")
    with (source / RUN).open("a") as extra:
        extra.write("- Release note.\n")
    release_now(source, monkeypatch, "release without a rule")
    update.update(target)
    assert "AGENTS.md" not in git(target, "diff", "--name-only", base).splitlines()
    assert runner.proven_elsewhere(base)
    later = git(target, "rev-parse", "HEAD")
    with (source / "AGENTS.md").open("a") as rules:
        rules.write("- Another shared rule.\n")
    release_now(source, monkeypatch, "release with a rule")
    update.update(target)
    assert "AGENTS.md" in git(target, "diff", "--name-only", later).splitlines()
    assert not runner.proven_elsewhere(later)
