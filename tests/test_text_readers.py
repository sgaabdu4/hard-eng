"""HE-NO-TEXT-WALLS: the TSX and JSX reader returns the text blocks of every changed file from one process."""

import text_readers
import text_walls

SCREEN = (
    "export const A = () => (\n"
    "  <main>\n"
    "    <p>\n"
    "      Hello <strong>big</strong> world, {name}!\n"
    "      Second line.\n"
    "    </p>\n"
    '    <Card title="A card title" />\n'
    "  </main>\n"
    ");\n"
)


def test_the_reader_returns_the_blocks_of_each_file_and_a_finding_for_a_broken_one() -> (
    None
):
    """HE-NO-TEXT-WALLS: one request holds every file; a touched-line list narrows the blocks of one file."""
    request = text_walls.request(
        [
            ("a.tsx", SCREEN, None),
            ("b.tsx", SCREEN, [7]),
            ("c.tsx", "const a = <p>oops</div>;", None),
        ]
    )
    first, second, third = text_readers.read("js", request)
    assert [(b["kind"], b["name"], b["line"]) for b in first["blocks"]] == [
        ("jsx", "p", 4),
        ("prop", "title", 7),
    ]
    assert first["blocks"][0]["parts"] == [
        "Hello ",
        "big",
        " world, ",
        {"x": 1},
        "! Second line.",
    ]
    assert [b["name"] for b in second["blocks"]] == ["title"]
    assert third["error"].startswith("line 1:")
