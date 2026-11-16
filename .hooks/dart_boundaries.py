"""Read a Dart package's Dart Decimate boundary rules and refuse unusable ones."""

import json
import os
import subprocess
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, TypedDict, cast
from urllib.parse import unquote, urljoin, urlparse

from gate_config import generated_sources
from project_files import GIT_LISTING

if TYPE_CHECKING:
    from gate_config import Group, JsonObject

SETTINGS_FILES = (
    ".dart-decimaterc",
    ".dart-decimaterc.json",
    ".dart-decimaterc.jsonc",
    "dart-decimate.toml",
    ".dart-decimate.toml",
)

DartAnalyzer = TypedDict(
    "DartAnalyzer",
    {"exclude": list[str], "errors": dict[str, str], "language": dict[str, bool]},
    total=False,
)
DartLinter = TypedDict(
    "DartLinter", {"rules": dict[str, bool] | list[str]}, total=False
)
DartOptions = TypedDict(
    "DartOptions",
    {"include": str | list[str], "analyzer": DartAnalyzer, "linter": DartLinter},
    total=False,
)

DART_TYPING: dict[str, dict[str, dict[str, bool] | list[str]]] = {
    "analyzer": {
        "exclude": [],
        "language": {
            "strict-inference": True,
        },
    },
    "linter": {
        "rules": {
            "no_dynamic_casts": True,
            "no_raw_types": True,
            "avoid_annotating_with_dynamic": True,
            "avoid_dynamic_calls": True,
            "strict_top_level_inference": True,
            "unawaited_futures": True,
        }
    },
}


def dart_rule_settings(value: object) -> object:
    if isinstance(value, list):
        if not all(isinstance(rule, str) for rule in value):
            raise ValueError("Dart lint rule names must be strings")
        return {rule: True for rule in value}
    if isinstance(value, dict):
        for rule, enabled in value.items():
            if enabled is False:
                raise ValueError(
                    f"analysis_options.yaml: {rule} is set to false, which turns off "
                    "a lint rule of the included set; remove that entry"
                )
    return value


def merge_options(base: object, over: object) -> object:
    """Later settings win; lint rule lists count as maps so a rule set to false shows."""
    if not isinstance(base, dict) or not isinstance(over, dict):
        return over
    merged = dict(base)
    for key, value in over.items():
        if key == "rules" and isinstance(value, (list, dict)):
            value = {**listed_rules(base.get(key)), **listed_rules(value)}
        merged[key] = merge_options(base.get(key), value) if key in base else value
    return merged


def listed_rules(value: object) -> dict[str, object]:
    if isinstance(value, list):
        return {rule: True for rule in value if isinstance(rule, str)}
    return dict(value) if isinstance(value, dict) else {}


def nested_options(
    path: Path, root_file: Path, seen: frozenset[Path] = frozenset()
) -> object | None:
    """The settings of a nested file merged over what its relative include chain reaches; None when the chain misses the package's own file."""
    own = dart_options(path)
    includes = own.get("include", [])
    for include in [includes] if isinstance(includes, str) else includes:
        target = (path.parent / include).resolve()
        if include.startswith("package:") or target in seen | {path.resolve()}:
            continue
        if target == root_file.resolve():
            return merge_options(dart_options(root_file), own)
        if (
            target.is_file()
            and (base := nested_options(target, root_file, seen | {path.resolve()}))
            is not None
        ):
            return merge_options(base, own)
    return None


def validate_dart_plugins(options: "JsonObject") -> None:
    from project_setup import migrate_dart_plugins

    plugins = options.get("plugins")
    if not isinstance(plugins, dict):
        return
    migrated = dict(plugins)
    updated: JsonObject = {"plugins": migrated}
    migrate_dart_plugins(updated, Path(__file__).resolve().parents[1])
    if updated["plugins"] != plugins:
        versions = {
            name: value.get("version") if isinstance(value, dict) else value
            for name, value in plugins.items()
        }
        changes = ", ".join(
            f"{name}: {versions[name]} -> {value.get('version') if isinstance(value, dict) else value}"
            for name, value in migrated.items()
            if value != plugins.get(name)
        )
        raise ValueError(
            f"Analyzer plugin version is older than the installed canonical profile ({changes}); run the supported Hard Eng updater and verify application compatibility"
        )


def dart_options(path: Path) -> DartOptions:
    try:
        import yaml
    except ImportError as error:
        raise ValueError(
            "Dart configuration checks require PyYAML in the Python environment"
        ) from error
    try:
        options = yaml.safe_load(path.read_text())
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid Dart analysis settings: {path}") from error
    if not isinstance(options, dict):
        raise TypeError(f"Dart analysis settings must be a mapping: {path}")
    return cast(DartOptions, options)


