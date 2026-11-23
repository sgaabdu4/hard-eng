"""Static UX audit rules: duplicate sibling React keys and DESIGN.md fontWeight token parity."""

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from generated_marks import generated_sources
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
TEXT_FAMILY_VAR = re.compile(r"--text-([a-zA-Z0-9_-]+)--font-family\s*:\s*([^;}\n]+)")
FONT_THEME_VAR = re.compile(r"--font-([a-zA-Z0-9_-]+)\s*:\s*([^;}\n]+)")
TAG_NAME_RE = re.compile(r"([A-Za-z][A-Za-z0-9_$.-]*)")
JSX_KEYWORD_BEFORE = re.compile(r"\b(?:return|case|yield|await)$")
YAML_TEXT_WEIGHT = re.compile(
    r"""^["']?--text-([a-zA-Z0-9_-]+)--font-weight["']?\s*:\s*["']?(\d{3})["']?"""
)
YAML_ROLE_KEY = re.compile(r"^([a-zA-Z][a-zA-Z0-9_-]*)\s*:\s*$")
YAML_WEIGHT_KEY = re.compile(
    r"""^(?:fontWeight|font_weight|weight)\s*:\s*["']?(\d{3})["']?"""
)
YAML_FAMILY_KEY = re.compile(r"""^(?:fontFamily|font_family|family)\s*:\s*(.+)$""")
THEME_DEFAULT_FLAG = re.compile(r"\bdefault\b", re.IGNORECASE)


@dataclass
class _JsxFrame:
    kind: str
    tag: str
    active: dict[str, tuple[int, int]]
    merged: dict[str, tuple[int, int]]
    depth: int = 0
    paren: int = 0


def _first_family(raw: str) -> str:
    return raw.split(",", 1)[0].strip().strip("\"'").lower()


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


def _jsx_key_attr(tag_body: str) -> tuple[str, int] | None:
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
            return value, index
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

    def _record_key(self, key: str, tag_line: int, key_line: int) -> None:
        if not self.stack or self.stack[-1].kind == "fn":
            return
        target = self.stack[-1].active
        if key not in target:
            target[key] = (tag_line, key_line)
            return
        first_tag, first_key = target[key]
        touched = {tag_line, key_line, first_tag, first_key} & self.added_lines
        if touched and (key_line, key) not in self.reported:
            self.reported.add((key_line, key))
            self.findings.append(
                f"{self.name}:{key_line}: duplicate sibling React key ({key}) matching line {first_key}. {KEY_STEP}"
            )

    def _pop_slot_to_parent(self) -> None:
        frame = self.stack.pop()
        if frame.kind == "slot":
            for key, (tag_line, key_line) in {**frame.merged, **frame.active}.items():
                self._record_key(key, tag_line, key_line)

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
        if len(self.stack) >= 2 and self.stack[-2].kind == "array":
            return
        self._pop_slot_to_parent()

    def _in_array_item(self) -> bool:
        return (
            len(self.stack) >= 2
            and self.stack[-2].kind == "array"
            and self.stack[-1].kind in ("slot", "fn")
            and self.stack[-1].depth == 0
            and self.stack[-1].paren == 0
        )

    def _handle_array_char(self, char: str) -> None:
        if char == "[" and (
            not self.stack or self.stack[-1].kind in ("slot", "fn", "array")
        ):
            self.stack.append(_JsxFrame("array", "", {}, {}))
            self.stack.append(_JsxFrame("slot", "", {}, {}))
        elif char == "," and self._in_array_item():
            self._pop_slot_to_parent()
            self.stack.append(_JsxFrame("slot", "", {}, {}))
        elif char == "]":
            if self._in_array_item():
                self._pop_slot_to_parent()
            if self.stack and self.stack[-1].kind == "array":
                self.stack.pop()

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
        if found := _jsx_key_attr(body):
            key, offset = found
            tag_line = code.count("\n", 0, index) + 1
            key_line = code.count("\n", 0, after + offset) + 1
            self._record_key(key, tag_line, key_line)
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
        elif char == "(" and self.stack and self.stack[-1].kind in ("slot", "fn"):
            self.stack[-1].paren += 1
        elif (
            char == ")"
            and self.stack
            and self.stack[-1].kind in ("slot", "fn")
            and self.stack[-1].paren > 0
        ):
            self.stack[-1].paren -= 1
        elif char in ("[", ",", "]"):
            self._handle_array_char(char)
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
    """Flag direct sibling JSX elements sharing a key inside the same parent, fragment or array."""
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


