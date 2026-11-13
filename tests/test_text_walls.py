"""HE-NO-TEXT-WALLS: screen text comes in short blocks of at most 25 words and 3 sentences."""

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
import text_walls
from comments import validate_suppressions
from conftest import SOURCE, change, commit, init

RULE = "HE-NO-TEXT-WALLS"
BASE = "export const A = () => <main />;\n"

X = {"x": 1}


@pytest.mark.parametrize(
    ("parts", "counts"),
    [
        (["Hello world."], (2, 1, 2)),
        (["Three short. Sentences here. Fine."], (5, 3, 2)),
        (["Pay $4.50 at 12:30 now."], (5, 1, 5)),
        (["See https://example.com/a.b. Next one."], (4, 2, 2)),
        (["Great 🎉 job."], (2, 1, 2)),
        (["Fast — simple | clean & small."], (4, 1, 4)),
        (["Use e.g. a cat. Then go."], (6, 2, 4)),
        (["Ask Mr. Smith at 9 a.m. today. Then rest."], (9, 2, 7)),
        (["Version 2.5 is out. Yes."], (5, 2, 4)),
        (["A well-known fact."], (3, 1, 3)),
        (["First line\nsecond line"], (4, 2, 2)),
        (["你好世界"], (2, 1, 2)),
        (["你好。再见。"], (2, 2, 1)),
        (["Hello ", X, "!"], (2, 1, 2)),
        (["Hi ", X, "'s book."], (3, 1, 3)),
        (["Hi ", X, " and ", {"x": 1, "field": "body"}, "."], (4, 1, 4)),
        (["Save ", {"alt": [["Saved changes to the file."], [X]]}], (6, 1, 6)),
        (["Say ", {"alt": [["a"], ["b c d"]]}, " now."], (5, 1, 5)),
        (["One. Two? Three! Four"], (4, 4, 1)),
        ([" ", "—", " "], (0, 0, 0)),
        ([], (0, 0, 0)),
    ],
)
def test_measure_counts_words_and_sentences(
    parts: list[object], counts: tuple[int, int, int]
) -> None:
    """HE-NO-TEXT-WALLS: one table fixes words, sentences and the longest sentence of every text form."""
    assert text_walls.measure(parts) == counts


def gates(root: Path, text_walls_key: object) -> None:
    (root / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [], "text_walls": text_walls_key})
    )


def test_settings_default_and_refuse_invalid_values(tmp_path: Path) -> None:
    """HE-NO-TEXT-WALLS: caps default with no setting, a project can change a number, and a bad value names its fix."""
    default = text_walls.Caps(25, 3, 20, ())
    assert text_walls.settings(tmp_path) == default
    (tmp_path / "hard-eng.gates.json").write_text('{"packages": []}')
    assert text_walls.settings(tmp_path) == default
    gates(tmp_path, {"words_per_block": 30, "paths": ["app/(app)/**"]})
    assert text_walls.settings(tmp_path) == text_walls.Caps(
        30, 3, 20, ("app/(app)/**",)
    )
    for bad, fix in [
        ({"words_per_block": 0}, "words_per_block"),
        ({"sentences_per_block": True}, "sentences_per_block"),
        ({"words_per_sentence": "20"}, "words_per_sentence"),
        ({"words_per_block": 25, "sentences": 3}, "sentences"),
        ({"paths": ["app"]}, "/**"),
        ({"paths": "app/**"}, "paths"),
        ([1], "text_walls"),
    ]:
        gates(tmp_path, bad)
        with pytest.raises(ValueError, match="HE-NO-TEXT-WALLS") as error:
            text_walls.settings(tmp_path)
        assert fix in str(error.value)


def sentence(count: int) -> str:
    return " ".join(["Word"] + ["word"] * (count - 1)) + "."


def screen(*lines: str) -> str:
    return (
        "export const A = () => (\n  <main>\n"
        + "".join(f"    {x}\n" for x in lines)
        + "  </main>\n);\n"
    )


def refused(root: Path) -> str:
    with pytest.raises(ValueError, match=RULE) as error:
        validate_suppressions(root, "HEAD")
    return str(error.value)


def test_a_46_word_literal_paragraph_is_refused_with_its_step(tmp_path: Path) -> None:
    """HE-NO-TEXT-WALLS: a long literal paragraph fails with its file, its line, its count and the step."""
    long = " ".join(["word"] * 46)
    root = change(tmp_path, "src/Card.tsx", BASE, screen("<p>", f"  {long}", "</p>"))
    message = refused(root)
    assert "src/Card.tsx:4:" in message
    assert "46 words" in message
    assert "at most 25" in message
    assert "Split" in message


