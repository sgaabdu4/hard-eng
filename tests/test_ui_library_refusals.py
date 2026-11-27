"""The library refusals of the whole-project UI pass name the step that a project takes."""

import shutil
from pathlib import Path

from test_ui_single_source import build, library_message, refusal
from ui_library import expected_index, index_text


def test_the_empty_library_refusal_names_the_key_and_the_value(tmp_path: Path) -> None:
    """HE-UI-SOURCE: an empty ui_library names the key, and the value when one `ui` folder holds the shared parts."""
    named = library_message(tmp_path / "a", ui_library=[])
    assert 'shipping "ui_library": ["src/ui/*"]' in named
    root = build(tmp_path / "b", "web-fixed", ui_library=[])
    shutil.move(root / "src/ui", root / "src/shared")
    generic = refusal(root)
    assert 'shipping "ui_library": ["<folder>/*"]' in generic
    assert "src/shared" not in generic.split('shipping "ui_library"')[1].split("\n")[0]


def test_a_file_outside_ui_paths_names_both_fixes(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a stylesheet outside ui_paths may be a shipped screen or a preview; the line gives the step for each."""
    root = build(tmp_path, "web-fixed")
    (root / "previews").mkdir()
    (root / "previews/base.css").write_text("body { margin: 0; }\n")
    line = next(
        row
        for row in refusal(root).splitlines()
        if "previews/base.css: a stylesheet outside ui_paths" in row
    )
    assert "add its folder to ui_paths" in line
    assert ".gitignore" in line


def _library_project(root: Path, parts: int, use: str, design: str) -> str:
    from ui_library import index_findings

    root.mkdir()
    texts = {
        f"src/ui/Part{number}.tsx": f"export const Part{number} = () => null;\n"
        for number in range(parts)
    }
    library = ["src/ui/*"]
    uses = {
        entry: dict.fromkeys(names, use)
        for entry, names in expected_index(texts, library).items()
    }
    index = index_text(texts, library, uses)
    assert index_findings({**texts, "UI-LIBRARY.md": index}, library) == []
    (root / "DESIGN.md").write_text(design)
    (root / "UI-LIBRARY.md").write_text(index)
    return index


def test_a_written_library_and_a_full_design_md_reach_look_whole(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: the index that Hard Eng requires never forces a cut or a refusal of a full DESIGN.md: 200 parts with full use lines beside a 22,700-byte DESIGN.md reach the reviewer whole."""
    import look

    design = "---\ncolors:\n  ink: '#111111'\n---\n\n# Design\n" + (
        "- A rule line that the reviewer must see in full.\n" * 450
    )
    design += "- The last rule.\n"
    use = "Use for the main action of a form or dialog; one per group, the rest plain."
    index = _library_project(tmp_path / "real", 200, use, design)
    assert len(design.encode()) + len(index.encode()) > 38_000
    text = look.design_text(tmp_path / "real")
    assert "- The last rule." in text
    assert "`Part99`" in text and text.rstrip().endswith(use)


def test_a_library_of_2000_parts_with_short_use_lines_reaches_look_whole(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: a refusal of the design text always has a fix in the project; short use lines bring even 2,000 parts inside the limit."""
    import look

    _library_project(
        tmp_path / "big",
        2000,
        "a part",
        "---\ncolors:\n  ink: '#111111'\n---\n\n# Big\n",
    )
    assert "`Part1999` — a part" in look.design_text(tmp_path / "big")


def test_the_ui_refusal_header_says_the_rule_is_intended_and_fixed_in_the_project(
    tmp_path: Path,
) -> None:
    """The first failed check after an update is printed by the new release, so its header carries the line."""
    message = library_message(tmp_path, ui_library=[])
    assert "The rule is intended and has no waiver; fix the project" in message
