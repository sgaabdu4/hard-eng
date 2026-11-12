"""A folder added to `sources` of a JavaScript package must also reach its TypeScript configuration."""

import json
import re
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from coverage_sources import require_listed_sources, source_roots
from gate_config import Group, validate_required_checks
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


def write_files(root: Path, files: dict[str, str]) -> list[Path]:
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    return sorted(path for path in root.rglob("*") if path.is_file())


def refusal(root: Path, files: list[Path], listed: list[str]) -> str | None:
    group: Group = {
        "path": ".",
        "language": "javascript",
        "sources": listed,
        "checks": [],
    }
    try:
        require_listed_sources(root, [group], files, False)
    except ValueError as error:
        return str(error)
    return None


PLAYWRIGHT_PROJECT = {
    "src/app.ts": "export const app = 1;\n",
    "playwright.config.ts": (
        'export default { testDir: "./e2e", globalSetup: "./e2e/global-setup.ts" };\n'
    ),
    "playwright.prod.config.ts": "export default { testDir: './e2e-prod' };\n",
    "e2e/login.spec.ts": 'import { auth } from "./fixtures/auth";\nimport "./login.page";\n',
    "e2e/login.page.ts": 'import "./pages/login";\n',
    "e2e/pages/login.ts": "export const login = 1;\n",
    "e2e/fixtures/auth.ts": 'import { base } from "./base";\nexport const auth = base;\n',
    "e2e/fixtures/base.ts": "export const base = 1;\n",
    "e2e/global-setup.ts": "export default async () => {};\n",
    "e2e-prod/smoke.spec.ts": "import { shared } from '../e2e-prod/support/shared';\n",
    "e2e-prod/support/shared.ts": "export const shared = 1;\n",
}


def test_the_test_folder_of_a_playwright_settings_file_is_test_code(
    tmp_path: Path,
) -> None:
    files = write_files(tmp_path, PLAYWRIGHT_PROJECT)
    assert refusal(tmp_path, files, ["src"]) is None
    assert source_roots(tmp_path, "javascript", files) == {"src"}


@pytest.mark.parametrize(
    ("extra", "folder"),
    [
        ({"browser/helper.ts": "export const helper = 1;\n"}, "browser"),
        (
            {
                "playwright.config.ts": (
                    'export default { testDir: path.join(__dirname, "e2e") };\n'
                ),
                "e2e/login.spec.ts": "test();\n",
                "e2e/support.ts": "export const support = 1;\n",
            },
            "e2e",
        ),
        (
            {
                "playwright.config.ts": 'export default { testDir: "./e2e" };\n',
                "e2e/login.spec.ts": "test();\n",
                "e2e/unused.ts": "export const unused = 1;\n",
            },
            "e2e",
        ),
        (
            {
                "playwright.config.ts": (
                    "const hint = \"testDir: 'server.ts'\";\nexport default {};\n"
                ),
                "server.ts": "export const server = 1;\n",
            },
            "server.ts",
        ),
    ],
)
def test_a_folder_that_no_playwright_setting_names_is_still_outside_the_sources(
    tmp_path: Path, extra: dict[str, str], folder: str
) -> None:
    files = write_files(tmp_path, {"src/app.ts": "export const app = 1;\n", **extra})
    message = refusal(tmp_path, files, ["src"])
    assert message is not None
    assert f"JavaScript code is outside its sources: {folder};" in message
    assert source_roots(tmp_path, "javascript", files) == {"src", folder}


BESIDE_CONFIG = {"playwright.config.ts": 'export default { testDir: "./src" };\n'}
BARREL = {
    "src/index.ts": 'export * from "./price";\nexport * from "./cart";\n',
    "src/price.ts": "export const price = 1;\n",
    "src/cart.ts": 'import { price } from "./price";\n',
}


@pytest.mark.parametrize(
    "package",
    [
        {
            "src/main.ts": "export const main = 1;\n",
            "src/price.ts": "export const price = 1;\n",
            "src/price.spec.ts": 'import { price } from "./price";\n',
        },
        {**BARREL, "src/index.spec.ts": 'import "./index";\n'},
        {**BARREL, "src/__tests__/index.spec.ts": 'import "../index";\n'},
    ],
)
def test_application_code_beside_playwright_tests_stays_a_source(
    tmp_path: Path, package: dict[str, str]
) -> None:
    files = write_files(tmp_path, {**BESIDE_CONFIG, **package})
    assert source_roots(tmp_path, "javascript", files) == {"src"}
    message = refusal(tmp_path, files, [])
    assert message is not None
    assert "outside its sources: src;" in message


def test_a_package_with_no_code_outside_its_sources_reads_no_playwright_settings_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = write_files(tmp_path, PLAYWRIGHT_PROJECT)
    inside = [path for path in files if path.relative_to(tmp_path).parts[0] != "e2e"]

    def unreadable(self: Path, *_: object, **__: object) -> str:
        raise AssertionError(f"read {self.name}")

    monkeypatch.setattr(Path, "read_text", unreadable)
    assert refusal(tmp_path, inside, ["src", "e2e-prod"]) is None
