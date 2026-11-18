"""The Hard Eng workflow must block: its check steps must be the generated ones, and nothing may turn a failure into a pass."""

from pathlib import Path

import pytest
from test_strict_refusals import project, refusal
from whole_project import validate_whole_project

WORKFLOW = ".github/workflows/hard-eng.yml"
BASE = "${{ inputs.base_sha || github.event.pull_request.base.sha || github.event.before }}"
ON = "on:\n  push:\n  pull_request:\n  workflow_call:\n"
CHECK = 'python3 .hooks/hard-eng.py check --base "$BASE_SHA"'
IMPACT = 'python3 .hooks/hard-eng.py impact --base "$BASE_SHA" >> "$GITHUB_OUTPUT" || echo docs_only=false >> "$GITHUB_OUTPUT"'
MISE = 'bun x --package="$MISE_PACKAGE" mise --no-config exec uv@latest -- uv run --no-project --with pyyaml python .hooks/hard-eng.py check --base "$BASE_SHA"'
ENV = f"        env:\n          BASE_SHA: {BASE}\n"


def launcher(name: str = "PROJECT_MISE_BINARY", second: str | None = None) -> str:
    """The form older generated workflows use: a variable that names a cached Mise binary."""
    return (
        'mise_command=(bun x --package="$MISE_PACKAGE" mise)\n'
        f'if [[ -n "${name}" ]]; then mise_command=("${second or name}"); fi\n'
        '"${mise_command[@]}" --no-config install uv@latest &&\n'
        '"${mise_command[@]}" --no-config exec uv@latest -- uv run --no-project --with pyyaml python .hooks/hard-eng.py check --base "$BASE_SHA"'
    )


def second_job(flag: str) -> str:
    return f"  apple:\n    runs-on: ubuntu-latest\n    steps:\n      - run: |\n          {CHECK} {flag}\n"


def indented(text: str) -> str:
    return "".join(f"          {line}\n" for line in text.splitlines())


def workflow(
    run: str = CHECK,
    *,
    on: str = ON,
    step: str = "",
    job: str = "",
    extra: str = "",
    env: str = ENV,
) -> str:
    return (
        f"name: Hard Eng\n{on}jobs:\n  hard-eng:\n    name: hard-eng\n    runs-on: ubuntu-latest\n{job}"
        f"    steps:\n      - name: Run required checks\n{step}{env}        run: |\n{indented(run)}{extra}"
    )


def folded(command: str) -> str:
    return (
        "name: Hard Eng\n"
        + ON
        + "jobs:\n  hard-eng:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Run required checks\n"
        + ENV
        + f"        run: >-\n          {command}\n          || true\n"
    )


REFUSED = {
    "job continue-on-error": workflow(job="    continue-on-error: true\n"),
    "step continue-on-error": workflow(step="        continue-on-error: true\n"),
    "continue-on-error expression": workflow(
        job="    continue-on-error: ${{ github.ref != 'refs/heads/main' }}\n"
    ),
    "or true": workflow(f"{CHECK} || true"),
    "or colon": workflow(f"{CHECK} || :"),
    "then true": workflow(f"{CHECK}; true"),
    "or exit 0": workflow(f"{CHECK} || exit 0"),
    "or echo": workflow(f"{CHECK} || echo failed"),
    "folded or true": folded(CHECK),
    "base HEAD": workflow('python3 .hooks/hard-eng.py check --base "HEAD"'),
    "no base": workflow("python3 .hooks/hard-eng.py check"),
    "set plus e": workflow(f"set +e\n{CHECK}"),
    "set plus eu": workflow(f"set +eu\n{CHECK}"),
    "set plus o errexit": workflow(f"set +o errexit\n{CHECK}"),
    "trap": workflow(f"trap 'exit 0' EXIT\n{CHECK}"),
    "shell": workflow(step="        shell: bash {0}\n"),
    "step if false": workflow(step="        if: false\n"),
    "step if expression": workflow(step="        if: github.actor == 'nobody'\n"),
    "working directory": workflow(step="        working-directory: docs\n"),
    "defaults shell": workflow(
        job="    defaults:\n      run:\n        shell: bash {0}\n"
    ),
    "defaults working directory": workflow(
        job="    defaults:\n      run:\n        working-directory: docs\n"
    ),
    "base prefix": workflow(f"BASE_SHA=HEAD {CHECK}"),
    "path prefix": workflow(f"PATH=./fake:$PATH {CHECK}"),
    "env base sha": workflow(job="    env:\n      BASE_SHA: ${{ github.sha }}\n"),
    "step env base sha": workflow(
        env="        env:\n          BASE_SHA: ${{ github.sha }}\n"
    ),
    "step env path": workflow(
        env=f"        env:\n          BASE_SHA: {BASE}\n          PATH: ./fake\n"
    ),
    "docs only after impact": workflow(
        f'{IMPACT}\necho docs_only=true >> "$GITHUB_OUTPUT"\n{CHECK}'
    ),
    "check deleted": workflow("echo nothing"),
    "on narrowed": workflow(on="on:\n  workflow_dispatch:\n"),
    "on narrowed to a string": workflow(on="on: workflow_dispatch\n"),
    "job if false": workflow(job="    if: false\n"),
    "job if false string": workflow(job="    if: 'false'\n"),
    "job if false expression": workflow(job="    if: ${{ false }}\n"),
    "job if event name": workflow(job="    if: github.event_name == 'push'\n"),
    "apple job if on the main check job": workflow(
        job="    needs: impact\n    if: ${{ needs.impact.outputs.apple != 'false' }}\n"
    ),
    "pull request branch filter": workflow(
        on="on:\n  pull_request:\n    branches: [never-a-real-base]\n"
    ),
    "pull request paths filter": workflow(
        on="on:\n  pull_request:\n    paths: ['docs/**']\n"
    ),
    "pull request types filter": workflow(
        on="on:\n  pull_request:\n    types: [closed]\n"
    ),
    "skip language alone": workflow(CHECK + " --skip-language python"),
    "skip language beside another only": workflow(
        CHECK + " --skip-language python", extra=second_job("--only-language swift")
    ),
    "launcher variable of the runner": workflow(launcher("CI")),
    "launcher variable of github": workflow(launcher("GITHUB_ACTOR")),
    "launcher variable of the runner os": workflow(launcher("RUNNER_OS")),
    "launcher variable names differ": workflow(
        launcher("PROJECT_MISE_BINARY", "OTHER_BINARY")
    ),
    "launcher variable in the job env": workflow(
        launcher(), job="    env:\n      PROJECT_MISE_BINARY: 'true'\n"
    ),
    "launcher variable in the workflow env": workflow(
        launcher(), on=ON + "env:\n  PROJECT_MISE_BINARY: 'true'\n"
    ),
    "launcher variable in the step env": workflow(
        launcher("MISE_LAUNCHER_BIN"),
        env=f"        env:\n          BASE_SHA: {BASE}\n          MISE_LAUNCHER_BIN: 'true'\n",
    ),
}


