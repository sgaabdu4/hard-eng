"""HE-NO-TEXT-WALLS: screen text comes in short blocks, counted by one measure and one settings reader."""

import json
import re
from pathlib import Path
from typing import NamedTuple

SLOT = ""
WORD = re.compile(r"\S+")
HAS_LETTER_OR_DIGIT = re.compile(r"[^\W_]")
CLOSERS = "\"')]}”’»"
OPENERS = "\"'“‘("
SENTENCE_ENDS = (".", "!", "?", "…")
CJK_ENDS = ("。", "！", "？")
ABBREVIATIONS = frozenset(
    "e.g. i.e. etc. vs. mr. mrs. ms. dr. st. no. approx. incl. min. max. a.m. p.m.".split()
)
DOTTED = re.compile(r"^(?:[^\W\d_]\.)+$")
CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿]+")
CJK_END = re.compile(r"([。！？])")
KEYS = {
    "words_per_block": 25,
    "sentences_per_block": 3,
    "words_per_sentence": 20,
}
INLINE = ("strong", "em", "b", "i", "span", "a", "Link")
TEXT_PROPS = (
    "title label description body message subtitle hint helperText note text details "
    "summary caption lead"
).split()
SKIP = ("script", "style", "code", "pre")
STORED = "body content description details notes note summary comment bio about".split()
TAP_NAMES = ("button", "a", "Link", "summary", "Pressable", "TouchableOpacity", "TouchableHighlight")
TAP_ATTRS = ("onClick", "onPress", "href")
USER_CONTENT = "UserContent"


class Caps(NamedTuple):
    words: int
    sentences: int
    sentence_words: int
    paths: tuple[str, ...]


def flatten(parts: list[object]) -> str:
    out: list[str] = []
    for part in parts:
        if isinstance(part, str):
            out.append(part)
        elif isinstance(part, dict) and "alt" in part:
            branches = [flatten(branch) for branch in part["alt"]]
            out.append(max(branches, key=lambda text: measure_line(text)[:2]))
        else:
            out.append(SLOT)
    return "".join(out)


def word_weight(token: str) -> int:
    if SLOT in token:
        return 1
    if not HAS_LETTER_OR_DIGIT.search(token):
        return 0
    runs = CJK.findall(token)
    if not runs:
        return 1
    rest = HAS_LETTER_OR_DIGIT.search(CJK.sub("", token))
    return sum((len(run) + 1) // 2 for run in runs) + bool(rest)


def ends_sentence(token: str, following: str | None) -> bool:
    core = token.rstrip(CLOSERS)
    if core.endswith(CJK_ENDS):
        return True
    if not core.endswith(SENTENCE_ENDS):
        return False
    if following is None:
        return True
    if core.lower() in ABBREVIATIONS or DOTTED.match(core):
        return False
    head = following.lstrip(CLOSERS + OPENERS)[:1]
    return head == SLOT or head.isupper() or head.isdigit() or not head.isalpha()


def measure_line(text: str) -> tuple[int, int, int]:
    tokens = WORD.findall(text)
    words = sentences = longest = current = 0
    for index, token in enumerate(tokens):
        weight = word_weight(token)
        words += weight
        current += weight
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        if current and ends_sentence(token, following):
            sentences += 1
            longest = max(longest, current)
            current = 0
    if current:
        sentences += 1
        longest = max(longest, current)
    return words, sentences, longest


def measure(parts: list[object]) -> tuple[int, int, int]:
    """Words, sentences and the longest sentence of one block; a line break ends a sentence."""
    lines = [
        measure_line(CJK_END.sub(r"\1 ", line))
        for line in flatten(parts).split("\n")
    ]
    return (
        sum(line[0] for line in lines),
        sum(line[1] for line in lines),
        max(line[2] for line in lines),
    )


def settings(root: Path) -> Caps:
    """The caps of a project; each key is optional, so a project can change a number, never a file."""
    try:
        raw = json.loads((root / "hard-eng.gates.json").read_text()).get("text_walls")
    except FileNotFoundError:
        raw = None
    if raw is None:
        return Caps(*KEYS.values(), ())
    if not isinstance(raw, dict):
        raise ValueError(
            "HE-NO-TEXT-WALLS: `text_walls` in hard-eng.gates.json must be an object; "
            "remove it or give it the keys " + ", ".join([*KEYS, "paths"])
        )
    unknown = sorted(set(raw) - {*KEYS, "paths"})
    if unknown:
        raise ValueError(
            f"HE-NO-TEXT-WALLS: `text_walls` has the unknown key {unknown[0]!r}; "
            "remove it or use " + ", ".join([*KEYS, "paths"])
        )
    numbers = []
    for key, default in KEYS.items():
        value = raw.get(key, default)
        if type(value) is not int or value < 1:
            raise ValueError(
                f"HE-NO-TEXT-WALLS: `text_walls.{key}` must be a whole number of 1 or more; "
                "set it in hard-eng.gates.json or remove it to use " + str(default)
            )
        numbers.append(value)
    paths = raw.get("paths", [])
    if not isinstance(paths, list) or not all(
        isinstance(path, str) and path.endswith("/**") for path in paths
    ):
        raise ValueError(
            "HE-NO-TEXT-WALLS: `text_walls.paths` must be a list of folder globs that "
            "end in /**, for example app/**; it narrows the folders and never exempts a file"
        )
    return Caps(*numbers, tuple(paths))


def request(files: list[tuple[str, str, list[int] | None]]) -> dict[str, object]:
    """The request that every reader takes: the word lists and each file with its touched lines."""
    return {
        "inline": INLINE,
        "text_props": TEXT_PROPS,
        "skip": SKIP,
        "user": USER_CONTENT,
        "stored": STORED,
        "tap_names": TAP_NAMES,
        "tap_attrs": TAP_ATTRS,
        "files": [
            {"path": path, "source": source, "touched": touched}
            for path, source, touched in files
        ],
    }
