"""The reviewer's answer to a look run: its lines, the rules it decides, and why a line cannot stand."""

import re
from collections.abc import Mapping
from itertools import pairwise
from typing import NamedTuple

from look_facts import claim_in
from plans import split_rule_line, usability_lines, usability_rules

FIX_PART = re.compile(r"(?i)\bfix:\s*\S")
ITEM_START = re.compile(r"image-\d+\.png\s*:")
KIND_TAG = re.compile(r"\[([A-Za-z-]+)\]")
CLAIM = re.compile(
    r"(?i)\d+(?:\.\d+)?\s*(?:px|pt|rem|em)\b|\d+(?:\.\d+)?\s*:\s*1\b|#(?:[0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})\b|#(?=\d*[a-f])[0-9a-f]{4}\b|\b(?:rgb|hsl)a?\("
)
FRAME = re.compile(r"image-\d+\.png")
CLAIM_NOTES = {
    "radius": "Start the note with the claim, such as `square corners`, only when you claim that the corners are square; any other note is judgement",
    "align": "Start the note with the claim, such as `centred`, only when you claim that the text is centred; write `not centred` when you claim that it is not",
    "gap": "Start the note with the claim, such as `chips touch`, only when you claim that the neighbours touch; any other note is judgement",
}
RECHECK_LINE = re.compile(r"(?i)^recheck\s+R(\d+)\s*:\s*(still shown|gone)\b(.*)")
NUMBER = re.compile(r"\d+")
COUNT_LIST = r"\d+(?:\s*/\s*\d+)*"
REMOVED_AFTER = re.compile(rf"(?i)\bremoved\s*:?\s*({COUNT_LIST})")
REMOVED_BEFORE = re.compile(rf"(?i)\b({COUNT_LIST})\s+removed\b")
BULLET = re.compile(r"^[-*•]\s+")
COUNT_NOTE = re.compile(r"([^:(]+?)\s*(\([^)]*\))\s*:\s*(.*)")
NOTE_AFTER_VERDICT = re.compile(
    r"(?!Image )([^:(]+): (Pass|Fail|N/A)\s+(\([^()]*(?:[A-Za-z]:?\s*\d|\d\s+[A-Za-z])[^()]*\))\s*[.:—–-]?\s*(\S.*)"
)
PLAIN_VERDICT = re.compile(r"(?!Image )([^:]+): (Pass|Fail|N/A)(?:\.|\s[-–])\s*(\S.*)")
IMAGE_DETAIL = re.compile(r"Image (\S+?\.png)\s*[:—–-]+\s*(.+)")
VERDICT_WORDS = frozenset(("pass", "fail", "n/a"))
VERDICTS = {"VERDICT: clean": "clean", "VERDICT: findings": "findings"}
VERDICT_OUTCOMES = frozenset(VERDICTS.values())


def clean_line(line: str) -> str:
    """A reviewer line in the stored form `Rule: Pass — text`: no bullet or bold marks, a count note such as `(clicks: 2)`, before the colon or right after the verdict, moved after the text, and the plain verdict forms `Pass. text` and `Pass - text` set to the stored dash."""
    text = line.strip().replace("**", "").replace("`", "")
    text = BULLET.sub("", text)
    found = COUNT_NOTE.match(text)
    text = f"{found[1]}: {found[3]} {found[2]}" if found else text
    after = NOTE_AFTER_VERDICT.fullmatch(text)
    if after:
        return f"{after[1]}: {after[2]} — {after[4]} {after[3]}"
    plain = PLAIN_VERDICT.fullmatch(text)
    return f"{plain[1]}: {plain[2]} — {plain[3]}" if plain else text


def answer_lines(raw: list[str]) -> list[str]:
    """The answer's lines in the stored form, with each rule's block (its rule line and every line below it up to the next rule line or image line) joined into one line."""
    names = {name for name, _ in usability_rules()}
    groups: list[list[str]] = []
    in_rule = False
    for text in raw:
        cleaned = clean_line(text)
        label, verdict, _, _ = split_rule_line(cleaned)
        if label in names and (
            verdict.lower() in VERDICT_WORDS or not text[:1].isspace()
        ):
            groups.append([text])
            in_rule = True
        elif (
            in_rule
            and not IMAGE_DETAIL.match(cleaned)
            and not RECHECK_LINE.match(cleaned)
        ):
            if cleaned:
                groups[-1].append(BULLET.sub("", text.strip()))
        else:
            groups.append([text])
            in_rule = False
    return [clean_line(" ".join(group)) for group in groups]


