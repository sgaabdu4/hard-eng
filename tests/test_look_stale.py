"""look refuses an image that is a stale copy of an older capture, and leaves mockups and native screens alone."""

import shutil
from pathlib import Path

import look
import pytest
from test_look import PNG, good_answer, install_agent, look_project, next_head, run_look
from test_look_proof_kinds import captures

project = pytest.fixture(look_project)


def copy_to_tmp(images: list[Path], folder: Path) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    return [Path(shutil.copy(image, folder / image.name)) for image in images]


def recapture(project: Path, stem: str) -> None:
    import ui_measure

    for number, width in enumerate((390, 768, 1280)):
        image = project / f".hard-eng/browser/{stem}-{width}.png"
        image.write_bytes(PNG + bytes([number + 50]) * 20)
        ui_measure.write_record(project, image, width, [], "/home")


def test_a_stale_copy_is_refused_and_the_newer_capture_is_named(
    tmp_path: Path, project: Path
) -> None:
    stale = copy_to_tmp(captures(project), tmp_path / "tmp")
    next_head(project)
    recapture(project, "fresh")
    install_agent(tmp_path, "claude", 3, good_answer(3))
    with pytest.raises(ValueError, match="stale") as refused:
        look.look_command(project, ["--host", "codex", *map(str, stale)])
    for width in (390, 768, 1280):
        assert f".hard-eng/browser/fresh-{width}.png" in str(refused.value)


def test_every_stale_image_is_named_in_one_message(
    tmp_path: Path, project: Path
) -> None:
    images = captures(project)
    next_head(project)
    with pytest.raises(ValueError, match="stale") as refused:
        look.look_command(project, ["--host", "codex", *map(str, images)])
    message = str(refused.value)
    for image in images:
        assert image.name in message
    assert "browser capture" in message


def test_a_mockup_with_no_capture_record_is_still_reviewed(
    tmp_path: Path, project: Path
) -> None:
    images = captures(project)
    next_head(project)
    mockup = tmp_path / "mockup.png"
    mockup.write_bytes(PNG + b"\x07" * 20)
    install_agent(tmp_path, "claude", 1, good_answer(1))
    record = run_look(project, "codex", [mockup])
    assert record["outcome"] == "clean"
    assert images[0].is_file()


def test_captures_taken_at_the_head_are_still_reviewed(
    tmp_path: Path, project: Path
) -> None:
    images = captures(project)
    install_agent(tmp_path, "claude", 3, good_answer(3))
    assert run_look(project, "codex", images)["outcome"] == "clean"
