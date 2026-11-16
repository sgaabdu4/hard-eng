"""A switch-off cannot hide in a link, a config chain or an odd spelling."""

import os
from pathlib import Path

import pytest
from comments import validate_suppressions
from conftest import commit, git, init
from gitleaks_entries import validate_entries
from test_strict_refusals import project, refusal
from whole_project import validate_whole_project

KEY = 'token = "AKIA' + 'IOSFODNN7EXAMPLQ"\n'
RULE = "aws-access-token"


def linked_project(tmp_path: Path, link: str, target: str, text: str) -> Path:
    root = tmp_path / "repo"
    init(root)
    (root / "README.md").write_text("fixture\n")
    (root / "live.py").write_text(KEY)
    (root / target).parent.mkdir(parents=True, exist_ok=True)
    (root / target).write_text(text)
    os.symlink(target, root / link)
    commit(root, "baseline")
    return root


@pytest.mark.parametrize(
    ("link", "target"),
    [
        (".gitleaksignore", "docs/scan-notes.txt"),
        (".semgrepignore", "docs/notes.txt"),
        (".gitleaks.toml", "docs/notes.toml"),
        ("ruff.toml", "docs/ruff-base.toml"),
        (".fallowrc.json", "docs/fallow.json"),
        ("Cargo.toml", "docs/Cargo.toml"),
    ],
)
def test_a_linked_ignore_or_settings_file_is_refusal(
    tmp_path: Path, link: str, target: str
) -> None:
    """HE-NO-SWITCH-OFF: a link to an ignore or settings file hides its lines from every check, so the link fails."""
    root = linked_project(tmp_path, link, target, f"live.py:{RULE}:1\n")
    with pytest.raises(ValueError, match=rf"{link}:1 is a link") as error:
        validate_whole_project(root)
    assert "HE-NO-SWITCH-OFF" in str(error.value)


def test_a_linked_root_gitleaks_entry_file_hides_no_secret(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: the entry judge and the changed-file check both refuse the link; Gitleaks would read it."""
    root = linked_project(
        tmp_path, ".gitleaksignore", "docs/scan-notes.txt", f"live.py:{RULE}:1\n"
    )
    with pytest.raises(ValueError, match="is a link"):
        validate_entries(root, 900)
    fresh = tmp_path / "fresh"
    init(fresh)
    (fresh / "README.md").write_text("fixture\n")
    base = commit(fresh, "baseline")
    (fresh / "docs").mkdir()
    (fresh / "docs/scan-notes.txt").write_text(f"live.py:{RULE}:1\n")
    os.symlink("docs/scan-notes.txt", fresh / ".gitleaksignore")
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_suppressions(fresh, base)
    commit(fresh, "link")
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_suppressions(fresh, base)


MUTED = {
    "entropy": "[extend]\nuseDefault = true\n[[rules]]\nid = 'aws-access-token'\nregex = '''AKIA[A-Z0-9]{16}'''\nentropy = 99.0\n",
    "regex": "[extend]\nuseDefault = true\n[[rules]]\nid = 'aws-access-token'\nregex = '''a^'''\n",
    "same regex": "[extend]\nuseDefault = true\n[[rules]]\nid = 'aws-access-token'\nregex = '''AKIA[A-Z0-9]{16}'''\n",
}
NEW_RULE = "[extend]\nuseDefault = true\n[[rules]]\nid = 'my-own-token'\nregex = '''own_[a-z]{12}'''\n"


def leaks(root: Path) -> int:
    from gitleaks_entries import ensure_gitleaks, scan

    ensure_gitleaks(900)
    report = root / "report.json"
    config = ["--config", str(root / ".gitleaks.toml")]
    return len(scan(["dir", "."], root, report, config, 900))


@pytest.mark.parametrize("form", MUTED)
def test_a_gitleaks_rule_that_overrides_a_default_rule_is_refusal(
    tmp_path: Path, form: str
) -> None:
    """HE-NO-SWITCH-OFF: a rule with a default rule's id replaces it, so a key can stop matching; the real scan shows the miss."""
    root = tmp_path / "repo"
    init(root)
    (root / "README.md").write_text("fixture\n")
    (root / "live.py").write_text("AKIA" + "IOSFODNN7EXAMPLQ\n")
    (root / ".gitleaks.toml").write_text("[extend]\nuseDefault = true\n")
    assert leaks(root) == 1
    (root / ".gitleaks.toml").write_text(MUTED[form])
    commit(root, "baseline")
    if form != "same regex":
        assert leaks(root) == 0
    with pytest.raises(
        ValueError,
        match=r"\.gitleaks\.toml:\d+ overrides the default rule aws-access-token",
    ):
        validate_whole_project(root)


def test_a_new_gitleaks_rule_passes(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init(root)
    (root / "README.md").write_text("fixture\n")
    (root / ".gitleaks.toml").write_text(NEW_RULE)
    commit(root, "baseline")
    validate_whole_project(root)


RUFF_BASE = '[lint]\nignore = ["F401"]\n'


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("ruff.toml", 'extend = "configs/base.toml"\n'),
        ("pyproject.toml", '[tool.ruff]\nextend = "configs/base.toml"\n'),
        ("ruff.toml", 'extend = "configs/mid.toml"\n'),
    ],
)
def test_a_ruff_ignore_in_an_extended_file_is_refusal(
    tmp_path: Path, name: str, text: str
) -> None:
    """HE-NO-SWITCH-OFF: ruff reads the `extend` chain, so an ignore in a base file is an ignore."""
    files = {
        name: text,
        "configs/base.toml": RUFF_BASE,
        "configs/mid.toml": 'extend = "base.toml"\n',
    }
    message = refusal(project(tmp_path, files))
    assert "configs/base.toml:2 sets the ruff setting ignore" in message


