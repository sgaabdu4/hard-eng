"""The comment rule: changed source files hold one-line comments at most."""

import json
import re
import subprocess
import time
from pathlib import Path
from types import ModuleType

import pytest
from comments import RETRY_WORDS, validate_comments, validate_suppressions
from conftest import SOURCE, commit, git, init
from shipping import ShippingPolicy
from switch_off_forms import RETRY_FORMS, RETRY_PASSES, RUFF_FORMS, SWITCHES, TEST_FLAGS

BLOCK = "Code comments are none by default"


@pytest.mark.parametrize(
    ("name", "text", "line"),
    [
        ("app.py", "x = 1\n# first\n# second\n", 2),
        ("app.py", "# one why\nx = 1  # trailing\ny = 2  # trailing\n", None),
        ("app.py", 'DOC = """\n# heading\n# another\n"""\n', None),
        ("app.py", "# noqa: E501\n# pyright: basic\nx = 1\n", None),
        ("app.py", "def f(:\n# broken\n# syntax\n", 2),
        ("lib/app.dart", "/// Adds.\n/// Twice.\nint add() => 1;\n", 1),
        ("src/app.ts", "/* one */\nconst a = 1;\n", None),
        ("src/app.ts", "const a = 1;\n/*\n * why\n */\n", None),
        ("src/app.ts", "/**\n * Explains.\n *\n * Again.\n */\n", 2),
        ("src/app.js", "/**\n * @param {string} p\n * @returns {number}\n */\n", None),
        ("src/lib.rs", "/// # Errors\n///\n/// Fails on I/O.\npub fn f() {}\n", None),
        ("src/lib.rs", "/// Reads.\n///\n/// # Errors\n/// Fails on I/O.\n", 1),
        ("app.py", "# why\n# noqa: E501\n# more why\n", 1),
        (
            "src/app.ts",
            "// eslint-disable-next-line\n// @ts-expect-error\nf();\n",
            None,
        ),
        ("src/app.ts", "const list = `\n* bullet\n* bullet\n`;\n", None),
        ("src/app.tsx", "const v = <p>You're in.</p>;\n// first\n// second\n", 2),
        ("run.sh", "#!/bin/sh\n# one why\necho\n", None),
        ("run.sh", "echo\n# first\n# second\n", 2),
        ("NOTES.md", "# a\n# b\n", None),
        ("src/app.ts", "const t = `\n// data\n// lines\n`;\n", None),
        ("src/app.ts", "const n = 1; /* why\ncontinued\n*/\n", 1),
        ("src/app.ts", "const x = 1; /*\n * One reason.\n */ const y = 2;\n", None),
        ("src/app.ts", "const t = `\\`\n// data\n// lines\n`;\n", None),
        ("run.sh", "x=$((1 << n))\n# first\n# second\n", 2),
        ("run.sh", 'echo "cat <<EOF"\n# first\n# second\n', 2),
        ("src/app.js", 'const p = /[/*]/;\nconst v = 1;\nconst e = "*/";\n', None),
        ("src/app.ts", "const r = a / b;\n// one\n// two\n", 2),
        ("run.sh", "cat <<EOF\n  EOF\n# data one\n# data two\nEOF\n", None),
        ("run.sh", 'value="\\""\n# first\n# second\n', 2),
        ("src/lib.rs", 'let s = r#"say "hi"\n// data\n// lines\n"#;\n', None),
        ("lib/app.dart", "final s = r'\\';\n// one\n// two\n", 2),
        ("src/app.ts", "const q = String.raw`\n// data\n// lines\n`;\n// a\n// b\n", 5),
        ("src/app.ts", "const t = `${\n// first\n// second\n1}`;\n", 2),
        ("src/app.ts", "const t = `a ${ {x: `}`}.x } b`;\n// one\n// two\n", 2),
        ("run.sh", "cat <<'123'\n# data\n# data\n123\n", None),
        ("run.sh", "cat <<EOF-JSON\n# data\nEOF-JSON\n# a\n# b\n", 4),
        (
            "src/app.js",
            'if (true) /[/*]/.test("x");\nconst a = 42;\nconst m = "*/";\n',
            None,
        ),
        ("src/app.js", "const r = f(x) / 2;\n// one\n// two\n", 2),
        ("run.sh", "cat <<A <<B\nx\nA\n# data\n# data\nB\n# a\n# b\n", 7),
        ("run.sh", 'cat <<EO"F"\nhello\nEOF\n# first\n# second\n', 4),
        ("lib/app.dart", "const s = '''\n// a\n// b\n''';\n", None),
        ("src/lib.rs", "fn f<'a>(x: &'a str) {}\n// one\n// two\n", 2),
        ("run.sh", "cat <<'EOF'\n# data\n# more\nEOF\n# after\n", None),
        ("run.sh", 'echo "\n# inside\n# string\n"\n', None),
        (".agents/skills/tool/run.sh", "echo\n# vendored\n# skill script\n", None),
    ],
)
def test_changed_source_holds_one_line_comments_only(
    tmp_path: Path, name: str, text: str, line: int | None
) -> None:
    """HE-COMMENT-LINES: a changed source file may hold only one-line comments."""
    init(tmp_path / "repo")
    root = tmp_path / "repo"
    (root / "README.md").write_text("fixture\n")
    commit(root, "baseline")
    (root / name).parent.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(text)
    if line is None:
        validate_comments(root, "HEAD")
    else:
        with pytest.raises(ValueError, match=BLOCK) as error:
            validate_comments(root, "HEAD")
        assert re.findall(rf"{name}:(\d+) holds", str(error.value)) == [str(line)]


