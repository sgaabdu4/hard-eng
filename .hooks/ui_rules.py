"""HE-UI-SOURCE: added UI lines hold no every-property transition, no colour literal outside a theme file and no undefined Tailwind @theme colour token."""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from generated_marks import generated_sources
from plans import _is_test as is_test_path
from project_files import GIT_LISTING

UNOWNED = (".hooks/", ".agents/", ".claude/")
THEME_WORDS = frozenset(
    ("theme", "token", "color", "colour", "palette")
    + ("themes", "tokens", "colors", "colours", "palettes")
)
NAME_WORDS = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z0-9]+")
COMMENT_LINE = re.compile(r"^\s*(?:\{\s*)?(?://|/\*|<!--|\*(?:\s|/|$))")
TRANSITION_CLASS = re.compile(r"(?<![\w-])transition-all(?![\w-])")
TRANSITION_STYLE = re.compile(
    r"(?<!\w)transition(?:-property|Property)?[\"']?\s*:\s*[\"'`]?(?:[^;\"'`,]*,\s*)?all(?![\w-])"
)
TAILWIND_COLOUR = re.compile(
    r"-\[(?:#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F\w])"
    r"|(?:rgba?|hsla?|oklch)\((?!\s*var\())"
)
DART_COLOUR = re.compile(
    r"\bColor\(\s*0x|\bColor\.from(?:ARGB|RGBO)?\(|\bColors\.(?!transparent\b)[A-Za-z]"
)
SWIFT_COLOUR = re.compile(
    r"\b(?:UI|NS)?Color\((?:\.(?:sRGB|sRGBLinear|displayP3)\s*,\s*)?red:|#colorLiteral\("
)
TRANSITION_STEP = (
    "List the properties that change, for example transition-[opacity,transform] "
    "or transition: opacity 150ms"
)
COLOUR_STEP = (
    "Use a colour of the theme, or add the colour to a theme or token file "
    "(a folder or file named theme, token, color, colour or palette, or tailwind.config.*)"
)
TOKEN_STEP = (
    "Use an existing @theme colour token or define --color-<name> in a CSS @theme block"
)
MARKUP_TOKEN_SUFFIXES = (".tsx", ".jsx", ".html", ".vue", ".svelte", ".astro")
SCRIPT_TOKEN_SUFFIXES = (".ts", ".js")
STYLE_TOKEN_SUFFIXES = (".css", ".scss", ".less")
BUILD_FOLDERS = frozenset(("dist", "build", ".next", "out", "coverage", "node_modules"))
SAFE_PLUGINS = frozenset(
    (
        "@tailwindcss/typography",
        "@tailwindcss/forms",
        "@tailwindcss/aspect-ratio",
        "@tailwindcss/container-queries",
    )
)
DEFAULT_FAMILIES = frozenset(
    (
        "slate",
        "gray",
        "zinc",
        "neutral",
        "stone",
        "red",
        "orange",
        "amber",
        "yellow",
        "lime",
        "green",
        "emerald",
        "teal",
        "cyan",
        "sky",
        "blue",
        "indigo",
        "violet",
        "purple",
        "fuchsia",
        "pink",
        "rose",
    )
)
DEFAULT_SHADES = frozenset(
    ("50", "100", "200", "300", "400", "500", "600", "700", "800", "900", "950")
)
UNIVERSAL_COLORS = frozenset(("inherit", "current", "transparent"))
DEFAULT_SOLIDS = frozenset(("black", "white"))
BUILTIN_TEXT = frozenset(
    (
        "xs",
        "sm",
        "base",
        "lg",
        "xl",
        "2xl",
        "3xl",
        "4xl",
        "5xl",
        "6xl",
        "7xl",
        "8xl",
        "9xl",
        "left",
        "center",
        "right",
        "justify",
        "start",
        "end",
        "wrap",
        "nowrap",
        "balance",
        "pretty",
        "ellipsis",
        "clip",
        "align",
        "decoration",
        "decoration-line",
        "decoration-color",
        "decoration-style",
        "decoration-thickness",
        "transform",
        "indent",
        "overflow",
        "rendering",
        "underline-offset",
        "size-adjust",
        "emphasis",
        "orientation",
        "combine-upright",
        "autospace",
        "box",
        "box-trim",
        "box-edge",
        "spacing-trim",
    )
)
BUILTIN_BG = frozenset(
    (
        "auto",
        "cover",
        "contain",
        "fixed",
        "local",
        "scroll",
        "none",
        "bottom",
        "center",
        "left",
        "left-bottom",
        "left-top",
        "right",
        "right-bottom",
        "right-top",
        "top",
        "repeat",
        "no-repeat",
        "repeat-x",
        "repeat-y",
        "repeat-round",
        "repeat-space",
        "radial",
        "conic",
    )
)
BUILTIN_BG_PREFIXES = (
    "clip-",
    "origin-",
    "gradient-",
    "linear-",
    "radial-",
    "conic-",
    "blend-",
    "position-",
    "size-",
    "opacity-",
    "top-",
    "bottom-",
    "left-",
    "right-",
    "repeat-",
    "mask-",
)
BUILTIN_BORDER = frozenset(
    (
        "solid",
        "dashed",
        "dotted",
        "double",
        "hidden",
        "none",
        "collapse",
        "separate",
        "t",
        "r",
        "b",
        "l",
        "x",
        "y",
        "s",
        "e",
        "bs",
        "be",
        "box",
        "color",
        "radius",
        "width",
        "style",
        "top",
        "right",
        "bottom",
        "left",
        "inline",
        "block",
        "image",
        "start-start-radius",
        "start-end-radius",
        "end-start-radius",
        "end-end-radius",
        "top-left-radius",
        "top-right-radius",
        "bottom-left-radius",
        "bottom-right-radius",
    )
)
BORDER_SIDES = frozenset(("t", "r", "b", "l", "x", "y", "s", "e", "bs", "be"))
BUILTIN_RING = frozenset(("inset", "none"))
BUILTIN_FILL = frozenset(("none", "opacity", "rule"))
BUILTIN_STROKE = frozenset(
    (
        "none",
        "width",
        "linecap",
        "linejoin",
        "dasharray",
        "dashoffset",
        "miterlimit",
        "opacity",
    )
)
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
CSS_IMPORT = re.compile(r"""@import\s+(?:url\(\s*)?["']([^"']+)["']""")
THEME_BLOCK = re.compile(r"@theme\b[^{]*\{")
PLUGIN_CALL = re.compile(r"""@plugin\s+["']([^"']+)["']""")
CONFIG_CALL = re.compile(r"@config\b")
THEME_VAR = re.compile(
    r"--(color|text|background-image)-([a-zA-Z0-9_*-]+)\s*:\s*([^;}\n]+)"
)
UTILITY_DECL = re.compile(r"@utility\s+([a-zA-Z0-9_-]+(?:\*)?)")
CLASS_SELECTOR = re.compile(
    r"(?<![\w-])\.((?:text|bg|border|ring|fill|stroke)-[a-zA-Z0-9_-]+)"
)
APPLY_RULE = re.compile(r"@apply\b([^;{}]+)")
STRING_TOKEN = re.compile(r"""(["'`])((?:\\.|(?!\1)[^\\\n])*)\1""")
NON_CLASS_ATTR_OPEN = re.compile(
    r"""(?:\b(?:id|name|htmlFor|for|href|src|alt|title|placeholder|type|role|value|defaultValue|action|method|key|target|rel|as|accept|autoComplete)|(?:data|aria)-[\w-]+)\s*=\s*"""
)
SCRIPT_CLASS_CONTEXT = re.compile(
    r"\b(?:className|classList|cn|clsx|cva|twMerge|classNames)\b"
)
SCRIPT_CALL_OPEN = re.compile(
    r"\b(?:cn|clsx|cva|twMerge|classNames|classList\.\w+)\s*\("
)
CLASS_ATTR_EXPR = re.compile(r"\b(?:className|class)\s*=\s*\{")
CLASS_PROP_EXPR = re.compile(r"\bclassName\s*:\s*")
CLASS_TEMPLATE_ASSIGN = re.compile(r"\bclassName\s*[:=]\s*`")
COMPARE_BEFORE = re.compile(
    r"(?:===?|!==?|\bcase)\s*$|\.(?:includes|startsWith|endsWith|indexOf|match)\(\s*$"
)
COMPARE_AFTER = re.compile(r"^\s*(?:===?|!==?)")
TEMPLATE_EXPR = re.compile(r"\$\{[^}]*\}")
COLOR_CLASS = re.compile(r"^(text|bg|border|ring|fill|stroke)-([a-zA-Z0-9_-]+)$")
FILE_SUFFIXES = (
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".webp",
    ".gif",
    ".css",
    ".js",
    ".ts",
    ".json",
)


