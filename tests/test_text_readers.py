"""HE-NO-TEXT-WALLS: the TSX and JSX reader returns the text blocks of every changed file from one process."""

import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import comments
import pytest
import text_readers
import text_walls
from comments import validate_suppressions
from conftest import SOURCE, change, configure, flutter_project, gate

SCREEN = (
    "export const A = () => (\n"
    "  <main>\n"
    "    <p>\n"
    "      Hello <strong>big</strong> world, {name}!\n"
    "      Second line.\n"
    "    </p>\n"
    '    <Card title="A card title" />\n'
    "  </main>\n"
    ");\n"
)


def test_the_reader_returns_the_blocks_of_each_file_and_a_finding_for_a_broken_one() -> (
    None
):
    """HE-NO-TEXT-WALLS: one request holds every file; a touched-line list narrows the blocks of one file."""
    request = text_walls.request(
        [
            ("a.tsx", SCREEN, None),
            ("b.tsx", SCREEN, [7]),
            ("c.tsx", "const a = <p>oops</div>;", None),
        ]
    )
    first, second, third = text_readers.read("js", request)
    assert [(b["kind"], b["name"], b["line"]) for b in first["blocks"]] == [
        ("jsx", "p", 4),
        ("prop", "title", 7),
    ]
    assert first["blocks"][0]["parts"] == [
        "Hello ",
        "big",
        " world, ",
        {"x": 1},
        "! Second line.",
    ]
    assert [b["name"] for b in second["blocks"]] == ["title"]
    assert str(third["error"]).startswith("line 1:")


def no_bun(name: str) -> None:
    return None


WALL = "<p>" + " ".join(["word"] * 40) + "</p>"


@pytest.mark.parametrize(
    "name", ["src/a.py", "src/a.ts", "src/a.css", "README.md", "lib/a.dart"]
)
def test_a_change_with_no_screen_file_starts_no_reader_and_loads_no_rule_module(
    tmp_path: Path, name: str
) -> None:
    """HE-NO-TEXT-WALLS: only a TSX or JSX file starts a reader or loads the rule module."""
    root = change(tmp_path, name, "base\n", f"base\n{WALL}\n")
    assert started_after(root) == "[] False False"


def started_after(root: Path) -> str:
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(SOURCE / '.hooks')!r})\n"
        "started = []\n"
        "sys.addaudithook(lambda event, args: event == 'subprocess.Popen' and "
        "started.append(str(args[0]).rsplit('/', 1)[-1]))\n"
        "import comments\n"
        f"comments.validate_suppressions(__import__('pathlib').Path({str(root)!r}), 'HEAD')\n"
        "print(sorted(set(started) - {'git'}), 'text_walls' in sys.modules, 'text_readers' in sys.modules)\n"
    )
    done = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


@pytest.mark.parametrize(
    ("flutter", "line"),
    [
        (True, "final count = 1;"),
        (True, "import 'package:flutter/material.dart';"),
        (False, "final a = Text('Hello there');"),
    ],
)
def test_a_dart_change_with_no_text_line_starts_no_process(
    tmp_path: Path, flutter: bool, line: str
) -> None:
    """HE-NO-TEXT-WALLS: a Dart change starts no process unless a Flutter package gets a touched line with text."""
    root = flutter_project(tmp_path, "// base\n", f"// base\n{line}\n", flutter)
    seen = started_after(root)
    assert seen.startswith("[] ")
    if not flutter:
        assert seen == "[] False False"


def test_a_missing_tool_fails_closed_with_its_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HE-NO-TEXT-WALLS: a missing Bun or Dart names its install step, and a file that cannot be parsed is a finding."""
    root = change(
        tmp_path, "src/a.tsx", "export const a = 1;\n", f"const a = {WALL};\n"
    )
    with monkeypatch.context() as patch:
        patch.setattr(text_readers, "shutil", SimpleNamespace(which=no_bun))
        with pytest.raises(ValueError, match="needs Bun") as error:
            validate_suppressions(root, "HEAD")
    assert "oven-sh/setup-bun" in str(error.value)
    (root / "src/a.tsx").write_text("const a = <p>oops</div>;\n")
    with pytest.raises(ValueError, match="HE-NO-TEXT-WALLS") as broken:
        validate_suppressions(root, "HEAD")
    assert "src/a.tsx" in str(broken.value)
    assert "line 1:" in str(broken.value)
    flutter = flutter_project(
        tmp_path / "f", "// base\n", f"// base\nText('{WALL}');\n", True
    )
    with monkeypatch.context() as patch:
        patch.setattr(text_readers, "tool_folder", lambda: tmp_path / "empty-tools")
        patch.setattr(
            text_readers,
            "shutil",
            SimpleNamespace(which=no_bun, rmtree=shutil.rmtree),
        )
        with pytest.raises(ValueError, match="needs the Dart SDK") as missing:
            validate_suppressions(flutter, "HEAD")
    assert "add the Dart SDK before the check" in str(missing.value)


def test_the_merge_shard_skips_the_rule(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HE-NO-TEXT-WALLS: the merge shard has no Bun, so it asks for no screen check; other shards do."""
    configure(tmp_path, [gate("suite", "pass")])
    seen: list[bool] = []

    def stop(root: Path, base: str | None, screens: bool = True) -> None:
        seen.append(screens)
        raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(comments, "validate_suppressions", stop)
        for shard in ("merge", "rest", None):
            with pytest.raises(KeyboardInterrupt):
                runner.check(base="0" * 40, shard=shard)
    assert seen == [False, True, True]
    root = change(
        tmp_path / "w", "src/a.tsx", "export const a = 1;\n", f"const a = {WALL};\n"
    )
    validate_suppressions(root, "HEAD", screens=False)


