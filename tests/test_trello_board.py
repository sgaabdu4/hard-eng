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
    ago,
    checklist,
    comment,
    create_action,
    edit_comment,
    lease_owner,
    make_action,
    make_card,
    move_action,
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
        ("The fix is now live. I will check the totals tomorrow.", True),
        ("I am changing the screen", True),
        ("I am building the export", True),
        ("The export went live. Nothing more to do.", False),
        ("The new screens are live.", False),
        ("If it still fails, I will fix it today.", False),
        ("I post here when the store answers.", True),
        ("I check the next new order and post here who it was.", True),
        ("I'm adding the export now.", True),
        ("I am checking the logs.", True),
        ("I am testing it on the new build now.", True),
        ("I am going to move it today.", True),
        ("The report is being fixed.", True),
        ("I'll post the new build tonight, can you test it tomorrow?", True),
        ("I checked the logs. Nothing is wrong.", False),
        ("Can I check the totals with you?", False),
        ("Fixed in the new build. I move this card to Testing.", False),
        ("I tag @sam to test it.", False),
        ("I confirm the crash is gone.", False),
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
        ("I am building it", True),
        ("I am changing the screen", True),
        ("I will fix it", True),
        ("The export is being built", True),
        ("This waits for the #12 fix", True),
        ("I will fix it. The fix went live", False),
        ("Not built yet. The screens are live", False),
        ("Try it again. If it still fails, I will fix it today.", False),
        ("Should the menu change wait for the next release?", False),
        ("I am fixing the button colour.", True),
        ("I am fixing the crash now, can you send the log?", True),
        ("Next release has it. It is now live on the test site, can you check?", False),
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


def test_card_prints_the_whole_card_and_hides_secrets(project: Project) -> None:
    due = "2026-12-01T10:00:00.000Z"
    project.fake.cards = [
        make_card(
            1, "#1 Card", "l-doing", idLabels=["lb-sam"], idMembers=["m-sam"], due=due
        )
    ]
    project.fake.checklists = {
        "card1": checklist(
            ("ci1", "Check total", "complete"),
            ("ci2", "Check export", "incomplete"),
        )
    }
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
        "members": ["sam"],
        "checklists": [
            {
                "name": "Steps",
                "items": [
                    {"name": "Check total", "state": "complete"},
                    {"name": "Check export", "state": "incomplete"},
                ],
            }
        ],
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
    project.fake.cards += [
        make_card(2, "Copy", "l-doing"),
        make_card(9, "#9 Old", "l-done", closed=True),
    ]
    renumbered = project.run("update", "sl2", "--renumber")
    assert renumbered.code == 0, renumbered.text
    assert project.fake.writes[-1].form == {"name": "#10 Copy"}


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
    assert not (project.state / "lease").exists()


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
    note = tmp_path / "testing.txt"
    note.write_text("**Ready to try.**\n\n@sam please check the total.")
    result = project.run(
        "move",
        *("5", "testing", "--proof", str(proof), "--shows", "The new total"),
        *("--comment", str(note)),
    )
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
    "text,labelled,listed,later",
    [
        ("Thanks @sam, it is live now.", False, False, ""),
        ("Thanks @sam, it is live now.", True, True, ""),
        ("@sam can you confirm?", False, True, ""),
        ("@sam please reply with the page name", True, False, ""),
        ("@sam can you confirm?", False, True, "Still working on the fix"),
        ("@sam can you confirm?", True, False, "Still working on the fix"),
    ],
)
def test_labels_follow_open_questions_not_any_tag(
    project: Project, text: str, labelled: bool, listed: bool, later: str
) -> None:
    extra = {"idLabels": ["lb-sam"]} if labelled else {}
    project.fake.cards = [make_card(1, "#1 Card", "l-doing", **extra)]
    project.fake.actions = [comment("ours-1", 1, "m-owner", text, 30)]
    if later:
        project.fake.actions.append(comment("ours-2", 1, "m-owner", later, 2))
        project.mods.state.log_posted(project.state, "ours-2")
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
    posted = next(c for c in project.fake.writes if c.path.endswith("/comments"))
    assert ")\n\n![after.png]" in posted.form["text"]


def test_an_upload_body_holds_each_file(project: Project, tmp_path: Path) -> None:
    files = [tmp_path / "before.png", tmp_path / "after.png"]
    files[0].write_bytes(b"first-bytes")
    files[1].write_bytes(b"second-bytes")
    body, kind = project.mods.api.multipart(
        {"name": "Proof"}, [("file", path) for path in files]
    )
    assert kind.startswith("multipart/form-data; boundary=")
    for path in files:
        assert f'filename="{path.name}"'.encode() in body
        assert path.read_bytes() in body
    assert b'name="name"\r\n\r\nProof' in body


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


