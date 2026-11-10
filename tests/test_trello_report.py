from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from test_trello_board import ours
from trello_fakes import Project, ago, comment, edit_comment, make_card, refs
from trello_fixtures import load_mods, make_project

parse_time = datetime.fromisoformat

mods = pytest.fixture(load_mods)
project = pytest.fixture(make_project)


def wake(project: Project) -> dict[str, object]:
    result = project.run("check")
    assert result.code == 0, result.text
    return {name: result.payload[name] for name in project.mods.report.WAKE_FIELDS}


def hours_ahead(found: dict[str, object], hours: float) -> bool:
    due = parse_time(str(found["nextDue"]))
    return abs(due - (datetime.now(UTC) + timedelta(hours=hours))) < timedelta(
        minutes=1
    )


@pytest.mark.parametrize(("minutes", "idle"), [(59, False), (61, True)])
def test_the_board_goes_idle_only_after_the_stop_time(
    project: Project, minutes: int, idle: bool
) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    project.fake.actions.append(
        comment("s1", 1, "m-sam", "The total is wrong", minutes / 60)
    )
    ours(project, ("a1", 1, "**Fixed.** The total shows now.", 0.5))
    found = wake(project)
    assert found["idle"] is idle
    assert found["quietMinutes"] == minutes


def test_an_unanswered_request_keeps_a_quiet_board_awake(project: Project) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    project.fake.actions.append(comment("s1", 1, "m-sam", "The total is wrong", 3))
    found = wake(project)
    assert found["idle"] is False
    assert found["quietMinutes"] == 180


def test_our_own_comments_never_count_as_heard(project: Project) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    ours(project, ("a1", 1, "**Fixed.** The total shows now.", 5))
    found = wake(project)
    assert found["idle"] is False
    assert found["quietMinutes"] == 0


def test_next_due_is_the_earliest_promise_chase_or_due_date(
    project: Project,
) -> None:
    due = ago(-2)
    project.fake.cards = [
        make_card(1, "#1 Card", "l-doing"),
        make_card(2, "#2 Card", "l-doing"),
        make_card(3, "#3 Card", "l-doing", due=due),
    ]
    ours(
        project,
        ("a1", 1, "**Accepted.** I will post the fix tonight.", 1),
        ("a2", 2, "@sam can you confirm the total?", 20),
    )
    assert wake(project)["nextDue"] == due


def test_next_due_is_the_promise_when_it_comes_first(project: Project) -> None:
    project.fake.cards = [
        make_card(1, "#1 Card", "l-doing"),
        make_card(2, "#2 Card", "l-doing"),
        make_card(3, "#3 Card", "l-doing", due=ago(-2)),
    ]
    ours(
        project,
        ("a1", 1, "**Accepted.** I will post the fix tonight.", 5),
        ("a2", 2, "@sam can you confirm the total?", 20),
    )
    assert hours_ahead(wake(project), 1)


def test_a_ticked_due_date_is_not_overdue(project: Project) -> None:
    project.fake.cards = [
        make_card(1, "#1 Card", "l-doing", due=ago(3), dueComplete=True),
        make_card(2, "#2 Card", "l-doing", due=ago(3)),
    ]
    assert refs(project.report()["overdue"]) == {"2"}


def test_next_due_is_a_chase_and_never_beyond_chase_hours(project: Project) -> None:
    project.fake.cards = [make_card(n, f"#{n} Card", "l-doing") for n in (1, 2)]
    ours(project, ("a1", 1, "@sam can you confirm the total?", 20))
    assert hours_ahead(wake(project), 4)
    project.finish()
    project.fake.cards = project.fake.cards[1:]
    assert hours_ahead(wake(project), 24)


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
