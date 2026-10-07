"""Affected selection checks the packages a change reaches and nothing else."""

import json
import sys
from pathlib import Path
from types import ModuleType

import gate_config
import pytest
import shipping
import update
from conftest import commit, git, plan_document
from gate_config import Gate, Group, affected_groups, parse_config


@pytest.mark.parametrize(
    "changed,expected",
    [
        ("lib/a.py", ["lib", "app", "site", "."]),
        ("app/a.py", ["app", "site", "."]),
        ("other/a.py", ["other", "."]),
        ("README.md", ["."]),
        ("AGENTS.md", ["."]),
        ("CLAUDE.md", ["."]),
        (".agents/skills/x.md", ["."]),
        (".agents/skills/he/x.md", ["lib", "app", "site", "other", "."]),
        (".github/dependabot.yml", ["lib", "app", "site", "other", "."]),
        (".github/workflows/x.yml", ["."]),
        ("lib/README.md", ["."]),
        ("docs/notes/x.md", ["."]),
        ("site/content/post.md", ["site", "."]),
        (".hooks/a.py", ["lib", "app", "site", "other", "."]),
        ("PLAN.md", ["."]),
        ("features/task/PLAN.md", ["."]),
        ("docs/PLAN.md", ["."]),
    ],
)
def test_changed_package_includes_transitive_dependents_and_shared(
    repository: Path, changed: str, expected: list[str]
) -> None:
    groups: list[Group] = [
        {"path": "lib", "checks": [], "depends_on": []},
        {"path": "app", "checks": [], "depends_on": ["lib"]},
        {"path": "site", "checks": [], "depends_on": ["app"], "language": "javascript"},
        {"path": "other", "checks": [], "depends_on": []},
        {"path": ".", "checks": []},
    ]
    path = repository / changed
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("change")
    for name in ("PLAN.md", "features/task/PLAN.md"):
        plan = repository / name
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text("Task plan\n")
    assert [g["path"] for g in affected_groups(repository, groups, "HEAD")] == expected


def test_pre_push_scope_checks_changed_packages_without_dependents(
    repository: Path,
) -> None:
    install: Gate = {"name": "install", "command": ["true"], "role": "lockfiles"}
    groups: list[Group] = [
        {
            "path": ".",
            "checks": [install, {"name": "t", "command": ["true"]}],
            "depends_on": [],
        },
        {"path": "lib", "checks": [], "depends_on": []},
        {"path": "app", "checks": [], "depends_on": ["lib"]},
        {"path": ".", "checks": []},
    ]
    (repository / "lib").mkdir()
    (repository / "lib/a.py").write_text("change")
    assert affected_groups(repository, groups, "HEAD", dependents=False) == [
        {**groups[0], "checks": [install]},
        groups[1],
        groups[-1],
    ]
    assert [g["path"] for g in affected_groups(repository, groups, "HEAD")] == [
        ".",
        "lib",
        "app",
        ".",
    ]


def test_cross_package_fallow_coverage_owner_must_be_selected_with_its_consumer(
    repository: Path,
) -> None:
    groups: list[Group] = [
        {"path": "packages/website", "checks": [], "depends_on": ["packages/api"]},
        {"path": "packages/api", "checks": [], "depends_on": ["packages/website"]},
        {"path": ".", "checks": []},
    ]
    (repository / "packages/api").mkdir(parents=True)
    (repository / "packages/api/change.mjs").write_text(
        "export const changed = true;\n"
    )
    assert [group["path"] for group in affected_groups(repository, groups, "HEAD")] == [
        "packages/website",
        "packages/api",
        ".",
    ]
    assert [
        group["path"]
        for group in affected_groups(repository, groups, "HEAD", dependents=False)
    ] == ["packages/website", "packages/api", "."]
    groups[0]["depends_on"] = []
    assert [group["path"] for group in affected_groups(repository, groups, "HEAD")] == [
        "packages/api",
        ".",
    ]


