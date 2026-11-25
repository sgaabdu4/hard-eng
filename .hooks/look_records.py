"""The look records that back a head: its own, the clean verdicts that carry from earlier heads one image at a time, and the owner-check line of each rule that the reviewer does not decide."""

import json
import re
import subprocess
from pathlib import Path
from typing import cast

from challenge import store
from plans import split_rule_line, usability_rules

STORE = "look"
FRAME = re.compile(r"image-\d+\.png")


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
    unmeasured: bool,
) -> list[str]:
    """One key for each image: its bytes, its ring boxes and measured values, the rules, the design documents and the plan scope that the reviewer reads."""
    import look

    names = [f"image-{number}.png" for number in range(1, len(digests) + 1)]
    ringed, values = look.image_inputs(root, names, digests)
    shared = look.sha256(
        json.dumps(
            [
                look.prompt_for([], design, scope=scope, unmeasured=unmeasured),
                design_digest,
            ]
        ).encode()
    )
    return [
        look.sha256(
            json.dumps(
                [shared, digest, ringed.get(name, []), values.get(name, "")]
            ).encode()
        )
        for name, digest in zip(names, digests, strict=True)
    ]


def _same(recorded: object, wanted: object) -> bool:
    """A recorded field that is missing never equals anything, so an old-format record cannot match by lacking the field."""
    return recorded is not None and recorded == wanted


def carried_record(
    root: Path,
    head: str,
    record: dict[str, object],
    evidence: Path | None = None,
    design_rev: str = "",
) -> dict[str, object] | None:
    """A clean record of another head, set to this head, when each image has the same key now; the browser records come from `evidence`, the design documents from `design_rev` or the disk."""
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
        look.design_text(root, design_rev),
        look.design_hash(root, design_rev),
        [str(item["sha256"]) for item in entries],
        lacks_record(evidence or root, [str(item["sha256"]) for item in entries]),
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
    root: Path, head: str, evidence: Path | None = None, design_rev: str = ""
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
            carried_record(root, head, record, evidence, design_rev)
            if record and owned
            else None
        )
        if carried:
            found.append((path, carried))
    return found


def records_for(root: Path, head: str) -> list[dict[str, object]]:
    return [record for _, record in record_files(root, head, design_rev=head)]


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


def earlier_findings(
    root: Path, head: str, pairs: list[tuple[str, str, str]], judged: list[str]
) -> list[tuple[str, str]]:
    """The Fail lines of the newest clean or findings record on this branch for each file name, as (rule, text) items to recheck. A later clean record of a file ends its list. Frame names in a line are set to the names of this run. No line claims that a finding is fixed. `pairs` holds (prompt name, file name, digest)."""
    prefixes = owner_prefixes()
    current = {file: name for name, file, _ in pairs}
    items: dict[str, tuple[str, list[str]]] = {}
    claimed: set[str] = set()
    newest = sorted(
        _record_paths(root), key=lambda path: path.stat().st_mtime_ns, reverse=True
    )
    for path in newest:
        record = _read_record(path)
        owner = record.get("head") if record else None
        if (
            record is None
            or record.get("outcome") not in ("clean", "findings")
            or not isinstance(owner, str)
            or not _on_branch(root, owner, head)
        ):
            continue
        entries = cast(list[dict[str, object]], record.get("images", []))
        then = {str(item.get("name")): str(item.get("file")) for item in entries}
        files = [
            file for file in current if file not in claimed and file in then.values()
        ]
        claimed.update(files)
        if not files or record.get("outcome") != "findings":
            continue
        names = [current[file] for file in files]

        def now(found: re.Match[str], table: dict[str, str] = then) -> str:
            file = table.get(found[0], found[0])
            return current.get(file, file)

        lines = [
            *cast(list[str], record.get("rules", [])),
            *cast(list[str], record.get("reviewer_fails", [])),
        ]
        for line in lines:
            label, verdict, text, _ = split_rule_line(line)
            if verdict == "Fail" and label in judged and not text.startswith(prefixes):
                shown = FRAME.sub(now, line)
                items.setdefault(shown, (label, []))[1].extend(
                    name for name in names if name not in items[shown][1]
                )
    return [
        (label, f"{line} (frames: {', '.join(names)})")
        for line, (label, names) in items.items()
    ]


def _on_branch(root: Path, ancestor: str, head: str) -> bool:
    done = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, head],
        cwd=root,
        capture_output=True,
        check=False,
    )
    return done.returncode == 0


def owner_prefixes() -> tuple[str, ...]:
    """The text starts that mark a line from an owner check, not from the reviewer."""
    from ui_measure import PROOF_KINDS

    kinds = {kind for found in PROOF_KINDS.values() for kind in found}
    return tuple(f"{kind}:" for kind in sorted(kinds - {"judgement"}))


def lacks_record(root: Path | None, digests: list[str]) -> bool:
    """True when an image has no `.hard-eng/browser` measure record, as a mockup or a native screen has none."""
    if root is None:
        return True
    from ui_proof import browser_record_files

    recorded = {record["sha256"] for _, record in browser_record_files(root)}
    return any(digest not in recorded for digest in digests)


