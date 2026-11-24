"""A clean look record carries to a new head one image at a time, and the reviewer gets the earlier fixed findings."""

import hashlib
import json
from pathlib import Path

import pytest
from conftest import commit, git
from plans import usability_rules
from test_look import (
    PNG,
    full_plan,
    good_answer,
    install_agent,
    listed,
    look_project,
    make_images,
    run_look,
)

project = pytest.fixture(look_project)


def clean_look_then_new_head(
    tmp_path: Path, project: Path, *, plan: bool = False, measured: bool = False
) -> tuple[list[Path], str, str]:
    """A clean look record at one head, then a commit that changes no input of the reviewer; returns the images, the old head and the new head."""
    (project / ".gitignore").write_text(".hard-eng/\n")
    if plan:
        plan_file = project / "features/kpi-board/PLAN.md"
        plan_file.parent.mkdir(parents=True)
        plan_file.write_text(full_plan("A KPI board with one card."))
    commit(project, "inputs")
    images = make_images(project, 1)
    if measured:
        import ui_measure

        values: dict[str, object] = {"radii": [{"at": "Go", "px": 6}]}
        ui_measure.write_record(project, images[0], 1280, [], "/kpi", measured=values)
    install_agent(tmp_path, "claude", 1, good_answer(1))
    extra = ["--plan", "features/kpi-board/PLAN.md"] if plan else None
    run_look(project, "claude", images, extra=extra)
    old = git(project, "rev-parse", "HEAD").strip()
    (project / "notes.txt").write_text("a change that the reviewer never reads\n")
    commit(project, "unrelated change")
    return images, old, git(project, "rev-parse", "HEAD").strip()


def test_a_clean_look_record_carries_to_a_new_head_with_the_same_reviewer_inputs(
    tmp_path: Path, project: Path
) -> None:
    import look_records

    _, old, new = clean_look_then_new_head(tmp_path, project, plan=True)
    plan_file = project / "features/kpi-board/PLAN.md"
    plan_file.write_text(full_plan("A KPI board with one card.", ux="Surface: New — x"))
    commit(project, "the plan changes outside its scope")
    new = git(project, "rev-parse", "HEAD").strip()
    found = look_records.records_for(project, new)
    assert [record["outcome"] for record in found] == ["clean"]
    assert found[0]["carried_from"] == old
    digest = hashlib.sha256(plan_file.read_bytes()).hexdigest()
    assert found[0]["plan_sha256"] == digest


@pytest.mark.parametrize("change", ["design", "plan scope", "ring boxes", "findings"])
def test_a_look_record_does_not_carry_when_one_reviewer_input_changed(
    tmp_path: Path, project: Path, change: str
) -> None:
    import look
    import look_records
    import ui_measure

    images, old, _ = clean_look_then_new_head(tmp_path, project, plan=True)
    if change == "design":
        (project / "DESIGN.md").write_text("# Design\n\n## Overview\nBrand navy.\n")
    elif change == "plan scope":
        plan_file = project / "features/kpi-board/PLAN.md"
        plan_file.write_text(full_plan("A KPI board with two cards."))
    elif change == "ring boxes":
        box = {"x": 1, "y": 2, "w": 30, "h": 40}
        ui_measure.write_record(project, images[0], 1280, [], "/kpi", ring_boxes=[box])
    else:
        hashes = [hashlib.sha256(image.read_bytes()).hexdigest() for image in images]
        path = look.record_path(project, old, hashes)
        record = json.loads(path.read_text())
        record["outcome"] = "findings"
        path.write_text(json.dumps(record))
    (project / "notes.txt").write_text(f"{change}\n")
    commit(project, f"change: {change}")
    new = git(project, "rev-parse", "HEAD").strip()
    assert look_records.records_for(project, new) == []


def test_an_old_format_record_never_covers_and_a_new_format_record_still_does(
    tmp_path: Path, project: Path
) -> None:
    import look

    images, old, _ = clean_look_then_new_head(tmp_path, project)
    new_format = json.loads(
        look.record_path(
            project, old, [hashlib.sha256(images[0].read_bytes()).hexdigest()]
        ).read_text()
    )
    foreign = [hashlib.sha256(bytes([n])).hexdigest() for n in range(3)]
    old_format = {
        **new_format,
        "head": "1" * 40,
        "images": [
            {"name": f"image-{n}.png", "sha256": digest, "read": True, "read_at": "t"}
            for n, digest in enumerate(foreign)
        ],
    }
    path = look.record_path(project, "1" * 40, foreign)
    path.write_text(json.dumps(old_format))
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    log.unlink()
    record = run_look(project, "claude", images)
    assert not log.exists()
    assert [item.get("carried_from") for item in listed(record, "images")] == [old]


def test_a_carried_record_backs_the_new_head_in_ship_and_in_the_local_proof(
    tmp_path: Path, project: Path
) -> None:
    import local_ui_proof
    import look
    import look_records
    import ui_proof

    images, _, new = clean_look_then_new_head(
        tmp_path, project, plan=True, measured=True
    )
    after = [image.read_bytes() for image in images]
    plan_rel = "features/kpi-board/PLAN.md"
    digest = look.plan_scope(project, Path(plan_rel), new)[2]
    block = look.block_text(look_records.records_for(project, new)[0])
    assert ui_proof.look_problem(project, new, block, after, plan_rel, digest) is None
    opened = [{hashlib.sha256(data).hexdigest() for data in after}]
    assert (
        local_ui_proof._local_look_problem(
            project, project, new, opened, False, 0, lambda _: None
        )
        is None
    )

    problem = ui_proof.look_problem(
        project, new, block, [PNG + b"another image"], plan_rel, digest
    )
    assert problem is not None and "does not cover the After image" in problem


