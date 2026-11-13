"""Exclude the main gen-l10n file from Dart analysis, and nothing else near it."""

from pathlib import Path
from types import ModuleType

import pytest
import yaml
from gate_config import Group
from project_setup import validate_dart_exclusions

CUSTOM_L10N = "output-dir: lib/gen\noutput-localization-file: texts.dart\n"


@pytest.mark.parametrize(
    ("settings", "pattern", "marked", "refusal"),
    [
        ("", "lib/l10n/app_localizations.dart", True, None),
        (CUSTOM_L10N, "lib/gen/texts.dart", True, None),
        ("", "lib/l10n/app_localizations_en.dart", True, "cannot exclude project"),
        ("", "lib/l10n/helpers.dart", True, "cannot exclude project"),
        ("", "lib/l10n/**", True, "cannot exclude project"),
        (
            CUSTOM_L10N,
            "lib/l10n/app_localizations.dart",
            True,
            "cannot exclude project",
        ),
        (None, "lib/l10n/app_localizations.dart", True, "cannot exclude project"),
        ("", "lib/l10n/app_localizations.dart", False, "handwritten source"),
    ],
)
def test_dart_exclusions_accept_only_the_main_localization_file(
    runner: ModuleType,
    tmp_path: Path,
    settings: str | None,
    pattern: str,
    marked: bool,
    refusal: str | None,
) -> None:
    """Flutter 3.50 writes deprecated delegates into the main gen-l10n file, so only that file, marked generated, is excluded."""
    for name in ("l10n/app_localizations.dart", "l10n/app_localizations_en.dart"):
        (tmp_path / "lib" / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "lib" / name).write_text("class AppLocalizations {}\n")
    (tmp_path / "lib/l10n/helpers.dart").write_text("void important() {}\n")
    (tmp_path / "lib/gen").mkdir()
    (tmp_path / "lib/gen/texts.dart").write_text("class AppLocalizations {}\n")
    if settings is not None:
        (tmp_path / "l10n.yaml").write_text(settings)
    if marked:
        (tmp_path / ".gitattributes").write_text(f"{pattern} linguist-generated\n")
    if refusal is None:
        validate_dart_exclusions(tmp_path, [pattern])
        return
    with pytest.raises(ValueError, match=refusal):
        validate_dart_exclusions(tmp_path, [pattern])


@pytest.mark.parametrize(
    ("folder", "settings", "expected"),
    [
        (".", "", "lib/l10n/app_localizations.dart"),
        ("packages/ui", CUSTOM_L10N, "lib/gen/texts.dart"),
    ],
)
def test_dart_setup_excludes_the_main_localization_file_and_its_own_check_accepts_it(
    installer: ModuleType,
    runner: ModuleType,
    tmp_path: Path,
    folder: str,
    settings: str,
    expected: str,
) -> None:
    directory = tmp_path / folder
    (directory / expected).parent.mkdir(parents=True)
    (directory / expected).write_text("class AppLocalizations {}\n")
    (directory / "pubspec.yaml").write_text("name: app\n")
    (directory / "l10n.yaml").write_text(settings)
    package: Group = {"path": folder, "checks": []}
    changes: dict[str, str] = {}
    installer.configure_dart(tmp_path, directory, package, changes)
    for name, content in changes.items():
        (tmp_path / name).write_text(content)
    options = yaml.safe_load((directory / "analysis_options.yaml").read_text())
    assert options["analyzer"]["exclude"] == [expected]
    runner.validate_typing(directory, "dart", ["lib"])
    repeated: dict[str, str] = {}
    installer.configure_dart(tmp_path, directory, package, repeated)
    assert not {"analysis_options.yaml", ".gitattributes"} & repeated.keys()
