"""Static UX audit rules: duplicate sibling React keys and DESIGN.md fontWeight token parity."""

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from plans import _is_test as is_test_path

KEY_STEP = (
    "Give each sibling React element a distinct key (for example key={`item-${id}`})"
)
JSX_SUFFIXES = (".tsx", ".jsx")
YAML_FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", re.DOTALL)
FONT_FACE_BLOCK = re.compile(r"@font-face\s*\{([^}]*)\}", re.IGNORECASE | re.DOTALL)
FONT_FAMILY_DECL = re.compile(r"font-family\s*:\s*([^;}\n]+)", re.IGNORECASE)
FONT_WEIGHT_DECL = re.compile(
    r"font-weight\s*:\s*(\d{3})(?:\s+(\d{3}))?", re.IGNORECASE
)
TEXT_WEIGHT_VAR = re.compile(r"--text-([a-zA-Z0-9_-]+)--font-weight\s*:\s*(\d{3})\b")
FONT_SANS_VAR = re.compile(r"--font-sans\s*:\s*([^;}\n]+)")
TAG_NAME_RE = re.compile(r"([A-Za-z][A-Za-z0-9_$.-]*)")
JSX_KEYWORD_BEFORE = re.compile(r"\b(?:return|case|yield|await)$")
YAML_TEXT_WEIGHT = re.compile(
    r"""^["']?--text-([a-zA-Z0-9_-]+)--font-weight["']?\s*:\s*["']?(\d{3})["']?"""
)
YAML_ROLE_KEY = re.compile(r"^([a-zA-Z][a-zA-Z0-9_-]*)\s*:\s*$")
YAML_WEIGHT_KEY = re.compile(
    r"""^(?:fontWeight|font_weight|weight)\s*:\s*["']?(\d{3})["']?"""
)


@dataclass
class _JsxFrame:
    kind: str
    tag: str
    active: dict[str, tuple[int, str]]
    merged: dict[str, tuple[int, str]]
    depth: int = 0


def _jsx_key_value(tag_body: str, pos: int) -> str | None:
    from source_scan import string_end
    from ui_rules import _balanced_end

    length = len(tag_body)
    while pos < length and tag_body[pos].isspace():
        pos += 1
    if pos >= length or tag_body[pos] != "=":
        return None
    pos += 1
    while pos < length and tag_body[pos].isspace():
        pos += 1
    if pos < length and tag_body[pos] in ('"', "'"):
        end = string_end(tag_body, pos + 1, tag_body[pos], False)
        return tag_body[pos:end]
    if pos < length and tag_body[pos] == "{":
        end = _balanced_end(tag_body, pos + 1, "{", "}")
        inner = " ".join(tag_body[pos + 1 : max(pos + 1, end - 1)].split())
        return f"{{{inner}}}" if inner else None
    return None


def _jsx_key_attr(tag_body: str) -> str | None:
    from source_scan import string_end
    from ui_rules import _balanced_end

    index, length = 0, len(tag_body)
    while index < length:
        char = tag_body[index]
        if char in ('"', "'", "`"):
            index = string_end(tag_body, index + 1, char, False)
            continue
        if char == "{":
            index = _balanced_end(tag_body, index + 1, "{", "}")
            continue
        if (
            tag_body[index : index + 3] == "key"
            and (
                index == 0
                or not (tag_body[index - 1].isalnum() or tag_body[index - 1] in "_$-")
            )
            and (value := _jsx_key_value(tag_body, index + 3))
        ):
            return value
        index += 1
    return None


def _scan_jsx_tag_end(code: str, start: int) -> int | None:
    from source_scan import string_end
    from ui_rules import _balanced_end

    index, length = start, len(code)
    while index < length:
        char = code[index]
        if char in ('"', "'", "`"):
            index = string_end(code, index + 1, char, False)
        elif char == "{":
            index = _balanced_end(code, index + 1, "{", "}")
        elif char == ">":
            return index
        elif char == ";":
            return None
        else:
            index += 1
    return None


def _is_jsx_open_context(code: str, pos: int) -> bool:
    before = code[:pos].rstrip()
    return (
        not before
        or before.endswith(("=>", "&&", "||", "??"))
        or before[-1] in "([{,?:=>}"
        or bool(JSX_KEYWORD_BEFORE.search(before))
    )