def test_a_carried_record_reads_the_browser_records_of_the_evidence_checkout(
    tmp_path: Path, project: Path
) -> None:
    import look_records

    _, _, new = clean_look_then_new_head(tmp_path, project, plan=True, measured=True)
    snapshot = tmp_path / "snapshot"
    git(project, "worktree", "add", "-q", str(snapshot), new)
    assert [
        r["head"] for _, r in look_records.record_files(snapshot, new, project)
    ] == [new]
    assert look_records.record_files(snapshot, new, snapshot) == []


def findings_answer(images: int, rule: str, text: str) -> str:
    rules = [
        f"- {name}: {f'Fail — {text} Fix: change it.' if name == rule else 'Pass — looked at it'}"
        for name, _ in usability_rules()
    ]
    details = [f"Image image-{n}.png: a card" for n in range(1, images + 1)]
    return "\n".join([*rules, *details, "VERDICT: findings"])


def two_images_with_a_clean_look_of_the_first(
    tmp_path: Path, project: Path
) -> tuple[list[Path], str]:
    (project / ".gitignore").write_text(".hard-eng/\n")
    commit(project, "inputs")
    images = make_images(project, 2)
    install_agent(tmp_path, "claude", 1, good_answer(1))
    run_look(project, "claude", images[:1])
    old = git(project, "rev-parse", "HEAD").strip()
    (project / "notes.txt").write_text("a change that the reviewer never reads\n")
    commit(project, "unrelated change")
    return images, old


def test_an_unchanged_image_is_not_sent_to_the_reviewer_again(
    tmp_path: Path, project: Path
) -> None:
    images, old = two_images_with_a_clean_look_of_the_first(tmp_path, project)
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    record = run_look(project, "claude", images)
    sent = [name for name in json.loads(log.read_text())["files"] if "image-" in name]
    assert sent == ["image-1.png"]
    assert record["outcome"] == "clean"
    listed_images = listed(record, "images")
    assert [item["sha256"] for item in listed_images] == [
        hashlib.sha256(image.read_bytes()).hexdigest() for image in images
    ]
    assert [item.get("carried_from") for item in listed_images] == [old, None]
    assert all(item["read"] is True for item in listed_images)


def test_a_run_whose_images_are_all_unchanged_does_not_start_the_reviewer(
    tmp_path: Path, project: Path
) -> None:
    images, old = two_images_with_a_clean_look_of_the_first(tmp_path, project)
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    run_look(project, "claude", images)
    middle = git(project, "rev-parse", "HEAD").strip()
    log.unlink()
    (project / "notes.txt").write_text("another change\n")
    commit(project, "another unrelated change")
    record = run_look(project, "claude", images[:1])
    assert not log.exists()
    assert record["outcome"] == "clean"
    assert middle != old
    assert [item.get("carried_from") for item in listed(record, "images")] == [middle]


def a_look_that_found_the_badge_fault(tmp_path: Path, project: Path) -> list[Path]:
    """One image that a first look run failed on Alignment."""
    (project / ".gitignore").write_text(".hard-eng/\n")
    commit(project, "inputs")
    images = make_images(project, 1)
    install_agent(
        tmp_path,
        "claude",
        1,
        findings_answer(1, "Alignment", "merge badge and meta into one line"),
    )
    run_look(project, "claude", images)
    return images


def test_the_prompt_holds_the_earlier_fixed_finding_for_the_same_image_name(
    tmp_path: Path, project: Path
) -> None:
    images = a_look_that_found_the_badge_fault(tmp_path, project)
    images[0].write_bytes(PNG + b"badge and meta on one line")
    (project / "notes.txt").write_text("the badge is fixed\n")
    commit(project, "fix the badge")
    head = git(project, "rev-parse", "HEAD").strip()
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    run_look(project, "claude", images)
    prompt = " ".join(json.loads(log.read_text())["argv"])
    assert "image-1.png: Alignment: Fail — merge badge and meta into one line" in prompt
    assert f"fixed at {head[:7]}" in prompt
    assert "never ask to undo an earlier fix" in prompt.lower()


@pytest.mark.parametrize("digest_kept", [True, False])
def test_a_finding_of_an_image_that_has_not_changed_is_not_called_fixed(
    tmp_path: Path, project: Path, *, digest_kept: bool
) -> None:
    import look

    images = a_look_that_found_the_badge_fault(tmp_path, project)
    if not digest_kept:
        head = git(project, "rev-parse", "HEAD").strip()
        path = look.record_path(
            project, head, [hashlib.sha256(images[0].read_bytes()).hexdigest()]
        )
        record = json.loads(path.read_text())
        del record["images"][0]["sha256"]
        path.write_text(json.dumps(record))
    (project / "notes.txt").write_text("a change that the reviewer never reads\n")
    commit(project, "unrelated change")
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    run_look(project, "claude", images)
    assert "fixed at" not in " ".join(json.loads(log.read_text())["argv"])


def test_a_run_that_holds_back_images_tells_the_reviewer_and_all_forces_a_full_review(
    tmp_path: Path, project: Path
) -> None:
    images, _ = two_images_with_a_clean_look_of_the_first(tmp_path, project)
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    run_look(project, "claude", images)
    prompt = " ".join(json.loads(log.read_text())["argv"])
    assert "holds back 1 unchanged image" in prompt
    assert "not shown" in prompt

    (project / "notes.txt").write_text("another change\n")
    commit(project, "another unrelated change")
    log = install_agent(tmp_path, "claude", 2, good_answer(2))
    run_look(project, "claude", images, extra=["--all"])
    sent = [name for name in json.loads(log.read_text())["files"] if "image-" in name]
    assert sent == ["image-1.png", "image-2.png"]
