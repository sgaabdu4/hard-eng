"""Rust lint switch-offs in attributes, Cargo settings, flags and Clippy settings."""

from pathlib import Path

import pytest
from comments import validate_suppressions
from conftest import change
from test_strict_refusals import project, refusal
from whole_project import validate_whole_project

RF = "rust" + "flags"
UPPER = RF.upper()
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


def fill(text: str) -> str:
    return text.replace("@LOW@", RF).replace("@UP@", UPPER)


CARGO_CONFIGS = [
    ('[build]\n@LOW@ = ["-A", "warnings"]\n', 2),
    ('[build]\n@LOW@ = ["-Awarnings"]\n', 2),
    ('[build]\n@LOW@ = ["--allow", "dead_code"]\n', 2),
    ('[build]\n@LOW@ = ["--cap-lints", "allow"]\n', 2),
    ('[build]\n@LOW@ = "-A dead_code"\n', 2),
    ('[target.x86_64-unknown-linux-gnu]\n@LOW@ = ["-Aunused"]\n', 2),
    ('[env]\n@UP@ = "--cap-lints allow"\n', 2),
]


@pytest.mark.parametrize("name", [".cargo/config.toml", ".cargo/config"])
@pytest.mark.parametrize(("text", "line"), CARGO_CONFIGS)
def test_cargo_rust_flags_that_allow_lints_are_switch_offs(
    tmp_path: Path, name: str, text: str, line: int
) -> None:
    message = refusal(project(tmp_path, {name: fill(text)}))
    assert f"{name}:{line} sets {RF}" in message


def test_cargo_rust_flags_that_deny_or_set_codegen_pass(tmp_path: Path) -> None:
    kept = '[build]\n@LOW@ = ["-D", "warnings", "-C", "target-cpu=native"]\n'
    validate_whole_project(project(tmp_path, {".cargo/config.toml": fill(kept)}))


