"""The full check judges what Fallow prints as its resolved config, so no spelling of a setting can hide a switched-off rule."""

import json
import shutil
from pathlib import Path

import pytest
from conftest import git
from gate_config import Gate, Group
from resolved_settings import validate_resolved
from test_strict_refusals import project

SCAN = ["fallow", "--only", "dead-code,dupes,health", "--fail-on-issues"]


def need_fallow() -> None:
    if shutil.which("fallow") is None:
        from tool_setup import PACKAGES, provision_batch

        provision_batch([PACKAGES["fallow"] + "@latest"], 900)


def gate(role: str = "dead-code-duplicates") -> Gate:
    return {"name": "fallow", "role": role, "command": SCAN}


def repo(tmp_path: Path, files: dict[str, str]) -> Path:
    need_fallow()
    return project(tmp_path, files)


def groups(*paths: str) -> list[Group]:
    return [
        {"path": path, "language": "javascript", "checks": [gate()]} for path in paths
    ]


def settings(**values: object) -> str:
    return json.dumps(values)


SWITCHED_OFF = [
    ({"rules": {"unused-files": "off"}}, "rule unused-files is off"),
    (
        {"overrides": [{"files": ["a/**"], "rules": {"unused-exports": "off"}}]},
        "rule unused-exports is off",
    ),
    ({"ignoreFindings": ["anything"]}, "ignoreFindings"),
    ({"entry": ["src/**/*.ts"]}, "entry lists 'src/\\*\\*/\\*.ts'"),
    ({"duplicates": {"enabled": False}}, "duplicates.enabled is False"),
    ({"ignorePatterns": ["src/**"]}, r"does not check src/a\.ts"),
]


@pytest.mark.parametrize(("config", "reason"), SWITCHED_OFF)
def test_a_fallow_config_that_switches_a_check_off_is_refused(
    tmp_path: Path, config: dict[str, object], reason: str
) -> None:
    """HE-NO-SWITCH-OFF: `fallow config` shows the switch-off after `extends`, overrides and defaults, whatever its spelling."""
    root = repo(
        tmp_path,
        {".fallowrc.json": json.dumps(config), "src/a.ts": "export const a = 1;\n"},
    )
    with pytest.raises(ValueError, match=rf"HE-NO-SWITCH-OFF[\s\S]*{reason}"):
        validate_resolved(root, groups("."), 900)


def test_a_fallow_config_that_keeps_every_check_passes(tmp_path: Path) -> None:
    config = settings(
        ignorePatterns=[".hooks/**"],
        rules={"unused-files": "warn", "unused-exports": "error"},
        entry=["src/main.ts", "playwright.config.ts"],
        duplicates={"enabled": True},
    )
    root = repo(tmp_path, {".fallowrc.json": config, "src/main.ts": "export {};\n"})
    validate_resolved(root, groups("."), 900)


def test_a_rule_that_is_off_by_default_may_stay_off(tmp_path: Path) -> None:
    root = repo(tmp_path, {".fallowrc.json": settings(rules={"prop-drilling": "off"})})
    validate_resolved(root, groups("."), 900)


