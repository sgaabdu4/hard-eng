"""The client report check refuses a report that left the saved template or shows cross-reference codes."""

import ast
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


NAMES = (
    "Where it stands",
    "What is live",
    "How it was checked",
    "Not checked",
    "Everything left",
)
SECTIONS = "".join(f"<h2>{name}</h2><p>Text.</p>" for name in NAMES)


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


def test_a_report_without_the_kept_sections_is_refused(tmp_path: Path) -> None:
    template = write(tmp_path, "template.html")
    none = write(tmp_path, "none.html", sections="")
    lacking = [f"report lacks the section {name!r}" for name in NAMES]
    assert problems(none, template) == lacking
    half = write(
        tmp_path,
        "half.html",
        sections="".join(f"<h2>{name}</h2>" for name in NAMES[:2]),
    )
    assert problems(half, template) == lacking[2:]
    assert problems(write(tmp_path, "full.html"), template) == []
    prose = write(
        tmp_path,
        "prose.html",
        sections="<p>What is live is below. Email was not checked.</p>",
    )
    assert problems(prose, template) == lacking
    h4 = write(tmp_path, "h4.html", sections=SECTIONS.replace("h2", "h4"))
    assert problems(h4, template) == []


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


def _run_script(path: Path) -> tuple[int, str]:
    done = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), path.name],
        cwd=path.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode, done.stdout


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

    assert _run_script(report) == (0, "")
    code, out = _run_script(loose)
    assert code == 1
    assert out == "run inside the project's git checkout\n"
    empty_nested = tmp_path / "empty-nested"
    (empty_nested / ".git").mkdir(parents=True)
    assert _run_script(write(empty_nested, "report.html")) == (0, "")
    git_inner = tmp_path / ".git/hooks"
    git_inner.mkdir(parents=True, exist_ok=True)
    assert _run_script(write(git_inner, "report.html")) == (
        1,
        "run inside the project's git checkout\n",
    )
    (tmp_path / "docs/client-report/template.html").unlink()
    assert _run_script(report)[1].startswith("no saved template at ")


def test_the_command_validates_gitdir_and_worktree_metadata(
    tmp_path: Path,
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "docs/client-report").mkdir(parents=True)
    write(tmp_path / "docs/client-report", "template.html")
    outside = (1, "run inside the project's git checkout\n")

    broken_wt = tmp_path.parent / (tmp_path.name + "-broken-wt")
    (broken_wt / "docs/client-report").mkdir(parents=True)
    write(broken_wt / "docs/client-report", "template.html")
    (broken_wt / ".git").write_text("gitdir: /nonexistent/worktree/gitdir\n")
    assert _run_script(write(broken_wt, "report.html")) == outside

    nested_stale = tmp_path / "nested-stale"
    nested_stale.mkdir()
    (nested_stale / ".git").write_text("gitdir: /nonexistent/nested/gitdir\n")
    assert _run_script(write(nested_stale, "report.html")) == outside

    missing_common = tmp_path.parent / (tmp_path.name + "-missing-common")
    (missing_common / "docs/client-report").mkdir(parents=True)
    write(missing_common / "docs/client-report", "template.html")
    fake_gitdir = missing_common / "wt-meta"
    fake_gitdir.mkdir()
    (fake_gitdir / "HEAD").write_text("ref: refs/heads/main\n")
    (fake_gitdir / "commondir").write_text("../missing-common-dir\n")
    (missing_common / ".git").write_text(f"gitdir: {fake_gitdir}\n")
    assert _run_script(write(missing_common, "report.html")) == outside

    missing_refs = tmp_path.parent / (tmp_path.name + "-missing-refs")
    (missing_refs / "docs/client-report").mkdir(parents=True)
    write(missing_refs / "docs/client-report", "template.html")
    (missing_refs / "common/objects").mkdir(parents=True)
    wt_no_refs = missing_refs / "wt-meta"
    wt_no_refs.mkdir()
    (wt_no_refs / "HEAD").write_text("ref: refs/heads/main\n")
    (wt_no_refs / "commondir").write_text("../common\n")
    (missing_refs / ".git").write_text(f"gitdir: {wt_no_refs}\n")
    assert _run_script(write(missing_refs, "report.html")) == outside


