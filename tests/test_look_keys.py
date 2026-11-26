"""Code decides alignment, the zero token and every measured look item from an exact key; an item with no key is refused by form."""

from pathlib import Path

from look_facts import Tokens
from test_look_facts import answer_with, control, text_fact, tokens_of, values

ZERO_DESIGN = (
    "---\ncolors:\n  ink: '#1a1a1a'\nspacing:\n  none: 0\n  sm: 8px\n"
    "rounded:\n  none: 0\n  sm: 4px\n---\n# Design\n"
)


def test_a_zero_token_is_a_length_and_keeps_the_other_verdicts() -> None:
    import look_facts

    tokens = look_facts.tokens_from_text(ZERO_DESIGN)
    assert look_facts.length_scale(tokens.rounded, 16) == {0, 4}
    assert look_facts.length_scale(tokens.spacing, 16) == {0, 8}
    radius = values(radii=[{"at": "Save", "px": 5, "clamped": False}])
    gap = values(gaps=[{"at": "Save", "to": "Cancel", "px": 5, "axis": "y"}])
    off_radius = look_facts.verdict("radius", "Save", radius, tokens)
    off_gap = look_facts.verdict("gap", "Save to Cancel", gap, tokens)
    assert off_radius is not None
    assert off_radius[0] is False
    assert off_gap is not None
    assert off_gap[0] is False


def test_code_decides_text_alignment(tmp_path: Path) -> None:
    import look_facts

    tokens = tokens_of(tmp_path)
    measured = values(
        texts=[
            text_fact("Intro line", 14, align="start", centred=False),
            text_fact("Section title", 20, align="center", centred=True),
            text_fact("Old line", 14),
        ]
    )
    left = look_facts.verdict("align", "Intro line", measured, tokens)
    assert left is not None
    assert left[0] is False
    assert left[1] == "text-align start, not centred in its parent"
    middle = look_facts.verdict("align", "Section title", measured, tokens)
    assert middle is not None
    assert middle[0] is True
    assert look_facts.verdict("align", "Old line", measured, tokens) is None
    listed = look_facts.measured_text(measured, tokens)
    assert "- Intro line: 14 px, weight 400, align start, colour" in listed
    assert (
        "- Section title: 20 px, weight 400, align center (centred), colour" in listed
    )
    assert (
        "align: checked for all 2 text elements: 1 not centred in their parent"
        in listed
    )


def test_the_tap_fact_of_a_link_at_its_floor_says_so_and_code_decides_it(
    tmp_path: Path,
) -> None:
    import look_facts

    tokens = tokens_of(tmp_path)
    measured = values(
        sizes={
            "controls": [
                control("Footer home", 90, 44, floor=44),
                control("Footer help", 90, 20, floor=44, under=True),
            ]
        }
    )
    listed = look_facts.measured_text(measured, tokens)
    assert "- Footer home: 90x44 px, at or over 44 px" in listed
    assert "- Footer help: 90x20 px, under 44 px" in listed
    found = look_facts.verdict("tap", "Footer home", measured, tokens)
    assert found is not None
    assert found[0] is True


UNSAFE_NAMES = [
    "Save; draft",
    "Fix: now",
    "**bold** `code`",
    "Tab [new]",
    '"quoted" name',
    "Plain",
    "",
    "image-2.png: Next",
    "Overdue tasks: 1",
]


def keyed(
    measured: dict[str, object], tokens: Tokens
) -> dict[str, dict[str, frozenset[str]]]:
    import look_facts

    return {"image-1.png": look_facts.item_keys(measured, tokens)}


def judged_with_keys(
    fail: str, measured: dict[str, object] | None, tokens: Tokens
) -> tuple[str, list[str]]:
    import look_answer

    keys = keyed(measured, tokens) if measured is not None else {"image-1.png": {}}
    outcome, rules, _ = look_answer.judge(
        answer_with(fail), ["image-1.png"], {"image-1.png": True}, keys=keys
    )
    return outcome, rules