def test_touched_files_answer_for_older_blocks_and_generated_output_is_skipped(
    tmp_path: Path,
) -> None:
    init(tmp_path / "repo")
    root = tmp_path / "repo"
    old = "# written long ago\n# across two lines\nx = 1\n"
    for name in ("touched.py", "untouched.py", "generated.g.py"):
        (root / name).write_text(old)
    (root / ".gitattributes").write_text("*.g.py linguist-generated=true\n")
    commit(root, "baseline")
    validate_comments(root, "HEAD")
    (root / "generated.g.py").write_text(old + "y = 2\n")
    validate_comments(root, "HEAD")
    (root / "touched.py").write_text(old + "y = 2\n")
    with pytest.raises(ValueError, match=r"touched\.py:1 holds a 2-line") as error:
        validate_comments(root, "HEAD")
    assert "untouched.py" not in str(error.value)


def test_the_install_change_keeps_older_blocks_in_files_its_tools_fixed(
    tmp_path: Path,
) -> None:
    init(tmp_path / "repo")
    root = tmp_path / "repo"
    old = "# written long ago\n# across two lines\nx = 1\n"
    (root / "app.py").write_text(old)
    commit(root, "baseline")
    (root / ".hooks").mkdir()
    (root / ".hooks/hard-eng.py").write_text("")
    (root / "app.py").write_text(old + "y = 2\n")
    validate_comments(root, "HEAD")
    (root / "app.py").write_text(old + "# added with the install\n# on two lines\n")
    with pytest.raises(ValueError, match=r"app\.py:4 holds a 2-line") as error:
        validate_comments(root, "HEAD")
    assert "app.py:1" not in str(error.value)
    (root / "app.py").write_text(old + "y = 2\n")
    commit(root, "Install Hard Eng")
    (root / "app.py").write_text(old + "z = 3\n")
    with pytest.raises(ValueError, match=r"app\.py:1 holds a 2-line"):
        validate_comments(root, "HEAD")


def test_the_install_change_compares_each_older_block_whole(tmp_path: Path) -> None:
    init(tmp_path / "repo")
    root = tmp_path / "repo"
    spaced = "x = 1\n# first\n#\n# old reason\n"
    (root / "app.py").write_text(spaced)
    commit(root, "baseline")
    (root / ".hooks").mkdir()
    (root / ".hooks/hard-eng.py").write_text("")
    (root / "app.py").write_text(spaced + "y = 2\n")
    validate_comments(root, "HEAD")
    (root / "app.py").write_text(spaced.replace("old reason", "new reason"))
    with pytest.raises(ValueError, match=r"app\.py:2 holds a 2-line"):
        validate_comments(root, "HEAD")


def test_pre_push_rejects_a_pushed_comment_block(
    tmp_path: Path, completed_plan: str, shipping_policy: ShippingPolicy
) -> None:
    root, bare = tmp_path / "repo", tmp_path / "origin.git"
    init(root)
    git(tmp_path, "init", "--bare", "-q", str(bare))
    git(root, "branch", "-M", "main")
    (root / ".hooks").mkdir()
    for source in (SOURCE / ".hooks").glob("*.py"):
        (root / ".hooks" / source.name).write_bytes(source.read_bytes())
    for name in ("PRODUCT.md", "DESIGN.md"):
        (root / name).write_text((SOURCE / name).read_text())
    check = {"name": "noop", "command": ["python3", "-c", "pass"]}
    gates: dict[str, object] = {
        "packages": [],
        "shipping": shipping_policy,
        "shared": [check],
    }
    (root / "hard-eng.gates.json").write_text(json.dumps(gates))
    commit(root, "baseline")
    git(root, "remote", "add", "origin", str(bare))
    git(root, "push", "-q", "origin", "main")
    hook = root / ".git/hooks/pre-push"
    hook.write_text(
        '#!/bin/sh\nexec python3 "$(git rev-parse --show-toplevel)/.hooks/hard-eng.py" pre-push\n'
    )
    hook.chmod(0o755)
    git(root, "switch", "-qc", "feature")
    (root / "PLAN.md").write_text(completed_plan)
    (root / "app.py").write_text("# narrates\n# the next line\nx = 1\n")
    commit(root, "add app")
    push = ["git", "push", "-q", "origin", "feature"]
    rejected = subprocess.run(
        push, cwd=root, capture_output=True, text=True, check=False
    )
    assert rejected.returncode != 0
    assert "app.py:1 holds a 2-line comment block" in rejected.stderr
    (root / "app.py").write_text("# why x starts at one\nx = 1\n")
    git(root, "commit", "-qam", "compress the comment")
    accepted = subprocess.run(
        push, cwd=root, capture_output=True, text=True, check=False
    )
    assert accepted.returncode == 0, accepted.stderr[-2000:]


