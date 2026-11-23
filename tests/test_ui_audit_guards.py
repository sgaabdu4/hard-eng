"""Runtime browser audit guards: competing same-colour CTAs, duplicates, hierarchy, clipping, waterfalls, and CLS."""

from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest
from test_ui_quality import pair
from ui_capture import WIDTHS, capture

AUDIT_FAULTS = {
    "competing-same-colour": (
        f"<div>{pair('#00b', '#00b')}</div>",
        "competing-buttons",
        1,
    ),
    "duplicate-buttons": (
        (
            "<div><div>"
            "<button style='min-height:44px;min-width:44px;font-size:16px;background:transparent;border:1px solid #333;color:#111'>Mark paid</button>"
            "<button style='min-height:44px;min-width:44px;font-size:16px;background:transparent;border:1px solid #333;color:#111'>Mark paid</button>"
            "</div></div>"
        ),
        "duplicate-buttons",
        1,
    ),
    "heading-hierarchy": (
        (
            "<main><h1 style='font-size:20px;font-weight:400'>Rentals</h1>"
            "<p style='font-size:16px;font-weight:600'>Unit 4B</p></main>"
        ),
        "heading-hierarchy",
        1,
    ),
    "clipped-select": (
        (
            "<label>Status <select aria-label='Status' style='width:52px;height:44px;font-size:16px'>"
            "<option selected>Awaiting Landlord Signature</option></select></label>"
        ),
        "clipped-control",
        1,
    ),
    "clipped-button": (
        "<button style='width:60px;height:44px;font-size:16px;overflow:hidden;white-space:nowrap'>Save Landlord Record</button>",
        "clipped-control",
        1,
    ),
    "clipped-chrome": (
        (
            "<aside style='position:fixed;top:0;left:0;width:200px;height:960px;overflow:visible'>"
            "<div style='height:880px'>Nav</div>"
            "<button style='min-height:44px;min-width:120px;font-size:16px'>Sign out</button></aside>"
        ),
        "clipped-chrome",
        1,
    ),
    "clipped-sticky-chrome": (
        (
            "<aside style='position:sticky;top:0;width:200px;height:620px;overflow:hidden'>"
            "<div style='height:610px'>Nav</div>"
            "<button style='min-height:44px;min-width:120px;font-size:16px'>Sign out</button></aside>"
        ),
        "clipped-chrome",
        1,
    ),
}


@pytest.mark.parametrize(
    ("body", "rule", "count"), AUDIT_FAULTS.values(), ids=AUDIT_FAULTS
)
def test_each_runtime_audit_guard_finds_one_fault(
    tmp_path: Path, site: str, browser: ModuleType, body: str, rule: str, count: int
) -> None:
    (tmp_path / "pages/audit.html").write_text(
        "<!doctype html><html lang=en><title>Audit</title>"
        f"<style>body{{margin:0;font:16px sans-serif}}</style><body>{body}</body>"
    )
    found = capture(browser, tmp_path, site, "audit")
    for width in WIDTHS:
        assert found[width] == Counter({rule: count}), (width, found[width])