def test_a_measured_item_is_decided_from_its_exact_key(tmp_path: Path) -> None:
    import look_answer
    import look_facts

    tokens = tokens_of(tmp_path)
    measured = values(
        texts=[text_fact(name, 10.5, under=True) for name in UNSAFE_NAMES],
        gaps=[{"at": "Save; draft", "to": "Fix: now", "px": 11, "axis": "y"}],
    )
    keys = sorted(look_facts.item_keys(measured, tokens)["size"])
    assert len(keys) == len(UNSAFE_NAMES)
    assert "no name" in keys
    for key in [*keys, "Save draft to Fix now"]:
        kind = "gap" if " to " in key else "size"
        outcome, rules = judged_with_keys(
            f"image-1.png: {key} [{kind}] Fix: change it", measured, tokens
        )
        assert outcome == "findings", key
        parts, _ = look_answer.fail_parts(
            next(r for r in rules if "Design system" in r)
        )
        _, item = look_answer.part_item(parts[0])
        assert item is not None
        assert item.element == key
        found = look_facts.verdict(kind, key, measured, tokens)
        assert found is not None
        assert found[0] is False
    assert look_facts.verdict("size", "Save button", measured, tokens) is None
    assert look_facts.verdict("size", "save draft", measured, tokens) is None
    listed = look_facts.measured_text(measured, tokens)
    assert "- Save draft: 10.5 px" in listed
    assert "- no name: 10.5 px" in listed


def test_a_measured_item_with_no_valid_key_is_refused_by_form(tmp_path: Path) -> None:
    tokens = tokens_of(tmp_path)
    measured = values(
        texts=[text_fact("Hint", 14)],
        gaps=[{"at": "THU 26 Nov", "to": "10:00 GMT", "px": 18, "axis": "y"}],
    )
    for fail in (
        "image-1.png: THU 26 Nov to 10:00 GMT, 18 px [gap] Fix: close it",
        "image-1.png: Hint button [size] Fix: bigger",
        "image-1.png: Hint [gap] Fix: close it",
        "image-1.png: Missing element [colour] Fix: ink",
    ):
        outcome, rules = judged_with_keys(fail, measured, tokens)
        assert outcome.startswith("not done: `image-1.png: "), fail
        assert "names no key of that image" in outcome
        assert "[judgement]" in outcome
        assert rules == []
    for fail in (
        "image-1.png: THU 26 Nov to 10 00 GMT [gap] 18 px, not a token Fix: close it",
        "image-1.png: Hint [size] Fix: bigger",
        "image-1.png: the card sits left of its title [judgement] Fix: centre it",
    ):
        outcome, rules = judged_with_keys(fail, measured, tokens)
        assert outcome == "findings", fail
        assert any(line.startswith("Design system: Fail") for line in rules)
    outcome, rules = judged_with_keys(
        "image-1.png: Hint [size] Fix: bigger", None, tokens
    )
    assert outcome.startswith("not done: `image-1.png: Hint [size]` names no key")
    outcome, rules = judged_with_keys(
        "image-1.png: Hint [judgement] Fix: bigger", None, tokens
    )
    assert outcome == "findings"


def proof_text(
    name: str,
    size: float,
    weight: int,
    colour: str,
    fill: str,
    fg: str,
    bg: str,
    **extra: object,
) -> dict[str, object]:
    return text_fact(
        name, size, weight=weight, colour=colour, fill=fill, fg=fg, bg=bg, **extra
    )


RELEASE_PROOF = values(
    texts=[
        proof_text(
            "Rescheduled from 05:45",
            12,
            500,
            "4a5a5aff",
            "eef1f1ff",
            "#4a5a5a",
            "#eef1f1",
        ),
        proof_text(
            "Forms needed", 12, 600, "7a5a3aff", "fff6e0ff", "#7a5a3a", "#fff6e0"
        ),
        *[
            proof_text(
                name,
                12,
                600,
                "2a6a50ff",
                "e6efe9bf",
                "#2a6a50",
                "#eef3f0",
                align="start",
                centred=False,
            )
            for name in ("Round", "5", "/36")
        ],
        proof_text("THU", 12, 700, "2a6a50ff", "e6efe959", "#2a6a50", "#f7f9f8"),
        proof_text("26 Nov", 14, 700, "2a6a50ff", "e6efe959", "#2a6a50", "#f7f9f8"),
        proof_text(
            "A helper sentence",
            16,
            400,
            "2b3d4fff",
            "ffffffff",
            "#2b3d4f",
            "#ffffff",
        ),
        proof_text("Send notes", 16, 500, "2a6a50ff", "e6efe9ff", "#2a6a50", "#e6efe9"),
        proof_text(
            "Guides intro",
            14,
            400,
            "1a1a1aff",
            "e6efe9ff",
            "#1a1a1a",
            "#e6efe9",
            align="start",
            centred=False,
        ),
        proof_text(
            "Section title",
            20,
            600,
            "1a1a1aff",
            "e6efe9ff",
            "#1a1a1a",
            "#e6efe9",
            align="center",
            centred=True,
        ),
    ],
    gaps=[
        {"at": "Rescheduled from 05:45", "to": "Forms needed", "px": 9, "axis": "x"},
        {
            "at": "A helper sentence",
            "to": "Send notes",
            "px": 12,
            "axis": "y",
        },
        {"at": "THU 26 Nov", "to": "10:00 GMT", "px": 18, "axis": "y"},
        {"at": "Round", "to": "5", "px": 6, "axis": "x"},
        {"at": "5", "to": "/36", "px": 6, "axis": "x"},
    ],
)
PROOF_FRAMES: dict[str, dict[str, object] | None] = dict.fromkeys(
    ("image-1.png", "image-2.png", "image-3.png"), RELEASE_PROOF
)