@pytest.mark.parametrize("shipping", [True, False])
def test_check_without_base_covers_committed_branch_changes(
    tmp_path: Path, shipping_policy: ShippingPolicy, shipping: bool
) -> None:
    root = tmp_path / "repo"
    init(root)
    gates: dict[str, object] = {"packages": [], "shared": []}
    if shipping:
        gates["shipping"] = shipping_policy
    (root / "hard-eng.gates.json").write_text(json.dumps(gates))
    commit(root, "baseline")
    git(root, "branch", "-M", shipping_policy["base"] if shipping else "main")
    git(root, "switch", "-qc", "feature")
    (root / "app.py").write_text("# narrates\n# the next line\nx = 1\n")
    commit(root, "add app")
    validate_comments(root, "HEAD")
    with pytest.raises(ValueError, match=r"app\.py:1 holds a 2-line"):
        validate_comments(root, None)


OFF = "A change must not switch a check off"


def switch_root(tmp_path: Path, name: str, before: str) -> Path:
    init(tmp_path / "repo")
    root = tmp_path / "repo"
    (root / "README.md").write_text("fixture\n")
    if before:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(before)
    commit(root, "baseline")
    return root


def refusal(tmp_path: Path, name: str, text: str) -> tuple[Path, str]:
    root = switch_root(tmp_path, name, "")
    (root / name).parent.mkdir(parents=True, exist_ok=True)
    (root / name).write_text("ok = 1\n" + text)
    with pytest.raises(ValueError, match=OFF) as error:
        validate_suppressions(root, "HEAD")
    return root, str(error.value)


@pytest.mark.parametrize(("name", "text", "pattern"), SWITCHES)
def test_added_switch_off_fails_naming_file_line_and_pattern(
    tmp_path: Path, name: str, text: str, pattern: str
) -> None:
    """HE-NO-SWITCH-OFF: an added suppression, skip or focus fails."""
    message = refusal(tmp_path, name, text)[1]
    assert f"{name}:2 adds {pattern!r}" in message
    assert "fix the cause" in message


@pytest.mark.parametrize(("text", "pattern"), RUFF_FORMS)
def test_each_ruff_suppression_form_is_refused(
    tmp_path: Path, text: str, pattern: str
) -> None:
    """HE-NO-SWITCH-OFF: every Ruff, isort and formatter off comment fails, in any letter case."""
    root = switch_root(tmp_path, "app.py", "")
    (root / "app.py").write_text(f"ok = 1\nx = 1  {text}\n")
    with pytest.raises(ValueError, match=OFF) as error:
        validate_suppressions(root, "HEAD")
    assert f"app.py:2 adds {pattern!r}" in str(error.value)


def test_the_word_for_a_ruff_comment_in_a_string_or_prose_passes(
    tmp_path: Path,
) -> None:
    root = switch_root(tmp_path, "app.py", "")
    (root / "app.py").write_text(
        "word = 'no" + "qa'\nnote = 'fmt: o" + "ff'\nmsg = 'isort: sk" + "ip'\n"
        "# the no" + "qa word is only prose here, and so is ruff: no" + "qa\n"
        "# yapf was the old formatter\n# yapf: enable\n"
    )
    validate_suppressions(root, "HEAD")


def test_an_external_diff_tool_does_not_hide_an_added_switch_off(
    tmp_path: Path,
) -> None:
    root = switch_root(tmp_path, "app.py", "ok = 1\n")
    git(root, "config", "diff.external", "true")
    (root / "app.py").write_text("ok = 1\nx = 1  # no" + "qa\n")
    with pytest.raises(ValueError, match=OFF) as error:
        validate_suppressions(root, "HEAD")
    assert "app.py:2 adds" in str(error.value)


ROUTE_FILES = (
    "app.py",
    "a.ts",
    "test/a_test.dart",
    "ios/RunnerTests/ATests.swift",
    "config.yml",
    ".gitleaksignore",
)
ROUTES = [next(row for row in SWITCHES if row[0] == name) for name in ROUTE_FILES]
ROUTES += [row for row in RETRY_FORMS if row[0] == "playwright.config.ts"]


@pytest.mark.parametrize(("name", "text", "pattern"), ROUTES)
def test_switch_off_already_in_the_project_is_not_flagged(
    tmp_path: Path, name: str, text: str, pattern: str
) -> None:
    root = switch_root(tmp_path, name, text)
    (root / name).write_text(text + "\n")
    validate_suppressions(root, "HEAD")


@pytest.mark.parametrize(("name", "text", "form"), RETRY_FORMS)
def test_an_added_retry_fails_naming_file_line_and_form(
    tmp_path: Path, name: str, text: str, form: str
) -> None:
    """HE-NO-SWITCH-OFF: an added test retry fails and passes again once it is gone."""
    root, message = refusal(tmp_path, name, text)
    assert f"{name}:2 adds {form!r}" in message
    (root / name).write_text("ok = 1\n")
    validate_suppressions(root, "HEAD")


@pytest.mark.parametrize(("name", "text"), RETRY_PASSES)
def test_retry_words_outside_tests_and_test_config_pass(
    tmp_path: Path, name: str, text: str
) -> None:
    root = switch_root(tmp_path, name, "")
    (root / name).parent.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(text)
    validate_suppressions(root, "HEAD")