class _JsxKeyScanner:
    def __init__(self, name: str, code: str, added_lines: set[int]) -> None:
        self.name = name
        self.code = code
        self.added_lines = added_lines
        self.stack: list[_JsxFrame] = []
        self.findings: list[str] = []
        self.reported: set[tuple[int, str]] = set()

    def _record_key(self, key: str, line_no: int) -> None:
        if not self.stack or self.stack[-1].kind == "fn":
            return
        target = self.stack[-1].active
        if key not in target:
            target[key] = (line_no, key)
            return
        first_line, _ = target[key]
        if (line_no in self.added_lines or first_line in self.added_lines) and (
            line_no,
            key,
        ) not in self.reported:
            self.reported.add((line_no, key))
            self.findings.append(
                f"{self.name}:{line_no}: duplicate sibling React key ({key}) matching line {first_line}. {KEY_STEP}"
            )

    def _handle_open_brace(self) -> None:
        if self.stack and self.stack[-1].kind == "jsx":
            self.stack.append(_JsxFrame("slot", "", {}, {}))
        elif self.stack and self.stack[-1].kind in ("slot", "fn"):
            self.stack[-1].depth += 1

    def _handle_close_brace(self) -> None:
        if not self.stack or self.stack[-1].kind not in ("slot", "fn"):
            return
        if self.stack[-1].depth > 0:
            self.stack[-1].depth -= 1
            return
        frame = self.stack.pop()
        if frame.kind == "slot":
            for key, (line_no, _) in {**frame.merged, **frame.active}.items():
                self._record_key(key, line_no)

    def _handle_open_tag(self, index: int) -> int:
        code = self.code
        if code[index : index + 2] == "</":
            return self._handle_close_tag(index)
        if code[index : index + 2] == "<>":
            self.stack.append(_JsxFrame("jsx", "", {}, {}))
            return index + 2
        if index + 1 >= len(code) or not code[index + 1].isalpha():
            return index + 1
        if not _is_jsx_open_context(code, index):
            return index + 1
        matched = TAG_NAME_RE.match(code[index + 1 :])
        if not matched:
            return index + 1
        tag_name = matched.group(1)
        after = index + 1 + len(tag_name)
        if after >= len(code) or code[after] not in " \t\r\n/>":
            return index + 1
        end = _scan_jsx_tag_end(code, after)
        if end is None:
            return index + 1
        body = code[after:end]
        if key := _jsx_key_attr(body):
            self._record_key(key, code.count("\n", 0, index) + 1)
        if not body.rstrip().endswith("/"):
            self.stack.append(_JsxFrame("jsx", tag_name, {}, {}))
        return end + 1

    def _handle_close_tag(self, index: int) -> int:
        close_end = self.code.find(">", index + 2)
        if close_end == -1:
            return index + 1
        close_tag = self.code[index + 2 : close_end].strip()
        for pos in range(len(self.stack) - 1, -1, -1):
            if self.stack[pos].kind == "jsx" and self.stack[pos].tag == close_tag:
                del self.stack[pos:]
                break
        return close_end + 1

    def _handle_punct(self, char: str, index: int) -> int:
        if char == "{":
            self._handle_open_brace()
        elif char == "}":
            self._handle_close_brace()
        elif (
            char == "["
            and self.stack
            and self.stack[-1].kind in ("slot", "fn", "array")
        ):
            self.stack.append(_JsxFrame("array", "", {}, {}))
        elif char == "]" and self.stack and self.stack[-1].kind == "array":
            self.stack.pop()
        elif (
            char in ("?", ":")
            and self.stack
            and self.stack[-1].kind == "slot"
            and self.stack[-1].depth == 0
        ):
            self.stack[-1].merged.update(self.stack[-1].active)
            self.stack[-1].active = {}
        return index + 1

    def scan(self) -> list[str]:
        from source_scan import string_end

        index, length = 0, len(self.code)
        while index < length:
            char = self.code[index]
            if char in ('"', "'", "`"):
                index = string_end(self.code, index + 1, char, False)
            elif (
                self.code[index : index + 2] == "=>"
                and self.stack
                and self.stack[-1].kind == "slot"
            ):
                self.stack[-1].kind = "fn"
                self.stack[-1].active = {}
                self.stack[-1].merged = {}
                index += 2
            elif char == "<":
                index = self._handle_open_tag(index)
            else:
                index = self._handle_punct(char, index)
        return self.findings


def duplicate_sibling_keys(
    name: str, file_text: str, added_lines: set[int]
) -> list[str]:
    """Flag direct sibling JSX elements sharing a key inside the same parent or fragment."""
    from ui_rules import UNOWNED

    if (
        not name.endswith(JSX_SUFFIXES)
        or not added_lines
        or "key" not in file_text
        or name.startswith(UNOWNED)
        or is_test_path(PurePosixPath(name))
    ):
        return []
    from source_scan import code_without_comments

    normalized = file_text.replace("\r\n", "\n").replace("\r", "\n")
    code = code_without_comments(normalized, PurePosixPath(name).suffix)
    return _JsxKeyScanner(name, code, added_lines).scan()


