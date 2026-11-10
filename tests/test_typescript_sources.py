"""A folder added to `sources` of a JavaScript package must also reach its TypeScript configuration."""

import json
import re
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from gate_config import validate_required_checks
from test_setup import repository
from untrusted_input import validate_typescript

UNTRUSTED = ".hooks/untrusted-input.d.ts"


def tsc_that_reads(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer `--showConfig` with the files that the `include` list of tsconfig.json names."""

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        include = json.loads((root / "tsconfig.json").read_text())["include"]
        files = [
            str(path.relative_to(root))
            for folder in include
            for path in sorted((root / folder).rglob("*.ts"))
        ]
        shown = {
            "compilerOptions": {"strict": True, "checkJs": True},
            "files": [*files, UNTRUSTED],
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(shown))

    monkeypatch.setattr(subprocess, "run", run)


def test_the_typescript_sources_error_names_the_files_and_the_configuration(
    installer: ModuleType,
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src/index.ts").write_text("export const a = 1;\n")
    (tmp_path / "tsconfig.json").write_text('{"include": ["src"]}')
    config = installer.gate_config(tmp_path)
    validate_required_checks(tmp_path, config)
    (tmp_path / "server").mkdir()
    (tmp_path / "server/main.ts").write_text("export const b = 2;\n")
    with pytest.raises(ValueError, match="outside its sources: server;") as refusal:
        validate_required_checks(tmp_path, config)
    assert "`include` list of the package's TypeScript configuration" in str(
        refusal.value
    )
    group = config["packages"][0]
    group["sources"].append("server")
    validate_required_checks(tmp_path, config)
    tsc_that_reads(tmp_path, monkeypatch)
    expected = runner.production_files(tmp_path, group)
    with pytest.raises(ValueError, match="omits declared production files") as omitted:
        validate_typescript(tmp_path, ["tsc"], tmp_path, expected, 10)
    assert re.search(r"files: server/main\.ts\b.*tsconfig\.json", str(omitted.value))
    (tmp_path / "tsconfig.json").write_text('{"include": ["src", "server"]}')
    validate_typescript(tmp_path, ["tsc"], tmp_path, expected, 10)