def nothing_removed(line: str) -> bool:
    """True when the line gives removed counts, one for each screen, and every one is 0. A count after the word `removed` wins over one before it, so `kept 34 removed 0` reads 0."""
    found = list(REMOVED_AFTER.finditer(line)) or list(REMOVED_BEFORE.finditer(line))
    counts = [int(number) for match in found for number in NUMBER.findall(match[1])]
    return bool(counts) and not any(counts)


class Item(NamedTuple):
    text: str
    frame: str
    element: str
    kind: str
    note: str


def fail_parts(line: str) -> tuple[list[str], str]:
    """The parts of a Fail line before its last `Fix:`, and the Fix part. A new part starts at each `;` and at each item after the first of a chunk, so a list with no `;` is still one item for each part."""
    text = split_rule_line(line)[2]
    fixes = list(FIX_PART.finditer(text))
    cut = fixes[-1].start() if fixes else len(text)
    parts: list[str] = []
    for chunk in text[:cut].split(";"):
        starts = [found.start() for found in ITEM_START.finditer(chunk)]
        edges = [0, *starts[1:], len(chunk)]
        parts.extend(chunk[a:b] for a, b in pairwise(edges) if chunk[a:b].strip())
    return parts, text[cut:]


def part_item(part: str) -> tuple[str, Item | None]:
    """The words of a part before its item, and its item `image-N.png: <element> [kind]`, if it has one."""
    found = ITEM_START.search(part)
    if not found:
        return part, None
    text = part[found.start() :].strip()
    frame, _, rest = text.partition(":")
    tag = KIND_TAG.search(rest)
    element = (rest[: tag.start()] if tag else rest).strip()
    note = rest[tag.end() :].strip(" -:—") if tag else ""
    kind = tag[1].lower() if tag else ""
    return part[: found.start()], Item(text, frame.strip(), element, kind, note)


Keys = Mapping[str, Mapping[str, frozenset[str]]]


def item_problem(rule_lines: list[str], keys: Keys | None = None) -> str | None:
    """Why a Fail line cannot stand: a size, ratio or colour stated anywhere but in an item of a measured kind, or, when the keys of the images are given, an item of a measured kind whose element is not a key of its image for that kind. A missing or unknown kind is a judgement item and never refuses the line."""
    from ui_measure import MEASURED_KINDS

    for line in rule_lines:
        if split_rule_line(line)[1] != "Fail":
            continue
        for part in fail_parts(line)[0]:
            prose, item = part_item(part)
            states = CLAIM.search(prose) or (
                None if item and item.kind in MEASURED_KINDS else CLAIM.search(part)
            )
            if states:
                return (
                    f"not done: a Fail line states {states[0]} outside an item of a measured kind "
                    f"({', '.join(sorted(MEASURED_KINDS))}); write `image-N.png: <key> [kind]` or leave the number out: {line}"
                )
            if keys is not None and item and (found := key_problem(item, keys, line)):
                return found
    return None


def key_problem(item: Item, keys: Keys, line: str) -> str | None:
    """Why an item cannot stand by its key: an item of a measured kind whose element is no key of its image for that kind, or an item of another kind that states a claim form about a measured element, which code must check."""
    from ui_measure import MEASURED_KINDS

    held = keys.get(item.frame, {})
    if item.kind in MEASURED_KINDS:
        if item.element in held.get(item.kind, ()):
            return None
        return (
            f"not done: `{item.frame}: {item.element} [{item.kind}]` names no key of that image for the kind {item.kind}. "
            f"Copy one key exactly as the measured values list it, with no other word before the tag, "
            f"or tag the item [judgement]: {line}"
        )
    if found := claim_in(f"{item.element} {item.note}", held):
        kind, key, word = found
        return (
            f"not done: `{item.text}` states a claim about a measured element ({word} about {key}). "
            f"Write it as `{item.frame}: {key} [{kind}] <note>`, with the key copied exactly, "
            f"so that code checks the claim against the measured value. {CLAIM_NOTES[kind]}: {line}"
        )
    return None


def rule_refusal(
    rule_lines: list[str], names: list[str], keys: Keys | None = None
) -> str | None:
    """Why a Fail line cannot stand: its own count says 0 removed, it names no fix or no frame of the run, it states a measured fact outside a measured item, or a measured item has no key."""
    if empty := [
        line
        for line in rule_lines
        if split_rule_line(line)[:2] == ("No clutter", "Fail") and nothing_removed(line)
    ]:
        return f"not done: No clutter is a Fail, but its own count says 0 removed: {empty[0]}"
    if unfixed := [
        line
        for line in rule_lines
        if split_rule_line(line)[1] == "Fail" and not FIX_PART.search(line)
    ]:
        return f"not done: a Fail line names no `Fix: <the change>`: {unfixed[0]}"
    if unframed := [
        line
        for line in rule_lines
        if split_rule_line(line)[1] == "Fail"
        and not any(name in FRAME.findall(line) for name in names)
    ]:
        return f"not done: a Fail line names no frame (image-N.png) of this run: {unframed[0]}"
    return item_problem(rule_lines, keys)