def nested_package_patterns(
    group: "Group", groups: "list[Group]", role: str = "types"
) -> frozenset[str]:
    from dependency_graph import child_groups

    return frozenset(
        f"{PurePosixPath(child['path']).relative_to(group['path'])}/**"
        for child in child_groups(group, role, groups)
    )


def localization_file(options: object) -> PurePosixPath | None:
    """The main file that gen-l10n writes, relative to its package."""
    if not isinstance(options, dict) or options.get("synthetic-package", False):
        return None
    folder = options.get("output-dir", options.get("arb-dir", "lib/l10n"))
    name = options.get("output-localization-file", "app_localizations.dart")
    return PurePosixPath(str(folder), PurePosixPath(str(name)).name)


def localization_exclusions(directory: Path) -> frozenset[str]:
    """Flutter 3.50's gen-l10n lists deprecated delegates in its main file (flutter/flutter#191072)."""
    path = directory / "l10n.yaml"
    if not path.is_file():
        return frozenset()
    import yaml

    try:
        main = localization_file(yaml.safe_load(path.read_text()) or {})
    except yaml.YAMLError:
        return frozenset()
    if main is None or main.is_absolute() or ".." in main.parts:
        return frozenset()
    return frozenset({main.as_posix()})


def add_exclusions(options: "JsonObject", patterns: frozenset[str]) -> None:
    if patterns:
        analyzer = cast("JsonObject", options.setdefault("analyzer", {}))
        exclude = cast("list[str]", analyzer.setdefault("exclude", []))
        exclude.extend(sorted(patterns - set(exclude)))


def excludes_here(directory: Path, pattern: str) -> bool:
    """Whether a pattern from an included file matches a path here; the analyzer applies it from this folder. Python glob expands no braces and no partial `**`, so those count as a match."""
    if "{" in pattern or "}" in pattern:
        return True
    if any("**" in part and part != "**" for part in pattern.split("/")):
        return True
    folder = pattern.rstrip("/").removesuffix("/**").rstrip("/")
    try:
        return any(
            next(directory.glob(form), None) is not None for form in {pattern, folder}
        )
    except (ValueError, NotImplementedError):
        return True


def validate_dart_exclusions(
    directory: Path,
    values: object,
    children: frozenset[str] = frozenset(),
    holder: Path | None = None,
    origin: Path | None = None,
) -> None:
    """Refuse excludes of project files; holder is the file that writes them, and a holder in a parent folder is that folder's own options, included here. An inherited pattern is judged from origin, the folder of the options file the analyzer reads."""
    from project_setup import FLUTTER_PLATFORM_ROOTS, dependency_command

    allowed = {
        ".dart_tool/**",
        "**/*.g.dart",
        "**/*.freezed.dart",
        "**/*.gr.dart",
        "**/*.arb",
    }
    flutter = (directory / "pubspec.yaml").is_file() and dependency_command(
        directory, "dart"
    )[0] == "flutter"
    native = {"build/**"} if flutter else set()
    native.update(
        f"{root}/**"
        for root in FLUTTER_PLATFORM_ROOTS
        if flutter and (directory / root).is_dir()
    )
    options = holder or directory / "analysis_options.yaml"
    inherited = options.resolve().parent in directory.resolve().parents
    if not isinstance(values, list):
        raise TypeError(f"exclude in {options} must be a list of patterns")
    known = allowed | native | children
    if not known.issuperset(value for value in values if isinstance(value, str)):
        known |= localization_exclusions(directory)
    refused = [
        value
        for value in values
        if not isinstance(value, str)
        or (
            value not in known
            and (not inherited or excludes_here(origin or directory, value))
        )
    ]
    if refused:
        raise ValueError(
            "Dart strict analysis cannot exclude project files: remove "
            f"{', '.join(repr(value) for value in refused)} from exclude in {options}"
        )
    roots = {pattern.split("/", 1)[0] for pattern in set(values) & native}
    matches = {
        path
        for pattern in set(values) - native - children - {".dart_tool/**"}
        for path in (origin or directory if inherited else directory).glob(pattern)
        if path.relative_to(directory).parts[0] not in roots
    }
    if roots:
        listing = [*GIT_LISTING, "ls-files", "-zco", "--exclude-standard", "--"]
        names = subprocess.check_output(
            [*listing, *sorted(roots)], cwd=directory, text=True
        ).split("\0")
        matches.update(
            directory / name
            for name in names
            if name
            and (Path(name).suffix == ".dart" or (directory / name).is_symlink())
        )
    names = [str(path.relative_to(directory)) for path in matches]
    generated = generated_sources(directory, names)
    for path in matches:
        relative = path.relative_to(directory)
        if ".dart_tool/**" in values and relative.parts[0] == ".dart_tool":
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Dart generated exclusion matches an unsafe path: {path}")
        if path.suffix != ".dart" or str(relative) in generated:
            continue
        with path.open("rb") as source:
            header = source.read(2048).splitlines()[:10]
        if b"// GENERATED CODE - DO NOT MODIFY BY HAND" not in header:
            raise ValueError(f"Dart exclusion matches handwritten source: {path}")


