"""The Hard Eng workflow must block: each step that calls the hooks is a generated one, and nothing in its job turns a failure into a pass."""

import re
from pathlib import PurePosixPath

TOOLS = r'(?:bun x --package="\$MISE_PACKAGE" mise|"\$\{mise_command\[@\]\}")'
CHECK_COMMAND = (
    r"(?:MISE_FETCH_REMOTE_VERSIONS_CACHE=\w+ )?"
    rf"(?:{TOOLS} --no-config exec (?:[\w@.-]+ |\"\$\{{tools\[@\]\}}\" )+-- uv run --no-project --with pyyaml python"
    r"|python3(?: -B)?)"
    r' \.hooks/hard-eng\.py (?:check|impact) --base "\$BASE_SHA"'
    r"(?: --(?:only|skip)-language \w+)?"
    r'(?: --shard (?:rest|merge|"\$SHARD"))?'
    r'(?: >> "\$GITHUB_OUTPUT" \|\| (?:echo docs_only=false|printf \'runner=[\w.-]+\\napple=(?:true|false)\\n\') >> "\$GITHUB_OUTPUT")?'
)
LAUNCHER = re.compile(
    r'if \[\[ -n "\$(?P<name>[A-Z_]+)" \]\]; then mise_command=\("\$(?P=name)"\); fi'
)
LANGUAGE_FLAG = re.compile(r"--(only|skip)-language (\w+)")
GENERATED_LINES = [
    re.compile(pattern)
    for pattern in (
        CHECK_COMMAND,
        r"\{",
        r'\} >> "\$GITHUB_ENV"',
        r'echo "(?:MISE_DATA_DIR|MISE_CACHE_DIR|MISE_STATE_DIR|BUN_INSTALL_CACHE_DIR)=\$\{\w+:-\$RUNNER_TEMP/hard-eng-tools/[\w/]+\}"',
        r'echo "MISE_PACKAGE=@jdxcode/mise-\$\(uname -s \| tr \'\[:upper:\]\' \'\[:lower:\]\'\)-\$\(echo "\$RUNNER_ARCH" \| tr \'\[:upper:\]\' \'\[:lower:\]\'\)@latest"',
        r'read -r -a tools <<< "\$SDK_TOOLS \$\{EXTRA_SDK_TOOLS:-\}"',
        r'SDK_TOOLS="\$\{SDK_TOOLS//[\w@.-]+/\}"',
        r'if \[ "\$CHECKS" != success \] \|\| \[ "\$TESTS" != success \]; then',
        r'echo "checks: \$CHECKS, tests: \$TESTS"',
        r"exit 1",
        r"fi",
        r'mise_command=\(bun x --package="\$MISE_PACKAGE" mise\)',
        LAUNCHER.pattern,
        rf"{TOOLS} --no-config install (?:[\w@.-]+ |\"\$\{{tools\[@\]\}}\" )+&&",
    )
]
STEP_IF = re.compile(
    r"steps\.impact\.outputs\.docs_only (?:==|!=) 'true'(?: && needs\.[\w-]+\.result == '(?:skipped|success)')?"
)
STEP_ENV = {
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "MISE_GITHUB_TOKEN",
    "BASE_SHA",
    "SDK_TOOLS",
    "PNPM_CONFIG_STORE_DIR",
    "PNPM_CONFIG_CACHE_DIR",
    "CHECKS",
    "TESTS",
    "EXTRA_SDK_TOOLS",
}
BASE_VALUES = {
    "${{ inputs.base_sha || github.event.pull_request.base.sha || github.event.before }}",
    "${{ github.event.pull_request.base.sha || github.event.before }}",
}
SPACES = re.compile(r"\s+")
SAFE_FALSE = {False, "false", "${{ false }}"}
TRIGGERS = {"pull_request", "workflow_call"}
FIX = "the Hard Eng job and its check steps must be blocking and must be the steps that setup generates; restore the generated step or run setup again"


def hard_eng_workflow(name: str) -> bool:
    path = PurePosixPath(name)
    return path.name == "hard-eng.yml" and ".github" in path.parts


