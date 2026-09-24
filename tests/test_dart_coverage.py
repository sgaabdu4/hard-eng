"""Native Dart syntax proof must not hide executable or malformed libraries."""

import subprocess
from pathlib import Path

import pytest
from dart_coverage import erased_dart
from reports import lcov_coverage, line_coverage


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
        "interface.dart": "abstract interface class Store { Future<int> read(); "
        "int get count; set count(int value); }\n",
        "abstract_contract.dart": "abstract class Store implements Reader { "
        "Future<int> read({required int page}); }\n",
        "redirecting_factory.dart": "@freezed\n"
        "sealed class State with _$State { const factory State({"
        "@Default(false) bool enabled}) = _State; }\n",
        "interface_method.dart": "abstract interface class Store { int read() => 1; }\n",
        "interface_field.dart": "abstract interface class Store { "
        "static final created = DateTime.now(); }\n",
        "interface_constructor.dart": "abstract interface class Store { "
        "Store() { print('created'); } }\n",
        "default_parameter.dart": "abstract class Store { int read([int page = 1]); "
        "Future<void> clear({bool files = false}); }\n",
        "default_body.dart": "abstract class Store { "
        "int read([int page = 1]) => page; }\n",
        "factory_body.dart": "abstract class Store { factory Store() { throw ''; } }\n",
        "factory_expression.dart": "abstract class Store { "
        "factory Store() => throw ''; }\n",
        "generative_constructor.dart": "abstract class Store { const Store(); }\n",
        "annotated_runtime.dart": "@freezed sealed class State { int run() => 1; }\n",
        "concrete_interface.dart": "interface class Store {}\n",
        "runtime.dart": "int call() => 1;\n",
        "getter.dart": "int get value => 1;\n",
        "initializer.dart": "final value = DateTime.now();\n",
        "late.dart": "late final value = DateTime.now();\n",
        "method.dart": "abstract final class Values { static int call() => 1; }\n",
        "constructor.dart": "class Value { const Value(); }\n",
        "enum_method.dart": "enum Choice { yes; int call() => 1; }\n",
        "enum_field.dart": "enum Shift { am('Morning'); "
        "const Shift(this.label); final String label; }\n",
        "enum_default.dart": "enum Level { low, high(2); "
        "const Level([this.value = 1]) : assert(value > 0); final int value; "
        "static const first = low; }\n",
        "enum_getter.dart": "enum Shift { am('Morning'); "
        "const Shift(this.label); final String label; "
        "String get upper => label.toUpperCase(); }\n",
        "enum_static_final.dart": "enum Choice { yes; "
        "static final created = DateTime.now(); }\n",
        "malformed.dart": "const int value = ;\n",
        "comment_trick.dart": "/* before */ int call() => 1; /* after */\n",
    }
    for name, source in sources.items():
        (tmp_path / name).write_text(source)
    expected = {tmp_path / name for name in sources}
    erased = erased_dart(expected, tmp_path)
    assert {path.name for path in erased} == {
        "barrel.dart",
        "constants.dart",
        "interface.dart",
        "abstract_contract.dart",
        "redirecting_factory.dart",
        "default_parameter.dart",
        "enum_field.dart",
        "enum_default.dart",
    }
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


