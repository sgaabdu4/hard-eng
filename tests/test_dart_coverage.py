"""Native Dart syntax proof must not hide executable or malformed libraries."""

import subprocess
from pathlib import Path

import pytest
from dart_coverage import erased_dart
from gate_config import Group
from project_setup import (
    BROWSER_TESTS,
    DART_TESTS,
    FLUTTER_TESTS,
    browser_test_coverage,
    outside_lib_coverage,
)
from reports import completed_tests, lcov_coverage, line_coverage


def test_native_dart_declarations_and_runtime_controls(tmp_path: Path) -> None:
    (tmp_path / "pubspec.yaml").write_text(
        "name: coverage_classifier_fixture\n"
        "environment:\n  sdk: '>=3.11.0 <4.0.0'\n"
        "dev_dependencies:\n  analyzer: 12.1.0\n"
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
    assert (
        '"name": "analyzer"'
        in (tmp_path / ".dart_tool/package_config.json").read_text()
    )
    erased = erased_dart(expected)
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


def test_missing_dart_parser_keeps_sources_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = tmp_path / ".dart_tool/package_config.json"
    registry.parent.mkdir()
    registry.write_text('{"configVersion":2,"packages":[]}')
    declarations = tmp_path / "constants.dart"
    declarations.write_text("const answer = 42;\n")
    runtime = tmp_path / "runtime.dart"
    runtime.write_text("int call() => 1;\n")
    report = tmp_path / "lcov.info"
    report.write_text("SF:covered.dart\nDA:1,1\nend_of_record\n")
    expected = {declarations, runtime, tmp_path / "covered.dart"}
    with pytest.raises(ValueError, match="omits production files: runtime.dart\\."):
        line_coverage(report, "dart-tests", tmp_path, expected)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    with pytest.raises(ValueError, match="classifier failed at `dart pub get") as error:
        line_coverage(report, "dart-tests", tmp_path, expected)
    assert "linguist-generated" not in str(error.value)


def test_native_dart_lcov_omits_declaration_only_libraries(tmp_path: Path) -> None:
    (tmp_path / "pubspec.yaml").write_text(
        "name: native_dart_coverage_fixture\n"
        "environment:\n  sdk: '>=3.11.0 <4.0.0'\n"
        "dev_dependencies:\n"
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
    assert {path.name for path in erased_dart(expected)} == {
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


def dart_tests(sources: list[str], command: list[str]) -> Group:
    package: Group = {
        "path": ".",
        "language": "dart",
        "sources": sources,
        "checks": [{"name": "tests", "role": "tests", "command": list(command)}],
    }
    outside_lib_coverage(package)
    return package


def test_only_generated_flutter_commands_gain_dart_vm_coverage(tmp_path: Path) -> None:
    lib_only = dart_tests(["lib"], FLUTTER_TESTS)
    assert lib_only["checks"][0]["command"] == FLUTTER_TESTS
    custom = ["sh", "-c", "custom"]
    assert dart_tests(["lib", "scripts"], custom)["checks"][0]["command"] == custom
    for previous in (BROWSER_TESTS, FLUTTER_TESTS):
        package = dart_tests(["lib", "scripts"], previous)
        command = package["checks"][0]["command"]
        assert command[:2] == ["sh", "-c"] and "--report-on=scripts" in command[2]
        outside_lib_coverage(package)
        browser_test_coverage(tmp_path, package)
        assert package["checks"][0]["command"] == command
    browser = dart_tests(["lib", "scripts"], BROWSER_TESTS)["checks"][0]["command"]
    vm_step = browser[2].index("dart test --coverage=coverage/vm")
    assert vm_step < browser[2].index("dart test --platform=chrome")


def test_flutter_dart_outside_lib_is_measured_on_the_dart_vm(tmp_path: Path) -> None:
    """Flutter's LCOV keeps only package: URIs, so scripts/ needs dart test's."""
    for directory in ("lib", "scripts", "test/scripts", "coverage/vm", "bin"):
        (tmp_path / directory).mkdir(parents=True)
    (tmp_path / "lib/app.dart").write_text("int one() => 1;\n")
    script = tmp_path / "scripts/check.dart"
    script.write_text("int two() => 2;\n")
    (tmp_path / "test/app_test.dart").write_text("void main() {}\n")
    (tmp_path / "test/helper.dart").write_text("import '../scripts/check.dart';\n")
    script_test = tmp_path / "test/scripts/check_test.dart"
    script_test.write_text('import "../../scripts/check.dart" as check;\n')
    (tmp_path / "coverage/vm/deleted_test.json").write_text("{}")
    command = dart_tests(["lib", "scripts"], FLUTTER_TESTS)["checks"][0]["command"]
    passed = '{"type":"testDone","result":"success","hidden":false,"skipped":false}'
    done = '{"type":"done","success":true}'
    tools = tmp_path / "bin"
    (tools / "flutter").write_text(
        "#!/bin/sh\nmkdir -p coverage\n"
        "printf 'SF:lib/app.dart\\nDA:1,1\\nend_of_record\\n' > coverage/lcov.info\n"
        f"echo '{passed}'; echo '{done}'\n"
    )
    (tools / "dart").write_text(
        '#!/bin/sh\nif [ "$1" = test ]; then echo "$@" > test.args;'
        " ls coverage/vm > vm.before 2>&1; mkdir -p coverage/vm;"
        f" echo '{passed}'; echo '{done}'; exit 0; fi\n"
        'echo "$@" > format.args\n'
        "printf 'SF:scripts/check.dart\\nDA:1,1\\nend_of_record\\n' > coverage/vm.lcov\n"
    )
    for tool in tools.iterdir():
        tool.chmod(0o755)
    report = tmp_path / "tests.jsonl"
    environment = {"PATH": f"{tools}:/usr/bin:/bin"}
    with report.open("w") as output:
        subprocess.run(
            command, cwd=tmp_path, stdout=output, env=environment, check=True
        )
    arguments = (tmp_path / "test.args").read_text().split()
    assert "--coverage=coverage/vm" in arguments
    assert [value for value in arguments if value.startswith("test/")] == [
        "test/scripts/check_test.dart"
    ]
    assert "No such file" in (tmp_path / "vm.before").read_text()
    assert "--report-on=scripts" in (tmp_path / "format.args").read_text().split()
    assert completed_tests(report, "dart-tests") == 2
    coverage = tmp_path / "coverage/lcov.info"
    expected = {(tmp_path / "lib/app.dart").resolve(), script.resolve()}
    assert line_coverage(coverage, "dart-tests", tmp_path.resolve(), expected) == (2, 2)
    script_test.unlink()
    with report.open("w") as output:
        result = subprocess.run(
            command,
            cwd=tmp_path,
            stdout=output,
            stderr=subprocess.PIPE,
            env=environment,
            text=True,
            check=True,
        )
    assert "import them by relative path and import package:test/test.dart" in (
        result.stderr
    )
    with pytest.raises(ValueError, match="omits production files: scripts/check.dart"):
        line_coverage(coverage, "dart-tests", tmp_path.resolve(), expected)


def test_pure_dart_outside_lib_is_measured_after_test_with_coverage(
    tmp_path: Path,
) -> None:
    """test_with_coverage scopes collection to package: URIs, so scripts/ needs dart test's."""
    assert dart_tests(["lib"], DART_TESTS)["checks"][0]["command"] == DART_TESTS
    package = dart_tests(["lib", "scripts"], DART_TESTS)
    command = package["checks"][0]["command"]
    outside_lib_coverage(package)
    assert package["checks"][0]["command"] == command
    for directory in ("lib", "scripts", "test", "bin"):
        (tmp_path / directory).mkdir()
    (tmp_path / "lib/app.dart").write_text("int one() => 1;\n")
    script = tmp_path / "scripts/check.dart"
    script.write_text("int two() => 2;\n")
    (tmp_path / "test/app_test.dart").write_text("void main() {}\n")
    (tmp_path / "test/check_test.dart").write_text("import '../scripts/check.dart';\n")
    tools = tmp_path / "bin"
    (tools / "dart").write_text(
        '#!/bin/sh\nif [ "$1" = test ]; then echo "$@" > test.args; exit 0; fi\n'
        'if [ "$2" = coverage:test_with_coverage ]; then mkdir -p coverage;'
        " printf 'SF:lib/app.dart\\nDA:1,1\\nend_of_record\\n' > coverage/lcov.info;"
        " exit 0; fi\n"
        "printf 'SF:scripts/check.dart\\nDA:1,1\\nend_of_record\\n' > coverage/vm.lcov\n"
    )
    (tools / "dart").chmod(0o755)
    subprocess.run(
        command, cwd=tmp_path, env={"PATH": f"{tools}:/usr/bin:/bin"}, check=True
    )
    arguments = (tmp_path / "test.args").read_text().split()
    assert [value for value in arguments if value.startswith("test/")] == [
        "test/check_test.dart"
    ]
    coverage = tmp_path / "coverage/lcov.info"
    expected = {(tmp_path / "lib/app.dart").resolve(), script.resolve()}
    assert line_coverage(coverage, "dart-tests", tmp_path.resolve(), expected) == (2, 2)