def test_scaffold_paths_and_ordinary_words_are_not_flagged(tmp_path: Path) -> None:
    root = switch_root(tmp_path, "app.py", "")
    (root / ".hooks").mkdir()
    (root / ".hooks/tool.py").write_text("x = 1  # no" + "qa\n")
    (root / "app.py").write_text("skip = True\nskipped = pytest_skip_reason\n")
    (root / "lib").mkdir()
    (root / "lib/a.dart").write_text("final f = Foo(ski" + "p: false);\n")
    (root / ".semgrepignore").write_text("# Include production and tests.\n\n")
    (root / "notes.md").write_text("Nosy semantics.\n")
    validate_suppressions(root, "HEAD")


def test_the_word_for_a_skipped_test_outside_a_raise_passes(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: a class, a catch and a prose line that name the skip error stay allowed."""
    root = switch_root(tmp_path, "app.py", "")
    for name, text in (
        ("src/app.py", "class Ski" + "pTest(Exception):\n    pass\n"),
        ("src/errors.py", "try:\n    run()\nexcept Ski" + "pTest:\n    pass\n"),
        ("notes.md", "A raise Ski" + "pTest is prose here.\n"),
    ):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    validate_suppressions(root, "HEAD")


@pytest.mark.parametrize(("text", "line"), TEST_FLAGS)
def test_a_class_mark_is_refused_only_when_the_class_holds_a_test(
    tmp_path: Path, text: str, line: int | None
) -> None:
    """HE-NO-SWITCH-OFF: a helper class may stay out of collection; a class with a test may not."""
    root = switch_root(tmp_path, "tests/doubles.py", "")
    (root / "tests").mkdir()
    (root / "tests/doubles.py").write_text(text)
    if line is None:
        validate_suppressions(root, "HEAD")
        return
    with pytest.raises(ValueError, match=OFF) as error:
        validate_suppressions(root, "HEAD")
    assert f"tests/doubles.py:{line} adds '__test__ " + "= False'" in str(error.value)


@pytest.mark.parametrize(
    ("name", "table", "sign"),
    [
        ("pyproject.toml", "[tool.pytest.ini_options]", " = "),
        ("pyproject.toml", "[tool.pytest]", " = "),
        ("pyproject.toml", "[ tool.pytest.ini_options ]", " = "),
        ("pytest.ini", "[pytest]", " = "),
        ("pytest.ini", "[pytest]", ": "),
        ("setup.cfg", "[tool:pytest]", " = "),
        ("pytest.toml", "[pytest]", " = "),
        (".pytest.toml", "[pytest]", " = "),
        (".pytest.ini", "[pytest]", " = "),
    ],
)
def test_a_retry_count_in_a_pytest_table_fails_at_its_line(
    tmp_path: Path, name: str, table: str, sign: str
) -> None:
    """HE-NO-SWITCH-OFF: the count of the pytest-retry plugin counts only in a pytest table."""
    text = table + "\nminversion = '8'\nre" + "tries" + sign + "2\n"
    message = refusal(tmp_path, name, text)[1]
    assert f"{name}:4 adds " + repr("re" + "tries") in message


@pytest.mark.parametrize(("name", "text", "form"), RETRY_FORMS)
def test_every_refused_retry_form_holds_a_word_that_loads_the_rules(
    name: str, text: str, form: str
) -> None:
    assert any(word in text for word in RETRY_WORDS), (name, form)


@pytest.mark.parametrize("name", ["test/a_test.dart", "src/a.test.ts"])
def test_a_long_line_of_open_brackets_ends_fast(name: str) -> None:
    from retry_forms import retry_form

    line = "test('x', " + "f(" * 1000 + ", re" + "try: 2)"
    started = time.perf_counter()
    retry_form(name, line)
    assert time.perf_counter() - started < 1


def test_a_skip_name_used_as_a_value_is_refused_only_in_a_test_file(
    tmp_path: Path,
) -> None:
    """HE-NO-SWITCH-OFF: a callback argument named it is data; a skip call is not."""
    root = switch_root(tmp_path, "app.py", "")
    (root / "src").mkdir()
    (root / "src/list.ts").write_text(
        "const a = items.filter((it) => it.sk" + "ip);\n"
        "if (it.on" + "ly) return;\n"
        "const b = todos.map(it => it.to" + "do);\n"
    )
    validate_suppressions(root, "HEAD")
    for name, text in (
        ("src/list.test.ts", "const run = flag ? it.sk" + "ip : it;\n"),
        ("src/list.ts", "it.sk" + "ip('x', () => {});\n"),
    ):
        (root / name).write_text(text)
        with pytest.raises(ValueError, match=f"{name}:1 adds") as error:
            validate_suppressions(root, "HEAD")
        assert OFF in str(error.value)
        (root / name).unlink()


def test_names_close_to_a_skip_form_pass(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: a helper, a longer name and an ordinary pytest import stay allowed."""
    root = switch_root(tmp_path, "app.py", "")
    for name, text in (
        (
            "tests/test_rows.py",
            "rows = ski" + "p_rows(data)\nfrom pytest import fixture\n",
        ),
        ("src/page.ts", "const slow = ski" + "p ? 1 : 2;\n"),
        ("src/page.test.ts", "const testSki" + "p = 1;\nconst it_ski" + "p = 2;\n"),
        ("src/guard.test.ts", "expect.fa" + "il('x');\nassert.fa" + "il('y');\n"),
    ):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    validate_suppressions(root, "HEAD")


def test_skip_argument_counts_only_in_test_files(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: a paging value named skip is data; a skipped test is not."""
    root = switch_root(tmp_path, "app.py", "")
    for name, text in (
        ("lib/page.dart", "final rows = query(ski" + "p: offset, so" + "lo: true);\n"),
        ("src/page.ts", "const rows = find({ ski" + "p: true, on" + "ly: true });\n"),
        (
            "src/page.test.ts",
            "const rows = find({ ski" + "p: 10, on" + "ly: 'admin' });\n",
        ),
    ):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    validate_suppressions(root, "HEAD")
    (root / "test").mkdir()
    (root / "test/page_test.dart").write_text("test('t', () {}, ski" + "p: offset);\n")
    with pytest.raises(ValueError, match="test/page_test.dart:1 adds 'ski" + "p:'"):
        validate_suppressions(root, "HEAD")


@pytest.mark.parametrize(
    ("text", "pattern"),
    [
        ("x = 1  # pyre-ig" + "nore", "# pyre-ig" + "nore"),
        ("x = 1  # pyre-ig" + "nore[16]", "# pyre-ig" + "nore"),
        ("x = 1  # pyre-fix" + "me[16]", "# pyre-fix" + "me"),
    ],
)
def test_the_pyre_ignore_comments_are_refused(
    tmp_path: Path, text: str, pattern: str
) -> None:
    """HE-NO-SWITCH-OFF: Pyrefly honours pyre comments when permissive ignores are on."""
    root = switch_root(tmp_path, "app.py", "")
    (root / "app.py").write_text(f"ok = 1\n{text}\n")
    with pytest.raises(ValueError, match=OFF) as error:
        validate_suppressions(root, "HEAD")
    assert f"app.py:2 adds {pattern!r}" in str(error.value)


@pytest.mark.parametrize(
    "form",
    ["to" + "do", "to" + "doIf", "fai" + "ling", "fa" + "ils", "i" + "f", "run" + "If"],
)
@pytest.mark.parametrize("caller", ["it", "test", "describe"])
def test_the_todo_and_conditional_test_forms_are_refused(
    tmp_path: Path, caller: str, form: str
) -> None:
    """HE-NO-SWITCH-OFF: Bun and Vitest skip or weaken a test with these forms too."""
    root = switch_root(tmp_path, "a.test.ts", "")
    (root / "a.test.ts").write_text(f"{caller}.{form}(cond)('s', () => {{}});\n")
    with pytest.raises(ValueError, match=OFF) as error:
        validate_suppressions(root, "HEAD")
    assert f"a.test.ts:1 adds '{caller}.{form}(" in str(error.value)


@pytest.mark.parametrize(
    "form",
    [
        "test.concurrent.sk" + "ip(",
        "it.concurrent.to" + "do(",
        "describe.sequential.sk" + "ip(",
        "describe.shuffle.on" + "ly(",
        "test.concurrent.sequential.fix" + "me(",
    ],
)
def test_a_chained_modifier_does_not_hide_a_switched_off_test(
    tmp_path: Path, form: str
) -> None:
    """HE-NO-SWITCH-OFF: Vitest and Bun chain concurrent, sequential and shuffle before the switch-off word."""
    root = switch_root(tmp_path, "a.test.ts", "")
    (root / "a.test.ts").write_text(f"{form}'s', () => {{}});\n")
    with pytest.raises(ValueError, match=OFF) as error:
        validate_suppressions(root, "HEAD")
    assert f"a.test.ts:1 adds '{form}'" in str(error.value)


def test_a_normal_test_and_another_object_named_todo_pass(tmp_path: Path) -> None:
    root = switch_root(tmp_path, "a.test.ts", "")
    (root / "a.test.ts").write_text(
        "test('s', () => {});\nlist.to" + "do('x');\nit.each([1])('s', () => {});\n"
        "test.concurrent('s', () => {});\ndescribe.sequential('s', () => {});\n"
    )
    validate_suppressions(root, "HEAD")


ASSERTS = [
    ("tests/test_a.py", "def test_a():\n    assert f() == 1\n    assert g()\n"),
    ("src/a.test.ts", "test('a', () => {\n  expect(f()).toBe(1);\n});\n"),
    ("test/a_test.dart", "void main() {\n  expect(f(), 1);\n}\n"),
]


@pytest.mark.parametrize(("name", "text"), ASSERTS)
def test_net_loss_of_assertions_fails_naming_lines_and_count(
    tmp_path: Path, name: str, text: str
) -> None:
    """HE-NO-SWITCH-OFF: a net loss of test assertions fails."""
    root = switch_root(tmp_path, name, text)
    (root / name).write_text(
        text.replace("assert g()\n", "")
        .replace("expect(f()).toBe(1);", "f();")
        .replace("expect(f(), 1);", "f();")
    )
    with pytest.raises(ValueError, match=OFF) as error:
        validate_suppressions(root, "HEAD")
    assert "tests lose 1 assertion lines net (1 removed, 0 added)" in str(error.value)
    assert re.search(rf"removed at {re.escape(name)}:\d+", str(error.value))


@pytest.mark.parametrize(
    ("path", "kept", "removed", "name"),
    [
        (
            "tests/test_a.py",
            "def test_keeps():\n    assert a() == 1\n",
            "def test_two():\n    assert a() == 1\n",
            "test_two",
        ),
        (
            "src/a.test.ts",
            "it('keeps a', () => {\n  expect(a()).toBe(1);\n});\n",
            "it('adds two numbers', () => {\n  expect(a()).toBe(1);\n});\n",
            "adds two numbers",
        ),
        (
            "test/a_test.dart",
            "testWidgets('keeps a', (t) async {\n  expect(a(), 1);\n});\n",
            "testWidgets('shows a title', (t) async {\n  expect(a(), 1);\n});\n",
            "shows a title",
        ),
    ],
)
def test_a_record_written_the_way_the_message_says_is_accepted(
    tmp_path: Path, path: str, kept: str, removed: str, name: str
) -> None:
    root = switch_root(tmp_path, path, kept + removed)
    (root / path).write_text(kept)
    with pytest.raises(ValueError, match=OFF) as error:
        validate_suppressions(root, "HEAD")
    message = str(error.value)
    assert "the function name for a Python test" in message
    assert "the text between the quotes for it(), test() and testWidgets()" in message
    (root / "features/x").mkdir(parents=True)
    record = f"Removed test: {path} :: {name} :: test keeps proves it"
    (root / "features/x/PLAN.md").write_text(f"# Plan\n\n{record}\n")
    validate_suppressions(root, "HEAD")


def test_the_lost_assertion_message_says_what_the_record_covers(
    tmp_path: Path,
) -> None:
    name, text = ASSERTS[0]
    root = switch_root(tmp_path, name, text)
    (root / name).write_text(text.replace("assert g()\n", ""))
    with pytest.raises(ValueError, match=OFF) as error:
        validate_suppressions(root, "HEAD")
    message = str(error.value)
    assert "To remove a whole test, add `Removed test:" in message
    assert "the test name is the function name for a Python test" in message
    assert "An assertion in a test that stays must stay" in message
    assert "get an equal check" in message


@pytest.mark.parametrize(
    "name", ["tests/test_my file.py", "tests/test_tab\tfile.py", 'tests/test_"q" é.py']
)
def test_tracked_paths_git_quotes_still_fail_suppressions_and_lost_assertions(
    tmp_path: Path, name: str
) -> None:
    text = "def test_a():\n    assert f()\n    assert g()\n"
    root = switch_root(tmp_path, name, text)
    (root / name).write_text(text.replace("assert g()", "g()  # no" + "qa"))
    with pytest.raises(ValueError, match=OFF) as error:
        validate_suppressions(root, "HEAD")
    assert f"{name}:3 adds '# no" + "qa'" in str(error.value)
    assert f"removed at {name}:3" in str(error.value)


def test_deleting_a_test_file_without_replacement_fails(tmp_path: Path) -> None:
    root = switch_root(tmp_path, "tests/test_a.py", "def t():\n    assert f()\n")
    (root / "tests/test_a.py").unlink()
    with pytest.raises(ValueError, match=r"tests/test_a\.py:2"):
        validate_suppressions(root, "HEAD")


TWO_TESTS = (
    "test('keeps a', () => {\n  expect(a()).toBe(1);\n});\n"
    "test('duplicate of a', () => {\n  expect(a()).toBe(1);\n});\n"
)


@pytest.mark.parametrize(
    ("entry", "passes"),
    [
        (
            "Removed test: src/a.test.ts :: duplicate of a :: 'keeps a' proves the same",
            True,
        ),
        (
            "- Removed test: `src/a.test.ts` :: `duplicate of a` :: same as keeps a",
            True,
        ),
        ("Removed test: src/a.test.ts :: duplicate of a ::", False),
        ("Removed test: src/a.test.ts :: keeps a :: wrong test named", False),
        ("Removed test: src/b.test.ts :: duplicate of a :: wrong file", False),
        ("Removed test: src/a.test.ts :: duplicate :: shared prefix only", False),
        ("Removed test: src/a.test.ts :: toBe :: name only in the body", False),
    ],
)
def test_planned_removal_with_a_reason_allows_only_the_named_test(
    tmp_path: Path, entry: str, passes: bool
) -> None:
    root = switch_root(tmp_path, "src/a.test.ts", TWO_TESTS)
    (root / "src/a.test.ts").write_text(TWO_TESTS.split("test('duplicate")[0])
    (root / "features/x").mkdir(parents=True)
    (root / "features/x/PLAN.md").write_text(f"# Plan\n\n{entry}\n")
    if passes:
        validate_suppressions(root, "HEAD")
    else:
        with pytest.raises(ValueError, match=r"tests lose 1 assertion lines net"):
            validate_suppressions(root, "HEAD")


KEEP = "test('keeps a', () => {\n  expect(a()).toBe(1);\n});\n"


@pytest.mark.parametrize(
    ("before", "passes"),
    [
        (
            KEEP
            + "test(\n  'duplicate of a',\n  () => {\n    expect(a()).toBe(1);\n  },\n);\n",
            True,
        ),
        (
            KEEP
            + "test.each([null, ''])(\n  'duplicate of a',\n  (v) => {\n"
            + "    expect(a(v)).toBe(1);\n  },\n);\n",
            True,
        ),
        (
            KEEP
            + "test.each([1])('duplicate of a again', (v) => {\n  expect(a(v)).toBe(1);\n});\n",
            False,
        ),
        (
            KEEP.replace("});", "  expect('duplicate of a').toBe(name());\n});"),
            False,
        ),
    ],
)
def test_planned_removal_names_only_a_deleted_declaration(
    tmp_path: Path, before: str, passes: bool
) -> None:
    root = switch_root(tmp_path, "src/a.test.ts", before)
    (root / "src/a.test.ts").write_text(KEEP)
    (root / "features/x").mkdir(parents=True)
    (root / "features/x/PLAN.md").write_text(
        "Removed test: src/a.test.ts :: duplicate of a :: keeps a proves it\n"
    )
    if passes:
        validate_suppressions(root, "HEAD")
    else:
        with pytest.raises(ValueError, match=r"tests lose 1 assertion lines net"):
            validate_suppressions(root, "HEAD")


NESTED = (
    "def test_keeps_a():\n    assert a()\n\n\n"
    "def test_duplicate_of_a():\n    def {helper}(value):\n        return value\n\n"
    "    assert {helper}(a())\n"
)
CASE = (
    "def test_keeps_a():\n    assert a()\n\n\n"
    "class DuplicateOfA(TestCase):\n    def runTest(self):\n"
    "        self.assertTrue(a())\n"
)


@pytest.mark.parametrize(
    ("before", "name", "passes"),
    [
        (NESTED.format(helper="check"), "test_duplicate_of_a", True),
        (NESTED.format(helper="check"), "check", False),
        (NESTED.format(helper="test_client"), "test_duplicate_of_a", True),
        (CASE, "runTest", True),
        (
            NESTED.format(helper="check").replace(
                "test_duplicate_of_a():",
                "test_duplicate_of_a(\n    value: int,\n) -> None:",
            ),
            "test_duplicate_of_a",
            True,
        ),
        (
            NESTED.format(helper="check")
            + "\n\nif LINUX:\n\n    def test_on_linux():\n        assert b()\n",
            "test_duplicate_of_a",
            False,
        ),
    ],
)
def test_planned_removal_covers_helpers_nested_in_the_named_test(
    tmp_path: Path, before: str, name: str, passes: bool
) -> None:
    root = switch_root(tmp_path, "tests/test_a.py", before)
    (root / "tests/test_a.py").write_text("def test_keeps_a():\n    assert a()\n")
    (root / "features/x").mkdir(parents=True)
    (root / "features/x/PLAN.md").write_text(
        f"Removed test: tests/test_a.py :: {name} :: test_keeps_a proves it\n"
    )
    if passes:
        validate_suppressions(root, "HEAD")
    else:
        with pytest.raises(ValueError, match=r"tests lose 1 assertion lines net"):
            validate_suppressions(root, "HEAD")


def retiring_root(tmp_path: Path) -> Path:
    root = switch_root(tmp_path, "app.py", "def keep():\n    return 1\n")
    (root / "migrate_users.py").write_text("def run():\n    return 2\n")
    (root / "jobs.py").write_text("def run():\n    return 0\n")
    (root / "app.py").write_text(
        "def keep():\n    return 1\n\n\ndef read_legacy():\n    return 3\n"
    )
    (root / "tests").mkdir()
    (root / "tests/test_migrate.py").write_text(
        "from migrate_users import run\n\n\ndef test_run():\n    assert run() == 2\n"
    )
    (root / "tests/test_app.py").write_text(
        "from app import keep, read_legacy\n\n\n"
        "def test_keep():\n    assert keep() == 1\n\n\n"
        "def test_legacy():\n    assert read_legacy() == 3\n"
    )
    commit(root, "subjects")
    return root


def test_removing_tests_with_the_code_they_cover_passes(tmp_path: Path) -> None:
    root = retiring_root(tmp_path)
    (root / "migrate_users.py").unlink()
    (root / "tests/test_migrate.py").unlink()
    (root / "app.py").write_text("def keep():\n    return 1\n")
    (root / "tests/test_app.py").write_text(
        "from app import keep\n\n\ndef test_keep():\n    assert keep() == 1\n"
    )
    validate_suppressions(root, "HEAD")


def test_removing_tests_for_code_still_in_use_fails(tmp_path: Path) -> None:
    root = retiring_root(tmp_path)
    (root / "tests/test_migrate.py").unlink()
    (root / "tests/test_app.py").write_text(
        "from app import keep, read_legacy\n\n\n"
        "def test_legacy():\n    assert read_legacy() == 3\n"
    )
    with pytest.raises(ValueError, match=OFF) as error:
        validate_suppressions(root, "HEAD")
    assert "tests lose 2 assertion lines net (2 removed, 0 added)" in str(error.value)


def test_deleting_a_test_file_that_also_covers_kept_code_fails(tmp_path: Path) -> None:
    root = retiring_root(tmp_path)
    (root / "app.py").write_text("def keep():\n    return 1\n")
    (root / "tests/test_app.py").unlink()
    with pytest.raises(ValueError, match=r"tests lose 1 assertion lines net"):
        validate_suppressions(root, "HEAD")


def test_changing_a_message_does_not_excuse_deleting_its_test(tmp_path: Path) -> None:
    root = switch_root(
        tmp_path, "app.py", "def check():\n    raise ValueError('Unknown account')\n"
    )
    (root / "tests").mkdir()
    (root / "tests/test_app.py").write_text(
        "def test_check():\n    assert 'Unknown' in message(check)\n"
    )
    commit(root, "message test")
    (root / "app.py").write_text(
        "def check():\n    raise ValueError('Invalid account')\n"
    )
    (root / "tests/test_app.py").unlink()
    with pytest.raises(ValueError, match=r"tests lose 1 assertion lines net"):
        validate_suppressions(root, "HEAD")


def test_retired_import_reaches_a_test_in_a_separate_hunk(tmp_path: Path) -> None:
    root = retiring_root(tmp_path)
    keep_test = "def test_keep():\n    assert keep() == 1\n"
    (root / "tests/test_app.py").write_text(
        "from app import keep\nfrom migrate_users import run as migrate\n\n\n"
        f"{keep_test}\n\ndef test_migrate():\n    assert migrate() == 2\n"
    )
    commit(root, "mixed test file")
    (root / "migrate_users.py").unlink()
    (root / "tests/test_migrate.py").unlink()
    (root / "tests/test_app.py").write_text(f"from app import keep\n\n\n{keep_test}")
    validate_suppressions(root, "HEAD")


def test_removing_a_typed_dart_constant_with_its_test_passes(tmp_path: Path) -> None:
    keep = "int keep() => 1;\n"
    root = switch_root(tmp_path, "lib/app.dart", f"{keep}const String legacy = '1';\n")
    keep_test = "  test('keep', () => expect(keep(), 1));\n"
    (root / "test").mkdir()
    (root / "test/app_test.dart").write_text(
        f"void main() {{\n{keep_test}  test('old', () => expect(legacy, '1'));\n}}\n"
    )
    commit(root, "dart test")
    (root / "lib/app.dart").write_text(keep)
    (root / "test/app_test.dart").write_text(f"void main() {{\n{keep_test}}}\n")
    validate_suppressions(root, "HEAD")


def test_inlining_a_local_does_not_excuse_deleting_its_test(tmp_path: Path) -> None:
    root = switch_root(
        tmp_path,
        "app.py",
        "def total(items):\n    subtotal = sum(items)\n    return subtotal\n",
    )
    (root / "tests").mkdir()
    (root / "tests/test_app.py").write_text(
        "def test_total():\n    subtotal = total([1, 2])\n    assert subtotal == 3\n"
    )
    commit(root, "total test")
    (root / "app.py").write_text("def total(items):\n    return sum(items)\n")
    (root / "tests/test_app.py").unlink()
    with pytest.raises(ValueError, match=r"tests lose 1 assertion lines net"):
        validate_suppressions(root, "HEAD")


def test_edited_moved_and_split_assertions_pass(tmp_path: Path) -> None:
    root = switch_root(
        tmp_path,
        "tests/test_a.py",
        "def t():\n    assert f() == 1\n\n\ndef u():\n    assert g()\n",
    )
    (root / "tests/test_a.py").write_text("def t():\n    assert f() == 2\n")
    (root / "tests/test_b.py").write_text("def u():\n    assert g()\n")
    validate_suppressions(root, "HEAD")


@pytest.mark.parametrize(
    ("name", "before", "after"),
    [
        (
            "tests/test_a.py",
            "def test_a():\n    assert f() == 3\n",
            "def test_a():\n    # assert f() == 3\n    pass\n",
        ),
        (
            "src/a.test.ts",
            "test('a', () => {\n  expect(f()).toBe(3);\n});\n",
            "test('a', () => {\n  // expect(f()).toBe(3);\n});\n",
        ),
    ],
)
def test_a_commented_out_assertion_counts_as_lost(
    tmp_path: Path, name: str, before: str, after: str
) -> None:
    root = switch_root(tmp_path, name, before)
    (root / name).write_text(after)
    with pytest.raises(ValueError, match=OFF) as error:
        validate_suppressions(root, "HEAD")
    assert "tests lose 1 assertion lines net (1 removed, 0 added)" in str(error.value)


def test_removed_assertion_outside_tests_passes(tmp_path: Path) -> None:
    root = switch_root(tmp_path, "lib.py", "assert ready\nx = 1\n")
    (root / "lib.py").write_text("x = 1\n")
    validate_suppressions(root, "HEAD")


def noop_gates_root(runner: ModuleType) -> Path:
    root = runner.ROOT
    (root / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [], "shared": [{"name": "noop", "command": ["true"]}]})
    )
    return root


def test_quick_check_runs_the_switch_off_guard(runner: ModuleType) -> None:
    root = noop_gates_root(runner)
    (root / "app.py").write_text("x = 1  # no" + "qa\n")
    with pytest.raises(ValueError, match=OFF):
        runner.check(quick=True, base="HEAD")


def test_quick_check_runs_the_decision_staleness_guard(runner: ModuleType) -> None:
    root = noop_gates_root(runner)
    (root / "docs/adr").mkdir(parents=True)
    (root / "docs/adr/0001-x.md").write_text("# 0001\n\nStatus: Accepted\n")
    with pytest.raises(ValueError, match="needs an 'Applies to:'"):
        runner.check(quick=True, base="HEAD")


def test_quick_check_runs_the_requirement_registry_guard(runner: ModuleType) -> None:
    root = noop_gates_root(runner)
    (root / "docs").mkdir(exist_ok=True)
    entry = f"## {'REQ'}-PAY-LIMIT\n\nPayments stop at the daily limit.\n"
    (root / "docs/requirements.md").write_text(entry)
    with pytest.raises(ValueError, match="needs a definition and a 'Proof"):
        runner.check(quick=True, base="HEAD")
