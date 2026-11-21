import argparse
import re
from html.parser import HTMLParser
from pathlib import Path

CODE = re.compile(r"\b[A-Z][0-9]+\b")
SHOWN = ("alt", "title", "aria-label")


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.css: list[str] = []
        self.text: list[str] = []
        self.inline_style = False
        self.linked_sheet = False
        self.inside = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.inside = tag if tag in {"style", "script"} else ""
        for name, value in attrs:
            self.inline_style |= name == "style"
            self.text += [value or ""] if name in SHOWN else []
        self.linked_sheet |= tag == "link" and ("rel", "stylesheet") in attrs

    def handle_endtag(self, tag: str) -> None:
        self.inside = ""

    def handle_data(self, data: str) -> None:
        if self.inside == "style":
            self.css.append(data)
        elif not self.inside:
            self.text.append(data)


def read(path: Path) -> Page:
    page = Page()
    page.feed(path.read_text())
    return page


def squeeze(css: list[str]) -> str:
    return re.sub(r"\s+", "", "".join(css))


def problems(report: Path, template: Path) -> list[str]:
    if not template.is_file():
        return [
            (
                f"no saved template at {template}; "
                "copy assets/starter.html there, commit it, then build the report"
            )
        ]
    page = read(report)
    found: list[str] = []
    if squeeze(page.css) != squeeze(read(template).css):
        found.append(
            "report CSS differs from the saved template; "
            "copy the template and change only the text"
        )
    if page.inline_style:
        found.append("report sets style in a tag; use a class from the template")
    if page.linked_sheet:
        found.append("report links a stylesheet; the template holds all CSS")
    found += [
        f"text holds the code {code!r}; write the item in full"
        for code in CODE.findall(" ".join(page.text))
    ]
    return found


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check a client report against its saved template."
    )
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--template", type=Path, default=Path("docs/client-report/template.html")
    )
    args = parser.parse_args()
    found = problems(args.report, args.template)
    print("".join(f"{line}\n" for line in found), end="")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
