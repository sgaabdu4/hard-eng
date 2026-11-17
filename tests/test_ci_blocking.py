"""The Hard Eng workflow must block: its check steps must be the generated ones, and nothing may turn a failure into a pass."""

from pathlib import Path

import pytest
from test_strict_refusals import project, refusal
from whole_project import validate_whole_project

WORKFLOW = ".github/workflows/hard-eng.yml"
JOB = "jobs:\n  hard-eng:\n    name: hard-eng\n    runs-on: ubuntu-latest\n"
CHECK = 'python3 .hooks/hard-eng.py check --base "$BASE_SHA"'
STEP = f"    steps:\n      - run: {CHECK}\n"
MISE = 'bun x --package="$MISE_PACKAGE" mise --no-config exec uv@latest -- uv run --no-project --with pyyaml python .hooks/hard-eng.py check --base "$BASE_SHA"'


def steps(*lines: str) -> str:
    return JOB + "    steps:\n" + "".join(f"      - run: {line}\n" for line in lines)


@pytest.mark.parametrize(
    "text",
    [
        JOB + "    continue-on-error: true\n" + STEP,
        JOB + STEP + "        continue-on-error: true\n",
        JOB + "    continue-on-error: ${{ github.ref != 'refs/heads/main' }}\n" + STEP,
        steps(f"{CHECK} || true"),
        steps(f"{CHECK} || :"),
        steps(f"{CHECK}; true"),
        steps(f"{CHECK};true"),
        steps(f"{CHECK} || exit 0"),
        steps(f"{CHECK} || echo failed"),
        steps(f"{CHECK} || /bin/true"),
        steps('python3 .hooks/hard-eng.py check --base "HEAD"'),
        steps("python3 .hooks/hard-eng.py check --base HEAD"),
        steps("python3 .hooks/hard-eng.py check"),
        steps("set +e", CHECK),
        steps("trap 'exit 0' EXIT", CHECK),
        JOB + "    steps:\n      - shell: bash {0}\n        run: " + CHECK + "\n",
        JOB + "    steps:\n      - if: false\n        run: " + CHECK + "\n",
        JOB + "    steps:\n      - if: ${{ false }}\n        run: " + CHECK + "\n",
    ],
)
def test_a_hard_eng_workflow_that_cannot_fail_is_refused(
    tmp_path: Path, text: str
) -> None:
    """HE-NO-SWITCH-OFF: the check steps are the generated ones, with no way to turn a failure into a pass."""
    message = refusal(project(tmp_path, {WORKFLOW: text}))
    assert f"{WORKFLOW}:" in message
    assert "blocking" in message


@pytest.mark.parametrize(
    ("name", "text"),
    [
        (WORKFLOW, JOB + "    continue-on-error: false\n" + STEP),
        (WORKFLOW, JOB + "    continue-on-error: ${{ false }}\n" + STEP),
        (WORKFLOW, steps(MISE)),
        (WORKFLOW, steps("rm -f x || true", CHECK)),
        (WORKFLOW, steps('echo "never write || true after a check"', CHECK)),
        (
            WORKFLOW,
            steps(
                'python3 .hooks/hard-eng.py impact --base "$BASE_SHA" >> "$GITHUB_OUTPUT" || echo docs_only=false >> "$GITHUB_OUTPUT"',
                CHECK,
            ),
        ),
        (
            WORKFLOW,
            steps(
                'python3 .hooks/hard-eng.py impact --base "$BASE_SHA" >> "$GITHUB_OUTPUT" || printf \'runner=ubuntu-latest\\napple=true\\n\' >> "$GITHUB_OUTPUT"',
                CHECK + " --only-language dart",
            ),
        ),
        (WORKFLOW, steps(CHECK + ' --shard "$SHARD"', CHECK + " --shard merge")),
        (".github/workflows/other.yml", JOB + "    continue-on-error: true\n"),
    ],
)
def test_a_generated_workflow_and_other_workflows_pass(
    tmp_path: Path, name: str, text: str
) -> None:
    validate_whole_project(project(tmp_path, {name: text}))