def step_hits(step: dict[str, object]) -> list[str]:
    hits = []
    for key in ("shell", "working-directory"):
        if key in step:
            hits.append(f"the check step sets {key}")
    if step.get("continue-on-error", False) not in SAFE_FALSE:
        hits.append("the check step sets continue-on-error")
    if "if" in step and not STEP_IF.fullmatch(str(step["if"]).strip()):
        hits.append(f"the check step runs only when {step['if']!r}")
    env = step.get("env")
    for key, value in (env if isinstance(env, dict) else {}).items():
        if key not in STEP_ENV and not key.startswith("MISE_"):
            hits.append(f"the check step sets the variable {key}")
        elif key == "BASE_SHA" and str(value).strip() not in BASE_VALUES:
            hits.append(f"the check step sets BASE_SHA to {value!r}")
    for name in sorted(launcher_names(step)):
        if name == "CI" or name.startswith(("GITHUB_", "RUNNER_")):
            hits.append(
                f"the check step runs ${name}, which the runner sets, as the Mise launcher"
            )
        if isinstance(env, dict) and name in env:
            hits.append(f"the check step sets the launcher variable {name}")
    for line in str(step.get("run", "")).splitlines():
        text = SPACES.sub(" ", line.strip())
        if text and not any(form.fullmatch(text) for form in GENERATED_LINES):
            hits.append(f"the check step holds {text!r}")
    return hits


def launcher_names(step: dict[str, object]) -> set[str]:
    return {
        match["name"]
        for line in str(step.get("run", "")).splitlines()
        if (match := LAUNCHER.fullmatch(SPACES.sub(" ", line.strip())))
    }


def job_hits(
    job: dict[str, object], workflow: dict[str, object], names: set[str]
) -> list[str]:
    hits = []
    if job.get("continue-on-error", False) not in SAFE_FALSE:
        hits.append("the job sets continue-on-error")
    if str(job.get("if", "")).strip() in {"false", "${{ false }}", "0", "''", '""'}:
        hits.append("the job never runs")
    for scope, holder in (("job", job), ("workflow", workflow)):
        defaults = holder.get("defaults")
        run = defaults.get("run") if isinstance(defaults, dict) else None
        for key in ("shell", "working-directory"):
            if isinstance(run, dict) and key in run:
                hits.append(f"the {scope} defaults set {key}")
        env = holder.get("env")
        for key in ("BASE_SHA", "PATH", *sorted(names)):
            if isinstance(env, dict) and key in env:
                hits.append(f"the {scope} sets the variable {key}")
    return hits


def line_of(text: str, step: dict[str, object]) -> int:
    first = next(iter(str(step.get("run", "")).strip().splitlines()), "").strip()
    at = text.find(first) if first else -1
    return text.count("\n", 0, at) + 1 if at >= 0 else 1


def workflow_hits(name: str, text: str) -> list[str]:
    """Findings for a Hard Eng workflow, read as YAML: only the steps that call the hooks and their job are judged."""
    try:
        import yaml
    except ImportError:
        return []
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return [f"{name}:1 cannot be read as YAML: {FIX}"]
    if not isinstance(data, dict):
        return [f"{name}:1 is not a workflow: {FIX}"]
    found: list[str] = []
    triggers = data.get("on", data.get(True))
    events = (
        {triggers}
        if isinstance(triggers, str)
        else set(triggers)
        if isinstance(triggers, (list, dict))
        else set()
    )
    if not events & TRIGGERS:
        found.append(f"{name}:1 runs on {sorted(map(str, events))} only: {FIX}")
    jobs = data.get("jobs")
    checks = 0
    words: list[tuple[str, str, int]] = []
    for job in (jobs if isinstance(jobs, dict) else {}).values():
        if not isinstance(job, dict):
            continue
        steps = [
            step
            for step in job.get("steps") or []
            if isinstance(step, dict)
            and ".hooks/hard-eng.py" in str(step.get("run", ""))
        ]
        if not steps:
            continue
        checks += sum(" check " in str(step["run"]) for step in steps)
        launchers = set().union(*map(launcher_names, steps))
        found += [f"{name}:1 {hit}: {FIX}" for hit in job_hits(job, data, launchers)]
        for step in steps:
            for match in LANGUAGE_FLAG.finditer(str(step["run"])):
                words.append((match[1], match[2], line_of(text, step)))
        for step in steps:
            found += [
                f"{name}:{line_of(text, step)} {hit}: {FIX}" for hit in step_hits(step)
            ]
    only = {language for kind, language, _ in words if kind == "only"}
    found += [
        f"{name}:{line} skips {language} with no job that checks only {language}: {FIX}"
        for kind, language, line in words
        if kind == "skip" and language not in only
    ]
    if not checks:
        found.append(f"{name}:1 holds no generated check step: {FIX}")
    return found