def judged_names(unmeasured: bool = False) -> list[str]:
    """The Usability rules with the judgement kind: the rules that the reviewer decides. An image with no measure record has no owner for a `measured` rule, so then the reviewer decides that rule too."""
    from ui_measure import PROOF_KINDS

    return [
        name
        for name, _ in usability_rules()
        if "judgement" in PROOF_KINDS[name]
        or (unmeasured and "measured" in PROOF_KINDS[name])
    ]


def judged_lines(unmeasured: bool = False) -> list[str]:
    """The rule lines of the rules that the reviewer decides."""
    wanted = set(judged_names(unmeasured))
    return [
        line
        for line, (name, _) in zip(usability_lines(), usability_rules(), strict=True)
        if name in wanted
    ]


def judge(
    answer: str,
    names: list[str],
    read: dict[str, bool],
    *,
    require_design: bool = False,
    unmeasured: bool = False,
    rechecks: list[str] | None = None,
    keys: Keys | None = None,
) -> tuple[str, list[str], dict[str, str]]:
    """The outcome, the rule lines and the image details of the reviewer's answer."""
    if unread := [name for name in names if not read[name]]:
        return f"not done: the reviewer did not open {', '.join(unread)}", [], {}
    raw = answer.strip().splitlines()
    if not raw or clean_line(raw[-1]) not in VERDICTS:
        return "not done: the reviewer gave no exact VERDICT line", [], {}
    lines = [*answer_lines(raw[:-1]), clean_line(raw[-1])]
    wanted = judged_names(unmeasured)
    found = {
        split_rule_line(line)[0]: line
        for line in lines
        if split_rule_line(line)[0] in wanted
    }
    details = {
        found[1]: found[2].strip()
        for found in (IMAGE_DETAIL.match(line) for line in lines)
        if found
    }
    if missing := [name for name in wanted if name not in found]:
        return f"not done: the reviewer skipped the rule {missing[0]}", [], {}
    bad = [line for line in found.values() if split_rule_line(line)[3]]
    if bad or not all(details.get(name) for name in names):
        return (
            "not done: a rule line or an image detail is empty or has the wrong form",
            [],
            {},
        )
    if require_design and split_rule_line(found["Design system"])[1] == "N/A":
        return (
            "not done: Design system cannot be N/A when DESIGN.md is present",
            [],
            {},
        )
    rule_lines = [found[name] for name in wanted]
    if refusal := rule_refusal(rule_lines, names, keys):
        return refusal, [], {}
    if refusal := recheck_problem(lines, rule_lines, rechecks or [], names):
        return refusal, [], {}
    failed = any(split_rule_line(line)[1] == "Fail" for line in rule_lines)
    outcome = "findings" if failed or VERDICTS[lines[-1]] == "findings" else "clean"
    return outcome, rule_lines, details


def recheck_lines(answer: str) -> list[str]:
    """The `Recheck R<n>: ...` lines of the reviewer's answer, as `R<n>: ...`."""
    return [
        line.partition(" ")[2]
        for line in (clean_line(raw) for raw in answer.strip().splitlines())
        if RECHECK_LINE.match(line)
    ]


def recheck_problem(
    lines: list[str], rule_lines: list[str], rules: list[str], names: list[str]
) -> str | None:
    """Why the answer to the earlier findings cannot stand: an item with no line, a line with no frame of the run, or `still shown` for a rule with no Fail line."""
    answers: dict[int, tuple[str, str]] = {}
    for line in lines:
        if found := RECHECK_LINE.match(line):
            answers.setdefault(int(found[1]), (found[2].lower(), found[3]))
    failed = {
        split_rule_line(line)[0]
        for line in rule_lines
        if split_rule_line(line)[1] == "Fail"
    }
    for number, rule in enumerate(rules, 1):
        if number not in answers:
            return f"not done: the reviewer skipped Recheck R{number}"
        verdict, text = answers[number]
        if not any(name in FRAME.findall(text) for name in names):
            return (
                f"not done: Recheck R{number} names no frame (image-N.png) of this run"
            )
        if verdict == "still shown" and rule not in failed:
            return f"not done: Recheck R{number} says still shown, but {rule} is not a Fail"
    return None