def validate_dart_includes(
    path: Path,
    directory: Path,
    seen: set[Path] | None = None,
    packaged: bool = False,
    children: frozenset[str] = frozenset(),
    origin: Path | None = None,
) -> None:
    seen = set() if seen is None else seen
    path = path.resolve()
    origin = origin or path.parent
    if path in seen:
        raise ValueError(f"Recursive Dart analysis include: {path}")
    seen.add(path)
    from gate_config import JsonObject

    options = dart_options(path)

    validate_dart_plugins(cast(JsonObject, options))
    analyzer = options.get("analyzer", {})
    if {"strict-casts", "strict-raw-types"} & analyzer.get("language", {}).keys():
        raise ValueError(
            f"Remove obsolete Dart language flags; use no_dynamic_casts and no_raw_types: {path}"
        )
    validate_dart_exclusions(
        directory,
        analyzer.get("exclude", []),
        children,
        path,
        origin,
    )
    if any(value == "ignore" for value in analyzer.get("errors", {}).values()):
        raise ValueError(
            f"Dart strict analysis cannot exclude files or ignore diagnostics: {path}"
        )
    includes = options.get("include", [])
    for include in [includes] if isinstance(includes, str) else includes:
        if include.startswith("package:"):
            name, relative = include.removeprefix("package:").split("/", 1)
            registry = directory / ".dart_tool/package_config.json"
            packages = json.loads(registry.read_text())["packages"]
            package = next((item for item in packages if item["name"] == name), None)
            if package is None:
                raise ValueError(f"Unresolved Dart analysis include: {include}")
            uri = urljoin(
                urljoin(registry.as_uri(), package["rootUri"]).rstrip("/") + "/",
                package.get("packageUri", "lib/"),
            )
            uri = urlparse(urljoin(uri, relative))
            if uri.scheme != "file":
                raise ValueError(f"Unsupported Dart analysis include: {include}")
            included = Path(unquote(uri.path))
        else:
            included = path.parent / include
        package = include.startswith("package:")
        try:
            validate_dart_includes(
                included, directory, seen.copy(), packaged or package, children, origin
            )
        except ValueError as error:
            if packaged or not package:
                raise
            raise ValueError(
                f"{error}. A package file cannot be changed: remove `include: {include}` "
                f"from {path} and list the lint rules that you need there"
            ) from error


def pubspec_lines(directory: Path) -> list[str]:
    pubspec = directory / "pubspec.yaml"
    return pubspec.read_text().splitlines() if pubspec.is_file() else []


def flutter_package(directory: Path) -> bool:
    return any(line.split() == ["sdk:", "flutter"] for line in pubspec_lines(directory))


def flutter_without_test(directory: Path) -> bool:
    """A Flutter project that does not list `test` cannot run its outside-lib tests on the Dart VM."""
    return flutter_package(directory) and not any(
        line.split(":")[0].strip() == "test" for line in pubspec_lines(directory)
    )


def require_flutter_skill_lints(
    options: DartOptions, path: Path, package_root: Path | None
) -> None:
    if package_root not in (None, path.parent) or not flutter_package(path.parent):
        return
    plugins = cast("JsonObject", options).get("plugins")
    if not isinstance(plugins, dict) or "flutter_skill_lints" not in plugins:
        raise ValueError(
            f"A Flutter package needs the flutter_skill_lints plugin, which holds the Flutter rules: add it under `plugins` in {path}, "
            "as .agents/skills/building-flutter-apps/references/analysis_options.yaml lists it"
        )


def has_dart_file(directory: Path, prefix: str) -> bool:
    """Looks only below the prefix: this runs in every check, and a walk of all of lib/ is slow."""
    parent, _, start = prefix.rpartition("/")
    folder = directory / parent
    return folder.is_dir() and any(
        entry.suffix == ".dart"
        if entry.is_file()
        else next(entry.rglob("*.dart"), None) is not None
        for entry in folder.iterdir()
        if entry.name.startswith(start)
    )


