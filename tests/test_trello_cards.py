"""A card list item for a second card of one client, and a card whose fix waits in an open PR."""

import json

import pytest
from test_trello_board import is_listed_as_waiting
from trello_fakes import CONFIG, Project, make_card
from trello_fixtures import load_mods, make_project

mods = pytest.fixture(load_mods)
project = pytest.fixture(make_project)


def test_a_second_open_card_for_the_same_client_is_listed_unless_it_is_marked_checked(
    project: Project,
) -> None:
    config = CONFIG | {"clientPattern": r"\[(C-\d+)\]", "checkedLabel": "Checked"}
    (project.main / "trello.json").write_text(json.dumps(config))
    project.fake.labels.append({"id": "lb-checked", "name": "Checked"})
    project.fake.cards = [
        make_card(1, "#1 [C-7] Fix the login page", "l-doing"),
        make_card(2, "#2 [C-7] Fix the login page again", "l-todo"),
        make_card(3, "#3 [C-8] Change the invoice list", "l-doing"),
        make_card(
            4, "#4 [C-7] Export the member list", "l-todo", idLabels=["lb-checked"]
        ),
        make_card(5, "#5 [C-7] Old login fix", "l-done"),
        make_card(6, "#6 Card for no client", "l-doing"),
    ]
    found = project.report()["unnumbered"]
    assert [item["url"] for item in found] == ["https://trello.com/c/sl2"]
    assert "C-7" in found[0]["excerpt"]


def test_a_card_with_an_unnamed_label_is_not_checked_when_no_checked_label_is_set(
    project: Project,
) -> None:
    config = CONFIG | {"clientPattern": r"\[(C-\d+)\]"}
    (project.main / "trello.json").write_text(json.dumps(config))
    project.fake.labels.append({"id": "lb-green", "name": ""})
    project.fake.cards = [
        make_card(1, "#1 [C-7] Fix the login page", "l-doing"),
        make_card(2, "#2 [C-7] Fix it again", "l-todo", idLabels=["lb-green"]),
    ]
    found = project.report()["unnumbered"]
    assert [item["url"] for item in found] == ["https://trello.com/c/sl2"]


def test_two_cards_with_no_client_setting_are_not_compared_by_client(
    project: Project,
) -> None:
    project.fake.cards = [
        make_card(1, "#1 [C-7] Fix the login page", "l-doing"),
        make_card(2, "#2 [C-7] Fix the login page again", "l-todo"),
    ]
    assert project.report()["unnumbered"] == []


@pytest.mark.parametrize(
    "role,text,listed",
    [
        ("l-doing", "The fix is in an open PR and waits for review.", True),
        ("l-doing", "Waiting for the pull request to merge.", True),
        ("l-doing", "The fix is in an open PR. It went live today.", False),
        ("l-doing", "Should the fix wait in an open PR?", False),
        ("l-doing", "I am fixing the button colour.", False),
        ("l-todo", "The fix is in an open PR and waits for review.", False),
        ("l-testing", "The fix is in an open PR and waits for review.", True),
    ],
)
def test_a_card_whose_fix_waits_in_an_open_pr_is_listed_in_doing_and_testing(
    project: Project, role: str, text: str, listed: bool
) -> None:
    assert is_listed_as_waiting(project, role, text) == listed