def test_the_three_caps_each_refuse_one_block(tmp_path: Path) -> None:
    """HE-NO-TEXT-WALLS: three short sentences pass; a fourth sentence and a 21-word sentence are refused."""
    short = "Save now. Pay later. Rest well."
    lines = [
        f"<p>{short}</p>",
        f"<p>{short} Go on.</p>",
        f"<p>{sentence(21)}</p>",
        f"<p>{sentence(20)} {sentence(5)}</p>",
    ]
    root = change(tmp_path, "src/Card.tsx", BASE, screen(*lines))
    message = refused(root)
    assert "src/Card.tsx:3:" not in message
    assert "src/Card.tsx:4: 4 sentences" in message
    assert "src/Card.tsx:5: a sentence of 21 words" in message
    assert "src/Card.tsx:6:" not in message


def test_each_text_form_is_one_block(tmp_path: Path) -> None:
    """HE-NO-TEXT-WALLS: inline elements merge, text props, object keys and prose constants are blocks, a class string passes."""
    ten = sentence(10).rstrip(".")
    classes = " ".join(f"text-sm-{n}" for n in range(30))
    source = (
        f'const INTRO = "Hello {sentence(30)}";\n'
        f'const CLASSES = "{classes}";\n'
        f'const COPY = {{ description: "{sentence(30)}" }};\n'
        "export const A = () => (\n"
        "  <main>\n"
        f"    <p>{ten} <strong>{ten}</strong> {ten}</p>\n"
        f'    <Card title="{sentence(30)}" />\n'
        f"    <p>{ten}<br />{ten}</p>\n"
        "  </main>\n"
        ");\n"
    )
    root = change(tmp_path, "src/Card.tsx", BASE, source)
    message = refused(root)
    for line in (1, 3, 6, 7):
        assert f"src/Card.tsx:{line}:" in message
    for line in (2, 8):
        assert f"src/Card.tsx:{line}:" not in message
    assert "30 words" in message


def old_wall() -> str:
    return screen("<p>", f"  {sentence(30)}", "</p>", "<p>Short.</p>")


def test_only_touched_text_is_judged(tmp_path: Path) -> None:
    """HE-NO-TEXT-WALLS: an old wall passes until a change touches it; a move passes; an edit and a deleted break are judged."""
    wall = old_wall()
    root = change(
        tmp_path / "a", "src/Card.tsx", wall, wall.replace("Short.", "Brief.")
    )
    validate_suppressions(root, "HEAD")
    wrapped = "".join(f"  {line}\n" for line in wall.splitlines())
    moved = change(tmp_path / "b", "src/Card.tsx", wall, wrapped)
    validate_suppressions(moved, "HEAD")
    edited = change(
        tmp_path / "c", "src/Card.tsx", wall, wall.replace("word", "work", 1)
    )
    assert "src/Card.tsx:4:" in refused(edited)
    halves = screen("<p>", f"  {sentence(13)}", "  <br />", f"  {sentence(13)}", "</p>")
    joined = change(
        tmp_path / "d", "src/Card.tsx", halves, halves.replace("    <br />\n", "")
    )
    assert "26 words" in refused(joined)


def test_exempt_files_and_paths_are_not_judged(tmp_path: Path) -> None:
    """HE-NO-TEXT-WALLS: tests, stories, generated files, tool folders and files outside paths are not judged."""
    root = tmp_path / "repo"
    init(root)
    (root / ".gitattributes").write_text("src/gen/** linguist-generated\n")
    commit(root, "baseline")
    wall = old_wall()
    for name in (
        "src/Card.test.tsx",
        "src/Card.stories.tsx",
        "tests/Card.tsx",
        "src/gen/Card.tsx",
        ".claude/Card.tsx",
    ):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(wall)
    validate_suppressions(root, "HEAD")
    (root / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [], "text_walls": {"paths": ["app/**"]}})
    )
    (root / "src/Page.tsx").write_text(wall)
    validate_suppressions(root, "HEAD")
    (root / "app").mkdir()
    (root / "app/Page.tsx").write_text(wall)
    message = refused(root)
    assert "app/Page.tsx:" in message
    assert "src/Page.tsx" not in message