def test_new_card_gets_the_next_number_at_the_top(
    project: Project, tmp_path: Path
) -> None:
    project.fake.cards = [
        make_card(4, "#4 Open", "l-doing"),
        make_card(9, "#9 Archived", "l-done", closed=True),
    ]
    details = tmp_path / "details.txt"
    details.write_text("Steps to reproduce")
    made = project.run(
        "new", "todo", "Export shops", "--description-file", str(details)
    )
    assert made.code == 0, made.text
    assert made.payload == {"card": 10, "url": "https://trello.com/c/card-1"}
    (post,) = project.fake.writes
    assert (post.method, post.path) == ("POST", "/cards")
    assert post.form == {
        "idList": "l-todo",
        "name": "#10 Export shops",
        "pos": "top",
        "desc": "Steps to reproduce",
    }
    assert project.run("new", "todo", "Call 07700 900123").code == 1
    planned = project.run("new", "todo", "Other", "--dry-run")
    assert isinstance(planned.payload["dryRun"], list)
    assert len(project.fake.writes) == 1


def test_card_text_must_be_short_and_laid_out(project: Project, tmp_path: Path) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    note = tmp_path / "note.txt"
    long_sentence = " ".join(["word"] * 26) + "."
    wall = "One. Two. Three. Four."
    unled = "The fix is live.\n- It shows the total.\n- It saves offline."
    for refused, reason in (
        (long_sentence, "26 words"),
        (wall, "4 sentences"),
        (unled, "bold"),
        ("The PR is merged.", "PR"),
        ("It is deployed to staging.", "deployed"),
        ("Open `settings` now.", "code"),
    ):
        note.write_text(refused)
        result = project.run("comment", "1", str(note))
        assert result.code == 1, refused
        assert reason in str(result.payload["error"])
        made = project.run("new", "todo", "Card", "--description-file", str(note))
        assert made.code == 1, refused
    assert project.fake.writes == []
    note.write_text(
        "**The fix is live.**\n\n"
        "- It shows the total.\n"
        "- It saves offline.\n\n"
        "![shot.png](https://files.example.test/" + "a" * 200 + ".png)\n\n"
        "Reply yes, or say what to change."
    )
    assert project.run("comment", "1", str(note)).code == 0
    note.write_text("@sam @pat **The fix is live.**\n\n- It shows the total.\n- Yes.")
    assert project.run("comment", "1", str(note)).code == 0


def test_comment_adds_the_needs_label_of_each_person_asked(
    project: Project, tmp_path: Path
) -> None:
    project.fake.cards = [
        make_card(1, "#1 Card", "l-doing"),
        make_card(
            2, "#2 Labelled", "l-doing", idLabels=["lb-sam"], idMembers=["m-sam"]
        ),
    ]
    note = tmp_path / "note.txt"
    note.write_text("@sam @pat can you check the total?")
    asked = project.run("comment", "1", str(note))
    assert asked.code == 0, asked.text
    assert asked.payload["addedLabels"] == ["Needs Sam"]
    assert asked.payload["addedMembers"] == ["sam", "pat"]
    post, label, *people = project.fake.writes
    assert post.path == "/cards/card1/actions/comments"
    assert (label.method, label.path, label.form) == (
        "POST",
        "/cards/card1/idLabels",
        {"value": "lb-sam"},
    )
    assert [(c.path, c.form) for c in people] == [
        ("/cards/card1/idMembers", {"value": "m-sam"}),
        ("/cards/card1/idMembers", {"value": "m-pat"}),
    ]
    assert project.run("comment", "2", str(note)).code == 0
    two = [c for c in project.fake.writes[4:] if c.path.startswith("/cards/card2")]
    assert [(c.path, c.form) for c in two] == [
        ("/cards/card2/actions/comments", {"text": note.read_text()}),
        ("/cards/card2/idMembers", {"value": "m-pat"}),
    ]
    note.write_text("@sam the total is live.")
    before = len(project.fake.writes)
    assert project.run("comment", "1", str(note)).code == 0
    assert [c.path for c in project.fake.writes[before:]] == [
        "/cards/card1/actions/comments"
    ]