def test_an_ignore_in_an_npm_extended_config_is_refused(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: Fallow loads an `npm:` base from node_modules; the printed config shows what it holds."""
    root = repo(
        tmp_path,
        {
            ".fallowrc.json": settings(extends=["npm:shared-fallow"]),
            "node_modules/shared-fallow/package.json": '{"name": "shared-fallow", "main": "base.json"}',
            "node_modules/shared-fallow/base.json": settings(ignoreFindings=["x"]),
        },
    )
    with pytest.raises(ValueError, match=r"ignoreFindings"):
        validate_resolved(root, groups("."), 900)


def test_generated_output_may_be_ignored_when_the_attributes_name_it(
    tmp_path: Path,
) -> None:
    """A pattern is allowed when every file it drops is marked linguist-generated."""
    files = {
        ".fallowrc.json": settings(ignorePatterns=["gen/**"]),
        ".gitattributes": "gen/** linguist-generated\n",
        "gen/a.ts": "export const a = 1;\n",
        "gen/b/c.ts": "export const c = 1;\n",
    }
    root = repo(tmp_path, files)
    validate_resolved(root, groups("."), 900)
    (root / "gen/plain.txt").write_text("x\n")
    (root / ".gitattributes").write_text("gen/a.ts linguist-generated\n")
    git(root, "add", "-A")
    with pytest.raises(ValueError, match=r"does not check gen/b/c\.ts"):
        validate_resolved(root, groups("."), 900)


def monorepo(tmp_path: Path, pattern: str, extra: dict[str, str] | None = None) -> Path:
    return repo(
        tmp_path,
        {
            ".fallowrc.json": settings(ignorePatterns=[pattern]),
            "apps/web/.fallowrc.json": "{}",
            "apps/web/src/a.ts": "export const a = 1;\n",
            "apps/api/.fallowrc.json": "{}",
            "apps/api/src/b.ts": "export const b = 1;\n",
            **(extra or {}),
        },
    )


def test_a_root_ignore_of_packages_that_have_their_own_gate_passes(
    tmp_path: Path,
) -> None:
    """The root run applies none of an app's own config, so it leaves out the apps that run Fallow themselves."""
    root = monorepo(tmp_path, "apps/**")
    validate_resolved(root, groups(".", "apps/web", "apps/api"), 900)


def test_a_root_ignore_that_covers_a_file_no_nested_gate_covers_is_refused(
    tmp_path: Path,
) -> None:
    root = monorepo(tmp_path, "apps/**", {"apps/shared/c.ts": "export const c = 1;\n"})
    with pytest.raises(ValueError, match=r"apps/shared/c\.ts"):
        validate_resolved(root, groups(".", "apps/web", "apps/api"), 900)
    root = monorepo(tmp_path / "other", "apps/**")
    with pytest.raises(ValueError, match=r"does not check apps/api/src/b\.ts"):
        validate_resolved(root, groups(".", "apps/web"), 900)


def test_a_nested_config_that_switches_a_check_off_is_refused(tmp_path: Path) -> None:
    """The nested package is judged by the same rules."""
    root = monorepo(
        tmp_path,
        "apps/**",
        {"apps/web/.fallowrc.json": settings(ignoreFindings=["x"])},
    )
    with pytest.raises(ValueError, match=r"ignoreFindings"):
        validate_resolved(root, groups(".", "apps/web", "apps/api"), 900)


PLAYWRIGHT = {
    "package.json": json.dumps({"devDependencies": {"@playwright/test": "1.0.0"}}),
    "playwright.config.ts": "export default { testDir: 'e2e', testMatch: '**/*.e2e.ts' };\n",
    "e2e/a.e2e.ts": "export const a = 1;\n",
}


def test_an_entry_glob_that_a_plugin_already_covers_names_the_plugin(
    tmp_path: Path,
) -> None:
    root = repo(
        tmp_path,
        {**PLAYWRIGHT, ".fallowrc.json": settings(entry=["e2e/**/*.e2e.ts"])},
    )
    with pytest.raises(
        ValueError,
        match=r"entry lists 'e2e/\*\*/\*\.e2e\.ts'[^\n]*playwright[^\n]*remove the entry",
    ):
        validate_resolved(root, groups("."), 900)


def test_an_entry_glob_for_files_no_plugin_finds_asks_for_names(
    tmp_path: Path,
) -> None:
    root = repo(
        tmp_path,
        {
            **PLAYWRIGHT,
            "scripts/run.ts": "export const run = 1;\n",
            ".fallowrc.json": settings(entry=["scripts/*.ts"]),
        },
    )
    with pytest.raises(ValueError, match=r"list each file by name") as refused:
        validate_resolved(root, groups("."), 900)
    assert "already finds" not in str(refused.value)


def tests_group(report: str = "coverage/lcov.info") -> list[Group]:
    tests: Gate = {
        "name": "tests",
        "role": "tests",
        "command": ["bun", "run", "test:coverage"],
        "report": {"type": "lcov-tests", "path": report},
    }
    return [{"path": ".", "language": "javascript", "checks": [gate(), tests]}]


def test_a_committed_coverage_file_cannot_feed_the_crap_score(tmp_path: Path) -> None:
    root = repo(
        tmp_path,
        {
            ".fallowrc.json": settings(health={"coverage": "committed.json"}),
            "committed.json": "{}",
            "src/main.ts": "export {};\n",
        },
    )
    with pytest.raises(ValueError, match=r"health\.coverage[\s\S]*tests gate writes"):
        validate_resolved(root, tests_group(), 900)


def test_the_coverage_file_that_the_tests_gate_writes_may_feed_it(
    tmp_path: Path,
) -> None:
    root = repo(
        tmp_path,
        {
            ".fallowrc.json": settings(
                health={"coverage": "coverage/coverage-final.json"}
            ),
            ".gitignore": "coverage/\n",
            "src/main.ts": "export {};\n",
        },
    )
    validate_resolved(root, tests_group(), 900)


def test_boundaries_must_cover_every_file(tmp_path: Path) -> None:
    config = settings(
        boundaries={
            "zones": [{"name": "app", "patterns": ["src/**"]}],
            "rules": [{"from": "app", "allow": []}],
        }
    )
    root = repo(tmp_path, {".fallowrc.json": config, "src/main.ts": "export {};\n"})
    with pytest.raises(ValueError, match=r"boundaries[\s\S]*requireAllFiles"):
        validate_resolved(root, groups("."), 900)
