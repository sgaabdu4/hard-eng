"""A findings record of an earlier head covers each image that holds no Fail, so a head with one Fail reads only the image that failed."""

import hashlib
import json
from pathlib import Path

import look
import look_dispute
import look_records
import pytest
import ui_measure
from conftest import commit, git
from plans import usability_rules
from test_look import (
    PNG,
    install_agent,
    listed,
    look_project,
    make_images,
    next_head,
    run_look,
)

project = pytest.fixture(look_project)

SOURCE = "export const label = 'one';\nexport const note = 'two';\n"


def sha(image: Path) -> str:
    return hashlib.sha256(image.read_bytes()).hexdigest()


def answer(images: int, fail: str = "", recheck: str = "") -> str:
    rules = [
        f"- {name}: Fail — {fail} Fix: change it."
        if fail and name == "Alignment"
        else f"- {name}: Pass — looked at it"
        for name, _ in usability_rules()
    ]
    details = [f"Image image-{n}.png: a card" for n in range(1, images + 1)]
    verdict = "findings" if fail else "clean"
    return "\n".join(
        [*rules, *details, *([recheck] if recheck else []), f"VERDICT: {verdict}"]
    )


def sent_files(log: Path) -> list[str]:
    return [name for name in json.loads(log.read_text())["files"] if "image-" in name]


def head(root: Path) -> str:
    return git(root, "rev-parse", "HEAD").strip()


def findings_over_three(tmp_path: Path, project: Path) -> tuple[list[Path], str]:
    """Three images; the first look run fails image-2 only. Returns the images and that head, with a new head on top."""
    (project / ".gitignore").write_text(".hard-eng/\n")
    (project / "src").mkdir()
    (project / "src/form.ts").write_text(SOURCE)
    commit(project, "inputs")
    images = make_images(project, 3)
    install_agent(tmp_path, "claude", 3, answer(3, "image-2.png: the card is cramped"))
    assert run_look(project, "claude", images)["outcome"] == "findings"
    old = head(project)
    next_head(project)
    return images, old


def covering(
    project: Path, images: list[Path]
) -> tuple[dict[str, object], set[str]] | None:
    digests = [sha(image) for image in images]
    keys = look_records.image_keys(
        project,
        "",
        look.design_text(project),
        look.design_hash(project),
        digests,
        look_records.lacks_record(project, digests),
    )
    return look_records.covering_record(
        project, head(project), dict(zip(digests, keys, strict=True))
    )


def record_file(project: Path, old: str, images: list[Path]) -> Path:
    return look.record_path(project, old, [sha(image) for image in images])


def edit_record(path: Path, change: dict[str, object]) -> None:
    record = json.loads(path.read_text())
    record.update(change)
    path.write_text(json.dumps(record))


def set_rule(project: Path, old: str, images: list[Path], rule: str, line: str) -> None:
    path = record_file(project, old, images)
    record = json.loads(path.read_text())
    record["rules"] = [
        line if text.startswith(f"{rule}:") else text for text in record["rules"]
    ]
    path.write_text(json.dumps(record))


def look_again_clean(
    tmp_path: Path, project: Path, images: list[Path]
) -> tuple[dict[str, object], Path]:
    """The next run, where the reviewer sees the one failed image and says that its earlier Fail is gone."""
    gone = "Recheck R1: gone. image-1.png: the card has room now"
    log = install_agent(tmp_path, "claude", 1, answer(1, recheck=gone))
    return run_look(project, "claude", images), log


def covered_images(found: tuple[dict[str, object], set[str]] | None) -> set[str]:
    return found[1] if found else set()


def test_a_findings_record_covers_each_image_that_holds_no_fail(
    tmp_path: Path, project: Path
) -> None:
    images, old = findings_over_three(tmp_path, project)
    record, log = look_again_clean(tmp_path, project, images)
    assert sent_files(log) == ["image-1.png"]
    assert record["outcome"] == "clean"
    entries = listed(record, "images")
    assert [item.get("carried_from") for item in entries] == [old, None, old]
    assert all(item["read"] is True for item in entries)


def test_an_image_whose_key_changed_is_not_covered_by_a_findings_record(
    tmp_path: Path, project: Path
) -> None:
    images, _ = findings_over_three(tmp_path, project)
    assert covered_images(covering(project, images)) == {sha(images[0]), sha(images[2])}
    box = {"x": 1, "y": 2, "w": 30, "h": 40}
    ui_measure.write_record(project, images[0], 1280, [], "/kpi", ring_boxes=[box])
    assert covered_images(covering(project, images)) == {sha(images[2])}


