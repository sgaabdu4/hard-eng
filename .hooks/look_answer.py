"""The reviewer's answer to a look run: its lines, the rules it decides, and why a line cannot stand."""

import re

from plans import split_rule_line, usability_lines, usability_rules

FIX_PART = re.compile(r"(?i)\bfix:\s*\S")
FRAME = re.compile(r"image-\d+\.png")
RECHECK_LINE = re.compile(r"(?i)^recheck\s+R(\d+)\s*:\s*(still shown|gone)\b(.*)")
NUMBER = re.compile(r"\d+")
COUNT_LIST = r"\d+(?:\s*/\s*\d+)*"
REMOVED_AFTER = re.compile(rf"(?i)\bremoved\s*:?\s*({COUNT_LIST})")
REMOVED_BEFORE = re.compile(rf"(?i)\b({COUNT_LIST})\s+removed\b")
BULLET = re.compile(r"^[-*•]\s+")
COUNT_NOTE = re.compile(r"([^:(]+?)\s*(\([^)]*\))\s*:\s*(.*)")
PLAIN_VERDICT = re.compile(r"(?!Image )([^:]+): (Pass|Fail|N/A)(?:\.|\s[-–])\s*(\S.*)")
IMAGE_DETAIL = re.compile(r"Image (\S+?\.png)\s*[:—–-]+\s*(.+)")
VERDICTS = {"VERDICT: clean": "clean", "VERDICT: findings": "findings"}
VERDICT_OUTCOMES = frozenset(VERDICTS.values())


def clean_line(line: str) -> str:
    """A reviewer line in the stored form `Rule: Pass — text`: no bullet or bold marks, a count note such as `(clicks: 2)` moved after the text, and the plain verdict forms `Pass. text` and `Pass - text` set to the stored dash."""
    text = line.strip().replace("**", "").replace("`", "")
    text = BULLET.sub("", text)
    found = COUNT_NOTE.match(text)
    text = f"{found[1]}: {found[3]} {found[2]}" if found else text
    plain = PLAIN_VERDICT.fullmatch(text)
    return f"{plain[1]}: {plain[2]} — {plain[3]}" if plain else text


def nothing_removed(line: str) -> bool:
    """True when the line gives removed counts, one for each screen, and every one is 0. A count after the word `removed` wins over one before it, so `kept 34 removed 0` reads 0."""
    found = list(REMOVED_AFTER.finditer(line)) or list(REMOVED_BEFORE.finditer(line))
    counts = [int(number) for match in found for number in NUMBER.findall(match[1])]
    return bool(counts) and not any(counts)


def rule_refusal(
    rule_lines: list[str], measured: list[dict[str, object]], names: list[str]
) -> str | None:
    """Why a Fail line cannot stand: its own count says 0 removed, it names no fix or no frame of the run, or it guesses a px size that the measured values do not hold."""
    from look_px import px_problem

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
    return px_problem(rule_lines, measured)


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
    measured: list[dict[str, object]] | None = None,
    unmeasured: bool = False,
    rechecks: list[str] | None = None,
) -> tuple[str, list[str], dict[str, str]]:
    """The outcome, the rule lines and the image details of the reviewer's answer."""
    if unread := [name for name in names if not read[name]]:
        return f"not done: the reviewer did not open {', '.join(unread)}", [], {}
    lines = [clean_line(line) for line in answer.strip().splitlines()]
    if not lines or lines[-1] not in VERDICTS:
        return "not done: the reviewer gave no exact VERDICT line", [], {}
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
    if refusal := rule_refusal(rule_lines, measured or [], names):
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
