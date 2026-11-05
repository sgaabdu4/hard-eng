import io
import json
import threading
import urllib.request
from datetime import UTC, datetime, timedelta
from http.client import HTTPMessage
from pathlib import Path

import pytest
from conftest import git
from trello_fakes import (
    BOARD,
    CONFIG,
    KEY,
    TOKEN,
    Mods,
    Project,
    comment,
    lease_owner,
    make_card,
    refs,
    write_lease,
)
from trello_fixtures import load_mods, make_project

mods = pytest.fixture(load_mods)
project = pytest.fixture(make_project)


def test_finish_only_ends_its_own_lease(project: Project) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    assert project.run("check").code == 0
    run_a = project.run_id
    write_lease(project, run_a, 31)
    assert project.run("check").code == 0
    run_b = project.run_id
    assert run_a != run_b
    assert project.run("finish", run_a).payload == {"finished": False}
    assert lease_owner(project) == run_b
    assert project.run("finish", run_b).payload == {"finished": True}
    assert not (project.state / "lease").exists()


def test_a_stale_lease_is_taken_by_one_run_only(project: Project, mods: Mods) -> None:
    project.state.mkdir(parents=True)
    write_lease(project, "old", 31)
    winners: list[str | None] = []
    start = threading.Barrier(8)

    def contend() -> None:
        start.wait()
        winners.append(mods.state.take_lease(project.state, 15))

    threads = [threading.Thread(target=contend) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len([w for w in winners if w]) == 1
    assert lease_owner(project) in winners


@pytest.mark.parametrize(
    "text,listed",
    [
        ("I will tell you when it is live", True),
        ("I'll update the card once it is live", True),
        ("Next: test it after it is live", True),
        ("I will wait until it is live", True),
        ("I will send the link. The fix is now live.", False),
        ("Next: nothing. It is done.", False),
    ],
)
def test_promises_ignore_conditional_live(
    project: Project, text: str, listed: bool
) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    project.fake.actions = [comment("ours-1", 1, "m-owner", text, 8)]
    project.mods.state.log_posted(project.state, "ours-1")
    assert (refs(project.report()["promises"]) == {"1"}) == listed


@pytest.mark.parametrize(
    "text,listed",
    [
        ("Not built yet. I will tell you when it is live", True),
        ("This waits for the next release, until it is live", True),
        ("Not built yet. The fix is now live", False),
    ],
)
def test_waits_on_us_ignores_conditional_live(
    project: Project, text: str, listed: bool
) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-testing")]
    project.fake.actions = [comment("ours-1", 1, "m-owner", text, 2)]
    project.mods.state.log_posted(project.state, "ours-1")
    assert (refs(project.report()["waitsOnUs"]) == {"1"}) == listed


def test_owner_comment_stays_listed_until_we_reply(
    project: Project, tmp_path: Path
) -> None:
    project.fake.cards = [make_card(3, "#3 Owner", "l-doing")]
    project.fake.actions = [
        comment("old", 3, "m-owner", "Before the first check", 5),
        comment("mid", 3, "m-owner", "During the first read", -0.01),
    ]
    first = project.report()
    assert [item["excerpt"] for item in first["owner"]] == ["During the first read"]
    project.finish()
    assert refs(project.report()["owner"]) == {"3"}
    project.finish()
    note = tmp_path / "note.txt"
    note.write_text("Thanks, I added it to the list")
    assert project.run("comment", "3", str(note)).code == 0
    report = project.report()
    assert report["owner"] == []
    assert report["requests"] == []
    assert report["information"] == []


def test_a_reply_clears_the_request_across_two_checks(
    project: Project, tmp_path: Path
) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    project.fake.actions = [comment("a1", 1, "m-sam", "Please add the export", 5)]
    assert refs(project.report()["requests"]) == {"1"}
    project.finish()
    note = tmp_path / "note.txt"
    note.write_text("Added, it is in review")
    assert project.run("comment", "1", str(note)).code == 0
    report = project.report()
    assert report["requests"] == []
    assert report["information"] == []


def test_card_prints_the_whole_card_and_hides_secrets(project: Project) -> None:
    due = "2026-12-01T10:00:00.000Z"
    project.fake.cards = [
        make_card(1, "#1 Card", "l-doing", idLabels=["lb-sam"], due=due)
    ]
    project.fake.descriptions = {"card1": f"Spec with {TOKEN}"}
    shot: dict[str, object] = {
        "id": "att9",
        "name": "shot.png",
        "date": due,
        "isUpload": True,
        "url": "https://files.example.test/shot.png",
    }
    project.fake.attachments = [shot]
    project.fake.actions = [
        comment("a2", 1, "m-owner", "Second", 1),
        comment("a1", 1, "m-sam", "First", 2),
        comment("x", 2, "m-pat", "Other card", 2),
    ]
    dates = {str(a["id"]): a["date"] for a in project.fake.actions}
    result = project.run("card", "1")
    assert result.code == 0, result.text
    assert result.payload == {
        "name": "#1 Card",
        "list": "Doing",
        "labels": ["Needs Sam"],
        "due": due,
        "description": "Spec with ***",
        "comments": [
            {"author": "sam", "date": dates["a1"], "text": "First"},
            {"author": "owner", "date": dates["a2"], "text": "Second"},
        ],
        "attachments": [
            {
                "id": "att9",
                "name": "shot.png",
                "url": "https://files.example.test/shot.png",
                "date": due,
            }
        ],
    }
    assert project.fake.writes == []
    assert TOKEN not in result.text


def test_update_renames_and_sets_the_due_date(project: Project) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    due = "2026-12-01T10:00:00Z"
    done = project.run("update", "1", "--name", "#1 New name", "--due", due)
    assert done.code == 0, done.text
    (put,) = project.fake.writes
    assert (put.method, put.path) == ("PUT", "/cards/card1")
    assert put.form == {"name": "#1 New name", "due": due}
    for argv in (["update", "1"], ["update", "1", "--due", "next week"]):
        assert project.run(*argv).code == 1
    planned = project.run("update", "1", "--name", "Other", "--dry-run")
    assert isinstance(planned.payload["dryRun"], list)
    assert len(project.fake.writes) == 1


def test_redirects_leave_the_trello_host_without_credentials(mods: Mods) -> None:
    handler = mods.api.StripAuthRedirects()
    request = urllib.request.Request(
        "https://api.trello.com/1/cards/x?key=k&token=t",
        headers={"Authorization": "OAuth secret"},
    )

    def follow(target: str) -> urllib.request.Request:
        moved = handler.redirect_request(
            request, io.BytesIO(), 302, "Found", HTTPMessage(), target
        )
        assert moved is not None
        return moved

    outside = follow("https://files.example.test/a.png?key=k&token=t&size=2")
    assert outside.get_header("Authorization") is None
    assert "key=" not in outside.full_url
    assert "token=" not in outside.full_url
    assert "size=2" in outside.full_url
    inside = follow("https://api.trello.com/1/cards/y")
    assert inside.get_header("Authorization") == "OAuth secret"
    assert any(
        isinstance(h, mods.api.StripAuthRedirects) for h in mods.api.OPENER.handlers
    )


class Failing:
    def __init__(self, error: OSError) -> None:
        self.error = error

    def open(self, *_args: object, **_kwargs: object) -> object:
        raise self.error


@pytest.mark.parametrize(
    "error", [TimeoutError("timed out"), ConnectionResetError("reset")]
)
def test_network_failures_print_a_json_error(
    project: Project, monkeypatch: pytest.MonkeyPatch, error: OSError
) -> None:
    monkeypatch.setattr(project.mods.api, "transport", project.real_transport)
    monkeypatch.setattr(project.mods.api, "OPENER", Failing(error))
    result = project.run("check")
    assert result.code == 1
    assert "could not be reached" in str(result.payload["error"])


def board_with_five_requests(project: Project) -> None:
    project.fake.cards = [make_card(n, f"#{n} Card", "l-doing") for n in range(1, 6)]
    project.fake.actions = [
        comment(f"a{n}", n, "m-sam", "Please", 6 - n) for n in range(1, 6)
    ]


def test_activity_paging_reads_every_page(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(project.mods.board, "PAGE", 2)
    board_with_five_requests(project)
    assert refs(project.report()["requests"]) == {"1", "2", "3", "4", "5"}
    pages = [c for c in project.fake.calls if c.path == f"/boards/{BOARD}/actions"]
    assert [c.query.get("before") for c in pages] == [None, "a4", "a2"]
    assert {c.query["limit"] for c in pages} == {"2"}


def test_activity_paging_stops_when_it_does_not_advance(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(project.mods.board, "PAGE", 2)
    board_with_five_requests(project)
    project.fake.ignore_before = True
    result = project.run("check")
    assert result.code == 1
    assert "paging" in str(result.payload["error"]).lower()
    assert not (project.state / "state.json").exists()


@pytest.mark.parametrize("name", ["call 07700 900123.png", "jo.smith@example.com.png"])
def test_comment_privacy_covers_image_names(
    project: Project, tmp_path: Path, name: str
) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    note, image = tmp_path / "note.txt", tmp_path / name
    note.write_text("All good")
    image.write_bytes(b"fake image")
    result = project.run("comment", "1", str(note), "--image", str(image))
    assert result.code == 1
    assert project.fake.writes == []


@pytest.mark.parametrize(
    "name,accepted",
    [
        ("notes.txt", False),
        ("clip.mp4", False),
        ("proof.PNG", True),
        ("proof.webp", True),
        ("proof.jpeg", True),
    ],
)
def test_testing_proof_must_be_an_image(
    project: Project, tmp_path: Path, name: str, accepted: bool
) -> None:
    project.fake.cards = [make_card(5, "#5 Move", "l-doing")]
    proof = tmp_path / name
    proof.write_bytes(b"fake image")
    result = project.run("move", "5", "testing", "--proof", str(proof))
    assert (result.code == 0) == accepted
    assert bool(project.fake.writes) == accepted


def test_detach_deletes_only_the_named_attachments(project: Project) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    done = project.run("detach", "1", "att1", "att3")
    assert done.code == 0, done.text
    assert done.payload == {"detached": ["att1", "att3"]}
    assert [(c.method, c.path) for c in project.fake.writes] == [
        ("DELETE", "/cards/card1/attachments/att1"),
        ("DELETE", "/cards/card1/attachments/att3"),
    ]
    planned = project.run("detach", "1", "att2", "--dry-run")
    assert isinstance(planned.payload["dryRun"], list)
    project.fake.account = "intruder"
    refused = project.run("detach", "1", "att2")
    assert refused.code == 1
    assert "another account" in str(refused.payload["error"])
    assert len(project.fake.writes) == 2


def test_owner_reply_before_a_missing_first_check_is_kept(project: Project) -> None:
    project.fake.cards = [make_card(3, "#3 Owner", "l-doing")]
    project.fake.actions = [comment("o1", 3, "m-owner", "Yes, go ahead", 0.5)]
    project.state.mkdir(parents=True)
    read_at = datetime.now(UTC) - timedelta(hours=1)
    project.mods.state.save_state(project.state, {"checkedAt": read_at.isoformat()})
    assert refs(project.report()["owner"]) == {"3"}


@pytest.mark.parametrize(
    "text,labelled,listed",
    [
        ("Thanks @sam, it is live now.", False, False),
        ("Thanks @sam, it is live now.", True, True),
        ("@sam can you confirm?", False, True),
        ("@sam please reply with the page name", True, False),
    ],
)
def test_labels_follow_open_questions_not_any_tag(
    project: Project, text: str, labelled: bool, listed: bool
) -> None:
    extra = {"idLabels": ["lb-sam"]} if labelled else {}
    project.fake.cards = [make_card(1, "#1 Card", "l-doing", **extra)]
    project.fake.actions = [comment("ours-1", 1, "m-owner", text, 30)]
    project.mods.state.log_posted(project.state, "ours-1")
    report = project.report()
    assert (refs(report["labels"]) == {"1"}) == listed
    assert (refs(report["silent"]) == {"1"}) == ("?" in text or "please" in text)


def test_repeated_image_flags_attach_every_image(
    project: Project, tmp_path: Path
) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    note = tmp_path / "note.txt"
    note.write_text("Before and after")
    shots = [tmp_path / "before.png", tmp_path / "after.png"]
    for shot in shots:
        shot.write_bytes(b"fake image")
    result = project.run(
        "comment", "1", str(note), "--image", str(shots[0]), "--image", str(shots[1])
    )
    assert result.code == 0, result.text
    uploads = [c for c in project.fake.writes if c.path.endswith("/attachments")]
    assert len(uploads) == 2


def paste(folder: Path, name: str, value: str) -> str:
    pasted = folder / name
    pasted.write_text(value + "\n")
    return str(pasted)


def test_save_secret_fills_the_main_checkout_from_a_worktree(
    project: Project, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = project.main / ".env.trello.local"
    env.write_text("# kept\nTRELLO_KEY=old\n")
    worktree = tmp_path / "worktree"
    git(project.main, "worktree", "add", "-q", str(worktree))
    monkeypatch.chdir(worktree)
    for name, value in (("TRELLO_KEY", KEY), ("TRELLO_TOKEN", TOKEN)):
        saved = project.run("save-secret", name, paste(tmp_path, name, value))
        assert saved.code == 0, saved.text
        assert saved.payload == {"saved": name}
        assert value not in saved.text
    assert env.read_text() == f"# kept\nTRELLO_KEY={KEY}\nTRELLO_TOKEN={TOKEN}\n"
    assert env.stat().st_mode & 0o777 == 0o600
    assert not (worktree / ".env.trello.local").exists()
    assert project.run("probe").code == 0


@pytest.mark.parametrize("value", ["", "two words"])
def test_save_secret_refuses_a_bad_paste(
    project: Project, tmp_path: Path, value: str
) -> None:
    env = project.main / ".env.trello.local"
    before = env.read_text()
    refused = project.run("save-secret", "TRELLO_TOKEN", paste(tmp_path, "t", value))
    assert refused.code == 1
    assert "TRELLO_TOKEN" in str(refused.payload["error"])
    assert env.read_text() == before


def test_save_secret_ignores_the_file_without_a_tracked_change(
    project: Project, tmp_path: Path
) -> None:
    (project.main / ".gitignore").write_text("")
    git(project.main, "add", ".gitignore")
    git(project.main, "commit", "-qm", "no ignore")
    (project.main / ".env.trello.local").unlink()
    saved = project.run("save-secret", "TRELLO_KEY", paste(tmp_path, "k", KEY))
    assert saved.code == 0, saved.text
    assert KEY not in saved.text
    exclude = project.main / ".git/info/exclude"
    assert ".env.trello.local" in exclude.read_text().splitlines()
    status = git(project.main, "status", "--porcelain")
    assert ".env.trello.local" not in status


def test_save_secret_refuses_a_tracked_file(project: Project, tmp_path: Path) -> None:
    git(project.main, "add", "-f", ".env.trello.local")
    git(project.main, "commit", "-qm", "tracked by mistake")
    before = (project.main / ".env.trello.local").read_text()
    refused = project.run("save-secret", "TRELLO_KEY", paste(tmp_path, "k", "new"))
    assert refused.code == 1
    assert (project.main / ".env.trello.local").read_text() == before


def test_without_allowed_every_board_member_makes_requests(project: Project) -> None:
    config = {name: value for name, value in CONFIG.items() if name != "allowed"}
    (project.main / "trello.json").write_text(json.dumps(config))
    project.fake.cards = [make_card(n, f"#{n} Card", "l-doing") for n in (1, 2)]
    project.fake.actions = [
        comment("a1", 1, "m-pat", "From a board member", 5),
        comment("a2", 2, "m-gone", "From someone no longer on the board", 5),
    ]
    report = project.report()
    assert refs(report["requests"]) == {"1"}
    assert refs(report["information"]) == {"2"}


def test_a_board_link_alone_is_enough(project: Project) -> None:
    link = f"https://trello.com/b/{BOARD}/my-board"
    (project.main / "trello.json").write_text(json.dumps({"board": link}))
    probe = project.run("probe")
    assert probe.code == 0, probe.text
    assert probe.payload["account"] == "owner"
    rows = probe.payload["lists"]
    assert isinstance(rows, list)
    roles = {str(row["role"]): str(row["name"]) for row in rows}
    assert roles == {
        "todo": "To do",
        "doing": "Doing",
        "testing": "Testing",
        "done": "Done",
    }
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    project.fake.actions = [comment("a1", 1, "m-pat", "Please add it", 5)]
    assert refs(project.report()["requests"]) == {"1"}


def test_a_board_without_a_needed_list_names_it(project: Project) -> None:
    (project.main / "trello.json").write_text(json.dumps({"board": BOARD}))
    project.fake.lists = [{"id": "l-todo", "name": "Backlog"}]
    refused = project.run("probe")
    assert refused.code == 1
    assert "doing" in str(refused.payload["error"])