@pytest.mark.parametrize("text", REFUSED.values(), ids=REFUSED.keys())
def test_a_hard_eng_workflow_that_cannot_fail_is_refused(
    tmp_path: Path, text: str
) -> None:
    """HE-NO-SWITCH-OFF: the check steps are the generated ones, with no way to turn a failure into a pass."""
    message = refusal(project(tmp_path, {WORKFLOW: text}))
    assert f"{WORKFLOW}:" in message
    assert "blocking" in message


PASSED = {
    "job continue-on-error false": workflow(job="    continue-on-error: false\n"),
    "job continue-on-error false expression": workflow(
        job="    continue-on-error: ${{ false }}\n"
    ),
    "mise launcher": workflow(MISE),
    "mise launcher with a cache prefix": workflow(
        "MISE_FETCH_REMOTE_VERSIONS_CACHE=1h " + MISE
    ),
    "impact and check": workflow(f"{IMPACT}\n{CHECK}"),
    "docs only step": workflow(
        step="        if: steps.impact.outputs.docs_only == 'true'\n"
    ),
    "shard": workflow(CHECK + ' --shard "$SHARD"'),
    "other steps are free": workflow(
        extra="      - name: Clean up\n        shell: bash\n        run: |\n          rm -f x || true\n          exit 0\n"
    ),
    "tool variables in the step env": workflow(
        env=f"        env:\n          BASE_SHA: {BASE}\n          MISE_PREFER_OFFLINE: 'false'\n"
    ),
    "shard merge step": workflow(
        'if [ "$CHECKS" != success ] || [ "$TESTS" != success ]; then\n  echo "checks: $CHECKS, tests: $TESTS"\n  exit 1\nfi\n'
        + CHECK
        + " --shard merge",
        env=f"        env:\n          CHECKS: ${{{{ needs.checks.result }}}}\n          TESTS: ${{{{ needs.tests.result }}}}\n          BASE_SHA: {BASE}\n",
    ),
    "swift split": workflow(
        CHECK + " --skip-language swift", extra=second_job("--only-language swift")
    ),
    "launcher variable set by an earlier step": workflow(launcher()),
    "workflow call only": workflow(on="on:\n  workflow_call:\n"),
    "job if of the generated impact jobs": workflow(
        job="    if: ${{ !cancelled() }}\n"
    ),
    "pull request on every branch": workflow(
        on="on:\n  pull_request:\n    branches: ['**']\n"
    ),
    "dispatch beside pull request": workflow(
        on="on:\n  pull_request:\n  workflow_dispatch:\n"
    ),
}


@pytest.mark.parametrize("text", PASSED.values(), ids=PASSED.keys())
def test_a_generated_workflow_passes(tmp_path: Path, text: str) -> None:
    validate_whole_project(project(tmp_path, {WORKFLOW: text}))


def test_other_workflows_are_free(tmp_path: Path) -> None:
    text = "jobs:\n  a:\n    continue-on-error: true\n    steps:\n      - run: exit 0\n"
    validate_whole_project(project(tmp_path, {".github/workflows/other.yml": text}))
