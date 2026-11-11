"""Split a pytest tests gate over CI shards; only a shard run or a full check loads this."""

from collections.abc import Callable
from pathlib import PurePosixPath

from gate_config import Gate, Group


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
