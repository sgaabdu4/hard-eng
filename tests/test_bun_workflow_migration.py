"""Generated pnpm workflows move to Bun; custom CI without Bun is reported."""

from pathlib import Path

import pytest
from ci_setup import configure_ci, migrate_bun

SOURCE = Path(__file__).resolve().parents[1]


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


def test_pnpm_bootstrap_migrates_to_the_template_bun_steps() -> None:
    template = (SOURCE / ".github/workflows/hard-eng.yml").read_text()
    launcher = 'bun x --package="@jdxcode/mise-linux-${RUNNER_ARCH,,}@latest" mise'
    old = (
        template.replace(
            "      - uses: oven-sh/setup-bun@0c5077e51419868618aeaa5fe8019c62421857d6 # v2.2.0\n"
            "        with:\n          bun-version: ${{ steps.impact.outputs.bun || 'latest' }}\n",
            "      - uses: pnpm/setup@703c52620218391530e48b9e8870d5c0082e1b9b # v2.1.0\n"
            "        with:\n          version: latest\n          runtime: node@latest\n"
            "          install: false\n",
        )
        .replace(
            launcher,
            "pnpm dlx --config.ignore-scripts=false --allow-build=@jdxcode/mise "
            "--package=@jdxcode/mise@latest mise",
        )
        .replace("'uv@latest python@3.12'", "'uv@latest python@3.12 node@latest'")
        .replace(
            '            echo "BUN_INSTALL_CACHE_DIR=$RUNNER_TEMP/hard-eng-tools/bun/cache"\n',
            '            echo "PNPM_CONFIG_STORE_DIR=$RUNNER_TEMP/hard-eng-tools/pnpm/store"\n'
            '            echo "PNPM_CONFIG_CACHE_DIR=$RUNNER_TEMP/hard-eng-tools/pnpm/cache"\n',
        )
    )
    assert "pnpm" in old and old != template
    assert migrate_bun(SOURCE, old) == template
    assert migrate_bun(SOURCE, template) == template


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