def stale_problem(
    root: Path, images: list[Path], digests: list[str], head: str
) -> str | None:
    """Each input image that is a stale copy: its digest has `.hard-eng/browser` capture records and none at the head. An image with no record is a mockup or a native screen and stays allowed."""
    from ui_proof import browser_record_files

    records = [record for _, record in browser_record_files(root)]
    stale = []
    for image, digest in zip(images, digests, strict=True):
        own = [record for record in records if record["sha256"] == digest]
        if not own or any(record.get("commit") == head for record in own):
            continue
        old = own[0]
        newer = sorted(
            str(record["image"])
            for record in records
            if record.get("commit") == head
            and record.get("width") == old.get("width")
            and record.get("route") == old.get("route")
        )
        use = (
            f"use .hard-eng/browser/{newer[0]}"
            if newer
            else "run `browser capture` again at this head"
        )
        taken = str(old.get("commit", ""))[:12]
        stale.append(
            f"{image} is a stale copy of the capture {old['image']} taken at {taken}, not at the head; {use}"
        )
    return "; ".join(stale) or None


def token_fault(root: Path, digests: list[str]) -> str:
    """The measured corner radii that no DESIGN.md token holds, or an empty text. A radius that its box clamped, a record without the clamp field or the root size, and a token that is not a plain length give no verdict. Text sizes stay with the reviewer, because fluid type and a changed root size make a rendered size inexact."""
    import look
    from look_facts import design_tokens, length_scale

    tokens = design_tokens(root).rounded
    faults: list[str] = []
    for digest in digests if tokens else []:
        values = look.recorded_measured(root, digest) or {}
        base = values.get("root_px")
        held = (
            length_scale(tokens, float(base))
            if isinstance(base, int | float) and not isinstance(base, bool)
            else None
        )
        if held is None:
            continue
        for item in cast(list[dict[str, object]], values.get("radii", [])):
            px = int(str(item["px"]))
            text = f"corner radius {px} px is in no rounded token ({', '.join(map(str, sorted(held)))} px)"
            if item.get("clamped") is False and px not in held and text not in faults:
                faults.append(text)
    return "; ".join(faults) + "; use a token or add it to DESIGN.md" if faults else ""


def code_fails(root: Path, head: str, digests: list[str]) -> dict[str, str]:
    """A Fail text for each judged rule that code decides: a measure finding of a rule that owns it, and the token fault of Design system. A rule without a fault is absent, so the reviewer's line for it stands."""
    from ui_measure import FINDING_RULES
    from ui_proof import measure_found

    found: dict[str, list[str]] = {}
    for _, record in measure_found(root, head, digests):
        names: dict[str, set[str]] = {}
        for item in cast(list[dict[str, object]], record.get("findings") or []):
            if rule := FINDING_RULES.get(str(item.get("rule"))):
                names.setdefault(rule, set()).add(str(item["rule"]))
        for rule, kinds in names.items():
            found.setdefault(rule, []).append(
                f"{record['image']} has findings ({', '.join(sorted(kinds))})"
            )
    fails = {
        rule: "; ".join(texts) + "; fix the screen and capture it again"
        for rule, texts in found.items()
    }
    if fault := token_fault(root, digests):
        fails["Design system"] = fault
    return fails


def owner_lines(
    root: Path, head: str, digests: list[str], plan: dict[str, tuple[str, str]] | None
) -> dict[str, str]:
    """One line for each rule that code decides, from its owner check: a measured rule from the browser records, a test rule from the plan's Rules line. A finding in a record fails a measured rule always; a measured rule with an unmeasured image keeps the reviewer's line unless a record fails. A rule with the judgement kind gets a line only for a code Fail, which the reviewer cannot overrule."""
    from ui_measure import PROOF_KINDS
    from ui_proof import measure_verdict

    measure = measure_verdict(root, head, digests)
    reviewed = lacks_record(root, digests)
    fails = code_fails(root, head, digests)
    lines: dict[str, str] = {}
    for name, _ in usability_rules():
        kinds = PROOF_KINDS[name]
        if "judgement" in kinds:
            if name in fails:
                lines[name] = f"{name}: Fail — measured: {fails[name]}"
            continue
        if "measured" in kinds:
            verdict, text = measure
            if verdict == "N/A" or (verdict == "Pass" and reviewed):
                continue
        elif plan is None:
            verdict, text = "N/A", "no plan given; the plan check decides"
        else:
            verdict, text = plan.get(
                name,
                ("N/A", "the plan has no line for this rule; the plan check decides"),
            )
        lines[name] = f"{name}: {verdict} — {kinds[0]}: {text or 'no text'}"
    return lines


def with_owner_lines(
    record: dict[str, object],
    root: Path,
    head: str,
    digests: list[str],
    plan: dict[str, tuple[str, str]] | None,
) -> None:
    """Give the record one line for each Usability rule, in rule order: the reviewer's line for a judged rule, the owner's line for the others. An owner Fail makes the run findings, and the reviewer's own Fail that it replaces stays under `reviewer_fails`, so the next run still rechecks it."""
    if record["outcome"] not in ("clean", "findings"):
        return
    owned = owner_lines(root, head, digests, plan)
    own = {split_rule_line(line)[0]: line for line in cast(list[str], record["rules"])}
    if replaced := [
        own[name]
        for name in owned
        if name in own and split_rule_line(own[name])[1] == "Fail"
    ]:
        record["reviewer_fails"] = replaced
    record["rules"] = [owned.get(name) or own[name] for name, _ in usability_rules()]
    if any(split_rule_line(line)[1] == "Fail" for line in owned.values()):
        record["outcome"] = "findings"
