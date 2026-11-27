"""`look` sends the design documents whole or refuses; it never cuts them."""

import hashlib
from pathlib import Path

import local_ui_proof
import look
import look_records
import pytest
import ui_proof
from challenge import git_text
from conftest import commit
from test_look import (
    good_answer,
    install_agent,
    look_project,
    make_images,
    prompt_text,
    run_look,
)

project = pytest.fixture(look_project)

LIBRARY = "# UI Library\n\nUse Button atom.\n"
TAIL = "LAST-RULE-OF-THE-DESIGN"


def sha(image: Path) -> str:
    return hashlib.sha256(image.read_bytes()).hexdigest()


def write_pair(project: Path, extra: int) -> None:
    """DESIGN.md that ends with the tail, sized so that the joined text is `extra` bytes over the limit."""
    (project / "UI-LIBRARY.md").write_text(LIBRARY)
    (project / "DESIGN.md").write_text(f"# Design\n{TAIL}\n")
    size = len(look.design_text(project).encode())
    filler = "x" * (look.DESIGN_BYTE_LIMIT - size + extra)
    (project / "DESIGN.md").write_text(f"# Design\n{filler}{TAIL}\n")
    commit(project, "design")


def test_a_design_pair_over_the_limit_is_refused_with_each_size(
    tmp_path: Path, project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_pair(project, 1)
    images = make_images(project, 1)
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    code = look.look_main(project, ["--host", "claude", str(images[0])])
    shown = capsys.readouterr().out
    design = len(
        f"### DESIGN.md\n{(project / 'DESIGN.md').read_text().strip()}".encode()
    )
    library = len(f"### UI-LIBRARY.md\n{LIBRARY.strip()}".encode())
    assert code == 1
    assert not log.exists()
    for wanted in (
        "DESIGN.md",
        "UI-LIBRARY.md",
        f"{design:,}",
        f"{library:,}",
        f"{design + library + 2:,}",
        f"{look.DESIGN_BYTE_LIMIT:,}",
    ):
        assert wanted in shown
    (project / "DESIGN.md").write_text(f"# Design\n{TAIL}\n")
    commit(project, "shorten the design")
    assert look.look_main(project, ["--host", "claude", str(images[0])]) == 0
    assert TAIL in prompt_text(log)


def test_a_design_pair_at_the_limit_is_sent_whole(
    tmp_path: Path, project: Path
) -> None:
    write_pair(project, 0)
    design = look.design_text(project)
    assert len(design.encode()) == look.DESIGN_BYTE_LIMIT
    assert TAIL in design
    images = make_images(project, 1)
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    run_look(project, "claude", images)
    assert TAIL in prompt_text(log)


def test_a_record_of_a_project_over_the_limit_gives_a_plain_refusal(
    tmp_path: Path, project: Path
) -> None:
    (project / ".gitignore").write_text(".hard-eng/\n")
    commit(project, "inputs")
    images = make_images(project, 1)
    install_agent(tmp_path, "claude", 1, good_answer(1))
    assert run_look(project, "claude", images)["outcome"] == "clean"
    write_pair(project, 1)
    new = git_text(project, "rev-parse", "HEAD")
    with pytest.raises(look.DesignTooLarge):
        look.design_text(project)
    assert look_records.records_for(project, new) == []
    assert look_records.record_files(project, new) == []
    after = [image.read_bytes() for image in images]
    shipped = ui_proof.look_problem(project, new, "", after)
    local = local_ui_proof._local_look_problem(
        project, project, new, [{sha(images[0])}], False, 0, lambda _: None
    )
    for message in (shipped, local):
        assert message is not None and message.startswith("Look review: no record")
