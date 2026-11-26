"""The rule text and the skill references that describe the single UI source."""

from pathlib import Path

SKILLS = Path(__file__).parents[1] / ".agents/skills"


def read_skill(name: str) -> str:
    return (SKILLS / name).read_text()


def requirement_text() -> str:
    text = read_skill("he/references/requirements.md")
    start = text.index("## HE-UI-SOURCE")
    return text[start : text.index("\n## ", start + 1)]


def test_requirement_text_names_every_kind() -> None:
    """HE-UI-SOURCE names each whole-project kind, the library, the index, the token compare, the coverage rule and the exemptions."""
    text = requirement_text()
    for word in (
        "whole project",
        "ui_paths",
        "ui_library",
        "UI-LIBRARY.md",
        "DESIGN.md",
        "front matter",
        "base element",
        "`<button`",
        "Tailwind default palette",
        "component file",
        "email",
        "standalone page",
        "PDF",
        "generated",
        "no waiver",
    ):
        assert word in text, word


def test_the_first_requirement_paragraph_speaks_of_the_quick_check_only() -> None:
    """HE-UI-SOURCE: the added-lines paragraph names the quick check, so it does not contradict the whole-project paragraph."""
    first, whole = requirement_text().split("\n\n")[1:3]
    assert first.startswith("The quick check fails a change when its added lines")
    assert "A change fails when" not in first
    assert "the quick check does not flag lines that existed before" in first
    assert whole.startswith("The full check also judges the whole project, old lines")


def test_ui_reference_names_the_fixed_parts() -> None:
    """ui.md names the five shared parts, bars a description slot and uses the same role words as ui_library.py."""
    from ui_library import FIXED_ROLES

    text = read_skill("codebase-design/references/ui.md")
    for words in FIXED_ROLES.values():
        assert words[0] in text, words[0]
    assert "no description or subtitle slot" in text


def test_ui_reference_states_the_layers() -> None:
    """ui.md states the five layers, keeps atomic folder names and names the library index."""
    text = read_skill("codebase-design/references/ui.md")
    for word in ("Fixed UX rules", "DESIGN.md", "Token files", "Library", "Screens"):
        assert word in text, word
    assert "atomic" in text.lower()
    assert "UI-LIBRARY.md" in text


def test_templates_point_to_the_one_source() -> None:
    """The planner reads the DESIGN.md front matter and UI-LIBRARY.md before it names the controls; the template holds the front matter groups."""
    grounding = next(
        line
        for line in read_skill("he-plan/references/ux.md").splitlines()
        if line.startswith("- Grounding")
    )
    assert "front matter" in grounding
    assert "UI-LIBRARY.md" in grounding
    template = read_skill("he/templates/DESIGN.md")
    for word in ("colors:", "spacing:", "rounded:", "typography:", "UI-LIBRARY.md"):
        assert word in template, word


def test_ux_text_names_the_gap_items() -> None:
    reference = read_skill("he-plan/references/ux.md")
    for words in (
        "think and remember as little as possible",
        "Alignment:",
        "Spacing:",
        "Design system:",
        "plain, calm and positive",
        "phone 390, tablet 768 and desktop 1280 px",
        "A Pass line you type is a claim, not proof",
    ):
        assert words in reference, words


def test_ux_text_states_the_measured_limits() -> None:
    from ui_measure import LIMITS

    reference = read_skill("he-plan/references/ux.md")
    floor = LIMITS["text_px"]
    assert (
        f"Text at least {floor} pt on iOS, {floor} sp on Android and {floor} px on the web"
        in reference
    )
    assert f"at most {LIMITS['accent_colours']} accent colours" in reference
    assert f"{LIMITS['control_px']} × {LIMITS['control_px']} px on the web" in reference
    assert f"{LIMITS['link_px']} × {LIMITS['link_px']} px (WCAG" in reference
    assert f"over {LIMITS['secondary_words']} words" in reference
