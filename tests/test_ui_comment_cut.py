"""A slash-star inside a string opens no comment."""

from ui_exempt import code_of, exemption
from ui_tokens import token_facts
from ui_whole import code_lines, config_colour_names, file_findings

CONFIG = (
    "module.exports = {\n"
    '  content: ["./src/**/*.{js,ts}", "./src/*.html"],\n'
    '  theme: { colors: { brand: "#123456" }, spacing: { 4: "16px" } },\n'
    "};\n"
    "/* the end */\n"
)


def test_a_slash_star_inside_a_string_does_not_start_a_comment() -> None:
    """HE-UI-SOURCE: a glob such as `./src/*.html` stays code, and the comment after the theme is still cut."""
    code = code_of(CONFIG)
    assert "brand" in code
    assert "the end" not in code
    assert config_colour_names(CONFIG) == {"brand"}
    assert token_facts([CONFIG]).colours == {"123456ff"}
    assert token_facts([CONFIG]).lengths == {16.0}


def test_a_string_with_a_slash_star_keeps_the_page_and_the_email_exempt() -> None:
    page = (
        'app.get("/*", (_, res) => res.send(`<!doctype html><p>x</p>`));\n/* end */\n'
    )
    assert exemption("src/server.ts", page) == "standalone"
    mail = (
        "import { Html } from '@react-email/components';\n"
        'const logo = "assets/*.png";\n'
        "export const Mail = () => <Html />;\n"
        "/** the end */\n"
    )
    assert exemption("src/mail.tsx", mail) == "email"


def test_a_comment_still_grants_no_exemption_and_a_comment_after_prose_is_still_cut() -> (
    None
):
    page = "// <!doctype html>\nexport const x = 1;\n/* <!doctype html> */\n"
    assert exemption("src/server.ts", page) is None
    mail = "/* import { Html } from '@react-email/components'; <Html /> */\nexport const x = 1;\n"
    assert exemption("src/mail.tsx", mail) is None
    prose = "<p>it's fine</p>\n/* hidden */ const x = 1;\n"
    assert code_of(prose) == "<p>it's fine</p>\n const x = 1;\n"
    assert code_of('const url = "http://a.test/*"; // note\nconst y = 2;\n') == (
        'const url = "http://a.test/*"; \nconst y = 2;\n'
    )


def test_the_lines_that_hold_code_keep_a_string_whole_and_cut_each_real_comment() -> (
    None
):
    """A slash-star inside a string neither hides the code after it nor keeps a later comment as code."""
    page = (
        'app.get("/*", (_, res) => res.send(`<!doctype html><p>x</p>`));\n'
        "/* <button>old draft</button> */\n"
        'const glob = "assets/*.png";\n'
        "/** Renders a <button> with padding: 12px */\n"
    )
    assert file_findings("src/server.ts", page, [], set(), set()) == []
    assert [number for number, _ in code_lines(page)] == [1, 3]
    template = (
        "export const page = `<!doctype html>\n<p>Match src/* files</p>\n"
        '<button>Click</button>\n<p style="color: #ff0000">Red</p>`;\n/* footer */\n'
    )
    found = file_findings("src/page.ts", template, [], set(), set())
    assert {line.split(":")[1] for line in found} == {"3", "4"}
    escaped = (
        'const msg = "Don\\"t use /*";\n'
        'export const Bad = () => <button style={{ color: "#ff0000" }}>Go</button>;\n'
        "/* end */\n"
    )
    assert len(file_findings("src/bad.tsx", escaped, [], set(), set())) == 2
