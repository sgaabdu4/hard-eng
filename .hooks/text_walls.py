"""HE-NO-TEXT-WALLS: screen text comes in short blocks, counted by one measure and one settings reader."""

import json
import re
import subprocess
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import NamedTuple

from comments import is_test_path
from gate_config import generated_sources
from text_readers import Block, read

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
        data = json.loads((root / "hard-eng.gates.json").read_text())
    except (OSError, ValueError):
        data = None
    raw = data.get("text_walls") if isinstance(data, dict) else None
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


PLAIN_WORD = re.compile(r"[A-Za-z]+(?:'[a-z]+)?")
SCREEN_SUFFIXES = (".tsx", ".jsx")
UNOWNED_FOLDERS = (".hooks/", ".agents/", ".claude/")
USER_LITERAL = (
    "UserContent holds literal text. Pass the text as an expression, for example {item.text}"
)
STORED_TEXT = (
    "Stored text `{field}` shows in full. Render it inside UserContent, or clamp it "
    "to 2 lines or fewer inside a control that opens the full text"
)
FIX = "Split it into blocks of one idea each, with dates, names and amounts on their own labelled lines"


def is_prose(parts: list[object]) -> bool:
    """A copy constant is prose when it starts like a sentence and most of its words are plain words."""
    words = flatten(parts).split()
    if not words:
        return False
    plain = sum(bool(PLAIN_WORD.fullmatch(word.strip(".,;:!?\"'()"))) for word in words)
    starts = words[0][:1].isupper() or any(
        word.rstrip(CLOSERS).endswith(SENTENCE_ENDS) for word in words
    )
    return starts and plain * 10 >= len(words) * 7


def literal_text(parts: list[object]) -> bool:
    return any(
        bool(HAS_LETTER_OR_DIGIT.search(part))
        if isinstance(part, str)
        else isinstance(part, dict) and any(literal_text(b) for b in part.get("alt", []))
        for part in parts
    )


def stored_field(parts: list[object]) -> str:
    return next(
        (str(part["field"]) for part in parts if isinstance(part, dict) and "field" in part),
        "",
    )


def problems(block: Block, caps: Caps) -> str:
    parts = block["parts"]
    if block["user"]:
        return USER_LITERAL if literal_text(parts) else ""
    words, sentences, longest = measure(parts)
    over = []
    if words > caps.words:
        over.append(f"{words} words, at most {caps.words}")
    if sentences > caps.sentences:
        over.append(f"{sentences} sentences, at most {caps.sentences}")
    if longest > caps.sentence_words:
        over.append(f"a sentence of {longest} words, at most {caps.sentence_words}")
    found = "; ".join(over) + f". {FIX}" if over else ""
    field = stored_field(parts)
    clamp = block["clamp"]
    if field and not (clamp is not None and clamp <= 2 and block["tap"]):
        found += (" " if found else "") + STORED_TEXT.format(field=field)
    return found


def judged(name: str, blocks: list[Block], caps: Caps) -> list[tuple[str, str]]:
    """The (flattened text, finding) pair of each block over a cap."""
    out = []
    for block in blocks:
        if block["kind"] == "const" and not is_prose(block["parts"]):
            continue
        if found := problems(block, caps):
            text = " ".join(flatten(block["parts"]).split())
            out.append((text, f"{name}:{block['line']}: {found}"))
    return out


def in_scope(name: str, caps: Caps) -> bool:
    return (
        name.endswith(SCREEN_SUFFIXES)
        and not name.startswith(UNOWNED_FOLDERS)
        and ".stories." not in name
        and not is_test_path(PurePosixPath(name))
        and (not caps.paths or any(fnmatchcase(name, glob) for glob in caps.paths))
    )


def base_sources(root: Path, point: str, names: list[str]) -> list[tuple[str, str, None]]:
    """The text of each file at the base, from one git process."""
    wanted = [f"{point}:{name}\n" for name in names]
    done = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=root,
        input="".join(wanted).encode(),
        capture_output=True,
        check=True,
    )
    out, data = [], done.stdout
    for name in names:
        end = data.index(b"\n")
        header = data[:end].split()
        data = data[end + 1 :]
        if header[-1] == b"missing":
            continue
        size = int(header[2])
        out.append((name, data[:size].decode(errors="replace"), None))
        data = data[size + 1 :]
    return out


def unchanged_texts(root: Path, point: str, names: list[str]) -> set[str]:
    files = base_sources(root, point, names)
    if not files:
        return set()
    return {
        " ".join(flatten(block["parts"]).split())
        for result in read("js", request(files))
        for block in result["blocks"]
    }


def wall_check(
    root: Path,
    added: dict[str, list[tuple[int, str]]],
    removed: dict[str, list[tuple[int, str]]],
    joins: dict[str, list[int]],
    point: str,
) -> None:
    caps = settings(root)
    names = sorted(name for name in {*added, *removed, *joins} if in_scope(name, caps))
    files = [
        (
            name,
            (root / name).read_text(errors="replace"),
            sorted({number for number, _ in added.get(name, [])} | set(joins.get(name, []))),
        )
        for name in names
        if (root / name).is_file() and (name in added or name in joins)
    ]
    if not files:
        return
    found: dict[str, list[tuple[str, str]]] = {}
    for result in read("js", request(files)):
        name = result["path"]
        if result["error"]:
            found[name] = [("", f"{name}: the text cannot be read, {result['error']}. Fix the syntax of the file")]
        elif hits := judged(name, result["blocks"], caps):
            found[name] = hits
    if not found:
        return
    skipped = generated_sources(root, sorted(found))
    old = unchanged_texts(root, point, names)
    lines = [
        line
        for name, hits in found.items()
        if name not in skipped
        for text, line in hits
        if not text or text not in old
    ]
    if lines:
        raise ValueError(
            f"HE-NO-TEXT-WALLS: Screen text comes in short blocks of at most {caps.words} "
            f"words and {caps.sentences} sentences, and a sentence of at most "
            f"{caps.sentence_words} words. " + "; ".join(lines)
        )