def test_unknown_base_checks_all_but_missing_dependency_review_fails(
    repository: Path,
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    groups: list[Group] = [
        {"path": "a", "checks": [], "depends_on": []},
        {"path": "b", "checks": [], "depends_on": []},
        {"path": ".", "checks": []},
    ]
    assert affected_groups(repository, groups, "missing-reference") == groups
    del groups[0]["depends_on"]
    changed = repository / "a/change.py"
    changed.parent.mkdir()
    changed.write_text("change")
    config = json.dumps({"packages": groups[:-1], "shared": []})
    with pytest.raises(ValueError, match="Review `depends_on`.*a"):
        parse_config(config)
    assert parse_config(config, require_impact_review=False)["packages"] == groups[:-1]
    for base in (None, "HEAD", "missing-reference"):
        with pytest.raises(ValueError, match="Review `depends_on`.*a"):
            affected_groups(repository, groups, base)
    (repository / "hard-eng.gates.json").write_text(config)
    monkeypatch.setattr(runner, "ROOT", repository)

    def verified(_root: Path, _base: str) -> bool:
        return True

    monkeypatch.setattr(update, "check_scaffold_update", verified)
    with pytest.raises(ValueError, match="Review `depends_on`.*a"):
        runner.check(base="HEAD")


def test_shared_package_paths_cannot_hide_a_declared_document_input(
    repository: Path,
) -> None:
    groups: list[Group] = [
        {
            "path": ".",
            "language": "python",
            "checks": [],
            "depends_on": [],
            "impact_inputs": ["README.md"],
        },
        {"path": ".", "language": "javascript", "checks": [], "depends_on": []},
        {"path": ".", "checks": []},
    ]
    (repository / "README.md").write_text("A build consumes this document.\n")
    assert affected_groups(repository, groups, "HEAD") == groups


@pytest.mark.parametrize(
    "docs", [[], ["PLAN.md", "features/task/PLAN.md"], ["README.md", "CHANGELOG.md"]]
)
@pytest.mark.parametrize("root", ["a", "."])
def test_docs_only_change_runs_only_the_secret_scan(
    repository: Path, docs: list[str], root: str
) -> None:
    secrets: Gate = {"name": "secrets", "role": "secrets-files", "command": ["x"]}
    workflows: Gate = {"name": "workflows", "role": "workflows", "command": ["x"]}
    groups: list[Group] = [
        {"path": root, "checks": [], "depends_on": []},
        {"path": "b", "checks": [], "depends_on": []},
        {"path": ".", "checks": [secrets, workflows]},
    ]
    for name in docs:
        document = repository / name
        document.parent.mkdir(parents=True, exist_ok=True)
        document.write_text("Documentation\n")
    assert affected_groups(repository, groups, "HEAD") == [
        {"path": ".", "checks": [secrets]}
    ]


@pytest.mark.parametrize("change", ["edited", "deleted", "replaced"])
@pytest.mark.parametrize("runs_checks", [False, True])
def test_only_workflows_that_run_the_checks_select_every_package(
    repository: Path,
    runner: ModuleType,
    capsys: pytest.CaptureFixture[str],
    change: str,
    runs_checks: bool,
) -> None:
    secrets: Gate = {"name": "secrets", "role": "secrets-files", "command": ["x"]}
    lint: Gate = {"name": "lint", "role": "workflows", "command": ["x"]}
    audit: Gate = {"name": "audit", "role": "ci-security", "command": ["x"]}
    shell: Gate = {"name": "shell", "role": "shell", "command": ["x"]}
    groups: list[Group] = [
        {"path": ".", "checks": [], "depends_on": []},
        {"path": "b", "checks": [], "depends_on": []},
        {"path": ".", "checks": [secrets, lint, audit, shell]},
    ]
    (repository / "hard-eng.gates.json").write_text(
        json.dumps({"packages": groups[:-1], "shared": groups[-1]["checks"]})
    )
    workflow = repository / ".github/workflows/deploy.yml"
    workflow.parent.mkdir(parents=True)
    step = "python3 .hooks/hard-eng.py check" if runs_checks else "echo deploy"
    workflow.write_text(f"jobs:\n  deploy:\n    steps:\n      - run: {step}\n")
    commit(repository, "workflow")
    if change == "deleted":
        workflow.unlink()
    elif change == "replaced":
        workflow.write_text("jobs:\n  deploy:\n    steps:\n      - run: echo moved\n")
    else:
        workflow.write_text(workflow.read_text() + "# reviewed\n")
    selected = affected_groups(repository, groups, "HEAD")
    shared: Group = {"path": ".", "checks": [secrets, lint, audit]}
    assert selected == (groups if runs_checks else [shared])
    assert (
        "Checking every package: .github/workflows/deploy.yml"
        in capsys.readouterr().out
    ) is runs_checks
    runner.__dict__["ROOT"] = repository
    assert runner.impact("HEAD") == 0
    assert f"docs_only={str(not runs_checks).lower()}\n" in capsys.readouterr().out


def test_ci_scripts_keep_their_owner_checks(repository: Path) -> None:
    shell: Gate = {"name": "shell", "role": "shell", "command": ["x"]}
    groups: list[Group] = [
        {"path": ".", "checks": [], "depends_on": []},
        {"path": "b", "checks": [], "depends_on": []},
        {"path": ".", "checks": [shell]},
    ]
    script = repository / ".github/scripts/deploy.sh"
    script.parent.mkdir(parents=True)
    script.write_text("echo deploy\n")
    assert affected_groups(repository, groups, "HEAD") == [groups[0], groups[-1]]


@pytest.mark.parametrize(
    "changed,expected",
    [
        ("apps/app/src/view.ts", ["apps/app", "."]),
        ("pnpm-lock.yaml", ["apps/app", ".", "tools/media"]),
    ],
)
def test_package_outside_a_cycle_reads_the_root_files_it_needs(
    repository: Path, changed: str, expected: list[str]
) -> None:
    packages: list[Group] = [
        {"path": "apps/app", "checks": [], "depends_on": ["."]},
        {"path": ".", "checks": [], "depends_on": ["apps/app"]},
        {"path": "tools/media", "checks": [], "depends_on": ["."]},
    ]
    with pytest.raises(ValueError, match=r"cycle.*: `tools/media` -> `\.`\. Replace"):
        parse_config(json.dumps({"packages": packages, "shared": []}))
    media: Group = {
        "path": "tools/media",
        "checks": [],
        "depends_on": [],
        "impact_inputs": ["pnpm-lock.yaml"],
    }
    packages[2] = media
    assert parse_config(json.dumps({"packages": packages, "shared": []}))
    path = repository / changed
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("change\n")
    groups: list[Group] = [*packages, {"path": ".", "checks": []}]
    assert [group["path"] for group in affected_groups(repository, groups, "HEAD")] == [
        *expected,
        ".",
    ]


def test_single_package_without_dependency_mapping_checks_full_package(
    repository: Path,
) -> None:
    groups: list[Group] = [
        {"path": "app", "checks": []},
        {"path": ".", "checks": []},
    ]
    changed = repository / "app/change.py"
    changed.parent.mkdir()
    changed.write_text("change")
    assert affected_groups(repository, groups, "HEAD") == groups


def test_root_lockfile_change_includes_reviewed_consumers(repository: Path) -> None:
    groups: list[Group] = [
        {"path": ".", "checks": [], "depends_on": []},
        {"path": "packages/app", "checks": [], "depends_on": ["."]},
        {"path": "packages/site", "checks": [], "depends_on": ["."]},
        {"path": ".", "checks": []},
    ]
    (repository / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    assert [group["path"] for group in affected_groups(repository, groups, "HEAD")] == [
        ".",
        "packages/app",
        "packages/site",
        ".",
    ]


@pytest.mark.parametrize(
    "changed,expected",
    [
        ("contracts/schema.json", ["contracts", "app", "site", "."]),
        ("shared/schema.json", ["app", "site", "."]),
        ("CONTRACT.md", ["app", "site", "."]),
        ("features/contracts/PLAN.md", ["app", "site", "."]),
        ("README.md", ["."]),
        ("other/notes.md", ["."]),
        ("contracts/notes.md", ["contracts", "app", "site", "."]),
        ("shared/schema.json.old", ["contracts", "app", "site", "other", "."]),
        (".github/workflows/check.yml", ["app", "site", "."]),
    ],
)
def test_explicit_inputs_select_consumers_before_docs_filtering(
    repository: Path,
    runner: ModuleType,
    capsys: pytest.CaptureFixture[str],
    changed: str,
    expected: list[str],
) -> None:
    groups: list[Group] = [
        {"path": "contracts", "checks": [], "depends_on": []},
        {
            "path": "app",
            "checks": [],
            "depends_on": [],
            "impact_inputs": [
                "contracts/",
                "shared/schema.json",
                "CONTRACT.md",
                "features/contracts/PLAN.md",
                ".github/",
            ],
        },
        {"path": "site", "checks": [], "depends_on": ["app"]},
        {"path": "other", "checks": [], "depends_on": []},
        {"path": ".", "checks": []},
    ]
    (repository / "hard-eng.gates.json").write_text(
        json.dumps({"packages": groups[:-1], "shared": []})
    )
    commit(repository, "input configuration")
    path = repository / changed
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("change\n")
    assert [
        group["path"] for group in affected_groups(repository, groups, "HEAD")
    ] == expected
    runner.__dict__["ROOT"] = repository
    assert runner.impact("HEAD") == 0
    assert (
        f"docs_only={str(changed in {'README.md', 'other/notes.md'}).lower()}\n"
        in capsys.readouterr().out
    )


@pytest.mark.parametrize("change", ["deleted", "renamed", "staged", "untracked"])
def test_input_selection_reads_native_git_paths(repository: Path, change: str) -> None:
    groups: list[Group] = [
        {"path": "contracts", "checks": [], "depends_on": []},
        {
            "path": "app",
            "checks": [],
            "depends_on": [],
            "impact_inputs": ["contracts/old schema.json"],
        },
        {"path": "other", "checks": [], "depends_on": []},
        {"path": ".", "checks": []},
    ]
    source = repository / "contracts/old schema.json"
    source.parent.mkdir()
    source.write_text("baseline\n")
    if change != "untracked":
        commit(repository, "shared contract")
    if change == "deleted":
        source.unlink()
    elif change == "renamed":
        (repository / "other").mkdir()
        git(repository, "mv", str(source), "other/new schema.json")
    elif change == "staged":
        source.write_text("changed\n")
        git(repository, "add", str(source))
    expected = ["contracts", "app"]
    if change == "renamed":
        expected.append("other")
    assert [group["path"] for group in affected_groups(repository, groups, "HEAD")] == [
        *expected,
        ".",
    ]


def _no_requirements(_root: Path, _config: object) -> None:
    return None


@pytest.mark.parametrize(
    ("plan_stage", "point", "failed"),
    [("Draft", True, False), ("Draft", False, True), (None, True, True)],
)
def test_plan_stage_check_skips_packages_unchanged_since_a_passed_branch_point(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    plan_stage: str | None,
    point: bool,
    failed: bool,
) -> None:
    failing = {
        "name": "fails",
        "command": [sys.executable, "-c", "raise SystemExit(2)"],
    }
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg/source.py").write_text("value = 1\n")
    (tmp_path / "hard-eng.gates.json").write_text(
        json.dumps(
            {
                "packages": [{"path": "pkg", "checks": [failing], "depends_on": []}],
                "shared": [],
            }
        )
    )
    monkeypatch.setattr(gate_config, "validate_required_checks", _no_requirements)
    git(tmp_path, "config", "user.name", "Fixture")
    git(tmp_path, "config", "user.email", "fixture@example.invalid")
    head = commit(tmp_path, "main")
    (tmp_path / "PLAN.md").write_text(plan_document().replace("Complete", "Draft", 1))

    def passed(_root: Path) -> str | None:
        return head if point else None

    monkeypatch.setattr(shipping, "passed_branch_point", passed)
    assert runner.check(plan_stage=plan_stage) == int(failed)
    assert ("FAIL fails" in capsys.readouterr().out) is failed
