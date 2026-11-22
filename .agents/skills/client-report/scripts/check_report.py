import argparse
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import override

CODE = re.compile(r"\b[A-Z][0-9]+\b")
SHOWN = ("alt",)
INLINE = {"a", "b", "code", "em", "i", "mark", "small", "span", "strong", "u"}
BLOCK = "\x00"
PLACEHOLDER = re.compile(r"\[[^\]\x00]*\]")
SECTIONS = (
    "Where it stands",
    "What is live",
    "How it was checked",
    "Not checked",
    "Everything left",
)
TEMPLATE = "docs/client-report/template.html"
HEADING = re.compile(r"h[1-6]")
SYMBOLS = re.compile(r"\s*([{};,])\s*|(:)\s+")


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.css: list[str] = []
        self.text: list[str] = []
        self.inline_style = False
        self.linked_sheet = False
        self.inside = ""
        self.headings: list[str] = []
        self.in_heading = False

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.inside = tag if tag in {"style", "script"} else ""
        if HEADING.fullmatch(tag):
            self.in_heading = True
            self.headings.append("")
        if tag == "style":
            self.css.append(f"<style {sorted(attrs)}>;")
        if tag not in INLINE:
            self.text.append(" " if tag == "br" else BLOCK)
            if self.in_heading:
                self.headings[-1] += " "
        for name, value in attrs:
            self.inline_style |= name == "style"
            self.text += [BLOCK, value or "", BLOCK] if name in SHOWN else []
        rel = dict(attrs).get("rel") or ""
        self.linked_sheet |= tag == "link" and "stylesheet" in rel.lower().split()

    @override
    def handle_endtag(self, tag: str) -> None:
        self.inside = ""
        self.in_heading &= not HEADING.fullmatch(tag)
        if tag not in INLINE and tag != "br":
            self.text.append(BLOCK)

    @override
    def handle_data(self, data: str) -> None:
        if self.inside == "style":
            self.css.append(data)
        elif not self.inside:
            self.text.append(data)
            if self.in_heading:
                self.headings[-1] += data


def read(path: Path) -> Page:
    page = Page()
    page.feed(path.read_text())
    return page


def squeeze(css: list[str]) -> str:
    return SYMBOLS.sub(
        lambda m: m.group(1) or ":", re.sub(r"\s+", " ", "".join(css))
    ).strip()


def problems(report: Path, template: Path) -> list[str]:
    if not template.is_file():
        return [
            (
                f"no saved template at {template}; "
                "copy assets/starter.html there, show the user the report, "
                "and commit it only after approval"
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
    shown = "".join(page.text)
    found += [
        f"report lacks the section {name!r}"
        for name in SECTIONS
        if name.lower() not in {" ".join(h.split()).lower() for h in page.headings}
    ]
    found += [
        f"text holds the placeholder {mark!r}; replace it with real text"
        for mark in PLACEHOLDER.findall(" ".join(shown.split()))
    ]
    found += [
        f"text holds the code {code!r}; write the item in full"
        for code in CODE.findall(shown)
    ]
    return found


HEX = re.compile(r"^[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?$")
HEAD_REF = re.compile(r"^ref:[ \t\n\r]*refs/")


def _valid_head(head: Path) -> bool:
    if not head.is_file():
        return False
    text = head.read_text(errors="replace").strip()
    return bool(HEAD_REF.match(text) or HEX.fullmatch(text))


def _requires_target(text: str) -> bool:
    return text.endswith(("/", "\\", "/.", "\\.")) or text in (".", "..")


def _has_existing_parent(path: Path, raw: str) -> bool:
    must_exist = _requires_target(raw)
    cur = path
    seen: set[Path] = set()
    while cur.is_symlink():
        if cur in seen or len(seen) >= 40:
            return False
        seen.add(cur)
        target_text = os.readlink(cur)
        if _requires_target(target_text):
            must_exist = True
        link = Path(target_text)
        cur = link if link.is_absolute() else (cur.parent / link)
    return cur.exists() if must_exist else cur.parent.is_dir()


def _check_gitdir(gitdir: Path) -> str:
    if not _valid_head(gitdir / "HEAD"):
        return "invalid"
    commondir = gitdir / "commondir"
    if commondir.is_file():
        raw = commondir.read_text(errors="replace").rstrip("\r\n")
        if not raw:
            return "stop"
        target = Path(raw)
        common = target if target.is_absolute() else (gitdir / target)
        if not _has_existing_parent(common, raw):
            return "stop"
    else:
        common = gitdir
    ok = (common / "objects").is_dir() and (common / "refs").is_dir()
    return "valid" if ok else "invalid"


def saved_template() -> Path | None:
    cwd = Path.cwd().resolve()
    if ".git" in cwd.parts:
        return None
    for folder in (cwd, *cwd.parents):
        marker = folder / ".git"
        if marker.is_dir():
            status = _check_gitdir(marker)
            if status == "valid":
                return folder / TEMPLATE
            if status == "stop":
                return None
            continue
        if marker.is_file():
            lines = marker.read_text(errors="replace").splitlines()
            if not lines or not lines[0].startswith("gitdir:"):
                return None
            target = Path(lines[0].removeprefix("gitdir:").strip())
            gitdir = target if target.is_absolute() else (folder / target)
            return folder / TEMPLATE if _check_gitdir(gitdir) == "valid" else None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check a client report against its saved template."
    )
    parser.add_argument("report", type=Path)
    parser.add_argument("--template", type=Path, default=None)
    args = parser.parse_args()
    template = args.template or saved_template()
    if template is None:
        print("run inside the project's git checkout")
        return 1
    found = problems(args.report, template)
    print("".join(f"{line}\n" for line in found), end="")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