def validate_dart_boundaries(
    command: list[str], directory: Path, timeout: float
) -> None:
    if command[:3] != ["dart-decimate", "check", "."]:
        return
    from tool_setup import managed_command

    try:
        output = subprocess.check_output(
            managed_command(["dart-decimate", "config", ".", "--format", "json"]),
            cwd=directory,
            text=True,
            timeout=timeout,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as error:
        lines = (error.stderr or error.output or "").strip().splitlines()
        raise ValueError(
            f"{directory.name}: dart-decimate config failed: " + " ".join(lines[-3:])
        ) from error
    settings = json.loads(output)["config"]
    boundaries = settings.get("boundaries")
    if (
        not isinstance(boundaries, list)
        or not boundaries
        or any(
            not isinstance(rule, dict)
            or not all(
                isinstance(rule.get(key), str)
                and rule[key].strip()
                and not any(mark in rule[key] for mark in "*?")
                for key in ("from", "disallow")
            )
            for rule in boundaries
        )
    ):
        raise ValueError(
            "Dart boundaries are missing or not usable: each rule needs a `from` and a "
            "`disallow` folder prefix of this project, with no `*` or `?`. Set "
            '"boundaries": [{"from": "lib/domain", "disallow": "lib/ui"}] with your own '
            "prefixes in the package's Dart Decimate settings file; if the package "
            "has none, make .dart-decimaterc.json for it"
        )
    settings_file = next(
        (name for name in SETTINGS_FILES if (directory / name).exists()),
        "the Dart Decimate settings file",
    )
    for rule in boundaries:
        for prefix in (rule["from"], rule["disallow"]):
            if not has_dart_file(directory, prefix):
                raise ValueError(
                    f"{directory.name}: the boundary prefix {prefix} in {settings_file} "
                    "matches no .dart file; correct the prefix or remove the rule"
                )
    validate_crap_limit(settings, f"{directory.name}: {settings_file}")


def validate_crap_limit(settings: "JsonObject", where: str) -> None:
    from fallow_report import HEALTH_LIMITS

    max_crap = HEALTH_LIMITS["max_crap_threshold"]
    health = settings.get("health")
    limit = health.get("max_crap") if isinstance(health, dict) else None
    if type(limit) is not int or not 1 <= limit <= max_crap:
        raise ValueError(
            f'{where}: Dart Decimate must fail the CRAP scores that Fallow fails. Set "health": '
            f'{{"max_crap": {max_crap}}} in that file: from release 0.0.76 it fails a score equal '
            "to its limit, so 30 matches the limit that Fallow uses"
        )


def typing_options(
    path: Path, directory: Path, package_root: Path | None
) -> DartOptions:
    """A nested file is judged by its settings merged over the package's own file."""
    if package_root is None or package_root == directory:
        return dart_options(path)
    root_file = package_root / "analysis_options.yaml"
    merged = nested_options(path, root_file)
    if merged is None:
        link = os.path.relpath(root_file, directory)
        raise ValueError(
            f"A nested Dart settings file must include the package settings: {path}. "
            f"Add `include: {link}` to it, or remove the file"
        )
    return cast(DartOptions, merged)


def validate_dart_typing(
    directory: Path,
    sources: list[str] | tuple[str, ...],
    package_root: Path | None,
    children: frozenset[str] = frozenset(),
) -> None:
    from gate_config import JsonObject

    path = directory / "analysis_options.yaml"
    options = typing_options(path, directory, package_root)
    where = f": {path}"
    for section, groups in DART_TYPING.items():
        for group, settings in groups.items():
            section_options = cast(JsonObject, options).get(section)
            if not isinstance(section_options, dict):
                raise TypeError(f"Dart requires {section} settings{where}")
            actual = section_options.get(group)
            if group == "rules":
                actual = dart_rule_settings(actual)
            if isinstance(settings, list):
                validate_dart_exclusions(
                    directory, section_options.get(group, []), children
                )
                continue
            if not isinstance(actual, dict) or any(
                actual.get(key) != value for key, value in settings.items()
            ):
                raise ValueError(
                    f"Dart requires strict {section}.{group} settings{where}"
                )
    validate_dart_includes(path, package_root or directory, children=children)
    require_flutter_skill_lints(options, path, package_root)
    for source in {*sources, "test", "tests"}:
        for nested in (directory / source).rglob("analysis_options.yaml"):
            if nested.parent != directory:
                validate_dart_typing(nested.parent, (), package_root or directory)
