"""Rust lint switch-offs in attributes, Cargo settings, flags and Clippy settings."""

from pathlib import Path

import pytest
from test_strict_refusals import project, refusal
from whole_project import validate_whole_project

ALLOW = "al" + "low"
EXPECT = "ex" + "pect"

SPACED = [
    f"# [{ALLOW}(dead_code)]\nfn a() {{}}\n",
    f"#  [ {ALLOW} (dead_code)]\nfn a() {{}}\n",
    f"# ! [{ALLOW}(unused)]\n",
    f"#![ {EXPECT}(unused)]\n",
    f"#[cfg_attr(test, {ALLOW}(dead_code))]\nfn a() {{}}\n",
    "#[rustfmt::skip]\nfn a() {}\n",
    "# [ rustfmt :: skip ]\nfn a() {}\n",
    "#[cfg_attr(test, rustfmt::skip)]\nfn a() {}\n",
]


@pytest.mark.parametrize("text", SPACED)
def test_a_spaced_or_formatter_attribute_is_a_switch_off(
    tmp_path: Path, text: str
) -> None:
    """HE-NO-SWITCH-OFF: Rust ignores blanks between `#`, `!` and `[`, so the check does too; `rustfmt::skip` turns the formatter off."""
    assert "src/lib.rs:1 holds" in refusal(project(tmp_path, {"src/lib.rs": text}))


PASSING = [
    f"/// Never add #[{ALLOW}(x)] here.\nfn a() {{}}\n",
    f"// #[{ALLOW}(x)] is refused\nfn a() {{}}\n",
    f"/* #[{ALLOW}(x)] and #[{EXPECT}(y)] */\nfn a() {{}}\n",
    f'const NOTE: &str = "use #[{ALLOW}(dead_code)] sparingly";\n',
    f'const RAW: &str = r#"#[{ALLOW}(dead_code)]"#;\n',
    f'const LONG: &str = "first\n#[{ALLOW}(x)]\nlast";\n',
    "fn rustfmt_skip() {}\n",
]


@pytest.mark.parametrize("text", PASSING)
def test_rust_comments_and_strings_that_name_an_attribute_pass(
    tmp_path: Path, text: str
) -> None:
    """HE-NO-SWITCH-OFF: only code counts; a comment, a doc comment or a string that names the attribute is text."""
    validate_whole_project(project(tmp_path, {"src/lib.rs": text}))


def test_ordinary_rust_attributes_pass(tmp_path: Path) -> None:
    passing = (
        "#[derive(Debug)]\n#[cfg(test)]\n#[ignored_name]\n#[test]\n"
        '#[cfg_attr(feature = "x", derive(Debug))]\nstruct A;\n'
        "fn allow(x: u8) -> u8 { x }\n"
    )
    validate_whole_project(project(tmp_path, {"src/lib.rs": passing}))


CARGO_CONFIGS = [
    ('[build]\nrustflags = ["-A", "warnings"]\n', 2),
    ('[build]\nrustflags = ["-Awarnings"]\n', 2),
    ('[build]\nrustflags = ["--allow", "dead_code"]\n', 2),
    ('[build]\nrustflags = ["--cap-lints", "allow"]\n', 2),
    ('[build]\nrustflags = "-A dead_code"\n', 2),
    ('[target.x86_64-unknown-linux-gnu]\nrustflags = ["-Aunused"]\n', 2),
    ('[env]\nRUSTFLAGS = "--cap-lints allow"\n', 2),
]


@pytest.mark.parametrize("name", [".cargo/config.toml", ".cargo/config"])
@pytest.mark.parametrize(("text", "line"), CARGO_CONFIGS)
def test_cargo_rust_flags_that_allow_lints_are_switch_offs(
    tmp_path: Path, name: str, text: str, line: int
) -> None:
    assert f"{name}:{line} sets rustflags" in refusal(project(tmp_path, {name: text}))


def test_cargo_rust_flags_that_deny_or_set_codegen_pass(tmp_path: Path) -> None:
    kept = '[build]\nrustflags = ["-D", "warnings", "-C", "target-cpu=native"]\n'
    validate_whole_project(project(tmp_path, {".cargo/config.toml": kept}))


@pytest.mark.parametrize(
    "text",
    [
        'env:\n  RUSTFLAGS: "-A warnings"\n',
        "env:\n  RUSTFLAGS: --cap-lints allow\n",
        "export RUSTFLAGS='-Adead_code'\n",
        "RUSTFLAGS=--allow=unused cargo build\n",
    ],
)
def test_a_rustflags_variable_that_allows_lints_is_refused(
    tmp_path: Path, text: str
) -> None:
    name = ".github/workflows/rust.yml" if "env:" in text else "build.sh"
    assert f"{name}:" in refusal(project(tmp_path, {name: text}))
    validate_whole_project(
        project(
            tmp_path / "ok",
            {
                name: text.replace("-A", "-D")
                .replace("--allow", "--deny")
                .replace("--cap-lints allow", "--cap-lints forbid")
            },
        )
    )


CLIPPY = [
    ("cognitive-complexity-threshold = 30\n", "cognitive-complexity-threshold"),
    ("too-many-arguments-threshold = 8\n", "too-many-arguments-threshold"),
    ("too-many-lines-threshold = 200\n", "too-many-lines-threshold"),
    ("type-complexity-threshold = 500\n", "type-complexity-threshold"),
]


@pytest.mark.parametrize("name", ["clippy.toml", ".clippy.toml"])
@pytest.mark.parametrize(("text", "key"), CLIPPY)
def test_a_raised_clippy_threshold_is_a_switch_off(
    tmp_path: Path, name: str, text: str, key: str
) -> None:
    assert f"{name}:1 sets {key}" in refusal(project(tmp_path, {name: text}))


def test_clippy_thresholds_at_or_below_the_default_pass(tmp_path: Path) -> None:
    kept = 'cognitive-complexity-threshold = 25\ntoo-many-arguments-threshold = 5\ndisallowed-names = ["foo"]\nmsrv = "1.70"\n'
    validate_whole_project(project(tmp_path, {"clippy.toml": kept}))
