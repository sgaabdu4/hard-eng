"""Raw colours and sizes: the forms of one line, judged without a project."""

import pytest
from ui_raw import raw_value_hits
from ui_whole import defined_colours, file_findings, token_values


def raw(name: str, text: str, defined: tuple[str, ...] = ()) -> list[tuple[str, str]]:
    lines = list(enumerate(text.splitlines(), 1))
    return [(kind, hit) for _, kind, hit in raw_value_hits(name, lines, set(defined))]


@pytest.mark.parametrize(
    ("name", "text", "found"),
    [
        ("a.tsx", "const style = { color: WHITE };", []),
        ("a.tsx", "const style = { color: theme.white };", []),
        ("a.tsx", "const style = { borderColor: BLACK, fill: WHITE };", []),
        ("a.tsx", "<i style={{ color: WHITE }} />", []),
        ("a.tsx", "const style = { color: 'white' };", [("colour", "color: white")]),
        ("a.tsx", 'const style = { color: "White" };', [("colour", "color: white")]),
        (
            "a.tsx",
            "<i style={{ border: `1px solid ${WHITE}` }} />",
            [],
        ),
        (
            "a.tsx",
            "<i style={{ background: `linear-gradient(to right, white, ${end})` }} />",
            [("colour", "background: white")],
        ),
        ("a.ts", "text(ctx, WORD, x, y, { size: 30, color: WHITE, family });", []),
        (
            "a.ts",
            "text(ctx, WORD, x, y, { size: 30, color: 'white', family });",
            [("colour", "color: white")],
        ),
        (
            "a.ts",
            "const Box = styled.div`\n  color: white;\n`;",
            [("colour", "color: white")],
        ),
        ("a.tsx", 'const css = "color: white";', [("colour", "color: white")]),
        ("a.html", '<p style="color: white">Hi</p>', [("colour", "color: white")]),
        (
            "a.tsx",
            'function css(style: CSSProperties = {}) { return ".a { color: white; }"; }',
            [("colour", "color: white")],
        ),
        (
            "a.tsx",
            '<i className="[color:white]" style={{ opacity: 0.5 }} />',
            [("colour", "color: white")],
        ),
        ("a.tsx", "const headerStyle: React.CSSProperties = { color: WHITE };", []),
        (
            "a.tsx",
            "export const badgeStyle: CSSProperties = { color: 'white' };",
            [("colour", "color: white")],
        ),
        ("a.css", ".x { color: White; }", [("colour", "color: white")]),
        ("a.css", ".x { color: WHITE; }", [("colour", "color: white")]),
    ],
)
def test_a_colour_name_in_script_code_counts_only_as_a_quoted_string(
    name: str, text: str, found: list[tuple[str, str]]
) -> None:
    """HE-UI-SOURCE: a JS constant named like a colour is no typed colour; a quoted word, CSS text in a string and a declaration that ends with a semicolon are, and a stylesheet reads a name in any case."""
    assert raw(name, text) == found


def test_code_after_a_closed_comment_on_the_same_line_is_judged() -> None:
    """HE-UI-SOURCE: a closed comment at the start of a line hides nothing after it; an open comment line and a whole comment line stay skipped."""
    tsx = '{/* x */}<button style={{ color: "#0a0b0c" }}>Go</button>\n'
    found = file_findings("a.tsx", tsx, [], set(), set())
    assert any("a base element (<button)" in line for line in found)
    assert any("(#0a0b0c)" in line for line in found)
    css = "/**/ .x { color: #ff0000; padding: 13px; }\n"
    found = file_findings("a.css", css, [], set(), set())
    assert any("(#ff0000)" in line for line in found)
    assert any("(padding: 13px)" in line for line in found)
    twice = "/* a */ /* b */ .x { color: #ff0000; }\n"
    assert file_findings("a.css", twice, [], set(), set())
    html = "<!-- x --><button>Go</button>\n"
    assert file_findings("a.html", html, [], set(), set())
    skipped = "/* .x { color: #ff0000; } */\n// <button>\n/* open\n"
    assert file_findings("a.css", skipped, [], set(), set()) == []


def test_a_line_comment_that_holds_a_block_opener_hides_nothing() -> None:
    """HE-UI-SOURCE: a // line with /* in it is a line comment; the code after it is judged, and a // inside a URL is no comment."""
    css = "// see /* here\n.x { color: #ff0000; }\n"
    found = file_findings("a.css", css, [], set(), set())
    assert [line.split(":")[1] for line in found] == ["2"]
    tsx = "// note /*\nconst c = '#ff0000';\nconst d = '#00ff00'; // */\n"
    found = file_findings("a.tsx", tsx, [], set(), set())
    assert [line.split(":")[1] for line in found] == ["2", "3"]
    url = "const u = 'http://x.test/*'; const c = '#ff0000';\n"
    assert file_findings("a.tsx", url, [], set(), set())


