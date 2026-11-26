"""HE-UI-SOURCE: which files the repository itself marks as email, standalone page or PDF code."""

import re
from pathlib import PurePosixPath

SCRIPT_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte")
PDF_MODULE = r"(?:@react-pdf/renderer|jspdf|pdfmake|pdf-lib)(?:/[^'\"]*)?"
EMAIL_MODULE = r"(?:@react-email/[^'\"]+|mjml)(?:/[^'\"]*)?"
STRING = r"(?P<string>\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`)"
COMMENT = re.compile(
    STRING + r"|(?:^|(?<=\s))//[^\n]*|/\*.*?\*/", re.DOTALL | re.MULTILINE
)
EMAIL_FOLDERS = frozenset(("email", "emails", "mail", "mails"))
STANDALONE = re.compile(r"<!doctype html", re.IGNORECASE)
DART_PDF = re.compile(r"(?m)^\s*import\s+['\"]package:(?:pdf|printing)/")


def import_forms(module: str) -> list[re.Pattern[str]]:
    """Each form starts a line, and binds the names that the file must then use."""
    quoted = rf"['\"]{module}['\"]"
    return [
        re.compile(
            rf"(?m)^\s*import\s+(?!type\b)(?P<bound>[^;'\"]*?)\s*\bfrom\s*{quoted}"
        ),
        re.compile(
            rf"(?m)^\s*(?:const|let|var)\s+(?P<bound>\w+|\{{[^}}]*\}})\s*="
            rf"\s*(?:await\s+)?(?:require|import)\(\s*{quoted}\s*\)"
        ),
    ]


PDF_IMPORTS = import_forms(PDF_MODULE)
EMAIL_IMPORTS = import_forms(EMAIL_MODULE)
CLAUSE_SPLIT = re.compile(r"[{},]")
IDENTIFIER = re.compile(r"[A-Za-z_$][\w$]*")
USED_NAME = re.compile(r"(?<![\w$.])[A-Za-z_$][\w$]*")


def bound_names(clause: str) -> set[str]:
    """The names an import clause or a destructuring binds; a type-only named item binds none."""
    names: set[str] = set()
    for part in CLAUSE_SPLIT.split(clause.replace("*", " ")):
        words = part.split()
        if not words or words[0] == "type":
            continue
        names.add(words[-1] if "as" in words or ":" in part else words[0])
    return {name for name in names if IDENTIFIER.fullmatch(name)}


def used_import(code: str, patterns: list[re.Pattern[str]]) -> bool:
    for pattern in patterns:
        for hit in pattern.finditer(code):
            rest = code[: hit.start()] + code[hit.end() :]
            if bound_names(hit["bound"]) & set(USED_NAME.findall(rest)):
                return True
    return False


def code_of(text: str) -> str:
    """The text without comments; a string is read whole, so a /* inside it opens nothing, and a line comment is matched before a block comment, so a // line that holds /* hides nothing."""
    return COMMENT.sub(lambda hit: hit["string"] or "", text)


def exemption(name: str, text: str) -> str | None:
    path = PurePosixPath(name)
    code = code_of(text) if name.endswith((*SCRIPT_SUFFIXES, ".dart")) else ""
    if (name.endswith(".dart") and DART_PDF.search(code)) or (
        name.endswith(SCRIPT_SUFFIXES) and used_import(code, PDF_IMPORTS)
    ):
        return "pdf"
    if (
        (name.endswith(SCRIPT_SUFFIXES) and used_import(code, EMAIL_IMPORTS))
        or path.suffix == ".mjml"
        or (path.suffix == ".html" and EMAIL_FOLDERS.intersection(path.parts[:-1]))
    ):
        return "email"
    if path.suffix in (".ts", ".js") and STANDALONE.search(code):
        return "standalone"
    return None
