"""The client report check refuses a report that left the saved template or shows cross-reference codes."""

import subprocess
import sys
from pathlib import Path

from conftest import SOURCE

SKILL = SOURCE / ".agents/skills/client-report"
sys.path.insert(0, str(SKILL / "scripts"))
sys.dont_write_bytecode = True

from check_report import problems

STYLE = "<style>body { color: #111; } .live { background: #0a0; }</style>"
PAGE = "<!doctype html><html><head><title>Report</title>{style}</head><body>{body}</body></html>"
BODY = "<h1>Changes for Friday 4 December</h1><p>Stage 1 starts.</p>"


def write(folder: Path, name: str, style: str = STYLE, body: str = BODY) -> Path:
    path = folder / name
    path.write_text(PAGE.format(style=style, body=body))
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
    command = [sys.executable, str(SKILL / "scripts/check_report.py")]
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