def test_block_comments_are_cut_over_lines_and_every_other_line_is_judged() -> None:
    """HE-UI-SOURCE: a comment that closes on a later line hides nothing after it, a line that starts with * is judged, and a doc comment body is not."""
    css = "* .card { color: #ff0000; padding: 13px; }\n"
    found = file_findings("a.css", css, [], set(), set())
    assert any("(#ff0000)" in line for line in found)
    assert any("(padding: 13px)" in line for line in found)
    star = "* + * { margin-top: 13px; }\n"
    assert file_findings("a.css", star, [], set(), set())
    later = "/*\n*/ .x { color: #ff0000; }\n"
    found = file_findings("a.css", later, [], set(), set())
    assert [line.split(":")[1] for line in found] == ["2"]
    both = "/* a\n * b */ .x { color: #ff0000; }\n"
    assert file_findings("a.css", both, [], set(), set())
    jsx = '{/*\n*/}<button style={{ color: "#0a0b0c" }}>Go</button>\n'
    found = file_findings("a.tsx", jsx, [], set(), set())
    assert any(":2: a base element (<button)" in line for line in found)
    assert any(":2: a colour typed in the file (#0a0b0c)" in line for line in found)
    doc = "/**\n * .card { color: #ff0000; padding: 13px; }\n */\n"
    assert file_findings("a.css", doc, [], set(), set()) == []
    glob = "const g = 'src/**/*.ts';\nconst c = '#ff0000';\n"
    assert [x.split(":")[1] for x in file_findings("a.ts", glob, [], set(), set())] == [
        "2"
    ]


def test_a_tailwind_config_defines_a_palette_name_only_with_a_literal_colour() -> None:
    """HE-UI-SOURCE: a config key counts as a palette name only when its value holds a colour the token compare reads; references and comments define nothing."""
    config = "tailwind.config.js"

    def names(text: str) -> set[str]:
        return defined_colours({config: text})

    assert "blue" not in names("module.exports = { colors: { blue: colors.blue } };\n")
    assert names("// red: '#f00'\n/* green: '#0f0' */\nmodule.exports = {};\n") == set()
    found = names(
        "module.exports = { colors: { brand: '#123456', blue: { 500: '#0000ff' } } };\n"
    )
    assert found == {"brand", "blue-500"}
    assert names("colors: { blue: { DEFAULT: '#00f', 50: '#eef' } }") == {
        "blue",
        "blue-50",
    }
    shade = 'const a = "text-blue-500";\n'
    only_50 = names("colors: { blue: { 50: '#123456' } }")
    assert len(file_findings("a.tsx", shade, [], only_50, set())) == 1
    line = 'const a = "text-blue-500 bg-green-600";\n'
    red = file_findings(
        "a.tsx", line, [], names("colors: { blue: colors.blue, green: green }"), set()
    )
    assert len(red) == 2
    ok = file_findings(
        "a.tsx",
        line,
        [],
        names("colors: { blue: { 500: '#00f' }, green: { 600: '#0f0' } }"),
        set(),
    )
    assert ok == []


def test_standalone_and_email_values_equal_a_token_by_value_not_by_text() -> None:
    """HE-UI-SOURCE: 28px equals a token of 1.75rem and 0.75rem equals a token of 12px; 29px equals nothing."""
    tokens = token_values(
        {
            "src/theme/tokens.css": "@theme {\n  --spacing-3: 1.75rem;\n  --spacing-4: 12px;\n  --color-brand: #123456;\n}\n"
        },
        ["src/**"],
    )
    page = '<!doctype html><p style="padding: 28px; margin: 0.75rem; color: #123456; width: 29px">x</p>'
    found = file_findings(
        "src/page.ts", f"export const p = `{page}`;\n", [], set(), tokens
    )
    assert len(found) == 1
    assert "(width: 29px)" in found[0]
    mail = '<p style="padding: 0.75rem; color: #123457">x</p>\n'
    found = file_findings("emails/w.html", mail, [], set(), tokens)
    assert len(found) == 1
    assert "(#123457)" in found[0]


def test_em_and_pt_tokens_compare_as_values() -> None:
    """HE-UI-SOURCE: a token of 1.5em equals 24px and a token of 2pt equals 2pt, so a standalone page may type them."""
    tokens = token_values(
        {
            "src/theme/t.css": "@theme {\n  --spacing-a: 1.5em;\n  --spacing-b: 2pt;\n}\n"
        },
        ["src/**"],
    )
    page = '<!doctype html><p style="padding: 24px; margin: 2pt; width: 1.5em">x</p>'
    found = file_findings(
        "src/p.ts", f"export const p = `{page}`;\n", [], set(), tokens
    )
    assert found == []