def test_a_ruff_extend_outside_the_repository_is_refused(tmp_path: Path) -> None:
    root = project(tmp_path, {"ruff.toml": 'extend = "../elsewhere.toml"\n'})
    assert "ruff.toml:1 extends a file outside the repository" in refusal(root)
    plain = project(
        tmp_path / "ok",
        {
            "ruff.toml": 'extend = "base.toml"\n',
            "base.toml": '[lint]\nselect = ["E"]\n',
        },
    )
    validate_whole_project(plain)


GATE_CONFIGS = [
    ["--config", "configs/base.toml"],
    ["--config", "lint = { ignore = ['F401'] }"],
    ["--config", "lint . ignore = ['F401']"],
    ["--config=configs/base.toml"],
]


@pytest.mark.parametrize("flags", GATE_CONFIGS)
def test_a_ruff_gate_config_is_judged_by_what_it_holds(
    tmp_path: Path, flags: list[str]
) -> None:
    """HE-NO-SWITCH-OFF: a `--config` value is TOML text or a file; the gate fails when it ignores rules, whatever the spelling."""
    from gate_config import validate_gate

    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/base.toml").write_text(RUFF_BASE)
    gate = {"name": "lint", "role": "lint", "command": ["ruff", "check", ".", *flags]}
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_gate(gate, tmp_path, set())
    (tmp_path / "configs/base.toml").write_text("[lint.mccabe]\nmax-complexity = 10\n")
    ok = {
        "name": "lint",
        "role": "lint",
        "command": ["ruff", "check", ".", *flags[:0], "--config", "configs/base.toml"],
    }
    validate_gate(ok, tmp_path, set())


@pytest.mark.parametrize(
    "flags", [["--select", "E9"], ["--select=E9"], ["--config", "lint.select = ['E9']"]]
)
def test_a_ruff_lint_gate_that_narrows_the_rule_set_fails(
    tmp_path: Path, flags: list[str]
) -> None:
    """HE-NO-SWITCH-OFF: the lint gate adds rules with `--extend-select`; `--select` would replace the project's own set."""
    from gate_config import validate_gate

    gate = {"name": "lint", "role": "lint", "command": ["ruff", "check", ".", *flags]}
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_gate(gate, tmp_path, set())
    extended = {
        "name": "lint",
        "role": "lint",
        "command": ["ruff", "check", ".", "--extend-select", "C901"],
    }
    validate_gate(extended, tmp_path, set())
    for everything in (["--select", "ALL"], ["--select=ALL"], ["--select", "E9,ALL"]):
        validate_gate(
            {
                "name": "lint",
                "role": "lint",
                "command": ["ruff", "check", ".", *everything],
            },
            tmp_path,
            set(),
        )
    selecting = {
        "name": "complexity",
        "role": "complexity",
        "command": ["ruff", "check", ".", "--select", "C901"],
    }
    validate_gate(selecting, tmp_path, set())