def test_stored_text_needs_user_content_or_a_short_clamp_with_a_tap(
    tmp_path: Path,
) -> None:
    """HE-NO-TEXT-WALLS: a stored body shows only inside UserContent, or clamped to 2 lines inside a control that a tap opens."""
    lines = [
        '<div className="banner"><p>{notice.body}</p></div>',
        '<button onClick={open}><p className="line-clamp-2">{n.body}</p></button>',
        '<a href="/n"><p className="truncate">{n.description}</p></a>',
        "<button onClick={open}><p style={{ WebkitLineClamp: 2 }}>{n.body}</p></button>",
        "<Pressable onPress={open}><Text numberOfLines={2}>{n.body}</Text></Pressable>",
        '<button onClick={open}><p className="line-clamp-3">{n.body}</p></button>',
        '<div><p className="line-clamp-2">{n.body}</p></div>',
        "<p>{n.title}</p>",
        "<UserContent>{n.body}</UserContent>",
    ]
    root = change(tmp_path, "src/Card.tsx", BASE, screen(*lines))
    message = refused(root)
    flagged = [
        number for number in range(3, 12) if f"src/Card.tsx:{number}:" in message
    ]
    assert flagged == [3, 8, 9]
    assert "UserContent" in message


def test_user_content_takes_expressions_only(tmp_path: Path) -> None:
    """HE-NO-TEXT-WALLS: UserContent passes an expression and refuses literal text."""
    lines = [
        "<UserContent>{item.text}</UserContent>",
        "<UserContent>Literal text</UserContent>",
        '<UserContent text="Literal text" />',
        "<UserContent>{`Total ${count}`}</UserContent>",
        "<UserContent>{item.first + item.last}</UserContent>",
    ]
    root = change(tmp_path, "src/Card.tsx", BASE, screen(*lines))
    message = refused(root)
    flagged = [number for number in range(3, 8) if f"src/Card.tsx:{number}:" in message]
    assert flagged == [4, 5, 6]


def test_structural_skips_are_not_judged(tmp_path: Path) -> None:
    """HE-NO-TEXT-WALLS: structured data, script, style, code and pre are skipped; inline code is one word."""
    long = " ".join(["word"] * 40)
    source = (
        f'const DATA = {{ "@type": "Article", description: "{long}" }};\n'
        "export const A = () => (\n"
        "  <main>\n"
        f"    <script>{long}</script>\n"
        f"    <style>{long}</style>\n"
        f"    <code>{long}</code>\n"
        f"    <pre>{long}</pre>\n"
        f"    <p>Ten words <code>{long}</code> after the code.</p>\n"
        f"    <p>{long}</p>\n"
        "  </main>\n"
        ");\n"
    )
    root = change(tmp_path, "src/Card.tsx", BASE, source)
    message = refused(root)
    flagged = [
        number for number in range(1, 11) if f"src/Card.tsx:{number}:" in message
    ]
    assert flagged == [9]


def test_the_list_command_and_the_stdin_judge_share_the_caps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """HE-NO-TEXT-WALLS: the list command and the --stdin judge read the caps of the project and the same count."""
    root = tmp_path / "repo"
    init(root)
    gates(root, {"words_per_block": 30, "words_per_sentence": 30})
    (root / "src").mkdir()
    (root / "src/Card.tsx").write_text(
        screen(f"<p>{sentence(28)}</p>", f"<p>{sentence(40)}</p>")
    )
    (root / "src/Card.test.tsx").write_text(screen(f"<p>{sentence(40)}</p>"))
    commit(root, "baseline")
    assert text_walls.walls_command(root, [], False) == 1
    listed = capsys.readouterr().out
    assert "src/Card.tsx:4: 40 words, at most 30" in listed
    assert "src/Card.tsx:3:" not in listed
    assert "Card.test" not in listed
    assert text_walls.walls_command(root, ["src/Card.tsx"], False) == 1
    capsys.readouterr()
    strings = [sentence(28), sentence(40), "Short.\nSecond line."]
    monkeypatch.setattr(
        sys, "stdin", io.StringIO("".join(json.dumps(text) + "\n" for text in strings))
    )
    assert text_walls.walls_command(root, [], True) == 1
    judged = capsys.readouterr().out
    assert "line 2: 40 words, at most 30" in judged
    assert "line 1:" not in judged
    assert "line 3:" not in judged
    done = subprocess.run(
        [sys.executable, str(SOURCE / ".hooks/hard-eng.py"), "text-walls", "--stdin"],
        input=json.dumps(sentence(26)) + "\n",
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 1
    assert "line 1: 26 words, at most 25" in done.stdout