@dataclass(frozen=True)
class ThemeTokens:
    colors: frozenset[str]
    text_sizes: frozenset[str]
    bg_images: frozenset[str]
    custom_classes: frozenset[str]
    custom_prefixes: frozenset[str]
    default_colors: bool
    cleared_families: frozenset[str]
    cleared_colors: frozenset[str] = frozenset()


def is_theme_path(name: str) -> bool:
    path = PurePosixPath(name)
    parts = (NAME_WORDS.findall(part) for part in path.stem.split("+"))
    return (
        path.name.startswith("tailwind.config.")
        or any(part.lower() in THEME_WORDS for part in path.parts[:-1])
        or any(words and words[-1].lower() in THEME_WORDS for words in parts)
    )


def colour_pattern(name: str) -> re.Pattern[str]:
    if name.endswith(".dart"):
        return DART_COLOUR
    return SWIFT_COLOUR if name.endswith(".swift") else TAILWIND_COLOUR


def _theme_bodies(css: str) -> list[str]:
    from ui_audit_rules import _theme_blocks

    return [body for body, _ in _theme_blocks(css)]


def _package_dir(root: Path, name: str) -> Path:
    for parent in PurePosixPath(name).parents:
        candidate = root / parent
        if (candidate / "package.json").is_file():
            return candidate
    return root


