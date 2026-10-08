"""The comment rule: changed source files hold one-line comments at most."""

import json
import re
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from comments import validate_comments, validate_suppressions
from conftest import SOURCE, commit, git, init
from shipping import ShippingPolicy

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


def test_check_without_base_covers_committed_branch_changes(
    tmp_path: Path, shipping_policy: ShippingPolicy
) -> None:
    root = tmp_path / "repo"
    init(root)
    gates: dict[str, object] = {
        "packages": [],
        "shared": [],
        "shipping": shipping_policy,
    }
    (root / "hard-eng.gates.json").write_text(json.dumps(gates))
    commit(root, "baseline")
    git(root, "branch", "-M", shipping_policy["base"])
    git(root, "switch", "-qc", "feature")
    (root / "app.py").write_text("# narrates\n# the next line\nx = 1\n")
    commit(root, "add app")
    validate_comments(root, "HEAD")
    with pytest.raises(ValueError, match=r"app\.py:1 holds a 2-line"):
        validate_comments(root, None)


OFF = "A change must not switch a check off"
SWITCHES = [
    ("app.py", "x = 1  # no" + "qa: E501\n", "# no" + "qa"),
    ("app.py", "x = 1  # type:" + " ignore\n", "# type:" + " ignore"),
    ("app.py", "x = 1  # pyrefly:" + " ignore\n", "# pyrefly:" + " ignore"),
    ("app.py", "x = 1  # pyright:" + " ignore\n", "# pyright:" + " ignore"),
    ("app.py", "x = 1  # pylint:" + " disable=x\n", "# pylint:" + " disable"),
    ("app.py", "x = 1  # pragma:" + " no cover\n", "# pragma:" + " no cover"),
    ("t.py", "@pytest.mark." + "skip\ndef t(): ...\n", "pytest.mark." + "skip"),
    ("t.py", "@pytest.mark." + "skipif(a)\ndef t(): ...\n", "pytest.mark." + "skipif"),
    ("t.py", "@pytest.mark." + "xfail\ndef t(): ...\n", "pytest.mark." + "xfail"),
    (
        "t.py",
        "pytestmark = pytest.mark." + "skip(reason='x')\n",
        "pytest.mark." + "skip",
    ),
    ("t.py", "pytestmark = mark." + "skip(reason='x')\n", "mark." + "skip"),
    ("t.py", "pytest." + "skip('x')\n", "pytest." + "skip("),
    ("t.py", "pytest." + "xfail('x')\n", "pytest." + "xfail("),
    ("a.ts", "// eslint-" + "disable-next-line\nf();\n", "eslint-" + "disable"),
    ("a.ts", "// @ts-" + "ignore\nf();\n", "@ts-" + "ignore"),
    ("a.tsx", "// @ts-expect-" + "error\nf();\n", "@ts-expect-" + "error"),
    ("a.mjs", "// @ts-no" + "check\n", "@ts-no" + "check"),
    ("a.js", "// biome-" + "ignore lint: x\nf();\n", "biome-" + "ignore"),
    ("a.test.ts", "describe." + "only('s', () => {});\n", "describe." + "only("),
    ("a.test.js", "it." + "skip('s', () => {});\n", "it." + "skip("),
    ("a.test.js", "x" + "it('s', () => {});\n", "x" + "it("),
    ("a.test.js", "f" + "describe('s', () => {});\n", "f" + "describe("),
    ("a.js", "/* istanbul " + "ignore next */\nf();\n", "/* istanbul " + "ignore"),
    ("a.js", "/* c8 " + "ignore next */\nf();\n", "/* c8 " + "ignore"),
    ("a.js", "/* v8 " + "ignore next */\nf();\n", "/* v8 " + "ignore"),
    ("lib/a.dart", "// ig" + "nore: unused_import\n", "// ig" + "nore:"),
    ("lib/a.dart", "// ig" + "nore_for_file: x\n", "// ig" + "nore_for_file:"),
    ("test/a_test.dart", "test('t', () {}, ski" + "p: true);\n", "ski" + "p:"),
    (
        "test/a_test.dart",
        "group('t', () {}, ski" + "p: 'later');\n",
        "ski" + "p:",
    ),
    ("test/a_test.dart", "@Sk" + "ip('why')\nlibrary a;\n", "@Sk" + "ip("),
]


def switch_root(tmp_path: Path, name: str, before: str) -> Path:
    init(tmp_path / "repo")
    root = tmp_path / "repo"
    (root / "README.md").write_text("fixture\n")
    if before:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(before)
    commit(root, "baseline")
    return root


@pytest.mark.parametrize(("name", "text", "pattern"), SWITCHES)
def test_added_switch_off_fails_naming_file_line_and_pattern(
    tmp_path: Path, name: str, text: str, pattern: str
) -> None:
    root = switch_root(tmp_path, name, "")
    (root / name).parent.mkdir(parents=True, exist_ok=True)
    (root / name).write_text("ok = 1\n" + text)
    with pytest.raises(ValueError, match=OFF) as error:
        validate_suppressions(root, "HEAD")
    assert f"{name}:2 adds {pattern!r}" in str(error.value)
    assert "fix the cause" in str(error.value)


@pytest.mark.parametrize(("name", "text", "pattern"), SWITCHES)
def test_switch_off_already_in_the_project_is_not_flagged(
    tmp_path: Path, name: str, text: str, pattern: str
) -> None:
    root = switch_root(tmp_path, name, text)
    (root / name).write_text(text + "extra = 1\n")
    validate_suppressions(root, "HEAD")


def test_scaffold_paths_and_ordinary_words_are_not_flagged(tmp_path: Path) -> None:
    root = switch_root(tmp_path, "app.py", "")
    (root / ".hooks").mkdir()
    (root / ".hooks/tool.py").write_text("x = 1  # no" + "qa\n")
    (root / "app.py").write_text("skip = True\nskipped = pytest_skip_reason\n")
    (root / "lib").mkdir()
    (root / "lib/a.dart").write_text("final f = Foo(ski" + "p: false);\n")
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


def test_deleting_a_test_file_without_replacement_fails(tmp_path: Path) -> None:
    root = switch_root(tmp_path, "tests/test_a.py", "def t():\n    assert f()\n")
    (root / "tests/test_a.py").unlink()
    with pytest.raises(ValueError, match=r"tests/test_a\.py:2"):
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


def test_inlining_a_local_does_not_excuse_deleting_its_test(tmp_path: Path) -> None:
    root = switch_root(
        tmp_path, "app.py", "def total(items):\n    subtotal = sum(items)\n    return subtotal\n"
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
