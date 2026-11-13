"""HE-NO-TEXT-WALLS: screen text comes in short blocks of at most 25 words and 3 sentences."""

import json
from pathlib import Path

import pytest
import text_walls

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
    assert text_walls.settings(tmp_path) == text_walls.Caps(30, 3, 20, ("app/(app)/**",))
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