def test_native_dart_lcov_omits_declaration_only_libraries(tmp_path: Path) -> None:
    (tmp_path / "pubspec.yaml").write_text(
        "name: native_dart_coverage_fixture\n"
        "environment:\n  sdk: '>=3.11.0 <4.0.0'\n"
        "dev_dependencies:\n"
        "  analyzer: ^14.4.0\n"
        "  coverage: ^1.15.0\n"
        "  test: ^1.29.0\n"
    )
    library = tmp_path / "lib"
    library.mkdir()
    (library / "contract.dart").write_text(
        "abstract class Reader {}\n"
        "abstract class Contract implements Reader {\n"
        "  int read();\n"
        "  int page([int value = 1, Duration wait = const Duration(seconds: 1)]);\n"
        "  List<bool> clear({bool files = false});\n"
        "}\n"
    )
    (library / "runtime_contract.dart").write_text(
        "import 'contract.dart';\n"
        "final class RuntimeContract implements Contract {\n"
        "  @override\n"
        "  int read() => 2;\n"
        "  @override\n"
        "  int page([int value = 1, Duration wait = const Duration(seconds: 1)]) =>\n"
        "      value;\n"
        "  @override\n"
        "  List<bool> clear({bool files = false}) => [files];\n"
        "}\n"
    )
    (library / "state.dart").write_text(
        "part 'state.freezed.dart';\n"
        "sealed class State { const factory State({bool enabled}) = _State; }\n"
    )
    (library / "state.freezed.dart").write_text(
        "part of 'state.dart';\n"
        "final class _State implements State {\n"
        "  const _State({this.enabled = false});\n"
        "  final bool enabled;\n"
        "}\n"
    )
    (library / "shift.dart").write_text(
        "enum Shift {\n"
        "  am('Morning');\n"
        "  const Shift(this.label);\n"
        "  final String label;\n"
        "}\n"
    )
    (library / "runtime.dart").write_text("int run() => 1;\n")
    (library / "uncovered.dart").write_text("int uncalled() => 3;\n")
    tests = tmp_path / "test"
    tests.mkdir()
    (tests / "coverage_test.dart").write_text(
        "import 'package:native_dart_coverage_fixture/contract.dart';\n"
        "import 'package:native_dart_coverage_fixture/runtime.dart';\n"
        "import 'package:native_dart_coverage_fixture/runtime_contract.dart';\n"
        "import 'package:native_dart_coverage_fixture/shift.dart';\n"
        "import 'package:native_dart_coverage_fixture/state.dart';\n"
        "import 'package:native_dart_coverage_fixture/uncovered.dart';\n"
        "import 'package:test/test.dart';\n"
        "void main() {\n"
        "  test('runs declaration consumers', () {\n"
        "    final Contract contract = RuntimeContract();\n"
        "    expect(contract.read(), 2);\n"
        "    expect([contract.page(), contract.page(3)], [1, 3]);\n"
        "    expect([contract.clear(), contract.clear(files: true)], [\n"
        "      [false],\n"
        "      [true],\n"
        "    ]);\n"
        "    expect(State(enabled: true), isA<State>());\n"
        "    expect(Shift.am.label, 'Morning');\n"
        "    expect(run(), 1);\n"
        "    expect(uncalled, isA<Function>());\n"
        "  });\n"
        "}\n"
    )
    subprocess.run(
        ["dart", "pub", "get"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
        timeout=90,
    )
    subprocess.run(
        ["dart", "test", "--coverage=coverage"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
        timeout=90,
    )
    report = tmp_path / "lcov.info"
    subprocess.run(
        [
            "dart",
            "run",
            "coverage:format_coverage",
            "--lcov",
            "--in=coverage",
            f"--out={report}",
            "--packages=.dart_tool/package_config.json",
            "--report-on=lib",
        ],
        cwd=tmp_path,
        capture_output=True,
        check=True,
        timeout=90,
    )
    expected = {
        library / name
        for name in (
            "contract.dart",
            "state.dart",
            "shift.dart",
            "runtime.dart",
            "uncovered.dart",
        )
    }
    assert {path.name for path in erased_dart(expected, tmp_path)} == {
        "contract.dart",
        "state.dart",
        "shift.dart",
    }
    native = lcov_coverage(report, tmp_path)
    assert library / "contract.dart" not in native
    assert library / "state.dart" not in native
    assert library / "shift.dart" not in native
    assert native[library / "runtime_contract.dart"] == (4, 4)
    assert native[library / "runtime.dart"] == (1, 1)
    assert native[library / "uncovered.dart"] == (0, 1)
    assert line_coverage(report, "dart-tests", tmp_path, expected) == (1, 2)
