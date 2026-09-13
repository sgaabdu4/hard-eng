"""Native Dart syntax proof must not hide executable or malformed libraries."""

import subprocess
from pathlib import Path

import pytest
from dart_coverage import erased_dart
from reports import line_coverage


def test_native_dart_declarations_and_runtime_controls(tmp_path: Path) -> None:
    (tmp_path / "pubspec.yaml").write_text(
        "name: coverage_classifier_fixture\n"
        "environment:\n  sdk: '>=3.11.0 <4.0.0'\n"
        "dev_dependencies:\n  analyzer: ^14.4.0\n"
    )
    subprocess.run(
        ["dart", "pub", "get"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
        timeout=90,
    )
    sources = {
        "barrel.dart": "/* outer /* nested */ comment */ library;\n"
        "export 'runtime.dart' show call;\n",
        "constants.dart": "const int answer = 42;\n"
        "abstract final class Values { static const label = 'value'; }\n"
        "typedef Mapper = String Function(int value);\nenum Choice { yes, no }\n",
        "runtime.dart": "int call() => 1;\n",
        "getter.dart": "int get value => 1;\n",
        "initializer.dart": "final value = DateTime.now();\n",
        "late.dart": "late final value = DateTime.now();\n",
        "method.dart": "abstract final class Values { static int call() => 1; }\n",
        "constructor.dart": "class Value { const Value(); }\n",
        "enum_method.dart": "enum Choice { yes; int call() => 1; }\n",
        "malformed.dart": "const int value = ;\n",
        "comment_trick.dart": "/* before */ int call() => 1; /* after */\n",
    }
    for name, source in sources.items():
        (tmp_path / name).write_text(source)
    expected = {tmp_path / name for name in sources}
    erased = erased_dart(expected, tmp_path)
    assert {path.name for path in erased} == {"barrel.dart", "constants.dart"}
    report = tmp_path / "lcov.info"
    report.write_text("SF:runtime.dart\nDA:1,1\nend_of_record\n")
    assert line_coverage(
        report, "dart-tests", tmp_path, erased | {tmp_path / "runtime.dart"}
    ) == (1, 1)
    with pytest.raises(ValueError, match="omits production files"):
        line_coverage(report, "dart-tests", tmp_path, expected)
    with pytest.raises(ValueError, match="no executable lines"):
        line_coverage(report, "dart-tests", tmp_path, erased)


def test_missing_dart_parser_keeps_sources_required(tmp_path: Path) -> None:
    source = tmp_path / "constants.dart"
    source.write_text("const answer = 42;\n")
    assert erased_dart({source}, tmp_path) == set()
    registry = tmp_path / ".dart_tool/package_config.json"
    registry.parent.mkdir()
    registry.write_text('{"configVersion":2,"packages":[]}')
    assert erased_dart({source}, tmp_path) == set()