def test_people_moves_and_new_cards_are_requests(project: Project) -> None:
    project.fake.cards = [make_card(n, f"#{n} Card", "l-doing") for n in (1, 2, 3, 4)]
    project.fake.actions = [
        move_action("a1", 1, "l-testing", 3, who="m-sam", name="Testing"),
        create_action("a2", 2, "m-sam", 2),
        move_action("a3", 3, "l-done", 1, who="m-pat", name="Done"),
        make_action("a4", "updateCard", 4, "m-sam", 1, old={"pos": 1}),
    ]
    report = project.report()
    assert refs(report["requests"]) == {"1", "2"}
    excerpts = {item["card"]: item["excerpt"] for item in report["requests"]}
    assert excerpts == {"1": "[moved to Testing]", "2": "[made the card]"}
    assert refs(report["information"]) == {"3"}


def test_owner_moves_and_cards_not_made_by_the_tool_are_owner_items(
    project: Project, tmp_path: Path
) -> None:
    project.fake.cards = [make_card(n, f"#{n} Card", "l-doing") for n in (1, 2, 3)]
    assert project.report()["owner"] == []
    project.finish()
    project.fake.actions = [
        move_action("h1", 1, "l-testing", -0.02, name="Testing"),
        create_action("h2", 3, "m-owner", -0.02),
    ]
    assert project.run("move", "2", "doing").code == 0
    details = tmp_path / "details.txt"
    details.write_text("Steps")
    made = project.run(
        "new", "todo", "Made by the tool", "--description-file", str(details)
    )
    assert made.code == 0, made.text
    report = project.report()
    assert refs(report["owner"]) == {"1", "3"}
    excerpts = {item["card"]: item["excerpt"] for item in report["owner"]}
    assert excerpts == {"1": "[moved to Testing]", "3": "[made the card]"}
    assert report["requests"] == []
    posted = (project.state / "posted.log").read_text().split()
    assert len(posted) == 2
    assert not {"h1", "h2"} & set(posted)


def test_edited_comment_counts_at_its_edit_time(project: Project) -> None:
    project.fake.cards = [make_card(n, f"#{n} Card", "l-doing") for n in (1, 2)]
    said = "Please add the export too"
    edited = edit_comment(comment("e1", 1, "m-sam", said, 10), 1)
    early = edit_comment(comment("e2", 2, "m-sam", said, 10), 7)
    project.fake.actions = [edited, early]
    ours(project, ("ours-1", 1, "Added", 5), ("ours-2", 2, "Added", 5))
    report = project.report()
    assert refs(report["requests"]) == {"1"}
    (found,) = report["requests"]
    assert found["excerpt"] == said
    assert found["at"] == data_edit(edited)
    project.finish()
    project.fake.cards = [make_card(n, f"#{n} Card", "l-doing") for n in (1, 2, 3)]
    again = comment("e3", 3, "m-sam", "Please add the export", 40)
    project.fake.actions.append(again)
    ours(project, ("ours-3", 3, "Added", 30))
    assert project.run("check").code == 0
    project.finish()
    new = "Please add the export and the import"
    edit_comment(again, -0.02, new)
    project.fake.cards[2]["dateLastActivity"] = ago(-0.02)
    late = project.report()
    assert refs(late["requests"]) == {"1", "3"}
    third = next(item for item in late["requests"] if item["card"] == "3")
    assert (third["excerpt"], third["at"]) == (new, data_edit(again))


def data_edit(action: dict[str, object]) -> str:
    data = action["data"]
    assert isinstance(data, dict)
    return str(data["dateLastEdited"])


def test_duplicate_numbers_are_listed_and_refused_as_a_card_reference(
    project: Project, tmp_path: Path
) -> None:
    project.fake.cards = [
        make_card(1, "#1 Card", "l-doing"),
        make_card(2, "#1 Card copy", "l-doing"),
        make_card(3, "#3 Other", "l-doing"),
    ]
    found = project.report()["unnumbered"]
    assert [item["url"] for item in found] == ["https://trello.com/c/sl2"]
    note = tmp_path / "note.txt"
    note.write_text("All good")
    refused = project.run("comment", "1", str(note))
    assert refused.code == 1
    assert "sl1" in str(refused.payload["error"])
    assert "sl2" in str(refused.payload["error"])
    assert project.fake.writes == []
    assert project.run("comment", "sl1", str(note)).code == 0
    assert project.run("comment", "3", str(note)).code == 0


def ours(project: Project, *rows: tuple[str, int, str, float]) -> None:
    for ident, card, text, hours in rows:
        project.fake.actions.append(comment(ident, card, "m-owner", text, hours))
        project.mods.state.log_posted(project.state, ident)