def test_style_objects_outside_style_attributes_are_judged() -> None:
    """HE-UI-SOURCE: a bare number in a style object counts wherever the object is written, in one line or over several."""
    assert raw("a.ts", "const styles = { box: { padding: 13 } };\n") == [
        ("size", "padding: 13")
    ]
    text = "const styles = StyleSheet.create({\n  box: {\n    padding: 13,\n    margin: 4,\n  },\n});\nconst other = { width: 300 };\n"
    assert raw("a.ts", text) == [("size", "padding: 13"), ("size", "margin: 4")]


def test_an_object_used_as_a_style_is_judged_whatever_its_name() -> None:
    """HE-UI-SOURCE: an object that is spread into style={{...x}} or passed as style={x} is a style object under any name."""
    spread = "const box = { padding: 13, fontSize: 19 };\nconst other = { width: 300 };\nexport const A = () => <div style={{ ...box }} />;\n"
    assert raw("a.tsx", spread) == [("size", "padding: 13"), ("size", "font-size: 19")]
    passed = "const card = {\n  margin: 7,\n};\nexport const A = () => <div style={card} />;\n"
    assert raw("a.tsx", passed) == [("size", "margin: 7")]
    assert raw("a.tsx", "const other = { width: 300 };\n") == []


@pytest.mark.parametrize(
    "attribute",
    [
        "{a ? box : undefined}",
        "{[base, box]}",
        "{Object.freeze(box)}",
        "{{ ...(on ? box : {}) }}",
        "{theme.box}",
    ],
)
def test_an_object_named_anywhere_in_a_style_expression_is_judged(
    attribute: str,
) -> None:
    """HE-UI-SOURCE: a conditional, an array, a member, a freeze wrapper or a spread of a condition each judge the objects they name."""
    text = (
        "const box = { padding: 13 };\nconst theme = { box: { margin: 7 } };\n"
        f"export const A = () => <div style={attribute} />;\n"
    )
    found = {hit for _, hit in raw("a.tsx", text)}
    assert found & {"padding: 13", "margin: 7"}
    assert raw("a.tsx", "const other = { width: 300 };\n<div style={box} />;\n") == []


def test_two_arbitrary_properties_on_one_line_are_read_apart_and_a_colour_class_counts_once() -> (
    None
):
    """HE-UI-SOURCE: [color:#fff] [padding:15px] gives a colour and a size; bg-[#abcdef] is one finding."""
    both = raw("a.tsx", 'const a = "[color:#fff] [padding:15px]";\n')
    assert ("colour", "#fff") in both
    assert ("size", "padding: 15px") in both
    assert raw("a.tsx", 'const a = "bg-[#abcdef]";\n') == [("colour", "bg-[#abcdef]")]


def test_underscores_are_spaces_inside_arbitrary_class_brackets() -> None:
    """HE-UI-SOURCE: [padding:15px_13px] holds two sizes and [border:1px_solid_#ff0000] a colour."""
    both = raw("a.tsx", 'const a = "[padding:15px_13px]";\n')
    assert ("size", "padding: 15px") in both
    assert ("size", "padding: 13px") in both
    assert ("colour", "#ff0000") in raw(
        "a.tsx", 'const a = "[border:1px_solid_#ff0000]";\n'
    )


def test_every_css_colour_name_counts_wherever_it_stands_in_the_value() -> None:
    """HE-UI-SOURCE: a named colour is raw after other words of a shorthand and for every CSS name, not only thirteen."""
    assert raw("a.css", ".a { border: 1px solid red; }\n") == [
        ("colour", "border: red")
    ]
    assert raw("a.css", ".a { color: tomato; }\n") == [("colour", "color: tomato")]
    assert raw("a.css", ".a { background: url(red.png) var(--red) no-repeat; }\n") == []
    assert raw("a.css", ".a { color: transparent; outline: none; }\n") == []


def test_apply_lines_are_judged_like_class_names() -> None:
    """HE-UI-SOURCE: Tailwind classes named in @apply are judged like classes in markup."""
    assert raw("a.css", ".a { @apply bg-red-500 p-[13px]; }\n") == [
        ("size", "p-[13px]"),
        ("palette", "bg-red-500"),
    ]
    assert raw("a.css", ".a { @apply bg-red-500; }\n", ("red-500",)) == []


def test_a_palette_shade_needs_its_own_theme_entry() -> None:
    """HE-UI-SOURCE: a theme that defines only the bare colour name does not define its shades."""
    assert raw("a.tsx", 'const a = "text-blue-500";\n', ("blue",)) == [
        ("palette", "text-blue-500")
    ]
    assert raw("a.tsx", 'const a = "text-blue-500";\n', ("blue-500",)) == []
    assert raw("a.tsx", 'const a = "text-blue";\n', ("blue",)) == []