def listed_keys(tokens: Tokens) -> set[str]:
    import look_facts

    text = look_facts.measured_text(RELEASE_PROOF, tokens)
    return {
        line[2:].split(": ", 1)[0]
        for line in text.splitlines()
        if line.startswith("- ")
    }


def test_the_real_items_of_the_release_proof_are_decided_from_keys(
    tmp_path: Path,
) -> None:
    import look_records

    tokens = tokens_of(tmp_path)
    keys = listed_keys(tokens)
    gap_keys = [
        "Rescheduled from 05 45 to Forms needed",
        "A helper sentence to Send notes",
        "THU 26 Nov to 10 00 GMT",
    ]
    colour_keys = ["Rescheduled from 05 45", "Round", "26 Nov"]
    assert set(gap_keys) <= keys
    assert set(colour_keys) <= keys
    spacing = (
        "Spacing: Fail — "
        + "; ".join(
            f"image-{number}.png: {key} [gap] {px} px, not a spacing token"
            for key, px in zip(gap_keys, (9, 12, 18), strict=True)
            for number in (1, 2)
        )
        + ". Fix: use a token."
    )
    colour = (
        "Design system: Fail — "
        + "; ".join(
            f"image-{number}.png: {key} [colour] not a token"
            for key in colour_keys
            for number in (1, 2, 3)
        )
        + ". Fix: use a token."
    )
    decided = look_records.decide_line(spacing, PROOF_FRAMES, tokens)
    assert decided.count(" — code: ") == 6
    assert "gap 18 px is not a spacing token" in decided
    decided = look_records.decide_line(colour, PROOF_FRAMES, tokens)
    assert decided.count(" — code: ") == 9
    assert "is not in the colour tokens" in decided


def test_the_counter_and_the_centred_items_are_decided_by_code(tmp_path: Path) -> None:
    import look_records

    tokens = tokens_of(tmp_path)
    assert {"Round to 5", "5 to /36"} <= listed_keys(tokens)
    counter_line = (
        "Spacing: Fail — image-1.png: 5 [weight] bolder than Round and /36; "
        "image-1.png: Round to 5 [gap] uneven against 5 to /36. Fix: even them."
    )
    decided = look_records.decide_line(counter_line, PROOF_FRAMES, tokens)
    assert "5 [weight]" not in decided
    assert (
        "image-1.png: Round to 5 [gap] — code: gap 6 px is not a spacing token"
        in decided
    )
    centred_line = (
        "Alignment: Fail — image-1.png: Guides intro [align] sits on the left edge; "
        "image-1.png: Section title [align] not centred. Fix: centre the intro."
    )
    decided = look_records.decide_line(centred_line, PROOF_FRAMES, tokens)
    assert (
        "Guides intro [align] — code: text-align start, not centred in its parent"
        in decided
    )
    assert "Section title" not in decided


def test_the_old_shape_of_the_release_proof_items_is_refused_by_form(
    tmp_path: Path,
) -> None:
    tokens = tokens_of(tmp_path)
    for old in (
        "THU 26 Nov to 10:00 GMT, 18 px",
        "A status badge, ink #4a5a5a on fill #eef1f1, neither is a token",
        "Round 5 /36 badge fill #eef3f0, not mint #E6EFE9",
    ):
        kind = "gap" if " to " in old else "colour"
        outcome, _ = judged_with_keys(
            f"image-1.png: {old} [{kind}] Fix: use a token", RELEASE_PROOF, tokens
        )
        assert outcome.startswith("not done: `image-1.png: "), old


def test_weight_keys_skip_unnamed_and_repeated_elements(tmp_path: Path) -> None:
    import look_facts

    tokens = tokens_of(tmp_path)
    measured = values(
        texts=[
            text_fact("Round", 12, weight=600),
            text_fact("5", 12, weight=600),
            text_fact("Overdue", 12, weight=400),
            text_fact("5", 12, weight=600),
            text_fact("", 12, weight=400),
            text_fact("Hero title", 12, weight=700),
        ],
    )
    keys = look_facts.item_keys(measured, tokens)["weight"]
    assert keys == {"Round", "Overdue", "Hero title"}
    assert (
        look_facts.verdict("weight", "5", measured, tokens, "bolder than Round") is None
    )


