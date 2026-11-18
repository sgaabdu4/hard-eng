"""An After image that several capture sets share is judged by the sets taken at the head, not by the first record that has its hash."""

import json
from pathlib import Path

import ui_proof
from ui_proof import sha256

HEAD = "h" * 40
OLD = "o" * 40
IMAGE = b"same-screen-bytes"
WIDTHS = (390, 768, 1280)


def write_set(
    root: Path,
    stem: str,
    commit: str,
    findings: list[dict[str, object]] | None = None,
) -> None:
    folder = root / ".hard-eng/browser"
    folder.mkdir(parents=True, exist_ok=True)
    for width in WIDTHS:
        name = f"{stem}-{width}.png"
        data = IMAGE if width == WIDTHS[-1] else IMAGE + str(width).encode()
        (folder / name).write_bytes(data)
        (folder / f"{stem}-{width}.json").write_text(
            json.dumps(
                {
                    "image": name,
                    "sha256": sha256(data),
                    "width": width,
                    "findings": findings or [],
                    "commit": commit,
                    "dirty": False,
                }
            )
        )


def test_an_earlier_clean_capture_with_the_same_image_does_not_hide_findings(
    tmp_path: Path,
) -> None:
    write_set(tmp_path, "a-first", HEAD)
    write_set(tmp_path, "b-later", HEAD, [{"rule": "tap-size"}])
    problem = ui_proof.measured_problem(tmp_path, HEAD, [IMAGE])
    assert problem is not None and "tap-size" in problem


def test_a_capture_of_an_older_commit_with_the_same_image_does_not_refuse_the_current_one(
    tmp_path: Path,
) -> None:
    write_set(tmp_path, "a-old", OLD)
    write_set(tmp_path, "b-current", HEAD)
    assert ui_proof.measured_problem(tmp_path, HEAD, [IMAGE]) is None


def test_a_capture_of_an_older_commit_alone_is_still_refused(tmp_path: Path) -> None:
    write_set(tmp_path, "a-old", OLD)
    problem = ui_proof.measured_problem(tmp_path, HEAD, [IMAGE])
    assert problem is not None and "not taken at the head" in problem


def test_a_set_refreshed_at_one_width_with_a_finding_is_not_hidden_by_a_clean_set(
    tmp_path: Path,
) -> None:
    write_set(tmp_path, "a-part", OLD)
    refreshed = tmp_path / ".hard-eng/browser/a-part-390.json"
    record = json.loads(refreshed.read_text())
    refreshed.write_text(
        json.dumps({**record, "commit": HEAD, "findings": [{"rule": "tap-size"}]})
    )
    write_set(tmp_path, "b-current", HEAD)
    problem = ui_proof.measured_problem(tmp_path, HEAD, [IMAGE])
    assert problem is not None and "tap-size" in problem
