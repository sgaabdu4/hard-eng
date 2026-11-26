"""A merged pull request's look record is judged against the design documents of the PR's own head, never against the checkout that runs `ship --stage delivered`."""

from pathlib import Path

import pytest
from conftest import commit, git
from test_look import (
    good_answer,
    install_agent,
    look_project,
    make_images,
    run_look,
)

project = pytest.fixture(look_project)

DESIGN = "# Design\n\n## Overview\nBrand navy.\n"
LATER_DESIGN = "# Design\n\n## Overview\nBrand crimson.\n"


def look_at_a_design(tmp_path: Path, project: Path) -> tuple[list[Path], str, str]:
    """A clean look record at a head that holds DESIGN.md; returns the images, that head and the PR block."""
    import look

    (project / ".gitignore").write_text(".hard-eng/\n")
    (project / "DESIGN.md").write_text(DESIGN)
    commit(project, "design")
    images = make_images(project, 1)
    install_agent(tmp_path, "claude", 1, good_answer(1))
    block = look.block_text(run_look(project, "claude", images))
    return images, git(project, "rev-parse", "HEAD"), block


def test_a_merged_pr_still_passes_after_the_base_changes_design_md(
    tmp_path: Path, project: Path
) -> None:
    import ui_proof

    images, head, block = look_at_a_design(tmp_path, project)
    after = [images[0].read_bytes()]
    assert ui_proof.look_problem(project, head, block, after) is None
    (project / "DESIGN.md").write_text(LATER_DESIGN)
    commit(project, "the base changes the design after the merge")
    assert ui_proof.look_problem(project, head, block, after) is None


def test_a_record_that_judged_another_design_than_the_pr_head_still_fails(
    tmp_path: Path, project: Path
) -> None:
    import look
    import ui_proof

    (project / ".gitignore").write_text(".hard-eng/\n")
    (project / "DESIGN.md").write_text(DESIGN)
    commit(project, "design")
    (project / "DESIGN.md").write_text(LATER_DESIGN)
    images = make_images(project, 1)
    install_agent(tmp_path, "claude", 1, good_answer(1))
    block = look.block_text(run_look(project, "claude", images))
    (project / "DESIGN.md").write_text(DESIGN)
    head = git(project, "rev-parse", "HEAD")
    problem = ui_proof.look_problem(project, head, block, [images[0].read_bytes()])
    assert problem is not None and "current DESIGN.md" in problem


def test_the_design_hash_reads_crlf_text_the_same_from_the_disk_and_a_commit(
    tmp_path: Path, project: Path
) -> None:
    import look

    (project / "DESIGN.md").write_bytes(
        b"# Design\r\n\r\n## Overview\r\nBrand navy.\r\n"
    )
    head = commit(project, "design with Windows line ends")
    assert look.design_hash(project) == look.design_hash(project, head)
    assert look.design_text(project) == look.design_text(project, head)


def test_a_carried_record_still_backs_the_head_after_the_base_changes_design_md(
    tmp_path: Path, project: Path
) -> None:
    import look
    import look_records
    import ui_proof
    from test_look_carry import clean_look_then_new_head

    (project / "DESIGN.md").write_text(DESIGN)
    images, old, new = clean_look_then_new_head(
        tmp_path, project, plan=True, measured=True
    )
    found = look_records.records_for(project, new)
    assert [record["carried_from"] for record in found] == [old]
    block = look.block_text(found[0])
    plan_rel = "features/kpi-board/PLAN.md"
    digest = look.plan_scope(project, Path(plan_rel), new)[2]
    after = [images[0].read_bytes()]
    (project / "DESIGN.md").write_text(LATER_DESIGN)
    commit(project, "the base changes the design after the merge")
    assert ui_proof.look_problem(project, new, block, after, plan_rel, digest) is None


def test_a_carried_record_reads_the_design_of_its_own_revision_not_the_checkout(
    tmp_path: Path, project: Path
) -> None:
    import look_records
    import ui_measure
    from test_look_facts import text_fact, values

    (project / ".gitignore").write_text(".hard-eng/\n")
    (project / "DESIGN.md").write_text(
        "---\ncolors:\n  ink: '#1a1a1a'\n---\n# Design\n\n## Overview\nBrand navy.\n"
    )
    commit(project, "design")
    images = make_images(project, 1)
    measured = values(texts=[text_fact("Save")])
    ui_measure.write_record(project, images[0], 1280, [], "/kpi", measured=measured)
    install_agent(tmp_path, "claude", 1, good_answer(1))
    run_look(project, "claude", images)
    old = git(project, "rev-parse", "HEAD").strip()
    (project / "notes.txt").write_text("a change that the reviewer never reads\n")
    commit(project, "unrelated change")
    new = git(project, "rev-parse", "HEAD").strip()
    (project / "DESIGN.md").write_text(
        "---\ncolors:\n  text: '#1a1a1a'\n---\n# Design\n\n## Overview\nBrand navy.\n"
    )
    found = look_records.records_for(project, new)
    assert [record["carried_from"] for record in found] == [old]


def test_the_design_hash_of_a_revision_ignores_the_checkout(
    tmp_path: Path, project: Path
) -> None:
    import look

    _, head, _ = look_at_a_design(tmp_path, project)
    wanted, text = look.design_hash(project), look.design_text(project)
    (project / "DESIGN.md").write_text(LATER_DESIGN)
    assert look.design_hash(project) != wanted
    assert look.design_hash(project, head) == wanted
    assert look.design_text(project, head) == text
    with pytest.raises(ValueError, match="not in this checkout"):
        look.design_hash(project, "1" * 40)
