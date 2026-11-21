"""The client report check refuses a report that left the saved template or shows cross-reference codes."""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import SOURCE

SKILL = SOURCE / ".agents/skills/client-report"
SCRIPT = SKILL / "scripts/check_report.py"

STYLE = "<style>body { color: #111; } .live { background: #0a0; }</style>"
PAGE = "<!doctype html><html><head><title>Report</title>{style}</head><body>{body}</body></html>"
BODY = "<h1>Changes for Friday 4 December</h1><p>Stage 1 starts.</p>"


def problems(report: Path, template: Path) -> list[str]:
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(sys, "dont_write_bytecode", True)
        patch.syspath_prepend(str(SCRIPT.parent))
        found: list[str] = importlib.import_module("check_report").problems(
            report, template
        )
    return found


SECTIONS = "<h2>How it was checked</h2><p>One check ran.</p><h3>Not checked</h3><p>Nothing else.</p>"


def write(
    folder: Path,
    name: str,
    style: str = STYLE,
    body: str = BODY,
    sections: str = SECTIONS,
) -> Path:
    path = folder / name
    path.write_text(PAGE.format(style=style, body=body + sections))
    return path


def test_a_report_with_other_css_is_refused(tmp_path: Path) -> None:
    template = write(tmp_path, "template.html")
    report = write(tmp_path, "report.html", style="<style>body { color: red; }</style>")
    assert problems(report, template) == [
        "report CSS differs from the saved template; copy the template and change only the text"
    ]


def test_a_report_that_sets_style_in_a_tag_or_links_a_sheet_is_refused(
    tmp_path: Path,
) -> None:
    template = write(tmp_path, "template.html")
    inline = write(tmp_path, "inline.html", body='<p style="color: red">Text</p>')
    linked = write(
        tmp_path,
        "linked.html",
        style=STYLE + '<link rel="stylesheet" href="other.css">',
    )
    assert problems(inline, template) == [
        "report sets style in a tag; use a class from the template"
    ]
    assert problems(linked, template) == [
        "report links a stylesheet; the template holds all CSS"
    ]


def test_a_changed_selector_or_style_tag_attribute_is_refused(tmp_path: Path) -> None:
    template = write(
        tmp_path, "template.html", style="<style>.box.fix { color: red; }</style>"
    )
    selector = write(
        tmp_path, "selector.html", style="<style>.box .fix { color: red; }</style>"
    )
    media = write(
        tmp_path,
        "media.html",
        style='<style media="screen">.box.fix { color: red; }</style>',
    )
    spaced = write(
        tmp_path,
        "spaced.html",
        style="<style>\n.box.fix  {\n  color:   red ;\n}\n</style>",
    )
    differs = [
        (
            "report CSS differs from the saved template; "
            "copy the template and change only the text"
        )
    ]
    assert problems(selector, template) == differs
    assert problems(media, template) == differs
    assert problems(spaced, template) == []


def test_a_space_added_before_a_pseudo_class_is_refused(tmp_path: Path) -> None:
    template = write(
        tmp_path, "template.html", style="<style>:root:not(.a) { color: red; }</style>"
    )
    changed = write(
        tmp_path, "changed.html", style="<style>:root :not(.a) { color: red; }</style>"
    )
    assert len(problems(changed, template)) == 1


def test_a_stylesheet_link_in_any_spelling_is_refused(tmp_path: Path) -> None:
    template = write(tmp_path, "template.html")
    linked = write(
        tmp_path,
        "linked.html",
        style=STYLE + '<link rel=" StyleSheet " href="other.css">',
    )
    assert problems(linked, template) == [
        "report links a stylesheet; the template holds all CSS"
    ]


def test_a_code_split_by_inline_tags_is_refused_and_block_text_is_not_joined(
    tmp_path: Path,
) -> None:
    template = write(tmp_path, "template.html")
    split = write(tmp_path, "split.html", body="<p>See <strong>A</strong>1.</p>")
    tipped = write(
        tmp_path, "tipped.html", body='<p>A<span title="Reference">1</span></p>'
    )
    assert problems(tipped, template) == [
        "text holds the code 'A1'; write the item in full"
    ]
    apart = write(tmp_path, "apart.html", body="<h2>Stage A</h2><p>1 test passes.</p>")
    assert problems(split, template) == [
        "text holds the code 'A1'; write the item in full"
    ]
    assert problems(apart, template) == []


def test_a_missing_template_is_refused(tmp_path: Path) -> None:
    report = write(tmp_path, "report.html")
    assert problems(report, tmp_path / "template.html") == [
        (
            f"no saved template at {tmp_path / 'template.html'}; "
            "copy assets/starter.html there, show the user the report, "
            "and commit it only after approval"
        )
    ]