STARTED: list[str] = []
RECORDING: list[bool] = []


def record(event: str, arguments: tuple[object, ...]) -> None:
    if RECORDING and event == "subprocess.Popen":
        STARTED.append(Path(str(arguments[0])).name)


sys.addaudithook(record)

FLUTTER_SCREEN = (
    "import 'package:flutter/material.dart';\n"
    "Widget build() => Text.rich(TextSpan(text: 'Hello ', children: [\n"
    "  TextSpan(text: 'big'),\n"
    "  TextSpan(text: ' world', style: x),\n"
    "]));\n"
    "Widget other() => Text(n.body, maxLines: 2);\n"
)


def test_the_dart_reader_is_built_once_and_a_run_starts_no_dart_process() -> None:
    """HE-NO-TEXT-WALLS: the Dart reader is compiled into the cache once; a run starts only the compiled reader."""
    request = text_walls.request(
        [("lib/a.dart", FLUTTER_SCREEN, None), ("lib/b.dart", "void main( {", None)],
        "dart",
    )
    first, broken = text_readers.read("dart", request)
    assert [(b["kind"], b["name"], b["line"]) for b in first["blocks"]] == [
        ("jsx", "Text.rich", 2),
        ("jsx", "Text", 6),
    ]
    assert first["blocks"][0]["parts"] == ["Hello ", "big", " world"]
    assert first["blocks"][1]["parts"] == [{"x": 1, "field": "body"}]
    assert first["blocks"][1]["clamp"] == 2
    assert str(broken["error"]).startswith("line 1:")
    STARTED.clear()
    RECORDING.append(True)
    try:
        text_readers.read("dart", request)
    finally:
        RECORDING.clear()
    assert STARTED == ["reader.exe"]


def fake_reader(staging: Path, files: tuple[str, ...]) -> None:
    for name in files:
        (staging / name).parent.mkdir(parents=True, exist_ok=True)
        (staging / name).write_text("{}")


@pytest.mark.parametrize(
    ("prefix", "ready"),
    [("js", "node_modules/oxc-parser/package.json"), ("dart", "reader.exe")],
)
def test_a_half_deleted_reader_folder_is_built_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prefix: str, ready: str
) -> None:
    """HE-NO-TEXT-WALLS: a cached reader folder is reused only when its parser package or compiled file is there."""
    monkeypatch.setattr(text_readers, "tool_folder", lambda: tmp_path)
    built: list[str] = []

    def build(staging: Path) -> None:
        built.append(prefix)
        fake_reader(staging, (ready, "reader.mjs"))

    folder = text_readers.reader_folder(prefix, [b"key"], build)
    assert text_readers.reader_folder(prefix, [b"key"], build) == folder
    assert built == [prefix]
    (folder / ready).unlink()
    assert text_readers.reader_folder(prefix, [b"key"], build) == folder
    assert built == [prefix, prefix]
    assert (folder / ready).is_file()


def test_a_reader_with_its_parser_package_deleted_runs_again() -> None:
    """HE-NO-TEXT-WALLS: after the parser package is deleted from the cached folder, the next run installs it again."""
    request = text_walls.request([("a.tsx", SCREEN, None)])
    text_readers.read("js", request)
    folder = next((text_readers.tool_folder() / "text-readers").glob("js-*"))
    shutil.rmtree(folder / "node_modules/oxc-parser")
    assert text_readers.read("js", request)[0]["blocks"]


@pytest.mark.parametrize(("prefix", "label"), [("js", "TSX and JSX"), ("dart", "Dart")])
@pytest.mark.parametrize(
    "error", [subprocess.TimeoutExpired(["bun"], 120), OSError("no space left")]
)
def test_an_install_that_hangs_or_fails_to_start_is_a_plain_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prefix: str,
    label: str,
    error: Exception,
) -> None:
    """HE-NO-TEXT-WALLS: a timeout or an operating system error of an install or build gives the install-failed refusal."""
    monkeypatch.setattr(text_readers, "tool_folder", lambda: tmp_path)

    def build(staging: Path) -> None:
        raise error

    with pytest.raises(ValueError, match=f"installing the {label} reader failed"):
        text_readers.reader_folder(prefix, [b"key"], build)
    assert not list((tmp_path / "text-readers").glob(".staging-*"))


def test_a_reader_of_another_release_keeps_its_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HE-NO-TEXT-WALLS: building the reader of one release does not delete the reader folder of another."""
    monkeypatch.setattr(text_readers, "tool_folder", lambda: tmp_path)

    def build(staging: Path) -> None:
        fake_reader(staging, ("reader.exe",))

    first = text_readers.reader_folder("dart", [b"one"], build)
    second = text_readers.reader_folder("dart", [b"two"], build)
    assert first != second
    assert first.is_dir()
    assert second.is_dir()
