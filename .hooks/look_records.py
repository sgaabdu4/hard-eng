"""The look records that back a head: its own, and the clean verdicts that carry from earlier heads one image at a time."""

import json
import subprocess
from pathlib import Path
from typing import cast

from challenge import store
from plans import split_rule_line

STORE = "look"
MAX_FIXED_LINES = 8


def _read_record(path: Path) -> dict[str, object] | None:
    try:
        record = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def _record_paths(root: Path) -> list[Path]:
    folder = store(root, "records", STORE).parent
    return sorted(folder.glob("*-*.json")) if folder.is_dir() else []


def image_keys(
    root: Path | None,
    scope: str,
    design: str,
    design_digest: str,
    digests: list[str],
) -> list[str]:
    """One key for each image: its bytes and ring boxes, the rules, the design documents and the plan scope that the reviewer reads."""
    import look

    names = [f"image-{number}.png" for number in range(1, len(digests) + 1)]
    ringed = look.image_inputs(root, names, digests)
    shared = look.sha256(
        json.dumps([look.prompt_for([], design, scope=scope), design_digest]).encode()
    )
    return [
        look.sha256(json.dumps([shared, digest, ringed.get(name, [])]).encode())
        for name, digest in zip(names, digests, strict=True)
    ]


def _same(recorded: object, wanted: object) -> bool:
    """A recorded field that is missing never equals anything, so an old-format record cannot match by lacking the field."""
    return recorded is not None and recorded == wanted


def _changed(recorded: object, wanted: object) -> bool:
    return recorded is not None and not _same(recorded, wanted)


def carried_record(
    root: Path, head: str, record: dict[str, object], evidence: Path | None = None
) -> dict[str, object] | None:
    """A clean record of another head, set to this head, when each image has the same key now; the browser records come from `evidence`."""
    images = record.get("images")
    if (
        record.get("outcome") != "clean"
        or not isinstance(images, list)
        or not all(isinstance(item, dict) and "inputs" in item for item in images)
    ):
        return None
    import look

    plan = record.get("plan")
    try:
        rel, scope, digest = (
            look.plan_scope(root, Path(plan), head)
            if isinstance(plan, str) and plan
            else ("", "", "")
        )
    except ValueError:
        return None
    entries = look.listed_images(record)
    keys = image_keys(
        evidence or root,
        scope,
        look.design_text(root),
        look.design_hash(root),
        [str(item["sha256"]) for item in entries],
    )
    if keys != [item["inputs"] for item in entries]:
        return None
    carried = {**record, "carried_from": record.get("head"), "head": head}
    if rel:
        carried["plan_sha256"] = digest
    return carried


def _newest_earlier(paths: list[Path], head: str, own_sets: set[str]) -> list[Path]:
    """For each image set that this head has no record for, the newest record file of an earlier head."""
    newest: dict[str, tuple[int, Path]] = {}
    for path in paths:
        owner, _, image_set = path.stem.rpartition("-")
        if owner == head or image_set in own_sets:
            continue
        mtime = path.stat().st_mtime_ns
        if image_set not in newest or mtime > newest[image_set][0]:
            newest[image_set] = (mtime, path)
    return [path for _, path in newest.values()]


def record_files(
    root: Path, head: str, evidence: Path | None = None
) -> list[tuple[Path, dict[str, object]]]:
    """The records that back this head: its own, and for each image set without one, the newest clean record of an earlier head whose images all have the same key."""
    paths = _record_paths(evidence or root)
    found: list[tuple[Path, dict[str, object]]] = []
    for path in paths:
        if path.stem.rpartition("-")[0] == head and (
            (record := _read_record(path)) is not None
        ):
            found.append((path, record))
    own_sets = {path.stem.rpartition("-")[2] for path, _ in found}
    for path in _newest_earlier(paths, head, own_sets):
        record = _read_record(path)
        owned = bool(record) and record.get("head") == path.stem.rpartition("-")[0]
        carried = (
            carried_record(root, head, record, evidence) if record and owned else None
        )
        if carried:
            found.append((path, carried))
    return found


def records_for(root: Path, head: str) -> list[dict[str, object]]:
    return [record for _, record in record_files(root, head)]


def covering_record(
    root: Path, head: str, wanted: dict[str, str]
) -> tuple[dict[str, object], set[str]] | None:
    """The clean record of an earlier head that holds the most images with the wanted key (image digest to key), newest first, and the digests it covers."""
    best: tuple[tuple[int, int], dict[str, object], set[str]] | None = None
    for path in _record_paths(root):
        record = _read_record(path)
        if (
            record is None
            or record.get("outcome") != "clean"
            or record.get("head") == head
        ):
            continue
        covered = {
            str(item["sha256"])
            for item in cast(list[dict[str, object]], record.get("images", []))
            if item.get("read") is True
            and _same(item.get("inputs"), wanted.get(str(item.get("sha256"))))
        }
        rank = (len(covered), path.stat().st_mtime_ns)
        if covered and (best is None or rank > best[0]):
            best = (rank, record, covered)
    return (best[1], best[2]) if best else None


def combined(
    images: list[Path],
    digests: list[str],
    base: dict[str, object],
    covered: set[str],
    fresh: dict[str, object] | None,
) -> dict[str, object]:
    """One record for all images: each covered image keeps its entry from the earlier record, the others come from the new review."""
    record = dict(fresh if fresh is not None else base)
    kept = {
        str(item["sha256"]): {**item, "carried_from": base.get("head")}
        for item in cast(list[dict[str, object]], base.get("images", []))
        if str(item["sha256"]) in covered
    }
    reviewed = iter(cast(list[dict[str, object]], fresh["images"]) if fresh else [])
    record["images"] = [
        {**kept[digest], "file": image.name}
        if digest in covered
        else {**next(reviewed), "file": image.name}
        for image, digest in zip(images, digests, strict=True)
    ]
    if fresh is None:
        record.pop("plan", None)
        record.pop("plan_sha256", None)
    return record


def earlier_fixes(
    root: Path, head: str, pairs: list[tuple[str, str, str]]
) -> list[str]:
    """The Fail lines of earlier findings on this branch for the same file names, when the image has changed since; each is marked as fixed at this head. `pairs` holds (prompt name, file name, digest)."""
    lines: dict[str, list[str]] = {}
    fresh = sorted(
        _record_paths(root), key=lambda path: path.stat().st_mtime_ns, reverse=True
    )
    for path in fresh:
        record = _read_record(path)
        owner = record.get("head") if record else None
        if (
            record is None
            or record.get("outcome") != "findings"
            or not isinstance(owner, str)
            or not _on_branch(root, owner, head)
        ):
            continue
        entries = cast(list[dict[str, object]], record.get("images", []))
        names = [
            name
            for name, file, digest in pairs
            for item in entries
            if _same(item.get("file"), file) and _changed(item.get("sha256"), digest)
        ]
        for line in cast(list[str], record.get("rules", [])):
            _, verdict, _, _ = split_rule_line(line)
            if names and verdict == "Fail":
                lines.setdefault(line, [])
                lines[line] += [name for name in names if name not in lines[line]]
    return [
        f"{', '.join(names)}: {line} (fixed at {head[:7]})"
        for line, names in list(lines.items())[:MAX_FIXED_LINES]
    ]


def _on_branch(root: Path, ancestor: str, head: str) -> bool:
    done = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, head],
        cwd=root,
        capture_output=True,
        check=False,
    )
    return done.returncode == 0
