"""Generated pnpm workflows move to Bun; custom CI without Bun is reported."""

from pathlib import Path

import pytest
from ci_setup import configure_ci, migrate_bun
from conftest import SOURCE, migrates_to_template


@pytest.mark.parametrize(
    "step",
    [
        (
            "      - uses: pnpm/setup@703c52620218391530e48b9e8870d5c0082e1b9b # v2.1.0\n"
            "        if: runner.environment != 'self-hosted'\n"
            "        with:\n          install: false\n"
        ),
        (
            "      - if: runner.environment != 'self-hosted'\n"
            "        uses: pnpm/setup@703c52620218391530e48b9e8870d5c0082e1b9b # v2.1.0\n"
            "        with:\n          install: false\n"
        ),
    ],
)
def test_pnpm_setup_step_with_a_condition_migrates_as_one_step(step: str) -> None:
    template = (SOURCE / ".github/workflows/hard-eng.yml").read_text()
    old = template.replace(
        "      - uses: oven-sh/setup-bun@0c5077e51419868618aeaa5fe8019c62421857d6 # v2.2.0\n"
        "        with:\n          bun-version: ${{ steps.impact.outputs.bun || 'latest' }}\n",
        step,
    )
    assert old != template
    assert migrate_bun(SOURCE, old) == template


def test_pnpm_bootstrap_migrates_to_the_template_bun_steps(tmp_path: Path) -> None:
    template = (SOURCE / ".github/workflows/hard-eng.yml").read_text()
    bun_step = (
        "      - uses: oven-sh/setup-bun@0c5077e51419868618aeaa5fe8019c62421857d6 # v2.2.0\n"
        "        with:\n          bun-version: ${{ steps.impact.outputs.bun || 'latest' }}\n"
    )
    pnpm_step = (
        "      - uses: pnpm/setup@703c52620218391530e48b9e8870d5c0082e1b9b # v2.1.0\n"
        "        with:\n          version: latest\n          runtime: node@latest\n"
        "          install: false\n"
    )
    pnpm_launcher = (
        "pnpm dlx --config.ignore-scripts=false --allow-build=@jdxcode/mise "
        "--package=@jdxcode/mise@latest mise"
    )
    bun_cache = (
        '            echo "BUN_INSTALL_CACHE_DIR=${BUN_INSTALL_CACHE_DIR:-'
        '$RUNNER_TEMP/hard-eng-tools/bun/cache}"\n'
    )
    pnpm_cache = (
        '            echo "PNPM_CONFIG_STORE_DIR=$RUNNER_TEMP/hard-eng-tools/pnpm/store"\n'
        '            echo "PNPM_CONFIG_CACHE_DIR=$RUNNER_TEMP/hard-eng-tools/pnpm/cache"\n'
    )
    pairs = (
        (bun_step, pnpm_step),
        ('bun x --package="$MISE_PACKAGE" mise', pnpm_launcher),
        ("'uv@latest python@3.12'", "'uv@latest python@3.12 node@latest'"),
        (bun_cache, pnpm_cache),
    )
    old = template
    for current, previous in pairs:
        assert current in template
        old = old.replace(current, previous)
    migrates_to_template(tmp_path, old)


def test_pnpm_tool_ending_a_tool_list_line_is_removed() -> None:
    old = "    env:\n      SDK_TOOLS: uv@latest python@3.12 node@24 pnpm@12.4.1\n"
    expected = "    env:\n      SDK_TOOLS: uv@latest python@3.12 node@24\n"
    assert migrate_bun(SOURCE, old) == expected


def test_existing_ci_without_bun_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / ".github/workflows/quality.yml"
    path.parent.mkdir(parents=True)
    job = "on: pull_request\njobs:\n  quality:\n    steps:\n{}      - run: {}\n"
    check = "pnpm dlx mise exec -- python3 .hooks/hard-eng.py check --base main"
    path.write_text(job.format("", check))
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, {})
    assert "quality.yml runs Hard Eng without setting up Bun" in capsys.readouterr().err
    setup = "      - uses: oven-sh/setup-bun@0c5077e51419868618aeaa5fe8019c62421857d6\n"
    path.write_text(job.format(setup, check))
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, {})
    assert "without setting up Bun" not in capsys.readouterr().err


def test_an_old_workflow_gets_double_quoted_mise_switches(tmp_path: Path) -> None:
    template = (SOURCE / ".github/workflows/hard-eng.yml").read_text()
    for name in ("MISE_PREFER_OFFLINE", "MISE_USE_VERSIONS_HOST"):
        assert f'{name}: "false"\n' in template
    old = template.replace('"false"', "'false'")
    assert old != template
    migrates_to_template(tmp_path, old)