@pytest.mark.parametrize(
    ("first", "second", "failing"),
    [("image-2.png", "image-3.png", 1), ("image-3.png", "image-2.png", 2)],
)
def test_a_fail_item_owns_only_the_image_it_names_first(
    tmp_path: Path, project: Path, first: str, second: str, failing: int
) -> None:
    images, old = findings_over_three(tmp_path, project)
    line = f"Alignment: Fail — {first}: the card clashes with {second} Fix: change it."
    set_rule(project, old, images, "Alignment", line)
    wanted = {sha(image) for number, image in enumerate(images) if number != failing}
    assert covered_images(covering(project, images)) == wanted


def test_a_disproved_dispute_covers_only_while_its_cited_bytes_hold(
    tmp_path: Path, project: Path
) -> None:
    images, old = findings_over_three(tmp_path, project)
    cited = look_dispute.read_cite(project, "src/form.ts:1-2", old)
    dispute = {
        "item": "image-3.png: the label is cut off",
        "cites": [
            {
                "path": "src/form.ts",
                "from": 1,
                "to": 2,
                "sha256": hashlib.sha256(cited.text.encode()).hexdigest(),
            }
        ],
        "verdict": "disproved",
        "relied": "src/form.ts:1",
    }
    edit_record(record_file(project, old, images), {"disputes": [dispute]})
    assert covered_images(covering(project, images)) == {sha(images[0]), sha(images[2])}
    (project / "src/form.ts").write_text(SOURCE.replace("two", "three"))
    commit(project, "the cited lines change")
    assert covering(project, images) is None


def test_a_findings_record_never_covers_the_whole_set(
    tmp_path: Path, project: Path
) -> None:
    images, _ = findings_over_three(tmp_path, project)
    passing = [images[0], images[2]]
    assert covering(project, passing) is None
    extra = images[0].with_name("after-9.png")
    extra.write_bytes(PNG + b"another image")
    found = covering(project, [*passing, extra])
    assert covered_images(found) == {sha(images[0]), sha(images[2])}


@pytest.mark.parametrize(
    "form", ["no image named", "image outside the run", "no entry name"]
)
def test_a_fail_that_names_no_run_image_covers_nothing(
    tmp_path: Path, project: Path, form: str
) -> None:
    images, old = findings_over_three(tmp_path, project)
    if form == "no entry name":
        path = record_file(project, old, images)
        record = json.loads(path.read_text())
        for item in record["images"]:
            item.pop("name")
        path.write_text(json.dumps(record))
    else:
        text = (
            "the card is cramped"
            if form == "no image named"
            else "image-9.png: the card is cramped"
        )
        set_rule(
            project,
            old,
            images,
            "Alignment",
            f"Alignment: Fail — {text} Fix: change it.",
        )
    assert covering(project, images) is None


def test_the_second_head_after_a_findings_head_reads_only_the_image_that_failed(
    tmp_path: Path, project: Path
) -> None:
    images, _ = findings_over_three(tmp_path, project)
    still = "Recheck R1: still shown. image-1.png: the card is cramped"
    install_agent(
        tmp_path,
        "claude",
        1,
        answer(1, "image-1.png: the card is cramped", recheck=still),
    )
    middle = run_look(project, "claude", images)
    assert middle["outcome"] == "findings"
    next_head(project)
    record, log = look_again_clean(tmp_path, project, images)
    assert sent_files(log) == ["image-1.png"]
    assert record["outcome"] == "clean"
    assert [item.get("carried_from") is None for item in listed(record, "images")] == [
        False,
        True,
        False,
    ]


def test_an_owner_check_fail_does_not_hold_an_image_back(
    tmp_path: Path, project: Path
) -> None:
    images, old = findings_over_three(tmp_path, project)
    line = "Accessibility: Fail — measured: after-0.png has findings (tap); fix the screen and capture it again"
    set_rule(project, old, images, "Accessibility", line)
    assert covered_images(covering(project, images)) == {sha(images[0]), sha(images[2])}


def test_a_piece_with_no_image_name_belongs_to_the_item_before_it(
    tmp_path: Path, project: Path
) -> None:
    images, old = findings_over_three(tmp_path, project)
    line = "Alignment: Fail — the cards are uneven; image-2.png: the card is cramped; it also overlaps the title Fix: change it."
    set_rule(project, old, images, "Alignment", line)
    assert covered_images(covering(project, images)) == {sha(images[0]), sha(images[2])}
