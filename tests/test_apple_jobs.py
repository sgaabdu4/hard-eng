"""A project with Swift runs its Swift checks on macOS and the rest on Linux behind one required check."""

import argparse
import os
import re
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from ci_jobs import (
    CHECKOUT,
    LanguageFilter,
    add_language_filters,
    language_filter,
    language_groups,
)
from ci_setup import configure_ci
from conftest import SOURCE, configure, gate
from gate_config import Gate, Group
from test_swift import LINUX_RUNNER, app_config, flutter_app, generated_workflow

WORKFLOW = ".github/workflows/hard-eng.yml"
MACOS_RUNNER = (
    "${{ vars.CI_MACOS_RUNS_ON && fromJSON(vars.CI_MACOS_RUNS_ON) || 'macos-latest' }}"
)
CURRENT_RUNNER = (
    "${{ needs.impact.outputs.runner == 'macos-latest' && 'macos-latest' || "
    "(vars.CI_RUNS_ON && fromJSON(vars.CI_RUNS_ON) || 'ubuntu-latest') }}"
)
OLD_RUNNER = "${{ needs.impact.outputs.runner || 'macos-latest' }}"
PREVIOUS_IMPACT = """  impact:
    name: impact
    runs-on: %(linux)s
    timeout-minutes: 5
    outputs:
      runner: ${{ steps.impact.outputs.runner }}
    steps:
%(checkout)s      - name: Choose the runner
        id: impact
        env:
          BASE_SHA: ${{ inputs.base_sha || github.event.pull_request.base.sha || github.event.before }}
          GH_TOKEN: ${{ github.token }}
        run: python3 .hooks/hard-eng.py impact --base "$BASE_SHA" >> "$GITHUB_OUTPUT" || echo runner=%(fallback)s >> "$GITHUB_OUTPUT"

"""


def previous_generation(plain: str, *, variable: bool) -> str:
    """The workflow as the releases before the macOS split generated it for a Swift project."""
    checkout = CHECKOUT.search(plain)
    assert checkout is not None
    hosted = "ubuntu-latest" if not variable else LINUX_RUNNER
    plain = plain.replace(f"runs-on: {LINUX_RUNNER}", f"runs-on: {hosted}")
    header = f"  hard-eng:\n    name: hard-eng\n    runs-on: {hosted}\n"
    assert plain.count(header) == 1
    impact = PREVIOUS_IMPACT % {
        "linux": hosted,
        "checkout": checkout[0],
        "fallback": "ubuntu-latest" if variable else "macos-latest",
    }
    runner = CURRENT_RUNNER if variable else OLD_RUNNER
    check = (
        f"  hard-eng:\n    name: hard-eng\n    needs: impact\n"
        f"    if: ${{{{ !cancelled() }}}}\n    runs-on: {runner}\n"
    )
    return plain.replace(header, impact + check, 1)


def generated(installer: ModuleType, tmp_path: Path) -> tuple[Path, str, str]:
    root = tmp_path / "app"
    flutter_app(root)
    plain = generated_workflow(root, installer.gate_config(root))
    return root, plain, generated_workflow(root, app_config(installer, root))


def language_flags(job: dict[str, object]) -> list[str]:
    steps = job["steps"]
    assert isinstance(steps, list)
    return [
        match[1] or ""
        for step in steps
        for match in re.finditer(
            r'\.hooks/hard-eng\.py (?:impact|check) --base "\$BASE_SHA"( --\w+-language \w+)?',
            step.get("run", ""),
        )
    ]


def test_swift_project_splits_the_check_by_runner(
    installer: ModuleType, tmp_path: Path
) -> None:
    _, _, workflow = generated(installer, tmp_path)
    jobs = yaml.safe_load(workflow)["jobs"]
    assert list(jobs) == ["impact", "linux", "apple", "hard-eng"]
    assert jobs["impact"]["runs-on"] == LINUX_RUNNER
    assert jobs["impact"]["outputs"] == {
        "runner": "${{ steps.impact.outputs.runner }}",
        "apple": "${{ steps.impact.outputs.apple }}",
    }
    linux, apple, required = jobs["linux"], jobs["apple"], jobs["hard-eng"]
    assert linux["name"] == "hard-eng-linux" and linux["runs-on"] == LINUX_RUNNER
    assert "needs" not in linux and "if" not in linux
    assert apple["name"] == "hard-eng-apple" and apple["runs-on"] == MACOS_RUNNER
    assert apple["needs"] == "impact"
    assert apple["if"] == "${{ needs.impact.outputs.apple != 'false' }}"
    assert required["name"] == "hard-eng" and required["runs-on"] == LINUX_RUNNER
    assert required["needs"] == ["impact", "linux", "apple"]
    assert required["if"] == "${{ !cancelled() }}"
    assert [job["timeout-minutes"] for job in jobs.values()] == [5, 20, 20, 5]