def test_sequential_fetch_waterfall_and_layout_shift_are_measured(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    (tmp_path / "pages/step.json").write_text('{"ok":true}')
    (tmp_path / "pages/waterfall.html").write_text(
        "<!doctype html><html lang=en><title>Waterfall</title>"
        "<style>body{margin:0;font:16px sans-serif}</style>"
        "<body><main><h1 style='font-size:24px;font-weight:700'>Board</h1><p id='out'>Loading</p></main>"
        "<script>(async () => {"
        "for (let i = 0; i < 4; i++) {"
        "await fetch('/step.json?w=' + i);"
        "}"
        "document.getElementById('out').textContent = 'Ready';"
        "})();</script></body>"
    )
    found_wf = capture(browser, tmp_path, site, "waterfall")
    for width in WIDTHS:
        assert found_wf[width] == Counter({"fetch-waterfall": 1}), (
            width,
            found_wf[width],
        )

    (tmp_path / "pages/cls.html").write_text(
        "<!doctype html><html lang=en><title>Shift</title>"
        "<style>body{margin:0;font:16px sans-serif}</style>"
        "<body><div id='slot'></div>"
        "<main id='content' style='height:500px;background:#fff'>"
        "<h1 style='font-size:24px;font-weight:700;margin:0'>Summary</h1>"
        "<p style='margin:0'>Main body text that shifts downward.</p></main>"
        "<script>setTimeout(() => {"
        "const b = document.createElement('div');"
        "b.style.height = '320px'; b.textContent = 'Late banner';"
        "document.getElementById('slot').appendChild(b);"
        "}, 120);</script></body>"
    )
    found_cls = capture(browser, tmp_path, site, "cls")
    for width in WIDTHS:
        assert found_cls[width] == Counter({"layout-shift": 1}), (
            width,
            found_cls[width],
        )


def test_display_heading_custom_select_sticky_sidebar_and_parallel_fetches_pass(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    (tmp_path / "pages/step.json").write_text('{"ok":true}')
    (tmp_path / "pages/clean.html").write_text(
        "<!doctype html><html lang=en><title>Clean</title>"
        "<style>body{margin:0;font:500 16px sans-serif}</style>"
        "<body><div style='display:flex;align-items:flex-start'>"
        "<aside style='position:sticky;top:0;width:120px;height:960px;overflow:visible'>"
        "<div style='height:880px'>Nav</div>"
        "<button style='min-height:44px;min-width:100px;font-size:16px'>Sign out</button></aside>"
        "<main style='height:1800px;padding:16px'>"
        "<h1 style='font-size:48px;font-weight:400;margin:0'>Overview</h1>"
        "<p>Body copy at medium weight.</p>"
        "<label>Role <select aria-label='Role' style='appearance:none;-webkit-appearance:none;width:84px;height:44px;padding:0 4px;font-size:16px'>"
        "<option selected>Manager</option></select></label>"
        "</main></div>"
        "<script>Promise.all([0,1,2,3].map((i) => fetch('/step.json?p=' + i)));</script></body>"
    )
    found = capture(browser, tmp_path, site, "clean")
    for width in WIDTHS:
        assert found[width] == Counter(), (width, found[width])


def test_parenthesized_ternaries_generated_siblings_separate_fonts_and_theme_default(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: parenthesized ternaries pass, unrelated generated CSS is ignored, sibling font sheets count, and @theme default yields to explicit tokens."""
    from comments import validate_suppressions
    from conftest import change, commit, init
    from test_ui_rules import refused

    paren = change(
        tmp_path / "paren",
        "src/Status.tsx",
        "export const Status = () => <div />;\n",
        "export const Status = ({ ready, ro }: { ready: boolean; ro: boolean }) => (\n"
        '  <div>{ready && (ro ? <span key="status" /> : <em key="status" />)}</div>\n'
        ");\n"
        'export const list = (ready: boolean, ro: boolean) => [ready && (ro ? <span key="st" /> : <em key="st" />)];\n',
    )
    validate_suppressions(paren, "HEAD")

    sep = tmp_path / "sep"
    init(sep)
    (sep / ".gitattributes").write_text("src/preview.css linguist-generated=true\n")
    (sep / "src").mkdir()
    (sep / "src/fonts.css").write_text(
        '@font-face {\n  font-family: "Inter";\n  font-weight: 400 600;\n}\n'
    )
    (sep / "src/preview.css").write_text(
        "@theme {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 500;\n}\n"
    )
    (sep / "src/brand.css").write_text(
        "@theme {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 600;\n}\n"
    )
    (sep / "src/defaults.css").write_text(
        "@theme default {\n  --text-heading--font-weight: 500;\n}\n"
    )
    (sep / "src/app.css").write_text(
        '@import "./brand.css";\n@import "./defaults.css";\n'
    )
    (sep / "DESIGN.md").write_text(
        "---\ntypography:\n  heading:\n    fontWeight: 600\n---\n# App\n"
    )
    commit(sep, "base")
    (sep / "src/app.css").write_text(
        '@import "./brand.css";\n@import "./defaults.css";\n/* touch */\n'
    )
    validate_suppressions(sep, "HEAD")
    (sep / "src/app.css").write_text(
        "@theme {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 700;\n}\n"
    )
    (sep / "DESIGN.md").write_text(
        "---\ntypography:\n  heading:\n    fontWeight: 700\n---\n# App\n"
    )
    assert "outside loaded @font-face font-weight ranges" in refused(sep)


def test_bundle_font_isolation_generated_wrapper_and_text_initial_reset(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: bundle font faces stay isolated, generated wrappers still check edited imports, and --text-*: initial clears explicit weights."""
    from comments import validate_suppressions
    from conftest import commit, init
    from test_ui_rules import refused

    bundles = tmp_path / "bundles"
    init(bundles)
    (bundles / "src").mkdir()
    (bundles / "src/storefront.css").write_text(
        '@font-face {\n  font-family: "Inter";\n  font-weight: 400 600;\n}\n'
        "@theme {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 600;\n}\n"
    )
    (bundles / "src/admin.css").write_text(
        '@font-face {\n  font-family: "Inter";\n  font-weight: 400 700;\n}\n'
    )
    (bundles / "DESIGN.md").write_text(
        "---\ntypography:\n  heading:\n    fontFamily: Inter\n    fontWeight: 700\n---\n# App\n"
    )
    commit(bundles, "base")
    (bundles / "src/storefront.css").write_text(
        '@font-face {\n  font-family: "Inter";\n  font-weight: 400 600;\n}\n'
        "@theme {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 700;\n}\n"
    )
    assert "outside loaded @font-face font-weight ranges" in refused(bundles)

    wrap = tmp_path / "wrap"
    init(wrap)
    (wrap / ".gitattributes").write_text("src/bundle.css linguist-generated=true\n")
    (wrap / "src").mkdir()
    (wrap / "src/tokens.css").write_text(
        "@theme {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 700;\n}\n"
    )
    (wrap / "src/bundle.css").write_text('@import "./tokens.css";\n')
    (wrap / "DESIGN.md").write_text(
        "---\ntypography:\n  heading:\n    fontWeight: 700\n---\n# App\n"
    )
    commit(wrap, "base")
    (wrap / "src/tokens.css").write_text(
        "@theme {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 500;\n}\n"
    )
    assert "--text-heading--font-weight: 500" in refused(wrap)

    reset = tmp_path / "reset"
    init(reset)
    (reset / "src").mkdir()
    (reset / "src/app.css").write_text(
        "@theme {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 500;\n}\n"
        "@theme {\n  --text-*: initial;\n}\n"
        "@theme default {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 700;\n}\n"
    )
    (reset / "DESIGN.md").write_text(
        "---\ntypography:\n  heading:\n    fontWeight: 700\n---\n# App\n"
    )
    commit(reset, "base")
    (reset / "src/app.css").write_text(
        (reset / "src/app.css").read_text() + "/* touch */\n"
    )
    validate_suppressions(reset, "HEAD")
