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


def test_a_large_library_passes_the_index_check_and_the_look_excerpt_stays_bounded(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: no refusal stops a library of 2,000 parts; the look excerpt keeps DESIGN.md and ends at its byte limit."""
    import look
    from ui_library import index_findings

    root = tmp_path / "big"
    root.mkdir()
    texts = {
        f"src/ui/Part{number}.tsx": f"export const Part{number} = () => null;\n"
        for number in range(2000)
    }
    library = ["src/ui/*"]
    uses = {
        entry: dict.fromkeys(parts, "a part")
        for entry, parts in expected_index(texts, library).items()
    }
    index = index_text(texts, library, uses)
    assert index_findings({**texts, "UI-LIBRARY.md": index}, library) == []
    design = "---\ncolors:\n  ink: '#111111'\n---\n\n# Big\n"
    (root / "DESIGN.md").write_text(design)
    (root / "UI-LIBRARY.md").write_text(index)
    excerpt = look.design_text(root)
    assert len(excerpt.encode()) <= look.DESIGN_BYTE_LIMIT
    assert design.strip() in excerpt
    assert excerpt.endswith("[truncated]")


def test_the_ui_refusal_header_says_the_rule_is_intended_and_fixed_in_the_project(
    tmp_path: Path,
) -> None:
    """The first failed check after an update is printed by the new release, so its header carries the line."""
    message = library_message(tmp_path, ui_library=[])
    assert "The rule is intended and has no waiver; fix the project" in message