def _design_yaml_typography(
    design_path: Path,
) -> tuple[dict[str, int], dict[str, str]]:
    """Extract explicit role -> fontWeight and optional fontFamily from DESIGN.md YAML front matter."""
    if not design_path.is_file():
        return {}, {}
    match = YAML_FRONT_MATTER.match(design_path.read_text(errors="replace"))
    if not match:
        return {}, {}
    weights: dict[str, int] = {}
    families: dict[str, str] = {}
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
        elif (
            current_key
            and (m_fam := YAML_FAMILY_KEY.match(stripped))
            and (fam := _first_family(m_fam.group(1)))
        ):
            families[current_key] = fam
    return weights, families


def _font_face_ranges(
    css_texts: list[str],
) -> tuple[dict[str, list[tuple[int, int]]], set[str]]:
    mono_only: set[str] = set()
    non_mono: set[str] = set()
    for text in css_texts:
        for name, raw in FONT_THEME_VAR.findall(text):
            if first := _first_family(raw):
                (mono_only if name == "mono" else non_mono).add(first)
    by_family: dict[str, list[tuple[int, int]]] = {}
    for text in css_texts:
        for block in FONT_FACE_BLOCK.findall(text):
            fam_match = FONT_FAMILY_DECL.search(block)
            wt_match = FONT_WEIGHT_DECL.search(block)
            if not fam_match or not wt_match:
                continue
            fam = _first_family(fam_match.group(1))
            lo = int(wt_match.group(1))
            hi = int(wt_match.group(2)) if wt_match.group(2) else lo
            by_family.setdefault(fam, []).append((min(lo, hi), max(lo, hi)))
    return by_family, mono_only - non_mono


def _theme_blocks(css: str) -> list[tuple[str, bool]]:
    from ui_rules import THEME_BLOCK

    blocks: list[tuple[str, bool]] = []
    for match in THEME_BLOCK.finditer(css):
        depth, index = 1, match.end()
        while index < len(css) and depth:
            depth += (css[index] == "{") - (css[index] == "}")
            index += 1
        body = css[match.end() : max(match.end(), index - 1)]
        blocks.append((body, bool(THEME_DEFAULT_FLAG.search(match[0]))))
    return blocks


def _clear_text_token(
    token: str,
    roles: set[str],
    weights: dict[str, int],
    families: dict[str, str],
    explicit_w: set[str],
    explicit_f: set[str],
) -> None:
    if token == "*":
        roles.clear()
        weights.clear()
        families.clear()
        explicit_w.clear()
        explicit_f.clear()
    elif token.endswith("--font-weight"):
        role = token[: -len("--font-weight")]
        weights.pop(role, None)
        explicit_w.discard(role)
    elif "--" not in token:
        roles.discard(token)


def _set_role_prop[T](
    table: dict[str, T], explicit: set[str], role: str, value: T, is_default: bool
) -> None:
    if not is_default or role not in explicit:
        table[role] = value
    if not is_default:
        explicit.add(role)


def _apply_theme_block(
    body: str,
    is_default: bool,
    roles: set[str],
    weights: dict[str, int],
    families: dict[str, str],
    explicit_w: set[str],
    explicit_f: set[str],
) -> None:
    from ui_rules import THEME_VAR

    for kind, token, raw_value in THEME_VAR.findall(body):
        if kind != "text":
            continue
        if raw_value.strip() == "initial":
            _clear_text_token(token, roles, weights, families, explicit_w, explicit_f)
        elif "--" not in token:
            roles.add(token)
    for role, wt in TEXT_WEIGHT_VAR.findall(body):
        _set_role_prop(weights, explicit_w, role, int(wt), is_default)
    for role, raw in TEXT_FAMILY_VAR.findall(body):
        if fam := _first_family(raw):
            _set_role_prop(families, explicit_f, role, fam, is_default)


def _theme_text_tokens(
    theme_blocks: list[tuple[str, bool]],
) -> tuple[set[str], dict[str, int], dict[str, str]]:
    roles: set[str] = set()
    weights: dict[str, int] = {}
    families: dict[str, str] = {}
    explicit_w: set[str] = set()
    explicit_f: set[str] = set()
    for body, is_default in theme_blocks:
        _apply_theme_block(
            body, is_default, roles, weights, families, explicit_w, explicit_f
        )
    return roles, weights, families


def _weight_covered(
    weight: int,
    role_family: str | None,
    by_family: dict[str, list[tuple[int, int]]],
    mono_only: set[str],
) -> bool:
    if not by_family:
        return True
    if role_family:
        ranges = by_family.get(role_family)
        return True if not ranges else any(lo <= weight <= hi for lo, hi in ranges)
    active = {fam: rngs for fam, rngs in by_family.items() if fam not in mono_only}
    pool = [rng for ranges in (active or by_family).values() for rng in ranges]
    return not pool or any(lo <= weight <= hi for lo, hi in pool)


