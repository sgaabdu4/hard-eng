import json
import os
from pathlib import Path

import pytest
from test_trello_coordinator import first_cells, sections
from trello_fakes import SKILL, Mods, Project, make_card, picture
from trello_fixtures import load_mods, make_project

mods = pytest.fixture(load_mods)
project = pytest.fixture(make_project)


def write_proof(shot: Path, proof: object) -> Path:
    sidecar = Path(f"{shot}.json")
    sidecar.unlink(missing_ok=True)
    if proof is not None:
        sidecar.write_text(proof if isinstance(proof, str) else json.dumps(proof))
    return sidecar


def test_a_picture_needs_a_current_proof_file(project: Project, tmp_path: Path) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    rules = dict.fromkeys(project.mods.commands.UI_RULES, "Checked on the picture.")
    base = {"change": "The total shows", "shows": "The list", "showsChange": True}
    good = base | {"uiRules": rules}
    shot = picture(tmp_path / "shot.png")
    refused: list[tuple[object, str]] = [
        (None, "No proof file"),
        ("not json", "JSON object"),
        ([], "JSON object"),
        ({**base, "showsChange": "yes"}, "showsChange"),
        ({"shows": "The list", "showsChange": True, "uiRules": rules}, "change"),
        (base, "uiRules.idiotProof"),
        ({**base, "uiRules": rules | {"nothingLost": "too short"}}, "nothingLost"),
        ({**base, "notNewUi": " "}, "notNewUi"),
    ]
    for proof, named in refused:
        write_proof(shot, proof)
        for flags in ((), ("--dry-run",)):
            result = project.run("upload", "1", str(shot), *flags)
            error = str(result.payload["error"])
            assert result.code == 1, proof
            assert "shot.png" in error and named in error, error
    sidecar = write_proof(shot, good)
    os.utime(sidecar, (os.path.getmtime(shot) - 60,) * 2)
    stale = project.run("upload", "1", str(shot))
    assert stale.code == 1
    assert "older" in str(stale.payload["error"])
    late = picture(tmp_path / "late.png")
    write_proof(shot, None)
    assert project.run("upload", "1", str(late), str(shot)).code == 1
    assert project.fake.writes == []
    for proof in (good, base | {"notNewUi": "An existing screen"}):
        write_proof(shot, proof)
        assert project.run("upload", "1", str(shot)).code == 0, proof
    paper = tmp_path / "plan.pdf"
    paper.write_bytes(b"pdf")
    assert project.run("upload", "1", str(paper)).code == 0


def test_a_new_screen_post_ends_with_the_closing_line(
    project: Project, tmp_path: Path
) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    commands = project.mods.commands
    rules = dict.fromkeys(commands.UI_RULES, "Checked on the picture.")
    note = tmp_path / "note.txt"
    note.write_text(
        "**Here is the new list.**\n\n@sam reply yes, or say what to change."
    )
    old = picture(tmp_path / "old.png")
    new = picture(tmp_path / "new.png", uiRules=rules)
    posts = []
    for images in ([old], [old, new]):
        flags = [part for image in images for part in ("--image", str(image))]
        result = project.run("comment", "1", str(note), *flags)
        assert result.code == 0, result.text
        sent = [c for c in project.fake.writes if c.path.endswith("/comments")]
        posts.append(sent[-1].form["text"])
    assert commands.CLOSING not in posts[0]
    last_picture = "![new.png](https://files.example.test/att-3.png)"
    assert posts[1].endswith(f"{last_picture}\n\n{commands.CLOSING}")


def test_mockup_rules_match_the_proof_gate(mods: Mods) -> None:
    text = (SKILL / "references/mockups.md").read_text()
    rules = sections(text)["Proof rules"]
    assert tuple(first_cells(rules)) == mods.commands.UI_RULES
    assert mods.commands.CLOSING in text