def test_the_command_validates_symlinked_worktree_head_and_commondir(
    tmp_path: Path,
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "docs/client-report").mkdir(parents=True)
    write(tmp_path / "docs/client-report", "template.html")
    outside = (1, "run inside the project's git checkout\n")

    symlink_wt = tmp_path.parent / (tmp_path.name + "-symlink-wt")
    (symlink_wt / "docs/client-report").mkdir(parents=True)
    write(symlink_wt / "docs/client-report", "template.html")
    wt_meta = symlink_wt / "wt-meta"
    wt_meta.mkdir()
    (wt_meta / "HEAD").write_text("ref: refs/heads/main\n")
    (wt_meta / "commondir").write_text(str(tmp_path / ".git") + "\n")
    (symlink_wt / ".git").symlink_to(wt_meta)
    assert _run_script(write(symlink_wt, "report.html")) == (0, "")

    (wt_meta / "HEAD").write_text("")
    assert _run_script(write(symlink_wt, "report.html")) == outside
    (wt_meta / "HEAD").write_text("ref: refs\n")
    assert _run_script(write(symlink_wt, "report.html")) == outside
    (wt_meta / "HEAD").write_text("ref: refs/heads/main\n")

    nested_empty_common = tmp_path / "nested-empty-common"
    nested_meta = tmp_path.parent / (tmp_path.name + "-empty-common-meta")
    nested_meta.mkdir()
    (nested_meta / "HEAD").write_text("ref: refs/heads/main\n")
    (nested_meta / "commondir").write_text("")
    nested_empty_common.mkdir()
    (nested_empty_common / ".git").symlink_to(nested_meta)
    assert _run_script(write(nested_empty_common, "report.html")) == outside

    (nested_meta / "HEAD").unlink()
    assert _run_script(write(nested_empty_common, "report.html")) == (0, "")

    abandoned = tmp_path / "abandoned-git"
    (abandoned / ".git").mkdir(parents=True)
    (abandoned / ".git/HEAD").write_text("ref: refs/heads/main\n")
    assert _run_script(write(abandoned, "report.html")) == (0, "")


def test_the_command_stops_at_a_missing_commondir_and_accepts_any_ref_name(
    tmp_path: Path,
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "docs/client-report").mkdir(parents=True)
    write(tmp_path / "docs/client-report", "template.html")
    outside = (1, "run inside the project's git checkout\n")

    nested = tmp_path / "nested-missing-common"
    meta = tmp_path.parent / (tmp_path.name + "-missing-common-meta")
    meta.mkdir()
    (meta / "HEAD").write_text("ref: refs/heads/main\n")
    (meta / "commondir").write_text("gone/deeper/common\n")
    nested.mkdir()
    (nested / ".git").symlink_to(meta)
    assert _run_script(write(nested, "report.html")) == outside

    (meta / "commondir").write_text(str(tmp_path / "missing-final") + "\n")
    assert _run_script(write(nested, "report.html")) == (0, "")

    (meta / "commondir").write_text(str(tmp_path / "missing-final") + "/\n")
    assert _run_script(write(nested, "report.html")) == outside

    dangling_link = tmp_path / "dangling-common-link"
    dangling_link.symlink_to(tmp_path / "no-such-parent/common")
    (meta / "commondir").write_text(str(dangling_link) + "\n")
    assert _run_script(write(nested, "report.html")) == outside

    (meta / "HEAD").write_text("ref:\u00a0refs/heads/main\n")
    (meta / "commondir").write_text(str(tmp_path / ".git") + "\n")
    assert _run_script(write(nested, "report.html")) == (0, "")

    spaced = tmp_path.parent / (tmp_path.name + "-spaced-ref")
    (spaced / "docs/client-report").mkdir(parents=True)
    write(spaced / "docs/client-report", "template.html")
    spaced_meta = spaced / "wt-meta"
    spaced_meta.mkdir()
    (spaced_meta / "HEAD").write_text("ref: refs/heads/a\u00a0branch\n")
    (spaced_meta / "commondir").write_text(str(tmp_path / ".git") + "\n")
    (spaced / ".git").write_text(f"gitdir: {spaced_meta}\n")
    assert _run_script(write(spaced, "report.html")) == (0, "")


def test_a_heading_broken_by_a_line_break_and_separate_rows_with_brackets_pass(
    tmp_path: Path,
) -> None:
    template = write(tmp_path, "template.html")
    broken = write(
        tmp_path,
        "broken.html",
        sections=SECTIONS.replace("How it was checked", "How it was<br>checked"),
    )
    rows = write(
        tmp_path,
        "rows.html",
        body="<table><tr><td>[</td></tr><tr><td>Previous layer</td></tr><tr><td>]</td></tr></table>",
    )
    inside = write(tmp_path, "inside.html", body="<p>[One line for<br>each check.]</p>")
    assert problems(inside, template) == [
        "text holds the placeholder '[One line for each check.]'; replace it with real text"
    ]
    closed = write(
        tmp_path, "closed.html", body="<p>[One line for<br />each check.]</p>"
    )
    assert problems(closed, template) == [
        "text holds the placeholder '[One line for each check.]'; replace it with real text"
    ]
    assert problems(broken, template) == []
    assert problems(rows, template) == []


def test_check_report_script_passes_strict_ruff_subprocess_rules() -> None:
    tree = ast.parse(SCRIPT.read_text())
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "subprocess" not in imported
    done = subprocess.run(
        ["uvx", "ruff@latest", "check", "--select", "S603,S607", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
