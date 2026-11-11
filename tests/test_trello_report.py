from pathlib import Path

import pytest
from test_trello_board import ours
from trello_fakes import (
    CONFIG,
    Project,
    ago,
    comment,
    edit_comment,
    make_action,
    make_card,
    move_action,
    refs,
)
from trello_fixtures import load_mods, make_project

mods = pytest.fixture(load_mods)
project = pytest.fixture(make_project)


def with_list(project: Project, role: str, name: str) -> None:
    lists = CONFIG["lists"]
    assert isinstance(lists, dict)
    project.fake.lists.append({"id": f"l-{role}", "name": name})
    project.configure(lists={**lists, role: name})


def test_an_open_card_nobody_touched_is_listed_as_idle(project: Project) -> None:
    with_list(project, "urgent", "Urgent")
    project.fake.cards = [
        make_card(1, "#1 Card", "l-todo", dateLastActivity=ago(50)),
        make_card(2, "#2 Card", "l-doing", dateLastActivity=ago(50)),
        make_card(3, "#3 Card", "l-urgent", dateLastActivity=ago(50)),
        make_card(4, "#4 Card", "l-doing", dateLastActivity=ago(2)),
    ]
    idle = project.report()["idle"]
    assert refs(idle) == {"1", "2", "3"}
    doing = next(found for found in idle if found["card"] == "2")
    assert doing["excerpt"] == "50 hours in Doing with no comment or move"


def test_a_recent_comment_or_move_keeps_an_open_card_off_the_idle_list(
    project: Project,
) -> None:
    with_list(project, "discuss", "Discuss")
    old = {"dateLastActivity": ago(50)}
    project.fake.cards = [
        make_card(1, "#1 Card", "l-doing", **old),
        make_card(2, "#2 Card", "l-todo", **old),
        make_card(3, "#3 Card", "l-testing", **old),
        make_card(4, "#4 Card", "l-done", **old),
        make_card(5, "#5 Card", "l-discuss", **old),
    ]
    project.fake.cards.append(make_card(6, "#6 Card", "l-doing", **old))
    project.fake.actions += [
        comment("c1", 1, "m-sam", "The total is 40.", 2),
        move_action("v2", 2, "l-todo", 3, name="To do"),
    ]
    ours(project, ("o6", 6, "**Working on it.** The export runs tonight.", 2))
    assert project.report()["idle"] == []


def test_a_bumped_last_activity_does_not_hide_an_idle_card(project: Project) -> None:
    project.fake.cards = [
        make_card(1, "#1 Card", "l-doing", dateLastActivity=ago(0.1)),
        make_card(2, "#2 Card", "l-todo", id="65a1b2c30000000000000000"),
        make_card(3, "#3 Card", "l-doing", dateLastActivity=ago(0.1)),
    ]
    project.fake.actions += [
        comment("c1", 1, "m-sam", "The total is 40.", 50),
        make_action(
            "i1", "addAttachmentToCard", 1, "m-sam", 1, attachment={"name": "a.png"}
        ),
        comment("c3", 3, "m-sam", "The total is 40.", 50),
        make_action("d3", "updateCard", 3, "m-sam", 1, old={"desc": ""}),
    ]
    assert refs(project.report()["idle"]) == {"1", "2", "3"}


def test_a_ticked_due_date_is_not_overdue(project: Project) -> None:
    project.fake.cards = [
        make_card(1, "#1 Card", "l-doing", due=ago(3), dueComplete=True),
        make_card(2, "#2 Card", "l-doing", due=ago(3)),
    ]
    assert refs(project.report()["overdue"]) == {"2"}


def test_a_chase_restarts_the_silent_clock(project: Project) -> None:
    project.fake.cards = [make_card(n, f"#{n} Card", "l-doing") for n in (1, 2)]
    ask = "@sam can you confirm the total?"
    chase = "@sam still waiting: can you confirm the total?"
    ours(
        project,
        ("a1", 1, ask, 60),
        ("b1", 1, chase, 0.2),
        ("a2", 2, ask, 60),
        ("b2", 2, chase, 30),
    )
    silent = project.report()["silent"]
    assert refs(silent) == {"2"}
    assert silent[0]["excerpt"] == chase


def test_a_testing_comment_keeps_the_tester_label(
    project: Project, tmp_path: Path
) -> None:
    project.fake.cards = [make_card(5, "#5 Job", "l-doing")]
    note = tmp_path / "n.txt"
    note.write_text("**Ready to try.**\n\n@sam the export is live now.")
    moved = project.run(
        "move", "5", "testing", "--comment", str(note), "--check", "Tap Export."
    )
    assert moved.code == 0, moved.text
    project.fake.cards[0]["idLabels"] = ["lb-sam"]
    report = project.report()
    assert report["labels"] == []
    assert refs(report["testQueue"]) == {"5"}
    project.finish()
    project.fake.actions.append(comment("s1", 5, "m-sam", "Works for me", -0.1))
    gap = project.report()["labels"]
    assert gap and "no open question" in gap[0]["excerpt"]


def test_buried_leaves_testers_on_testing_cards_alone(project: Project) -> None:
    project.fake.cards = [make_card(5, "#5 Job", "l-testing", idLabels=["lb-sam"])]
    ours(
        project,
        ("a1", 5, "**Ready to try.**\n\n@sam please check the total.", 30),
        ("b1", 5, "@pat thanks, I noted that.", 1),
    )
    report = project.report()
    assert report["buried"] == []
    assert report["silent"] == []
    assert refs(report["testQueue"]) == {"5"}


def test_an_edit_of_our_own_comment_keeps_its_date(project: Project) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    ours(project, ("a1", 1, "**Done.** The total shows now.", 5))
    project.fake.actions.append(
        comment("s1", 1, "m-sam", "The total is wrong on the second page", 3)
    )
    assert refs(project.report()["requests"]) == {"1"}
    project.finish()
    edit_comment(
        project.fake.actions[0], -0.03, "**Done.** The total shows now (typo)."
    )
    project.fake.cards[0]["dateLastActivity"] = ago(0)
    assert refs(project.report()["requests"]) == {"1"}