def test_a_link_in_a_sentence_is_not_said_to_meet_the_floor(tmp_path: Path) -> None:
    import look_facts

    tokens = tokens_of(tmp_path)
    measured = values(
        sizes={"controls": [control("terms", 100, 18, floor=44, exempt=True)]}
    )
    listed = look_facts.measured_text(measured, tokens)
    assert "- terms: 100x18 px, inline link, exempt from the 44 px floor" in listed
    assert "at or over" not in listed.partition("tap size")[2].partition("\n")[2]


def test_a_key_whose_facts_disagree_has_no_key_and_its_item_is_refused(
    tmp_path: Path,
) -> None:
    import look_facts

    tokens = tokens_of(tmp_path)
    measured = values(
        sizes={"controls": [control("Edit", 80, 44), control("Edit", 60, 30)]},
        texts=[
            text_fact("Settings", 14, align="center", centred=True),
            text_fact("Settings", 14, align="start", centred=False),
        ],
    )
    keys = look_facts.item_keys(measured, tokens)
    assert look_facts.verdict("tap", "Edit", measured, tokens) is None
    assert "Edit" not in keys["tap"]
    assert look_facts.verdict("align", "Settings", measured, tokens) is None
    assert "Settings" not in keys["align"]
    outcome, _ = judged_with_keys(
        "image-1.png: Edit [tap] looks like 10 px Fix: make it bigger",
        measured,
        tokens,
    )
    assert outcome.startswith("not done: `image-1.png: Edit [tap]`")


def test_a_listed_fact_that_code_cannot_decide_says_it_has_no_key() -> None:
    import look_facts

    tokens = look_facts.tokens_from_text(
        "---\ncolors:\n  ink: '#1a1a1a'\n---\n# Design\n"
    )
    measured = values(
        gaps=[{"at": "Place order", "to": "Cancel", "px": 4, "axis": "x"}],
        sizes={"controls": [control("Place order", 96, 32)]},
    )
    listed = look_facts.measured_text(measured, tokens).splitlines()
    gap = [line for line in listed if line.startswith("- Place order to Cancel")]
    tap = [line for line in listed if line.startswith("- Place order:")]
    assert len(gap) == 1
    assert "no key" in gap[0]
    assert len(tap) == 1
    assert "no key" not in tap[0]
    assert look_facts.item_keys(measured, tokens)["gap"] == frozenset()


def test_each_text_kind_lists_its_own_keys_and_a_disagreeing_key_is_not_listed(
    tmp_path: Path,
) -> None:
    import look_facts

    tokens = tokens_of(tmp_path)
    measured = values(
        texts=[
            text_fact("Even one", 14, weight=400),
            text_fact("Bold two", 14, weight=700),
            text_fact("Settings", 14, align="center", centred=True),
            text_fact("Settings", 14, align="start", centred=False),
            text_fact("Heading", 20, align="start", centred=False),
        ],
        gaps=[{"at": "Even one", "to": "Bold two", "px": 8, "axis": "x"}],
    )
    listed = look_facts.measured_text(measured, tokens).splitlines()
    weight = [line for line in listed if line.startswith("weight keys:")]
    align = [line for line in listed if line.startswith("align keys:")]
    assert weight == ["weight keys: Bold two | Even one | Heading"]
    assert len(align) == 1
    assert "Heading" in align[0]
    assert "Settings #1" in align[0]
    assert "Settings #2" in align[0]
    assert " Settings |" not in f" {align[0]} |"


def test_a_failing_key_leads_the_colour_keys_even_on_a_long_page(
    tmp_path: Path,
) -> None:
    import look_facts

    tokens = tokens_of(tmp_path)
    names = [f"Label number {number:02d} of the list" for number in range(70)]
    measured = values(
        texts=[
            *(text_fact(name, 14, align="start", centred=False) for name in names),
            text_fact("Zed total", 14, colour="767676ff", fg="#767676"),
            text_fact("Zed title", 20, align="center", centred=True),
        ]
    )
    listed = look_facts.measured_text(measured, tokens).splitlines()
    colour = [line for line in listed if line.startswith("colour keys:")]
    align = [line for line in listed if line.startswith("align keys:")]
    assert len(colour) == 1
    assert colour[0].startswith("colour keys: Zed total | ")
    assert len(align) == 1
    assert "Zed title" in align[0]
    assert "more keys" not in align[0]
    assert names[-1] in align[0]