def test_hidden_open_question_is_listed_as_buried(project: Project) -> None:
    project.fake.cards = [
        make_card(n, f"#{n} Card", "l-done" if n == 5 else "l-doing")
        for n in range(1, 6)
    ]
    ask = "@sam can you confirm?"
    ours(
        project,
        ("a1", 1, ask, 30),
        ("b1", 1, "Still working on the fix", 2),
        ("a2", 2, ask, 30),
        ("b2", 2, "@sam still waiting, can you confirm?", 2),
        ("a3", 3, ask, 30),
        ("b3", 3, "Still working on the fix", 2),
        ("a5", 5, ask, 30),
        ("b5", 5, "Still working on the fix", 2),
    )
    project.fake.actions.append(comment("s3", 3, "m-sam", "Yes, it works", 1))
    project.fake.actions.append(comment("a4", 4, "m-owner", ask, 3))
    project.mods.state.log_posted(project.state, "a4")
    buried = project.report()["buried"]
    assert refs(buried) == {"1"}
    assert buried[0]["author"] == "sam"
    assert buried[0]["excerpt"] == ask


def test_silent_uses_the_open_question_not_the_newest_comment(
    project: Project,
) -> None:
    project.fake.cards = [make_card(n, f"#{n} Card", "l-doing") for n in (1, 2)]
    ask = "@sam can you confirm?"
    ours(
        project,
        ("a1", 1, ask, 30),
        ("b1", 1, "Still working on the fix", 1),
        ("a2", 2, ask, 10),
        ("b2", 2, "Still working on the fix", 1),
    )
    asked_at = str(project.fake.actions[0]["date"])
    silent = project.report()["silent"]
    assert refs(silent) == {"1"}
    assert (silent[0]["at"], silent[0]["excerpt"]) == (asked_at, ask)


def test_a_member_asking_another_member_opens_a_question(project: Project) -> None:
    project.fake.cards = [
        make_card(1, "#1 Card", "l-doing"),
        make_card(2, "#2 Card", "l-doing", idLabels=["lb-sam"]),
        make_card(3, "#3 Card", "l-doing"),
    ]
    ask = "@sam can you check the total?"
    project.fake.actions = [
        comment("p1", 1, "m-pat", ask, 5),
        comment("p2", 2, "m-pat", ask, 5),
        comment("s2", 2, "m-sam", "Checked, it is right", 3),
        comment("p3", 3, "m-pat", ask, 20),
    ]
    ours(project, ("b3", 3, "On it", 2))
    report = project.report()
    assert refs(report["labels"]) == {"1", "2", "3"}
    gaps = {item["card"]: item["excerpt"] for item in report["labels"]}
    assert gaps["1"].startswith("open question to @sam")
    assert gaps["2"].startswith("Needs Sam is set")
    assert report["silent"] == []


def test_testing_cards_count_for_their_tester_and_are_not_chased(
    project: Project,
) -> None:
    project.fake.cards = [
        make_card(
            1, "#1 Card", "l-testing", idLabels=["lb-sam"], dateLastActivity=ago(10)
        ),
        make_card(
            2, "#2 Card", "l-testing", idLabels=["lb-sam"], dateLastActivity=ago(50)
        ),
        make_card(3, "#3 Card", "l-doing", idLabels=["lb-sam"]),
        make_card(4, "#4 Card", "l-testing"),
    ]
    ask = "@sam please test it"
    ours(project, ("a1", 1, ask, 30), ("a2", 2, ask, 30), ("a3", 3, ask, 30))
    report = project.report()
    assert refs(report["silent"]) == {"3"}
    (queue,) = report["testQueue"]
    assert (queue["author"], queue["card"]) == ("sam", "2")
    assert queue["excerpt"] == "2 cards in testing, oldest is #2"


def test_comment_refuses_links_to_cards_not_on_the_board(
    project: Project, tmp_path: Path
) -> None:
    project.fake.cards = [
        make_card(1, "#1 Card", "l-doing"),
        make_card(9, "#9 Old", "l-done", closed=True),
    ]
    note = tmp_path / "note.txt"
    for good in ("https://trello.com/c/sl1/1-card", "https://trello.com/c/sl9"):
        note.write_text(f"Same work as {good}")
        assert project.run("comment", "1", str(note)).code == 0, good
    writes = len(project.fake.writes)
    note.write_text("See https://trello.com/c/zzz999/1-gone")
    refused = project.run("comment", "1", str(note))
    assert refused.code == 1
    assert "zzz999" in str(refused.payload["error"])
    made = project.run("new", "todo", "Card", "--description-file", str(note))
    assert made.code == 1
    assert len(project.fake.writes) == writes