def test_each_check_job_runs_its_own_languages(
    installer: ModuleType, tmp_path: Path
) -> None:
    _, _, workflow = generated(installer, tmp_path)
    jobs = yaml.safe_load(workflow)["jobs"]
    for job, flag in (("linux", "skip"), ("apple", "only")):
        assert language_flags(jobs[job]) == [f" --{flag}-language swift"] * 3


@pytest.mark.parametrize(
    ("results", "passes"),
    [
        (("success", "success", "success"), True),
        (("success", "success", "skipped"), True),
        (("success", "failure", "skipped"), False),
        (("success", "success", "failure"), False),
        (("success", "success", "cancelled"), False),
        (("success", "skipped", "success"), False),
        (("failure", "success", "skipped"), False),
        (("failure", "skipped", "skipped"), False),
    ],
)
def test_the_required_check_passes_only_when_every_needed_job_did(
    installer: ModuleType,
    tmp_path: Path,
    results: tuple[str, str, str],
    passes: bool,
) -> None:
    _, _, workflow = generated(installer, tmp_path)
    step = yaml.safe_load(workflow)["jobs"]["hard-eng"]["steps"][0]
    environment = {
        **os.environ,
        **dict(zip(("IMPACT", "LINUX", "APPLE"), results, strict=True)),
    }
    result = subprocess.run(
        ["bash", "-e", "-c", step["run"]],
        check=False,
        env=environment,
        capture_output=True,
    )
    assert (result.returncode == 0) is passes


def test_new_install_without_swift_keeps_one_job(
    installer: ModuleType, tmp_path: Path
) -> None:
    _, plain, _ = generated(installer, tmp_path)
    jobs = yaml.safe_load(plain)["jobs"]
    assert list(jobs) == ["hard-eng"]
    assert language_flags(jobs["hard-eng"]) == ["", "", ""]


@pytest.mark.parametrize("variable", [True, False])
def test_previous_generation_splits_once(
    installer: ModuleType, tmp_path: Path, variable: bool
) -> None:
    root, plain, current = generated(installer, tmp_path)
    older = previous_generation(plain, variable=variable)
    path = root / WORKFLOW
    path.parent.mkdir(parents=True)
    path.write_text(older)
    config = app_config(installer, root)
    changes: dict[str, str] = {}
    configure_ci(root, SOURCE, config, changes)
    assert changes == {WORKFLOW: current}
    path.write_text(current)
    changes.clear()
    configure_ci(root, SOURCE, config, changes)
    assert changes == {}


def test_custom_lines_and_later_jobs_stay(
    installer: ModuleType, tmp_path: Path
) -> None:
    root, plain, current = generated(installer, tmp_path)
    older = previous_generation(plain, variable=True)
    custom = "      - run: echo project step\n"
    later = "\n  deploy:\n    needs: hard-eng\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ship\n"
    path = root / WORKFLOW
    path.parent.mkdir(parents=True)
    path.write_text(older.rstrip("\n") + "\n" + custom + later)
    changes: dict[str, str] = {}
    configure_ci(root, SOURCE, app_config(installer, root), changes)
    migrated = changes[WORKFLOW]
    jobs = yaml.safe_load(migrated)["jobs"]
    assert list(jobs) == ["impact", "linux", "apple", "hard-eng", "deploy"]
    assert (
        jobs["linux"]["steps"][-1]
        == jobs["apple"]["steps"][-1]
        == {"run": "echo project step"}
    )
    assert jobs["deploy"]["steps"] == [{"run": "echo ship"}]
    assert migrated.count(custom) == 2 and migrated.count("echo ship") == 1
    assert migrated.startswith(current.split("  impact:")[0])


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("if: ${{ !cancelled() }}", "if: always()"),
        ("      runner: ${{ steps", "      chosen: ${{ steps"),
        ('--base "$BASE_SHA"', "--base HEAD"),
    ],
    ids=["check header", "impact outputs", "check commands"],
)
def test_customised_previous_generation_is_left_with_a_note(
    installer: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    old: str,
    new: str,
) -> None:
    root, plain, _ = generated(installer, tmp_path)
    older = previous_generation(plain, variable=True)
    custom = older.replace(old, new)
    assert custom != older
    path = root / WORKFLOW
    path.parent.mkdir(parents=True)
    path.write_text(custom)
    changes: dict[str, str] = {}
    configure_ci(root, SOURCE, app_config(installer, root), changes)
    assert changes == {}
    assert "CI runner not added" in capsys.readouterr().err


