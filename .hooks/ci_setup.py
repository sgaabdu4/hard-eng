"""Adapt existing CI and generate only explicitly configured new workflows."""

import json
import math
import re
import sys
from pathlib import Path

from gate_config import GateConfig
from project_setup import dependency_command


def workflow_budget(root: Path, content: str) -> str:
    from shipping import load_policy

    policy = load_policy(root, required=False)
    if policy is None:
        return content
    return re.sub(
        r"(?m)^    timeout-minutes: \d+$",
        f"    timeout-minutes: {math.ceil(policy['ci_seconds'] / 60)}",
        content,
    )


def migrate_workflow_pins(content: str) -> str:
    for action, old, new, before, after in (
        (
            "actions/checkout",
            "fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09",
            "3d3c42e5aac5ba805825da76410c181273ba90b1",
            "v5",
            "v7.0.1",
        ),
        (
            "pnpm/setup",
            "c9883cc79df532ad1a7b81bf9ab944ceb090d65c",
            "703c52620218391530e48b9e8870d5c0082e1b9b",
            "v2.0.0",
            "v2.1.0",
        ),
    ):
        content = re.sub(
            rf"(?m)^([ \t]*(?:-[ \t]+)?uses:[ \t]+){re.escape(action)}@{old}([ \t]*(?:#.*)?)$",
            lambda match, action=action, new=new, before=before, after=after: (
                match[1]
                + action
                + "@"
                + new
                + match[2].replace(f"# {before}", f"# {after}", 1)
            ),
            content,
        )
    return content


def migrate_workflow_tools(content: str) -> str:
    launcher = "pnpm dlx --allow-build=@jdxcode/mise --package=@jdxcode/mise@latest mise --no-config"
    return re.sub(
        r"(?m)^        run: >-\n"
        r"          pnpm dlx --allow-build=@jdxcode/mise\n"
        r"          --package=@jdxcode/mise@latest mise --no-config exec\n"
        r"          (?P<tools>[^\n]+)\n"
        r"          -- (?P<check>uv run --no-project --with pyyaml python "
        r'\.hooks/hard-eng\.py check --base "\$BASE_SHA")\n',
        lambda match: (
            "        run: |\n"
            f"          {launcher} install {match['tools']} &&\n"
            f"          MISE_FETCH_REMOTE_VERSIONS_CACHE=1h {launcher} exec {match['tools']} -- {match['check']}\n"
        ),
        content,
    )


def workflow_tools(root: Path, config: GateConfig) -> list[str]:
    tools = ["uv@latest", "python@3.12", "node@latest"]
    for package in config["packages"]:
        directory = root / package["path"]
        language = package.get("language")
        if language not in {"python", "javascript", "dart"}:
            continue
        manager, _, _ = dependency_command(directory, language)
        if manager in {"dart", "flutter", "pnpm", "yarn", "bun", "poetry"}:
            version = "latest"
            if language == "javascript":
                declared = json.loads((directory / "package.json").read_text()).get(
                    "packageManager", ""
                )
                if declared.startswith(manager + "@"):
                    version = declared.split("@", 1)[1].split("+", 1)[0]
            specification = manager + "@" + version
            if specification not in tools:
                tools.append(specification)
    if "flutter@latest" in tools and "dart@latest" in tools:
        tools.remove("dart@latest")
    return tools


def configure_ci(
    root: Path, source: Path, config: GateConfig, changes: dict[str, str]
) -> None:
    name = ".github/workflows/hard-eng.yml"
    if (root / name).exists():
        original = (root / name).read_text()
        migrated = migrate_workflow_tools(migrate_workflow_pins(original))
        if migrated != original:
            changes[name] = migrated
        return
    if any(
        path.suffix in {".yml", ".yaml"}
        for path in (root / ".github/workflows").glob("*")
    ):
        print(
            "Existing CI retained: integrate missing Hard Eng checks into their current jobs and require those results in shipping.checks; do not add a duplicate full pipeline.",
            file=sys.stderr,
        )
        return
    from shipping import load_policy

    if load_policy(root, required=False) is None:
        print(
            "CI setup pending: configure project shipping checks and a measured ci_seconds budget, then rerun setup. The source repository's timeout is not a project budget.",
            file=sys.stderr,
        )
        return
    tools = workflow_tools(root, config)
    changes[name] = (
        (source / name)
        .read_text()
        .replace("uv@latest python@3.12 node@latest dart@latest", " ".join(tools))
    )
    changes[name] = workflow_budget(root, changes[name])