def _design_yaml_weights(design_path: Path) -> dict[str, int]:
    """Extract explicit role -> fontWeight pairs from DESIGN.md YAML front matter."""
    if not design_path.is_file():
        return {}
    match = YAML_FRONT_MATTER.match(design_path.read_text(errors="replace"))
    if not match:
        return {}
    weights: dict[str, int] = {}
    current_key, current_indent = "", -1
    for raw in match.group(1).splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if m_var := YAML_TEXT_WEIGHT.match(stripped):
            weights[m_var.group(1)] = int(m_var.group(2))
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if m_key := YAML_ROLE_KEY.match(stripped):
            current_key, current_indent = m_key.group(1), indent
            continue
        if indent <= current_indent:
            current_key, current_indent = "", -1
        if current_key and (m_wt := YAML_WEIGHT_KEY.match(stripped)):
            weights[current_key] = int(m_wt.group(1))
    return weights


def _primary_font_ranges(css_texts: list[str]) -> list[tuple[int, int]]:
    sans_families = {
        first
        for text in css_texts
        for match in FONT_SANS_VAR.finditer(text)
        if (first := match.group(1).split(",", 1)[0].strip().strip("\"'").lower())
    }
    ranges: list[tuple[int, int]] = []
    for text in css_texts:
        for block in FONT_FACE_BLOCK.findall(text):
            fam_match = FONT_FAMILY_DECL.search(block)
            wt_match = FONT_WEIGHT_DECL.search(block)
            if not fam_match or not wt_match:
                continue
            fam = fam_match.group(1).strip().strip("\"'").lower()
            if sans_families and fam not in sans_families:
                continue
            lo = int(wt_match.group(1))
            hi = int(wt_match.group(2)) if wt_match.group(2) else lo
            ranges.append((min(lo, hi), max(lo, hi)))
    return ranges


def _theme_text_weights(theme_bodies: list[str]) -> tuple[set[str], dict[str, int]]:
    from ui_rules import THEME_VAR

    roles: set[str] = set()
    weights: dict[str, int] = {}
    for body in theme_bodies:
        for kind, token, _ in THEME_VAR.findall(body):
            if kind == "text" and "--" not in token:
                roles.add(token)
        for role, wt in TEXT_WEIGHT_VAR.findall(body):
            weights[role] = int(wt)
    return roles, weights


def design_weight_findings(
    root: Path, package: Path, css_entries: list[str], changed: set[str]
) -> list[str]:
    """Verify DESIGN.md YAML fontWeight declarations match @theme --text-*--font-weight and loaded @font-face weights."""
    from ui_rules import CSS_COMMENT, _css_files, _theme_bodies

    design_path = (
        package / "DESIGN.md"
        if (package / "DESIGN.md").is_file()
        else root / "DESIGN.md"
    )
    files: list[Path] = (
        _css_files(root, package, css_entries) if design_path.is_file() else []
    )
    if not files:
        return []
    design_rel = design_path.relative_to(root).as_posix()
    css_rels = {path.relative_to(root).as_posix() for path in files}
    if design_rel not in changed and not (css_rels & changed):
        return []
    css_texts = [
        CSS_COMMENT.sub("", path.read_text(errors="replace")) for path in files
    ]
    theme_bodies = [body for text in css_texts for body in _theme_bodies(text)]
    if not theme_bodies:
        return []
    defined_roles, defined_weights = _theme_text_weights(theme_bodies)
    findings = [
        f"{design_rel}: DESIGN.md declares fontWeight {weight} for {role}, "
        f"but @theme defines --text-{role} without --text-{role}--font-weight"
        for role, weight in sorted(_design_yaml_weights(design_path).items())
        if weight != 400 and role in defined_roles and role not in defined_weights
    ]
    if ranges := _primary_font_ranges(css_texts):
        findings.extend(
            f"{design_rel}: --text-{role}--font-weight ({weight}) is outside loaded @font-face font-weight ranges"
            for role, weight in sorted(defined_weights.items())
            if not any(lo <= weight <= hi for lo, hi in ranges)
        )
    return findings


def audit_findings(
    root: Path,
    candidates: dict[str, list[tuple[int, str]]],
    css_entries: list[str] | None,
) -> list[str]:
    from ui_rules import STYLE_TOKEN_SUFFIXES, UNOWNED, _all_css_entries, _package_dir

    changed = set(candidates)
    checked: set[Path] = set()
    hits: list[str] = []
    for name in candidates:
        if name.startswith(UNOWNED) or is_test_path(PurePosixPath(name)):
            continue
        if not (
            name.endswith(STYLE_TOKEN_SUFFIXES)
            or PurePosixPath(name).name == "DESIGN.md"
        ):
            continue
        if css_entries is None:
            css_entries = _all_css_entries(root)
        package = _package_dir(root, name)
        if package not in checked:
            checked.add(package)
            hits.extend(design_weight_findings(root, package, css_entries, changed))
    return hits