FALLOW_BASE = '{"health": {"ignore": ["src/**"]}}\n'


def test_a_fallow_ignore_in_an_extended_file_is_refused(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: Fallow merges `extends`, so a health ignore in a base file drops findings."""
    files = {
        ".fallowrc.json": '{"extends": ["./config/base.json"]}\n',
        "config/base.json": FALLOW_BASE,
    }
    message = refusal(project(tmp_path, files))
    assert "config/base.json:1 sets ignore" in message
    toml = {
        "fallow.toml": 'extends = ["config/base.toml"]\n',
        "config/base.toml": '[health]\nignore = ["a"]\n',
    }
    assert "config/base.toml:2 sets ignore" in refusal(project(tmp_path / "toml", toml))
    outside = {".fallowrc.json": '{"extends": ["../base.json"]}\n'}
    assert "extends a file outside the repository" in refusal(
        project(tmp_path / "out", outside)
    )


def fallow_gate(tmp_path: Path, command: list[str]) -> None:
    from project_setup import validate_command_output

    validate_command_output(
        command, tmp_path, {"type": "fallow", "path": "coverage/fallow.json"}
    )


SCAN = ["fallow", "--only", "dead-code,dupes,health", "--fail-on-issues"]


@pytest.mark.parametrize(
    "extra",
    [
        ["--config", "config/other.json"],
        ["-c", "config/other.json"],
        ["--config=config/other.json"],
    ],
)
def test_a_fallow_gate_reads_the_config_it_names(
    tmp_path: Path, extra: list[str]
) -> None:
    """HE-NO-SWITCH-OFF: a gate that names another config is judged by that config."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config/other.json").write_text(FALLOW_BASE)
    with pytest.raises(ValueError, match="config/other.json:1 sets ignore"):
        fallow_gate(tmp_path, [*SCAN, *extra])
    (tmp_path / "config/other.json").write_text('{"health": {"maxCrap": 30}}\n')
    fallow_gate(tmp_path, [*SCAN, *extra])


@pytest.mark.parametrize(
    "extra",
    [
        ["src"],
        ["--workspace", "app"],
        ["-w", "app"],
        ["--changed-since", "main"],
        ["--root", "app"],
        ["-r", "app"],
        ["--changed-workspaces", "main"],
    ],
)
def test_a_fallow_gate_that_narrows_the_scan_fails(
    tmp_path: Path, extra: list[str]
) -> None:
    """HE-NO-SWITCH-OFF: the combined scan covers the whole project; a path, workspace, root or changed-since filter leaves files out."""
    with pytest.raises(ValueError, match="Fallow scans must cover the whole project"):
        fallow_gate(tmp_path, [*SCAN, *extra])
    fallow_gate(tmp_path, SCAN)
    fallow_gate(
        tmp_path,
        [
            "fallow",
            "audit",
            "--base",
            "origin/develop",
            "--gate",
            "all",
            "--format",
            "json",
            "--output-file",
            "coverage/fallow.json",
        ],
    )


def test_the_entry_judge_scans_only_the_files_its_entries_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The judge costs no whole-tree copy or scan: a finding of a file does not depend on other files."""
    import gitleaks_entries

    root = project(tmp_path, {"secret.txt": KEY, "big/a.txt": "x\n"})
    past = git(root, "rev-parse", "HEAD")
    (root / "secret.txt").unlink()
    commit(root, "remove")
    (root / ".gitleaksignore").write_text(f"{past}:secret.txt:{RULE}:1\n")

    def refuse(*_arguments: object) -> None:
        raise AssertionError("the judge copied the whole tree")

    monkeypatch.setattr(gitleaks_entries, "copy_scan_tree", refuse, raising=False)
    copied: list[str] = []
    real = gitleaks_entries.shutil.copy2

    def spy(source: str | Path, target: str | Path, **options: bool) -> str:
        copied.append(Path(source).name)
        return str(real(source, target))

    monkeypatch.setattr(gitleaks_entries.shutil, "copy2", spy)
    validate_entries(root, 900)
    assert "a.txt" not in copied


def test_every_installed_checkout_fetches_the_whole_history() -> None:
    """The entry judge needs each commit that an entry names; a shallow checkout would read a good entry as missing."""
    import yaml
    from ci_jobs import CHECKOUT
    from conftest import SOURCE

    for name in (".github/hard-eng.yml", ".github/workflows/hard-eng.yml"):
        workflow = yaml.safe_load((SOURCE / name).read_text())
        checkouts = [
            step
            for job in workflow["jobs"].values()
            for step in job.get("steps", [])
            if str(step.get("uses", "")).startswith("actions/checkout@")
        ]
        assert checkouts, name
        assert all(step["with"]["fetch-depth"] == 0 for step in checkouts), name
    template = (SOURCE / ".github/hard-eng.yml").read_text()
    copied = CHECKOUT.search(template)
    assert copied is not None
    assert "fetch-depth: 0" in copied[0]


@pytest.mark.parametrize(
    "extra",
    [
        ["--save-snapshot", "snap.json"],
        ["--save-regression-baseline", "base.json"],
        ["--parent-run", "run-1"],
        ["--runtime-coverage", "cov.json"],
        ["--mark-viewed", "a.ts"],
    ],
)
def test_a_fallow_option_value_is_not_a_scan_path(
    tmp_path: Path, extra: list[str]
) -> None:
    """The words that Fallow's own options take are values, so they never read as a path that narrows the scan."""
    fallow_gate(tmp_path, [*SCAN, *extra])


