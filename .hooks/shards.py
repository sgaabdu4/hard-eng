"""Split a pytest tests gate over CI shards; only a shard run or a full check loads this."""

import re
import subprocess
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from gate_config import Gate, Group
from process_group import run_in_group

COLLECTED_FILE = re.compile(r"^(\S.*): [0-9]+$", re.MULTILINE)
KEPT = "coverage/shards"


def split(sizes: dict[str, int], count: int) -> list[list[str]]:
    """Largest file first, each to the lightest shard; a tie goes to the lowest shard."""
    parts: list[list[str]] = [[] for _ in range(count)]
    loads = [0] * count
    for path, size in sorted(sizes.items(), key=lambda item: (-item[1], item[0])):
        lightest = loads.index(min(loads))
        parts[lightest].append(path)
        loads[lightest] += size
    return [sorted(part) for part in parts]


def require_pytest(groups: list[Group]) -> None:
    for group in groups:
        for gate in group["checks"]:
            direct = (
                gate.get("report", {}).get("type") == "python-tests"
                and "pytest" in gate["command"]
            )
            if "shards" in gate and not direct:
                raise ValueError(
                    f"{group['path']}/{gate['name']}: shards split pytest suites only, "
                    "and the command must run pytest directly. "
                    'Remove "shards" from this gate in hard-eng.gates.json.'
                )


def pick(
    groups: list[Group], keep: Callable[[Group, Gate], Gate | None]
) -> list[Group]:
    """Groups holding only the gates `keep` returns; a group left with none is dropped."""
    chosen = [
        (group, [keep(group, gate) for gate in group["checks"]]) for group in groups
    ]
    return [
        {**group, "checks": [gate for gate in gates if gate is not None]}
        for group, gates in chosen
        if any(gate is not None for gate in gates)
    ]


def shard_groups(groups: list[Group], shard: str) -> list[Group]:
    """The groups of one `check --shard` run; a kept tests gate carries its part."""
    require_pytest(groups)
    if shard == "rest":
        return pick(groups, lambda _group, gate: None if "shards" in gate else gate)
    if shard == "merge":
        return pick(
            groups,
            lambda _group, gate: {**gate, "part": shard} if "shards" in gate else None,
        )
    number = int(shard)
    homes = [
        PurePosixPath(group["path"])
        for group in groups
        if any(gate.get("shards", 0) >= number for gate in group["checks"])
    ]

    def keep(group: Group, gate: Gate) -> Gate | None:
        if gate.get("shards", 0) >= number:
            return {**gate, "part": shard}
        above = any(PurePosixPath(group["path"]) in (p, *p.parents) for p in homes)
        return gate if above and gate.get("role") == "lockfiles" else None

    return pick(groups, keep)


def shard_folder(root: Path, part: str, group: Group) -> Path:
    return root / KEPT / part / group["path"]


def runner_arguments(command: list[str]) -> list[str]:
    return command[len(command) - command[::-1].index("pytest") :]


def collected(
    root: Path, group: Group, gate: Gate, command: list[str], timeout: float
) -> tuple[Path, dict[str, int]]:
    """The folder pytest reports from and the size of each file the gate command collects."""
    parallel = any(
        argument.startswith(("-n", "--numprocesses"))
        for argument in runner_arguments(command)
    )
    listing = [*command, "--collect-only", "-qq", *(["-n", "0"] if parallel else [])]
    result = run_in_group(
        listing,
        cwd=root / group["path"],
        timeout=timeout,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    names = COLLECTED_FILE.findall(result.stdout)
    bases = [
        base
        for base in (root / group["path"], *(root / group["path"]).parents)
        if all((base / name).is_file() for name in names)
    ]
    if result.returncode not in (0, 5) or not bases:
        raise ValueError(
            f"{group['path']}/{gate['name']}: pytest could not list the tests of this "
            "shard, so the shard did not start. Run the tests command with "
            "--collect-only -qq to see the cause.\n" + result.stdout
        )
    return bases[0], {name: (bases[0] / name).stat().st_size for name in names}


def part_command(
    root: Path,
    group: Group,
    gate: Gate,
    command: list[str],
    coverage: Path | None,
    timeout: float,
) -> tuple[list[str], Path | None]:
    """The command of one shard: the gate command and the files of that shard."""
    base, sizes = collected(root, group, gate, command, timeout)
    names = split(sizes, gate["shards"])[int(gate["part"]) - 1]
    folder = shard_folder(root, gate["part"], group)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "shard-files.txt").write_text("".join(f"{name}\n" for name in names))
    for name in (gate["report"]["tests"], gate["report"]["coverage"]):
        (root / group["path"] / name).unlink(missing_ok=True)
    return ([*command, *(str(base / name) for name in names)] if names else []), None


def keep_reports(root: Path, group: Group, gate: Gate) -> None:
    """Move the reports of a numbered shard beside its file list, away from the normal paths."""
    if not gate["part"].isdecimal():
        return
    folder = shard_folder(root, gate["part"], group)
    for name in (gate["report"]["tests"], gate["report"]["coverage"]):
        source = root / group["path"] / name
        if source.is_file():
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            source.replace(folder / name)