def test_codes_in_the_text_are_refused_with_their_place(tmp_path: Path) -> None:
    template = write(tmp_path, "template.html")
    report = write(
        tmp_path,
        "report.html",
        body="<p>Update the script (A1).</p><p>Pick testers (C2).</p>"
        '<img alt="Figure B3" src="x.png">',
    )
    assert problems(report, template) == [
        "text holds the code 'A1'; write the item in full",
        "text holds the code 'C2'; write the item in full",
        "text holds the code 'B3'; write the item in full",
    ]


def test_a_report_with_the_same_css_and_plain_words_is_accepted(
    tmp_path: Path,
) -> None:
    template = write(tmp_path, "template.html", body="<p>Placeholder</p>")
    report = write(tmp_path, "report.html")
    reflowed = write(
        tmp_path,
        "reflowed.html",
        style="<style>\nbody  { color: #111; }\n.live { background: #0a0; }\n</style>",
    )
    assert problems(report, template) == []
    assert problems(reflowed, template) == []


def test_code_like_words_in_css_and_file_names_are_not_text(tmp_path: Path) -> None:
    style = "<style>.A1 { color: #111; } @page { size: A4; }</style>"
    template = write(tmp_path, "template.html", style=style)
    report = write(
        tmp_path,
        "report.html",
        style=style,
        body='<img src="B2.png" alt="Dashboard before"><p>MP4 file, Stage 1 and 4 December.</p>',
    )
    assert problems(report, template) == []


def test_the_command_exits_with_the_problems(tmp_path: Path) -> None:
    template = write(tmp_path, "template.html")
    good = write(tmp_path, "good.html")
    bad = write(tmp_path, "bad.html", body="<p>See A1.</p>")
    command = [sys.executable, "-B", str(SCRIPT)]
    refused = subprocess.run(
        [*command, str(bad), "--template", str(template)],
        capture_output=True,
        text=True,
        check=False,
    )
    accepted = subprocess.run(
        [*command, str(good), "--template", str(template)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert (refused.returncode, refused.stdout) == (
        1,
        "text holds the code 'A1'; write the item in full\n",
    )
    assert (accepted.returncode, accepted.stdout) == (0, "")


def test_a_report_without_the_check_sections_is_refused(tmp_path: Path) -> None:
    template = write(tmp_path, "template.html")
    none = write(tmp_path, "none.html", sections="")
    half = write(
        tmp_path, "half.html", sections="<h2>How it was checked</h2><p>One.</p>"
    )
    assert problems(none, template) == [
        "report lacks the section 'How it was checked'",
        "report lacks the section 'Not checked'",
    ]
    assert problems(half, template) == ["report lacks the section 'Not checked'"]
    assert problems(write(tmp_path, "full.html"), template) == []
    prose = write(
        tmp_path,
        "prose.html",
        sections="<p>How it was checked is below. Email was not checked.</p>",
    )
    assert problems(prose, template) == [
        "report lacks the section 'How it was checked'",
        "report lacks the section 'Not checked'",
    ]
    assert (
        problems(
            write(tmp_path, "h4.html", sections=SECTIONS.replace("h2", "h4")), template
        )
        == []
    )


def test_leftover_placeholder_text_is_refused_and_plain_brackets_pass(
    tmp_path: Path,
) -> None:
    template = write(tmp_path, "template.html")
    left = write(
        tmp_path,
        "left.html",
        body='<p>[Date]</p><img alt="[Before: what the screen shows]" src="x.png">',
    )
    assert problems(left, template) == [
        "text holds the placeholder '[Date]'; replace it with real text",
        "text holds the placeholder '[Before: what the screen shows]'; replace it with real text",
    ]
    wrapped = write(tmp_path, "wrapped.html", body="<p>[One line for\neach check.]</p>")
    assert problems(wrapped, template) == [
        "text holds the placeholder '[One line for each check.]'; replace it with real text"
    ]
    fine = write(tmp_path, "fine.html", body="<p>Stage 1 (our team tests).</p>")
    assert problems(fine, template) == []


def test_the_command_finds_the_template_from_the_git_top_level(
    tmp_path: Path,
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    folder = tmp_path / "docs/client-report"
    folder.mkdir(parents=True)
    write(folder, "template.html")
    inside = tmp_path / "work/report"
    inside.mkdir(parents=True)
    report = write(inside, "report.html")
    bare = tmp_path.parent / (tmp_path.name + "-bare")
    bare.mkdir()
    loose = write(bare, "report.html")

    def run(path: Path) -> tuple[int, str]:
        done = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), path.name],
            cwd=path.parent,
            capture_output=True,
            text=True,
            check=False,
        )
        return done.returncode, done.stdout

    assert run(report) == (0, "")
    code, out = run(loose)
    assert code == 1
    assert out.startswith("no saved template at ")
