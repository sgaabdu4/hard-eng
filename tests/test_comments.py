"""The comment rule: changed source files hold one-line comments at most."""

import json
import re
import subprocess
from pathlib import Path

import pytest
from comments import validate_comments
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