def _design_weight_mismatches(
    design_rel: str,
    design_weights: dict[str, int],
    defined_roles: set[str],
    defined_weights: dict[str, int],
) -> list[str]:
    findings: list[str] = []
    for role, weight in sorted(design_weights.items()):
        if role in defined_weights and defined_weights[role] != weight:
            findings.append(
                f"{design_rel}: DESIGN.md declares fontWeight {weight} for {role}, "
                f"but @theme defines --text-{role}--font-weight: {defined_weights[role]}"
            )
        elif weight != 400 and role in defined_roles and role not in defined_weights:
            findings.append(
                f"{design_rel}: DESIGN.md declares fontWeight {weight} for {role}, "
                f"but @theme defines --text-{role} without --text-{role}--font-weight"
            )
    return findings


def _group_weight_findings(
    design_rel: str,
    design_weights: dict[str, int],
    design_role_fams: dict[str, str],
    css_texts: list[str],
    pkg_faces: tuple[dict[str, list[tuple[int, int]]], set[str]],
) -> list[str]:
    theme_blocks = [blk for text in css_texts for blk in _theme_blocks(text)]
    if not theme_blocks:
        return []
    defined_roles, defined_weights, theme_role_fams = _theme_text_tokens(theme_blocks)
    findings = _design_weight_mismatches(
        design_rel, design_weights, defined_roles, defined_weights
    )
    group_faces = _font_face_ranges(css_texts)
    by_family = {**pkg_faces[0], **group_faces[0]}
    mono_only = group_faces[1] | {
        fam for fam in pkg_faces[1] if fam not in group_faces[0]
    }
    role_families = {**design_role_fams, **theme_role_fams}
    for role, weight in sorted(defined_weights.items()):
        if not _weight_covered(weight, role_families.get(role), by_family, mono_only):
            findings.append(
                f"{design_rel}: --text-{role}--font-weight ({weight}) is outside loaded @font-face font-weight ranges"
            )
    return findings


def _live_css_groups(
    root: Path, groups: list[list[Path]], changed: set[str]
) -> list[list[Path]]:
    all_rels = sorted(
        {path.relative_to(root).as_posix() for group in groups for path in group}
    )
    skipped = generated_sources(root, all_rels) if all_rels else set()
    live: list[list[Path]] = []
    for group in groups:
        if not group:
            continue
        rels = [path.relative_to(root).as_posix() for path in group]
        if rels[-1] not in skipped or any(
            rel in changed and rel not in skipped for rel in rels
        ):
            live.append(group)
    return live


def design_weight_findings(
    root: Path, package: Path, css_entries: list[str], changed: set[str]
) -> list[str]:
    """Verify DESIGN.md YAML fontWeight declarations match @theme --text-*--font-weight and loaded @font-face weights."""
    from ui_rules import CSS_COMMENT, _css_entrypoint_orders, _css_files

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
    text_by_path = {
        path: CSS_COMMENT.sub("", path.read_text(errors="replace")) for path in files
    }
    live_groups = _live_css_groups(
        root, _css_entrypoint_orders(files, text_by_path), changed
    )
    live_paths = list(dict.fromkeys(path for group in live_groups for path in group))
    pkg_faces = _font_face_ranges([text_by_path[path] for path in live_paths])
    design_weights, design_role_fams = _design_yaml_typography(design_path)
    seen: list[str] = []
    for group in live_groups:
        for hit in _group_weight_findings(
            design_rel,
            design_weights,
            design_role_fams,
            [text_by_path[path] for path in group],
            pkg_faces,
        ):
            if hit not in seen:
                seen.append(hit)
    return seen


def audit_findings(
    root: Path,
    candidates: dict[str, list[tuple[int, str]]],
    css_entries: list[str] | None,
) -> list[str]:
    from ui_rules import STYLE_TOKEN_SUFFIXES, UNOWNED, _all_css_entries, _package_dir

    relevant = [
        name
        for name in candidates
        if not name.startswith(UNOWNED)
        and not is_test_path(PurePosixPath(name))
        and (
            name.endswith(STYLE_TOKEN_SUFFIXES)
            or PurePosixPath(name).name == "DESIGN.md"
        )
    ]
    if not relevant:
        return []
    skipped = generated_sources(root, relevant)
    live = [name for name in relevant if name not in skipped]
    if not live:
        return []
    changed = set(live)
    if css_entries is None:
        css_entries = _all_css_entries(root)
    packages: set[Path] = set()
    for name in live:
        pkg = _package_dir(root, name)
        packages.add(pkg)
        if name == "DESIGN.md":
            packages.update(_package_dir(root, entry) for entry in css_entries)
    return [
        hit
        for package in sorted(packages)
        for hit in design_weight_findings(root, package, css_entries, changed)
    ]