def _all_css_entries(root: Path) -> list[str]:
    done = subprocess.run(
        [
            *GIT_LISTING,
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "*.css",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        return []
    return [entry for entry in done.stdout.split("\0") if entry]


def _css_files(
    root: Path, package: Path, entries: list[str] | None = None
) -> list[Path]:
    found: list[Path] = []
    for entry in _all_css_entries(root) if entries is None else entries:
        parts = PurePosixPath(entry).parts
        if (
            entry.startswith(UNOWNED)
            or is_test_path(PurePosixPath(entry))
            or BUILD_FOLDERS.intersection(parts)
            or _package_dir(root, entry) != package
        ):
            continue
        path = root / entry
        if path.is_file() and not path.is_symlink():
            found.append(path)
    return found


def _has_external_theme(package: Path, css_texts: list[str]) -> bool:
    if any(package.glob("tailwind.config.*")):
        return True
    for text in css_texts:
        if CONFIG_CALL.search(text):
            return True
        if any(plugin not in SAFE_PLUGINS for plugin in PLUGIN_CALL.findall(text)):
            return True
    return False


def _css_import_targets(
    path: Path, text: str, by_resolved: dict[Path, Path]
) -> list[Path]:
    found: list[Path] = []
    for target in CSS_IMPORT.findall(text):
        if target.startswith(("http://", "https://", "//")):
            continue
        for suffix in ("", ".css"):
            candidate = (path.parent / (target + suffix)).resolve()
            if candidate in by_resolved:
                found.append(by_resolved[candidate])
                break
    return found


def _css_entrypoint_orders(
    files: list[Path], texts: dict[Path, str]
) -> list[list[Path]]:
    """Expand each CSS entrypoint independently in exact @import order so separate builds do not reset one another."""
    by_resolved = {path.resolve(): path for path in files}
    edges = {
        path: _css_import_targets(path, texts[path], by_resolved) for path in files
    }
    imported = {target.resolve() for targets in edges.values() for target in targets}
    reached: set[Path] = set()
    groups: list[list[Path]] = []
    limit = max(64, len(files) * 8)

    def collect(root_path: Path) -> list[Path]:
        ordered: list[Path] = []
        visiting: set[Path] = set()

        def visit(path: Path) -> None:
            resolved = path.resolve()
            if resolved in visiting or len(ordered) >= limit:
                return
            visiting.add(resolved)
            for target in edges[path]:
                visit(target)
            visiting.remove(resolved)
            reached.add(resolved)
            ordered.append(path)

        visit(root_path)
        return ordered

    for path in files:
        if path.resolve() not in imported:
            groups.append(collect(path))
    for path in files:
        if path.resolve() not in reached:
            groups.append(collect(path))
    return groups


def _collect_theme_vars(
    body: str,
    colors: set[str],
    text_sizes: set[str],
    bg_images: set[str],
    cleared_families: set[str],
    cleared_colors: set[str],
    default_colors: bool,
) -> bool:
    """Populate token sets from one @theme body in cascade order."""
    for kind, token, raw_value in THEME_VAR.findall(body):
        value = raw_value.strip()
        if kind == "color" and value == "initial":
            if token == "*":
                default_colors = False
                colors.clear()
                cleared_families.clear()
                cleared_colors.clear()
            elif token.endswith("-*"):
                family = token[:-2]
                cleared_families.add(family)
                colors.difference_update(
                    {item for item in colors if item.startswith(f"{family}-")}
                )
            elif "*" not in token:
                cleared_colors.add(token)
                colors.discard(token)
        elif "*" in token or value == "initial":
            continue
        elif kind == "color":
            colors.add(token)
            cleared_colors.discard(token)
        elif kind == "text" and "--" not in token:
            text_sizes.add(token)
        elif kind == "background-image":
            bg_images.add(token)
    return default_colors


def _theme_for_group(texts: list[str]) -> tuple[ThemeTokens, bool]:
    colors: set[str] = set()
    text_sizes: set[str] = set()
    bg_images: set[str] = set()
    custom_classes: set[str] = set()
    custom_prefixes: set[str] = set()
    cleared_families: set[str] = set()
    cleared_colors: set[str] = set()
    default_colors = True
    has_theme = False
    for text in texts:
        utilities = UTILITY_DECL.findall(text)
        custom_prefixes.update(u[:-1] for u in utilities if u.endswith("*"))
        custom_classes.update(u for u in utilities if not u.endswith("*"))
        custom_classes.update(CLASS_SELECTOR.findall(text))
        for body in _theme_bodies(text):
            has_theme = True
            default_colors = _collect_theme_vars(
                body,
                colors,
                text_sizes,
                bg_images,
                cleared_families,
                cleared_colors,
                default_colors,
            )
    return (
        ThemeTokens(
            frozenset(colors),
            frozenset(text_sizes),
            frozenset(bg_images),
            frozenset(custom_classes),
            frozenset(custom_prefixes),
            default_colors,
            frozenset(cleared_families),
            frozenset(cleared_colors),
        ),
        has_theme,
    )


def _load_theme(
    root: Path, package: Path, entries: list[str] | None = None
) -> ThemeTokens | None:
    files = _css_files(root, package, entries)
    if not files:
        return None
    raw = {
        path: CSS_COMMENT.sub("", path.read_text(errors="replace")) for path in files
    }
    all_texts = list(raw.values())
    if not any(THEME_BLOCK.search(text) for text in all_texts) or _has_external_theme(
        package, all_texts
    ):
        return None
    evaluated = [
        _theme_for_group([raw[path] for path in group])
        for group in _css_entrypoint_orders(files, raw)
    ]
    all_tokens = [tokens for tokens, _ in evaluated]
    themed = [tokens for tokens, has_theme in evaluated if has_theme]
    with_defaults = [tokens for tokens in themed if tokens.default_colors]
    return ThemeTokens(
        frozenset().union(*(t.colors for t in all_tokens)),
        frozenset().union(*(t.text_sizes for t in all_tokens)),
        frozenset().union(*(t.bg_images for t in all_tokens)),
        frozenset().union(*(t.custom_classes for t in all_tokens)),
        frozenset().union(*(t.custom_prefixes for t in all_tokens)),
        bool(with_defaults),
        frozenset.intersection(*(t.cleared_families for t in with_defaults))
        if with_defaults
        else frozenset(),
        frozenset.intersection(*(t.cleared_colors for t in with_defaults))
        if with_defaults
        else frozenset(),
    )


def _strip_variants(token: str) -> str:
    depth = 0
    cut = -1
    for index, char in enumerate(token):
        if char in "[(":
            depth += 1
        elif char in "])":
            depth = max(depth - 1, 0)
        elif char == ":" and depth == 0:
            cut = index
    return token[cut + 1 :].lstrip("!-").rstrip("!")


def _is_known_color(value: str, theme: ThemeTokens) -> bool:
    if value in UNIVERSAL_COLORS or value in theme.colors:
        return True
    if not theme.default_colors or value in theme.cleared_colors:
        return False
    if value in DEFAULT_SOLIDS:
        return True
    family, sep, shade = value.rpartition("-")
    return bool(
        sep
        and family in DEFAULT_FAMILIES
        and family not in theme.cleared_families
        and shade in DEFAULT_SHADES
    )


def _valid_border(value: str, theme: ThemeTokens) -> bool:
    if (
        value in BUILTIN_BORDER
        or value.isdigit()
        or value.startswith(("spacing-", "opacity-"))
    ):
        return True
    side, sep, rest = value.partition("-")
    if sep and side in BORDER_SIDES:
        return rest.isdigit() or _is_known_color(rest, theme)
    return _is_known_color(value, theme)


def _valid_ring(value: str, theme: ThemeTokens) -> bool:
    if value in BUILTIN_RING or value.isdigit() or value.startswith("opacity-"):
        return True
    if value.startswith("offset-"):
        rest = value.removeprefix("offset-")
        return rest.isdigit() or _is_known_color(rest, theme)
    return _is_known_color(value, theme)


def _is_valid_utility(prefix: str, value: str, theme: ThemeTokens) -> bool:
    full = f"{prefix}-{value}"
    if full in theme.custom_classes or any(
        full.startswith(custom) for custom in theme.custom_prefixes
    ):
        return True
    if prefix == "text":
        return (
            value in BUILTIN_TEXT
            or value.startswith(("shadow-", "opacity-"))
            or value in theme.text_sizes
            or _is_known_color(value, theme)
        )
    if prefix == "bg":
        return (
            value in BUILTIN_BG
            or value.startswith(BUILTIN_BG_PREFIXES)
            or value in theme.bg_images
            or _is_known_color(value, theme)
        )
    if prefix == "border":
        return _valid_border(value, theme)
    if prefix == "ring":
        return _valid_ring(value, theme)
    if prefix == "fill":
        return value in BUILTIN_FILL or _is_known_color(value, theme)
    return value in BUILTIN_STROKE or value.isdigit() or _is_known_color(value, theme)


def _balanced_end(text: str, start: int, opener: str, closer: str) -> int:
    depth, index = 1, start
    while index < len(text) and depth:
        depth += (text[index] == opener) - (text[index] == closer)
        index += 1
    return index


def _mask_non_class_attrs(text: str, suffix: str) -> str:
    from source_scan import (
        blank_spans,
        code_without_comments,
        string_end,
        without_literals,
    )

    scan = (
        without_literals(f"x{suffix}", code_without_comments(text, suffix))
        if suffix in (".tsx", ".jsx")
        else text
    )
    spans: list[tuple[int, int]] = []
    pos = 0
    while match := NON_CLASS_ATTR_OPEN.search(scan, pos):
        start = match.end()
        if start >= len(text):
            break
        if text[start] in ('"', "'", "`"):
            end = string_end(text, start + 1, text[start], False)
            spans.append((start, end))
            pos = end
        elif text[start] == "{":
            end = _balanced_end(scan, start + 1, "{", "}")
            spans.append((start + 1, max(start + 1, end - 1)))
            pos = end
        else:
            pos = start
    return blank_spans(text, spans) if spans else text


def _apply_chunks_by_line(text: str) -> dict[int, list[str]]:
    masked = CSS_COMMENT.sub(lambda m: "\n" * m[0].count("\n"), text)
    by_line: dict[int, list[str]] = {}
    for match in APPLY_RULE.finditer(masked):
        line_no = masked.count("\n", 0, match.start(1)) + 1
        for offset, part in enumerate(match.group(1).split("\n")):
            if part.strip():
                by_line.setdefault(line_no + offset, []).append(part)
    return by_line


def _prop_expr_end(text: str, start: int) -> int:
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            if depth == 0:
                return index
            depth -= 1
        elif depth == 0 and char in ",;":
            return index
        elif depth == 0 and char == "\n":
            before = text[start:index].rstrip()
            after = text[index + 1 :].lstrip()
            if (not before or before[-1] not in "?:+&|=") and (
                not after or after[0] not in "?:+&|"
            ):
                return index
        index += 1
    return index


def _class_context_lines(text: str, suffix: str) -> set[int]:
    from source_scan import code_without_comments, string_end, without_literals

    code = code_without_comments(text, suffix)
    masked = without_literals(f"x{suffix}", code)
    lines = {
        number
        for number, line in enumerate(masked.splitlines(), 1)
        if SCRIPT_CLASS_CONTEXT.search(line)
    }
    for pattern, opener, closer in (
        (SCRIPT_CALL_OPEN, "(", ")"),
        (CLASS_ATTR_EXPR, "{", "}"),
    ):
        for match in pattern.finditer(masked):
            start_line = masked.count("\n", 0, match.start()) + 1
            end = _balanced_end(masked, match.end(), opener, closer)
            end_line = masked.count("\n", 0, end) + 1
            lines.update(range(start_line, end_line + 1))
    for match in CLASS_PROP_EXPR.finditer(masked):
        start_line = masked.count("\n", 0, match.start()) + 1
        end = _prop_expr_end(masked, match.end())
        end_line = masked.count("\n", 0, end) + 1
        lines.update(range(start_line, end_line + 1))
    for match in CLASS_TEMPLATE_ASSIGN.finditer(code):
        start_line = code.count("\n", 0, match.start()) + 1
        end = string_end(code, match.end(), "`", False)
        end_line = code.count("\n", 0, end) + 1
        lines.update(range(start_line, end_line + 1))
    return lines


def _mask_comparison_strings(text: str, suffix: str) -> str:
    from source_scan import blank_spans, code_without_comments

    code = (
        code_without_comments(text, suffix)
        if suffix in (".ts", ".js", ".tsx", ".jsx")
        else text
    )
    spans: list[tuple[int, int]] = []
    for match in STRING_TOKEN.finditer(code):
        before = code[max(0, match.start() - 64) : match.start()]
        after = code[match.end() : min(len(code), match.end() + 32)]
        if COMPARE_BEFORE.search(before) or COMPARE_AFTER.search(after):
            spans.append((match.start(), match.end()))
    return blank_spans(text, spans) if spans else text


def _multiline_template_chunks(
    text: str, suffix: str, allowed_lines: set[int]
) -> dict[int, list[str]]:
    from source_scan import scanned_spans

    by_line: dict[int, list[str]] = {}
    for comment, start, close, _ in scanned_spans(text, suffix):
        if comment:
            continue
        segment = text[start:close]
        if "\n" not in segment or not segment.startswith(("`", "}")):
            continue
        body = segment[1:]
        if segment.startswith("}"):
            body = "\x00 " + body
        if body.endswith("`"):
            body = body[:-1]
        elif body.endswith("${"):
            body = body[:-2] + " \x00"
        line_no = text.count("\n", 0, start) + 1
        for offset, part in enumerate(body.split("\n")):
            if part.strip() and (line_no + offset) in allowed_lines:
                by_line.setdefault(line_no + offset, []).append(part)
    return by_line


def _string_chunks(text: str) -> list[str]:
    chunks: list[str] = []
    for match in STRING_TOKEN.finditer(text):
        if COMPARE_BEFORE.search(text[: match.start()]) or COMPARE_AFTER.search(
            text[match.end() :]
        ):
            continue
        body = match.group(2)
        if match.group(1) == "`" and "${" in body:
            body = TEMPLATE_EXPR.sub(" \x00 ", body)
        chunks.append(body)
    return chunks


def _class_chunks(
    name: str,
    number: int,
    text: str,
    *,
    apply_lines: dict[int, list[str]] | None = None,
    script_lines: set[int] | None = None,
    masked_lines: list[str] | None = None,
    template_lines: dict[int, list[str]] | None = None,
) -> list[str]:
    if name.endswith(STYLE_TOKEN_SUFFIXES):
        return (
            apply_lines.get(number, [])
            if apply_lines is not None
            else APPLY_RULE.findall(text)
        )
    if name.endswith(SCRIPT_TOKEN_SUFFIXES):
        allowed = (
            number in script_lines
            if script_lines is not None
            else bool(SCRIPT_CLASS_CONTEXT.search(text))
        )
        if not allowed:
            return []
        line = (
            masked_lines[number - 1]
            if masked_lines is not None and 0 < number <= len(masked_lines)
            else text
        )
        extra = template_lines.get(number, []) if template_lines is not None else []
        return [*_string_chunks(line), *extra]
    if not name.endswith(MARKUP_TOKEN_SUFFIXES):
        return []
    line = (
        masked_lines[number - 1]
        if masked_lines is not None and 0 < number <= len(masked_lines)
        else _mask_non_class_attrs(text, PurePosixPath(name).suffix)
    )
    extra = template_lines.get(number, []) if template_lines is not None else []
    return [*_string_chunks(line), *extra]


def _undefined_tokens(chunks: list[str], theme: ThemeTokens) -> list[str]:
    bad: list[str] = []
    for chunk in chunks:
        parts = chunk.split()
        for index, raw in enumerate(parts):
            if "\x00" in raw:
                continue
            if (
                raw.endswith("-")
                and index + 1 < len(parts)
                and parts[index + 1] == "\x00"
            ):
                continue
            if raw.startswith(("/", "http://", "https://")) or raw.endswith(
                FILE_SUFFIXES
            ):
                continue
            utility = _strip_variants(raw)
            if "[" in utility or "(" in utility:
                continue
            core = utility.split("/", 1)[0]
            if "/" in utility and not core:
                continue
            matched = COLOR_CLASS.fullmatch(core)
            if matched and not _is_valid_utility(matched[1], matched[2], theme):
                bad.append(raw)
    return bad


def _file_token_context(
    name: str, file_text: str | None
) -> tuple[
    dict[int, list[str]] | None,
    set[int] | None,
    list[str] | None,
    dict[int, list[str]] | None,
]:
    if file_text is None:
        return None, None, None, None
    normalized = file_text.replace("\r\n", "\n").replace("\r", "\n")
    suffix = PurePosixPath(name).suffix
    if name.endswith(STYLE_TOKEN_SUFFIXES):
        return _apply_chunks_by_line(normalized), None, None, None
    if name.endswith(SCRIPT_TOKEN_SUFFIXES):
        allowed = _class_context_lines(normalized, suffix)
        masked = _mask_comparison_strings(normalized, suffix)
        return (
            None,
            allowed,
            masked.split("\n"),
            _multiline_template_chunks(masked, suffix, allowed),
        )
    if name.endswith(MARKUP_TOKEN_SUFFIXES):
        masked = _mask_comparison_strings(
            _mask_non_class_attrs(normalized, suffix), suffix
        )
        templates = (
            _multiline_template_chunks(
                masked, suffix, _class_context_lines(masked, suffix)
            )
            if suffix in (".tsx", ".jsx")
            else None
        )
        return None, None, masked.split("\n"), templates
    return None, None, None, None


def line_findings(
    name: str,
    lines: list[tuple[int, str]],
    theme: ThemeTokens | None = None,
    file_text: str | None = None,
) -> list[str]:
    """Findings for one file, from its path and lines alone: no process starts."""
    if name.startswith(UNOWNED) or is_test_path(PurePosixPath(name)):
        return []
    colours = None if is_theme_path(name) else colour_pattern(name)
    check_tokens = theme is not None and not is_theme_path(name)
    apply_lines, script_lines, masked_lines, template_lines = (
        _file_token_context(name, file_text)
        if check_tokens
        else (None, None, None, None)
    )
    found: list[str] = []
    for number, text in lines:
        if COMMENT_LINE.match(text):
            continue
        if TRANSITION_CLASS.search(text) or TRANSITION_STYLE.search(text):
            found.append(
                f"{name}:{number}: a transition on every property. {TRANSITION_STEP}"
            )
        elif colours is not None and (hit := colours.search(text)):
            found.append(
                f"{name}:{number}: a colour typed in the file ({hit[0].strip()}). {COLOUR_STEP}"
            )
        elif check_tokens and theme is not None:
            chunks = _class_chunks(
                name,
                number,
                text,
                apply_lines=apply_lines,
                script_lines=script_lines,
                masked_lines=masked_lines,
                template_lines=template_lines,
            )
            for token in _undefined_tokens(chunks, theme):
                found.append(
                    f"{name}:{number}: undefined Tailwind theme token ({token}). {TOKEN_STEP}"
                )
    return found


def ui_findings(root: Path, candidates: dict[str, list[tuple[int, str]]]) -> list[str]:
    """Findings for the marked lines of each UI file; only a file with a finding is looked up as generated."""
    from ui_audit_rules import JSX_SUFFIXES, audit_findings, duplicate_sibling_keys

    css_entries: list[str] | None = None
    themes: dict[Path, ThemeTokens | None] = {}
    found: dict[str, list[str]] = {}
    for name, lines in candidates.items():
        theme: ThemeTokens | None = None
        file_text: str | None = None
        if (
            not name.startswith(UNOWNED)
            and not is_test_path(PurePosixPath(name))
            and not is_theme_path(name)
            and name.endswith(
                (*MARKUP_TOKEN_SUFFIXES, *SCRIPT_TOKEN_SUFFIXES, *STYLE_TOKEN_SUFFIXES)
            )
        ):
            if css_entries is None:
                css_entries = _all_css_entries(root)
            package = _package_dir(root, name)
            if package not in themes:
                themes[package] = _load_theme(root, package, css_entries)
            theme = themes[package]
            if (theme is not None or name.endswith(JSX_SUFFIXES)) and (
                root / name
            ).is_file():
                file_text = (root / name).read_text(errors="replace")
        items = line_findings(name, lines, theme, file_text)
        if file_text is not None and name.endswith(JSX_SUFFIXES):
            items.extend(
                duplicate_sibling_keys(name, file_text, {num for num, _ in lines})
            )
        found[name] = items
    named = sorted(name for name, items in found.items() if items)
    skipped = generated_sources(root, named) if named else set()
    hits = [item for name in named if name not in skipped for item in found[name]]
    return [*hits, *audit_findings(root, candidates, css_entries)]