@pytest.mark.parametrize(
    "extra",
    [["-cconfig/other.json"], ["-c", "config/other.json"], ["-rapp"], ["-wapp"]],
)
def test_fallow_short_options_are_read_the_way_fallow_reads_them(
    tmp_path: Path, extra: list[str]
) -> None:
    """HE-NO-SWITCH-OFF: `-cFILE` names a config and `-rDIR` or `-wNAME` narrows, exactly as the long forms do."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config/other.json").write_text(FALLOW_BASE)
    with pytest.raises(
        ValueError, match="config/other.json:1 sets ignore|cover the whole project"
    ):
        fallow_gate(tmp_path, [*SCAN, *extra])


def test_a_fallow_ignore_in_an_npm_extended_package_is_refused(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: Fallow loads `npm:` extends from node_modules or from a workspace package; the real loader merged the ignore."""
    installed = {
        ".fallowrc.json": '{"extends": ["npm:mycfg"]}\n',
        "node_modules/mycfg/package.json": '{"name": "mycfg", "main": "cfg.json"}\n',
        "node_modules/mycfg/cfg.json": FALLOW_BASE,
    }
    assert "node_modules/mycfg/cfg.json:1 sets ignore" in refusal(
        project(tmp_path / "a", installed)
    )
    scoped = {
        ".fallowrc.json": '{"extends": ["npm:@team/cfg/shared.json"]}\n',
        "packages/cfg/package.json": '{"name": "@team/cfg"}\n',
        "packages/cfg/shared.json": FALLOW_BASE,
    }
    assert "packages/cfg/shared.json:1 sets ignore" in refusal(
        project(tmp_path / "b", scoped)
    )
    clean = dict(
        installed, **{"node_modules/mycfg/cfg.json": '{"health": {"maxCrap": 30}}\n'}
    )
    validate_whole_project(project(tmp_path / "c", clean))
    missing = {".fallowrc.json": '{"extends": ["npm:absent"]}\n'}
    validate_whole_project(project(tmp_path / "d", missing))


@pytest.mark.parametrize(
    "url", ["https://example.org/base.json", "http://example.org/base.json"]
)
def test_a_remote_fallow_extends_is_refused(tmp_path: Path, url: str) -> None:
    files = {".fallowrc.json": '{"extends": ["' + url + '"]}\n'}
    assert ".fallowrc.json:1 extends a remote file" in refusal(project(tmp_path, files))


@pytest.mark.parametrize(
    "path", ["/etc/hosts", "../outside.txt", "docs/../../outside.txt"]
)
@pytest.mark.parametrize("past", [False, True])
def test_an_entry_path_outside_the_repository_is_a_clear_refusal(
    tmp_path: Path, path: str, past: bool
) -> None:
    """HE-NO-SWITCH-OFF: an entry that names a path outside the repository is refused with its line, never a crash."""
    root = project(tmp_path, {"README.md": "fixture\n"})
    sha = git(root, "rev-parse", "HEAD")
    prefix = f"{sha}:" if past else ""
    (root / ".gitleaksignore").write_text(f"{prefix}{path}:{RULE}:1\n")
    with pytest.raises(
        ValueError, match=r"\.gitleaksignore:1 .*outside the repository"
    ):
        validate_entries(root, 900)