def test_generated_budget_applies_to_the_check_jobs(
    installer: ModuleType, tmp_path: Path
) -> None:
    _, _, workflow = generated(installer, tmp_path)
    jobs = yaml.safe_load(workflow)["jobs"]
    assert jobs["linux"]["timeout-minutes"] == jobs["apple"]["timeout-minutes"] == 20
    assert jobs["hard-eng"]["timeout-minutes"] == 5


def checks(*roles: str) -> list[Gate]:
    return [{"name": role, "role": role, "command": ["true"]} for role in roles]


def sample_groups() -> list[Group]:
    return [
        {"path": "app", "language": "dart", "checks": checks("lockfiles", "tests")},
        {"path": "app/ios", "language": "swift", "checks": checks("tests")},
        {"path": "app/macos", "language": "swift", "checks": checks("tests")},
        {"path": "web", "language": "javascript", "checks": checks("lockfiles")},
        {"path": ".", "checks": checks("secrets-files")},
    ]


def layout(groups: list[Group]) -> list[tuple[str, list[str]]]:
    return [(g["path"], [x.get("role", "") for x in g["checks"]]) for g in groups]


def test_skipping_a_language_keeps_everything_else_whole() -> None:
    kept = language_groups(sample_groups(), LanguageFilter(skip=("swift",)))
    assert layout(kept) == [
        ("app", ["lockfiles", "tests"]),
        ("web", ["lockfiles"]),
        (".", ["secrets-files"]),
    ]


def test_only_a_language_keeps_its_groups_and_their_dependency_installs() -> None:
    kept = language_groups(sample_groups(), LanguageFilter(only=("swift",)))
    assert layout(kept) == [
        ("app", ["lockfiles"]),
        ("app/ios", ["tests"]),
        ("app/macos", ["tests"]),
    ]


def test_the_two_halves_together_run_every_gate() -> None:
    groups = sample_groups()
    apple = language_groups(groups, LanguageFilter(only=("swift",)))
    linux = language_groups(groups, LanguageFilter(skip=("swift",)))
    ran = {
        (g["path"], x["name"])
        for half in (apple, linux)
        for g in half
        for x in g["checks"]
    }
    assert ran == {(g["path"], x["name"]) for g in groups for x in g["checks"]}
    assert not {g["path"] for g in linux} & {"app/ios", "app/macos"}


def test_an_ancestor_without_a_dependency_install_adds_nothing() -> None:
    groups = sample_groups()
    groups[0]["checks"] = checks("tests")
    kept = language_groups(groups, LanguageFilter(only=("swift",)))
    assert [g["path"] for g in kept] == ["app/ios", "app/macos"]


def test_no_filter_returns_the_groups_unchanged() -> None:
    groups = sample_groups()
    assert language_groups(groups, LanguageFilter()) is groups


def test_filter_announces_what_it_keeps(capsys: pytest.CaptureFixture[str]) -> None:
    language_groups(sample_groups(), LanguageFilter(only=("python",)))
    assert "Language filter: checking none" in capsys.readouterr().out


def test_language_flags_exclude_each_other() -> None:
    parser = argparse.ArgumentParser()
    add_language_filters(parser)
    assert language_filter(parser.parse_args(["--only-language", "swift"])) == (
        ("swift",),
        (),
    )
    assert language_filter(parser.parse_args(["--skip-language", "swift"])) == (
        (),
        ("swift",),
    )
    with pytest.raises(SystemExit):
        parser.parse_args(["--only-language", "swift", "--skip-language", "dart"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--only-language", "go"])


@pytest.mark.parametrize(
    ("languages", "ran"),
    [
        (LanguageFilter(), True),
        (LanguageFilter(skip=("swift",)), True),
        (LanguageFilter(only=("swift",)), False),
    ],
)
def test_check_applies_the_language_filter(
    runner: ModuleType, tmp_path: Path, languages: LanguageFilter, ran: bool
) -> None:
    configure(
        tmp_path,
        [gate("shared", "open('shared', 'w').close()", role="custom", parallel=True)],
    )
    assert runner.check(languages=languages) == 0
    assert (tmp_path / "shared").exists() is ran