@pytest.mark.parametrize(
    "text",
    [
        'env:\n  @UP@: "-A warnings"\n',
        "env:\n  @UP@: --cap-lints allow\n",
        "export @UP@='-Adead_code'\n",
        "@UP@=--allow=unused cargo build\n",
    ],
)
def test_a_rust_flags_variable_that_allows_lints_is_refused(
    tmp_path: Path, text: str
) -> None:
    name = ".github/workflows/rust.yml" if "env:" in text else "build.sh"
    assert f"{name}:" in refusal(project(tmp_path, {name: fill(text)}))
    validate_whole_project(
        project(
            tmp_path / "ok",
            {
                name: fill(text)
                .replace("-A", "-D")
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
    ("max-struct-bools = 4\n", "max-struct-bools"),
    ("max-fn-params-bools = 4\n", "max-fn-params-bools"),
    ("large-error-threshold = 256\n", "large-error-threshold"),
    ("max-trait-bounds = 9\n", "max-trait-bounds"),
]


@pytest.mark.parametrize("name", ["clippy.toml", ".clippy.toml"])
@pytest.mark.parametrize(("text", "key"), CLIPPY)
def test_a_raised_clippy_threshold_is_a_switch_off(
    tmp_path: Path, name: str, text: str, key: str
) -> None:
    assert f"{name}:1 sets {key}" in refusal(project(tmp_path, {name: fill(text)}))


def test_clippy_thresholds_at_or_below_the_default_pass(tmp_path: Path) -> None:
    kept = 'cognitive-complexity-threshold = 25\ntoo-many-arguments-threshold = 5\ndisallowed-names = ["foo"]\nmsrv = "1.70"\n'
    validate_whole_project(project(tmp_path, {"clippy.toml": kept}))


def test_every_clippy_limit_is_a_key_that_clippy_reads() -> None:
    """The list is Clippy's own numeric keys; the bool names that Clippy rejects as unknown fields are not in it."""
    from rust_settings import CLIPPY_DEFAULTS

    assert "struct-excessive-bools" not in CLIPPY_DEFAULTS
    assert "fn-params-excessive-bools" not in CLIPPY_DEFAULTS
    assert CLIPPY_DEFAULTS["max-struct-bools"] == 3
    assert len(CLIPPY_DEFAULTS) >= 20


PROSE = [
    ("README.md", "Set @UP@='-A warnings' only on your own machine.\n"),
    ("CONTRIBUTING.md", "```\n@UP@=-Adead_code cargo build\n```\n"),
    ("notes.txt", "@UP@ = -A unused\n"),
    (".github/workflows/rust.yml", "# Never set @UP@ to -A warnings here.\n"),
    ("build.sh", 'echo "the @UP@ variable must not hold -A warnings"\n'),
]


@pytest.mark.parametrize(("name", "text"), PROSE)
def test_prose_that_names_rust_flags_is_not_an_assignment(
    tmp_path: Path, name: str, text: str
) -> None:
    """Only a workflow, script or config line that assigns the flags counts; prose and notes pass."""
    validate_whole_project(project(tmp_path, {name: fill(text)}))


RUST_GATES = [
    ["cargo", "clippy", "--", "-A", "clippy::all"],
    ["cargo", "clippy", "--", "-Aclippy::all"],
    ["cargo", "clippy", "--", "--allow", "warnings"],
    ["cargo", "clippy", "--config", "build.@LOW@=['-Awarnings']"],
    ["cargo", "clippy", "--config=build.@LOW@=['-A', 'warnings']"],
    ["cargo", "clippy", "--", "--cap-lints", "allow"],
]


@pytest.mark.parametrize("command", RUST_GATES)
def test_a_cargo_gate_that_allows_lints_fails(
    tmp_path: Path, command: list[str]
) -> None:
    """HE-NO-SWITCH-OFF: a gate command can allow lints as a flag, a config value or a variable."""
    from gate_config import Gate, validate_gate

    gate: Gate = {
        "name": "clippy",
        "role": "lint",
        "command": [fill(word) for word in command],
    }
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_gate(gate, tmp_path, set())
    kept: Gate = {
        "name": "clippy",
        "role": "lint",
        "command": ["cargo", "clippy", "--", "-D", "warnings"],
    }
    validate_gate(kept, tmp_path, set())


WRAPPED = [
    f"#[cfg_attr(\n    test,\n    {ALLOW}(dead_code)\n)]\nfn a() {{}}\n",
    f"#[cfg_attr(\n    test,\n    {EXPECT}(unused),\n)]\nfn a() {{}}\n",
    "#[cfg_attr(all(), ignore)]\nfn a() {}\n",
    "#[cfg_attr(\n    test,\n    ignore\n)]\nfn a() {}\n",
    f"#![cfg_attr(\n    test,\n    {ALLOW}(unused)\n)]\n",
    f"#[cfg_attr(test, derive(Debug), {ALLOW}(dead_code))]\nfn a() {{}}\n",
]


@pytest.mark.parametrize("text", WRAPPED)
def test_a_wrapped_or_ignoring_cfg_attr_is_a_switch_off(
    tmp_path: Path, text: str
) -> None:
    """HE-NO-SWITCH-OFF: an attribute that Rust reads across lines is judged as one, and `ignore` inside `cfg_attr` counts like `allow`."""
    assert "src/lib.rs:1 holds" in refusal(project(tmp_path, {"src/lib.rs": text}))


WRAPPED_PASSING = [
    "#[cfg_attr(\n    test,\n    derive(Debug)\n)]\nstruct A;\n",
    '#[cfg_attr(feature = "ignore", derive(Debug))]\nstruct A;\n',
    f'const A: &str = "#[cfg_attr(\n    test,\n    {ALLOW}(dead_code)\n)]";\n',
    "#[cfg_attr(test, derive(Debug))]\nstruct ignored;\n",
]


@pytest.mark.parametrize("text", WRAPPED_PASSING)
def test_a_cfg_attr_without_a_switch_off_passes(tmp_path: Path, text: str) -> None:
    validate_whole_project(project(tmp_path, {"src/lib.rs": text}))


def test_a_line_added_inside_a_wrapped_cfg_attr_is_a_switch_off(
    tmp_path: Path,
) -> None:
    before = "#[cfg_attr(\n    test,\n    derive(Debug)\n)]\nstruct A;\n"
    after = f"#[cfg_attr(\n    test,\n    derive(Debug),\n    {ALLOW}(dead_code)\n)]\nstruct A;\n"
    root = change(tmp_path, "src/lib.rs", before, after)
    with pytest.raises(ValueError, match=r"src/lib.rs:\d adds"):
        validate_suppressions(root, "HEAD")


def test_a_rust_file_without_cfg_attr_is_not_masked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The quick check tests the text for `cfg_attr` first, so an ordinary Rust file costs no masking."""
    import comments

    def refuse(*_arguments: object) -> str:
        raise AssertionError("masked a file that holds no cfg_attr")

    monkeypatch.setattr(comments, "code_without_comments", refuse)
    monkeypatch.setattr(comments, "without_literals", refuse)
    source = "fn a() {}\n" * 50
    root = project(tmp_path, {"src/lib.rs": source})
    assert (
        comments.rust_cfg_attr_hits(root, "src/lib.rs", [(1, "fn a() {}")], "adds")
        == []
    )
    wrapped = project(
        tmp_path / "w", {"src/lib.rs": "#[cfg_attr(test, derive(Debug))]\nstruct A;\n"}
    )
    with pytest.raises(AssertionError, match="masked"):
        comments.rust_cfg_attr_hits(wrapped, "src/lib.rs", [(1, "x")], "adds")
