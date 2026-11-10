import importlib
import json
import os
import re
from pathlib import Path
from types import ModuleType

import agent_hooks
import pytest
from conftest import git
from test_setup import repository
from trello_fakes import (
    BOARD,
    KEY,
    ROLES,
    SKILL,
    TOKEN,
    Mods,
    Project,
    Result,
    ago,
    checklist,
    comment,
    lease_owner,
    make_action,
    make_card,
    move_action,
    refs,
    write_lease,
)
from trello_fixtures import (
    CLAIM_REF,
    drop_claim,
    enter,
    load_claim,
    load_mods,
    make_project,
    origin_of,
    second_machine,
)

mods = pytest.fixture(load_mods)
project = pytest.fixture(make_project)


def test_trello_json_installs_the_skill_only_when_present(
    installer: ModuleType, tmp_path: Path
) -> None:
    plain, trello, nested = (tmp_path / name for name in ("plain", "trello", "nested"))
    for root in (plain, trello, nested):
        root.mkdir()
        repository(root)
    (trello / "trello.json").write_text("{}")
    (nested / "apps").mkdir()
    (nested / "apps/trello.json").write_text("{}")
    script = ".agents/skills/trello-coordinator/scripts/trello.py"
    for root in (plain, trello, nested):
        installer.install(root)
    assert agent_hooks.integrated_services(trello) == ["Trello"]
    assert agent_hooks.integrated_services(plain) == []
    assert agent_hooks.integrated_services(nested) == []
    assert (trello / script).is_file()
    assert not (plain / script).exists()
    assert not (nested / script).exists()


def test_secrets_file_must_be_ignored_and_is_found_from_a_worktree(
    project: Project, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (project.main / ".gitignore").write_text("")
    refused = project.run("probe")
    assert refused.code == 1
    assert ".env.trello.local" in str(refused.payload["error"])
    assert project.fake.calls == []
    (project.main / ".gitignore").write_text(".env.trello.local\n")
    worktree = tmp_path / "worktree"
    git(project.main, "worktree", "add", "-q", str(worktree))
    assert not (worktree / ".env.trello.local").exists()
    monkeypatch.chdir(worktree)
    result = project.run("probe")
    assert result.code == 0, result.text
    assert result.payload["account"] == "owner"
    assert project.run("check").code == 0
    assert (project.state / "state.json").is_file()
    (project.main / ".env.trello.local").write_text(f"TRELLO_KEY={KEY}\n")
    missing = project.run("probe")
    assert "TRELLO_TOKEN" in str(missing.payload["error"])


def test_key_and_token_never_printed(project: Project) -> None:
    pasted = f"I pasted {KEY} and {TOKEN} by mistake"
    project.fake.cards = [make_card(1, "#1 Leak", "l-doing")]
    project.fake.actions = [comment("a1", 1, "m-sam", pasted, 2)]
    outputs = [project.run("probe").text, project.run("check").text]
    project.finish()
    project.fake.rejections = [(500, {}, f"broken {TOKEN}")]
    failed = project.run("probe")
    outputs.append(failed.text)
    assert failed.code == 1
    assert "***" in failed.text
    assert "***" in outputs[1]
    stored = [path.read_text() for path in project.state.rglob("*") if path.is_file()]
    for text in [*outputs, *stored]:
        assert KEY not in text
        assert TOKEN not in text
    assert any(TOKEN in call.auth for call in project.fake.calls)


@pytest.mark.parametrize(
    "changes",
    [
        {"board": "ab12" * 8},
        {"roles": {role: {"model": "m", "why": "ATTA" + "c3" * 20} for role in ROLES}},
    ],
)
def test_config_with_a_secret_is_refused(
    project: Project, changes: dict[str, object]
) -> None:
    project.configure(**changes)
    result = project.run("check")
    assert result.code == 1
    assert "key or token" in str(result.payload["error"])
    assert project.fake.calls == []


def test_config_takes_timing_overrides_and_refuses_retired_fields(
    project: Project,
) -> None:
    roles = {role: {"model": "m", "why": "w"} for role in ROLES}
    roles["builder"] = {"model": "m", "why": "w", "provider": "codex"}
    project.configure(roles=roles, timing={"chaseHours": 12})
    assert project.mods.config.load_config(project.main).chase_hours == 12
    for gone in ("quietHours", "timeZone"):
        project.configure(timing={gone: "22:00-07:00"})
        with pytest.raises(project.mods.api.TrelloError, match=f"delete {gone}"):
            project.mods.config.load_config(project.main)
    project.configure(timing={"chaseHours": 0})
    with pytest.raises(project.mods.api.TrelloError):
        project.mods.config.load_config(project.main)


@pytest.mark.parametrize("command", ["comment", "check"])
def test_wrong_account_is_refused(
    project: Project, tmp_path: Path, command: str
) -> None:
    note = tmp_path / "note.txt"
    note.write_text("hello")
    arguments = {"comment": ["1", str(note)], "check": []}
    project.fake.account = "intruder"
    project.fake.cards = [make_card(1, "#1 Card", "l-todo")]
    result = project.run(command, *arguments[command])
    assert result.code == 1
    assert "another account" in str(result.payload["error"])
    assert project.fake.writes == []
    probed = project.run("probe")
    assert probed.code == 1
    assert probed.payload["account"] == "intruder"


def test_check_reports_every_missed_item(project: Project) -> None:
    fake = project.fake
    todo, doing, testing = "l-todo", "l-doing", "l-testing"
    fake.cards = [
        make_card(1, "#1 Request", doing),
        make_card(2, "#2 Info", todo),
        make_card(3, "#3 Owner", doing),
        make_card(4, "#4 Promise", doing),
        make_card(5, "#5 Silent", doing),
        make_card(6, "#6 BadTag", doing),
        make_card(7, "#7 Waits", testing),
        make_card(8, "Unnumbered", todo),
        make_card(9, "#9 Overdue", doing, due=ago(48)),
        make_card(10, "#10 Label", todo, idLabels=["lb-sam"]),
        make_card(11, "#11 Real case", testing, idLabels=["lb-real"]),
        make_card(12, "#12 Real case done", "l-done", idLabels=["lb-real"]),
    ]
    fake.labels.append({"id": "lb-real", "name": "Waiting for real case"})
    fake.actions = [
        comment("a1", 1, "m-sam", "Please add the export", 48),
        comment("a2", 2, "m-pat", "Looks odd to me", 24),
        comment("o1", 3, "m-owner", "Owner note before the first check", 3),
        comment("ours-4", 4, "m-owner", "I will fix this", 8),
        comment("ours-5", 5, "m-owner", "@sam can you confirm?", 30),
        comment("ours-6", 6, "m-owner", "@ghost please look", 1),
        comment("ours-7", 7, "m-owner", "Fix goes in the next release", 2),
    ]
    for ident in ("ours-4", "ours-5", "ours-6", "ours-7"):
        project.mods.state.log_posted(project.state, ident)
    first = project.report()
    assert first["owner"] == []
    project.finish()
    fake.actions.append(comment("o2", 3, "m-owner", "Owner decision: ship it", -0.02))
    report = project.report()
    expected = {
        "requests": {"1"},
        "information": {"2"},
        "owner": {"3"},
        "promises": {"4"},
        "silent": {"5"},
        "buried": set(),
        "badTags": {"6"},
        "labels": {"5", "10"},
        "waitsOnUs": {"7"},
        "testQueue": set(),
        "unnumbered": {"sl8"},
        "overdue": {"9"},
        "realCases": {"11"},
    }
    assert {name: refs(items) for name, items in report.items()} == expected
    owner = report["owner"][0]
    assert set(owner) == {"card", "name", "list", "url", "at", "author", "excerpt"}
    assert owner["author"] == "owner"
    assert owner["excerpt"] == "Owner decision: ship it"
    assert owner["url"] == "https://trello.com/c/sl3"


def test_only_allowed_members_make_requests(project: Project) -> None:
    doing = "l-doing"
    project.fake.cards = [make_card(n, f"#{n} Card", doing) for n in (1, 2, 3, 4)]
    project.fake.actions = [
        comment("a1", 1, "m-sam", "From an allowed member", 5),
        comment("a2", 2, "m-pat", "From someone else", 5),
        make_action("a3", "updateCard", 3, "m-sam", 4, old={"desc": "before"}),
        make_action(
            "a4", "addAttachmentToCard", 4, "m-sam", 3, attachment={"name": "shot.png"}
        ),
    ]
    report = project.report()
    assert refs(report["requests"]) == {"1", "3", "4"}
    assert refs(report["information"]) == {"2"}
    excerpts = {item["card"]: item["excerpt"] for item in report["requests"]}
    assert excerpts["3"] == "[description edited]"
    assert excerpts["4"] == "[image] shot.png"


def test_done_card_requests_expire_after_the_grace_hours(project: Project) -> None:
    done, doing = "l-done", "l-doing"
    project.fake.cards = [
        make_card(1, "#1 Old done", done),
        make_card(2, "#2 Fresh done", done),
        make_card(3, "#3 Old open", doing),
        make_card(4, "#4 Thanked", done),
        make_card(5, "#5 Ok on open", doing),
    ]
    project.fake.actions = [
        move_action("m4", 4, done, 10),
        comment("a4", 4, "m-sam", "Thanks @owner, works!", 1),
        comment("a5", 5, "m-sam", "ok", 1),
        move_action("m1", 1, done, 100),
        comment("a1", 1, "m-sam", "One more thing", 1),
        move_action("m2", 2, done, 10),
        comment("a2", 2, "m-sam", "One more thing", 1),
        comment("a3", 3, "m-sam", "Forgotten for a month", 24 * 30),
    ]
    report = project.report()
    assert refs(report["requests"]) == {"2", "3", "5"}


def test_activity_query_and_rate_limit_retry(project: Project) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    project.fake.rejections = [(429, {"retry-after": "2"}, "")]
    assert project.run("check").code == 0
    assert project.waits == [2.0]
    first = [c for c in project.fake.calls if c.path == f"/boards/{BOARD}/actions"]
    assert first[0].query["filter"] == "all"
    assert "since" not in first[0].query
    saved = json.loads((project.state / "state.json").read_text())["checkedAt"]
    project.finish()
    project.fake.rejections = [
        (429, {"x-rate-limit-api-token-interval-ms": "10000"}, "")
    ]
    assert project.run("check").code == 0
    assert project.waits == [2.0, 10.0]
    later = [c for c in project.fake.calls if c.path == f"/boards/{BOARD}/actions"]
    assert later[-1].query["since"] == saved
    assert later[-1].query["filter"] == "all"


def test_comment_posts_new_and_blocks_private_data(
    project: Project, tmp_path: Path
) -> None:
    project.configure(privacy=[r"Project\s+Zed"])
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    note, image = tmp_path / "note.txt", tmp_path / "shot.png"
    note.write_text("The fix is live.")
    image.write_bytes(b"fake image")
    first = project.run("comment", "1", str(note), "--image", str(image))
    second = project.run("comment", "#1", str(note))
    assert (first.code, second.code) == (0, 0), first.text + second.text
    assert project.fake.writes[0].path == "/cards/card1/attachments"
    assert project.fake.writes[0].form == {"multipart": "yes"}
    text = project.fake.writes[1].form["text"]
    assert (
        text == "The fix is live.\n\n![shot.png](https://files.example.test/att-1.png)"
    )
    assert all(
        c.path.endswith(("/attachments", "/cards/card1/actions/comments"))
        for c in project.fake.writes
    )
    assert (project.state / "posted.log").read_text().split() == ["act-1", "act-2"]
    before = len(project.fake.writes)
    for private in (
        "Mail me at jo.smith@example.com",
        "Call +44 7700 900123",
        "About Project  Zed",
    ):
        note.write_text(private)
        result = project.run("comment", "1", str(note))
        assert result.code == 1, private
    note.write_text("Planned for 2026-11-05 10:00 as #12")
    assert project.run("comment", "1", str(note), "--dry-run").code == 0
    assert len(project.fake.writes) == before


def test_comment_dry_run_sends_no_write(project: Project, tmp_path: Path) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    note = tmp_path / "note.txt"
    note.write_text("Planned text")
    result = project.run("comment", "1", str(note), "--dry-run")
    planned = result.payload["dryRun"]
    assert isinstance(planned, list)
    assert planned[0]["method"] == "POST"
    assert project.fake.writes == []
    assert not (project.state / "posted.log").exists()


def write_note(tmp_path: Path, body: str = "") -> Path:
    note = tmp_path / ("other.txt" if body else "testing.txt")
    note.write_text(
        body or "**Ready to try.**\n\n@sam please open the list and check the total."
    )
    return note


def test_testing_move_needs_proof(project: Project, tmp_path: Path) -> None:
    project.fake.cards = [make_card(5, "#5 Move", "l-doing")]
    proof = tmp_path / "proof.png"
    proof.write_bytes(b"fake image")
    note = write_note(tmp_path)
    shows = "The saved total now shows on the list"
    refused = project.run("move", "5", "testing", "--comment", str(note))
    assert refused.code == 1
    assert "proof" in str(refused.payload["error"])
    unnamed = project.run(
        "move", "5", "testing", "--proof", str(proof), "--comment", str(note)
    )
    assert unnamed.code == 1
    assert "--shows" in str(unnamed.payload["error"])
    uncommented = project.run(
        "move", "5", "testing", "--proof", str(proof), "--shows", shows
    )
    assert uncommented.code == 1
    assert "--comment" in str(uncommented.payload["error"])
    for body in ("Ready to try.", "@ghost please check the total."):
        untagged = project.run(
            "move",
            *("5", "testing", "--proof", str(proof), "--shows", shows),
            *("--comment", str(write_note(tmp_path, body))),
        )
        assert untagged.code == 1, body
        assert "board member" in str(untagged.payload["error"])
    private = project.run(
        "move",
        *("5", "testing", "--proof", str(proof), "--shows", "Call +44 7700 900123"),
        *("--comment", str(note)),
    )
    assert private.code == 1
    assert project.fake.writes == []
    args = ("move", "5", "testing", "--proof", str(proof), "--shows", shows)
    planned = project.run(*args, "--comment", str(note), "--dry-run")
    assert planned.code == 0, planned.text
    writes = planned.payload["dryRun"]
    assert isinstance(writes, list)
    assert writes[0]["params"] == {"name": shows}
    moved = project.run(*args, "--comment", str(note))
    assert moved.code == 0, moved.text
    steps = [(c.method, c.path) for c in project.fake.writes]
    assert steps == [
        ("POST", "/cards/card5/attachments"),
        ("POST", "/cards/card5/actions/comments"),
        ("PUT", "/cards/card5"),
        ("POST", "/cards/card5/idLabels"),
        ("POST", "/cards/card5/idMembers"),
    ]
    post, put, label, member = project.fake.writes[1:]
    picture = "![proof.png](https://files.example.test/att-1.png)"
    assert post.form["text"] == note.read_text() + "\n\n" + picture
    assert put.form == {"idList": "l-testing", "pos": "top"}
    assert (label.form, member.form) == ({"value": "lb-sam"}, {"value": "m-sam"})
    assert (project.state / "posted.log").read_text().split() == ["act-1", "act-2"]


def test_testing_move_takes_a_written_check_for_work_with_no_screen(
    project: Project, tmp_path: Path
) -> None:
    project.fake.cards = [make_card(5, "#5 Job", "l-doing")]
    note = write_note(tmp_path)
    check = "Open Orders and tap Export. A file downloads."
    assert project.run("move", "5", "testing", "--check", check).code == 1
    private = project.run(
        "move",
        "5",
        "testing",
        "--check",
        "Call +44 7700 900123",
        "--comment",
        str(note),
    )
    assert private.code == 1
    assert project.fake.writes == []
    moved = project.run(
        "move", "5", "testing", "--check", check, "--comment", str(note)
    )
    assert moved.code == 0, moved.text
    assert [c.path for c in project.fake.writes][:2] == [
        "/cards/card5/actions/comments",
        "/cards/card5",
    ]
    assert (
        project.fake.writes[0].form["text"] == f"{note.read_text()}\n\nTo try: {check}"
    )
    other = project.run("move", "5", "doing", "--check", check)
    assert other.code == 1


def test_move_refuses_open_checklist_items(project: Project, tmp_path: Path) -> None:
    project.fake.cards = [make_card(5, "#5 Move", "l-doing")]
    project.fake.checklists = {
        "card5": checklist(
            ("ci1", "Check total", "complete"),
            ("ci2", "Check export", "incomplete"),
        )
    }
    note = write_note(tmp_path)
    for argv in (
        ["move", "5", "done"],
        ["move", "5", "testing", "--check", "Tap Export.", "--comment", str(note)],
    ):
        refused = project.run(*argv)
        assert refused.code == 1
        assert "Check export" in str(refused.payload["error"])
        assert "Check total" not in str(refused.payload["error"])
    assert project.fake.writes == []
    assert project.run("move", "5", "doing").code == 0
    project.fake.checklists = {
        "card5": checklist(
            ("ci1", "Check total", "complete"), ("ci2", "Check export", "complete")
        )
    }
    assert project.run("move", "5", "done").code == 0


def test_tick_marks_one_checklist_item(project: Project) -> None:
    project.fake.cards = [make_card(5, "#5 Move", "l-doing")]
    project.fake.checklists = {
        "card5": checklist(
            ("ci1", "Check total", "complete"),
            ("ci2", "Check export", "incomplete"),
            ("ci3", "Check export file", "incomplete"),
        )
    }
    for argv in (["tick", "5", "check"], ["tick", "5", "nothing like it"]):
        assert project.run(*argv).code == 1
    assert project.fake.writes == []
    done = project.run("tick", "5", "check total", "--undo")
    assert done.code == 0, done.text
    exact = project.run("tick", "5", "check export")
    assert exact.code == 0, exact.text
    first, second = project.fake.writes
    assert (first.method, first.path) == ("PUT", "/cards/card5/checkItem/ci1")
    assert first.form == {"state": "incomplete"}
    assert (second.path, second.form) == (
        "/cards/card5/checkItem/ci2",
        {"state": "complete"},
    )
    planned = project.run("tick", "5", "check total", "--dry-run")
    assert isinstance(planned.payload["dryRun"], list)
    assert len(project.fake.writes) == 2


def test_member_adds_and_removes_a_person(project: Project) -> None:
    project.fake.cards = [
        make_card(1, "#1 Card", "l-doing"),
        make_card(2, "#2 Card", "l-doing", idMembers=["m-sam"]),
    ]
    added = project.run("member", "1", "add", "Sam")
    assert added.code == 0, added.text
    (post,) = project.fake.writes
    assert (post.method, post.path, post.form) == (
        "POST",
        "/cards/card1/idMembers",
        {"value": "m-sam"},
    )
    assert project.run("member", "2", "add", "sam").payload == {"unchanged": True}
    assert project.run("member", "1", "remove", "sam").payload == {"unchanged": True}
    assert project.run("member", "2", "remove", "sam").code == 0
    delete = project.fake.writes[-1]
    assert (delete.method, delete.path) == ("DELETE", "/cards/card2/idMembers/m-sam")
    writes = len(project.fake.writes)
    ghost = project.run("member", "1", "add", "ghost")
    assert ghost.code == 1
    assert "ghost" in str(ghost.payload["error"])
    assert len(project.fake.writes) == writes


def test_a_comment_never_moves_a_card(project: Project, tmp_path: Path) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-testing")]
    note = tmp_path / "note.txt"
    note.write_text(
        "**Not built yet.**\n\nI am fixing the total. I will tell you when it is live."
    )
    result = project.run("comment", "1", str(note))
    assert result.code == 0, result.text
    assert "movedTo" not in result.payload
    assert not [c for c in project.fake.writes if c.method == "PUT"]


def test_label_upload_and_member_dry_runs_write_nothing(
    project: Project, tmp_path: Path
) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"fake image")
    for command in (
        ("label", "1", "add", "Needs Sam"),
        ("upload", "1", str(shot)),
        ("member", "1", "add", "sam"),
    ):
        result = project.run(*command, "--dry-run")
        assert result.code == 0, result.text
        assert result.payload["dryRun"], command
        assert project.fake.writes == [], command


def test_done_move_clears_needs_labels(project: Project) -> None:
    project.fake.cards = [make_card(5, "#5 Move", "l-testing", idLabels=["lb-sam"])]
    assert project.run("move", "5", "done").code == 0
    put, delete = project.fake.writes
    assert put.form["idList"] == "l-done"
    assert (delete.method, delete.path) == ("DELETE", "/cards/card5/idLabels/lb-sam")


def test_label_upload_and_download_use_the_card_endpoints(
    project: Project, tmp_path: Path
) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    project.fake.attachments = [
        {"id": "att9", "name": "shot.png", "date": ago(1), "isUpload": True},
        {"id": "att8", "name": "old.png", "date": ago(100), "isUpload": True},
    ]
    assert project.run("label", "1", "add", "Needs Sam").code == 0
    assert project.fake.writes[-1].form == {"value": "lb-sam"}
    project.fake.cards = [make_card(1, "#1 Card", "l-doing", idLabels=["lb-sam"])]
    assert project.run("label", "1", "add", "Needs Sam").payload == {"unchanged": True}
    assert project.run("label", "1", "remove", "Needs Sam").code == 0
    assert project.fake.writes[-1].method == "DELETE"
    assert project.run("label", "1", "add", "Needs Nobody").code == 1
    real = project.run("label", "1", "add", "Waiting for real case")
    assert real.code == 0, real.text
    create, add = project.fake.writes[-2:]
    assert (create.path, create.form["name"]) == (
        f"/boards/{BOARD}/labels",
        "Waiting for real case",
    )
    assert (add.path, add.form) == ("/cards/card1/idLabels", {"value": "lb-new-1"})
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"fake image")
    uploaded = project.run("upload", "1", str(shot))
    assert uploaded.payload["markdown"] == (
        "![shot.png](https://files.example.test/att-1.png)"
    )
    other = tmp_path / "other.png"
    other.write_bytes(b"fake image")
    both = project.run("upload", "1", str(shot), str(other))
    assert both.payload["markdown"] == (
        "![shot.png](https://files.example.test/att-2.png)\n\n"
        "![other.png](https://files.example.test/att-3.png)"
    )
    folder = tmp_path / "saved"
    downloaded = project.run("download", "1", "--since", ago(10), "--dir", str(folder))
    assert downloaded.payload == {"paths": [str(folder / "att9-shot.png")]}
    assert (folder / "att9-shot.png").read_bytes() == b"png-bytes"


def test_one_run_at_a_time(project: Project, mods: Mods) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    assert project.run("check").code == 0
    calls = len(project.fake.calls)
    saved = (project.state / "state.json").read_bytes()
    assert (project.state / "lease").is_file()
    skipped = project.run("check")
    assert (skipped.code, skipped.payload) == (0, {"skipped": True})
    assert len(project.fake.calls) == calls
    assert (project.state / "state.json").read_bytes() == saved
    assert project.finish().payload == {"finished": True}
    assert not (project.state / "lease").exists()
    assert project.run("check").code == 0
    assert len(project.fake.calls) > calls
    write_lease(project, "someone", 29)
    calls = len(project.fake.calls)
    assert project.run("check").payload == {"skipped": True}
    assert len(project.fake.calls) == calls
    write_lease(project, "someone", 31)
    assert project.run("check").code == 0
    assert len(project.fake.calls) > calls
    assert project.run_id != "someone"
    assert lease_owner(project) == project.run_id


def private_remote(_place: object) -> bool:
    return True


def make_note(tmp_path: Path) -> Path:
    note = tmp_path / "claim-note.txt"
    note.write_text("Planned text")
    return note


def run_and_remember(project: Project, tmp_path: Path) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    assert project.run("check").code == 0
    assert project.run("comment", "1", str(make_note(tmp_path))).code == 0
    (project.state / "handover.md").write_text("card 1: worker thread t1\n")
    assert project.finish().payload == {"finished": True}


def claim_commit(project: Project) -> str:
    return git(origin_of(project), "for-each-ref", "--format=%(objectname)", CLAIM_REF)


def test_a_second_machine_is_skipped_and_cannot_write(
    project: Project, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drop_claim(project)
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    first = project.run("check")
    assert first.code == 0 and "skipped" not in first.payload
    assert claim_commit(project)
    other = enter(monkeypatch, second_machine(project))
    calls = len(project.fake.calls)
    skipped = other.run("check")
    assert skipped.code == 0
    assert skipped.payload["skipped"] is True
    assert skipped.payload["heldElsewhere"] is True
    assert skipped.payload["heldSince"]
    assert len(project.fake.calls) == calls
    assert not (other.state / "lease").exists()
    refused = other.run("comment", "1", str(make_note(tmp_path)))
    assert refused.code == 1
    assert "claim" in str(refused.payload["error"])
    assert project.fake.writes == []
    who = git(
        origin_of(project), "log", "-1", "--format=%an <%ae>|%cn <%ce>", CLAIM_REF
    )
    fixed = "trello-coordinator <trello-coordinator@invalid>"
    assert who == f"{fixed}|{fixed}"
    assert (
        enter(monkeypatch, project).run("comment", "1", str(make_note(tmp_path))).code
        == 0
    )


def test_takeover_moves_the_claim_and_memory(
    project: Project, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(load_claim(), "is_private", private_remote)
    drop_claim(project)
    run_and_remember(project, tmp_path)
    names = git(origin_of(project), "ls-tree", "--name-only", CLAIM_REF).split()
    assert {"holder", "posted.log", "handover.md", "state.json"} <= set(names)
    other = enter(monkeypatch, second_machine(project))
    held = other.run("check").payload
    assert held["heldElsewhere"] is True
    write_lease(other, "busy", 1)
    busy = other.run("takeover")
    assert busy.code == 1 and "run" in str(busy.payload["error"])
    (other.state / "lease").unlink()
    moved = other.run("takeover")
    assert moved.code == 0, moved.text
    assert moved.payload == {"tookOver": True, "previousSince": held["heldSince"]}
    for name in ("posted.log", "handover.md"):
        assert (other.state / name).read_text() == (project.state / name).read_text()
    assert other.run("check").code == 0
    assert other.finish().payload == {"finished": True}
    old = enter(monkeypatch, project)
    assert old.run("check").payload["heldElsewhere"] is True
    assert not (old.state / "lease").exists()
    assert old.run("comment", "1", str(make_note(tmp_path))).code == 1
    (old.state / "handover.md").write_text("late note\n")
    lost = old.run("finish", "late")
    assert lost.code == 1
    assert "another machine holds" in str(lost.payload["error"]).lower()


def test_a_public_remote_gets_no_memory(
    project: Project, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drop_claim(project)
    run_and_remember(project, tmp_path)
    assert git(origin_of(project), "ls-tree", "--name-only", CLAIM_REF) == "holder"
    other = enter(monkeypatch, second_machine(project))
    (other.state).mkdir(parents=True)
    (other.state / "handover.md").write_text("my own note\n")
    moved = other.run("takeover")
    assert moved.code == 0, moved.text
    assert (other.state / "handover.md").read_text() == "my own note\n"
    assert other.run("check").code == 0


@pytest.mark.parametrize("leak", [KEY, TOKEN, "ab" * 16])
def test_memory_with_a_key_is_never_pushed(
    project: Project, monkeypatch: pytest.MonkeyPatch, leak: str
) -> None:
    monkeypatch.setattr(load_claim(), "is_private", private_remote)
    drop_claim(project)
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    assert project.run("check").code == 0
    before = claim_commit(project)
    (project.state / "notes.md").write_text(f"login was {leak} yesterday\n")
    refused = project.finish()
    assert refused.code == 1
    assert "notes.md" in str(refused.payload["error"])
    assert leak not in refused.text
    assert claim_commit(project) == before


def test_a_lost_local_record_is_rebuilt_from_the_claim(
    project: Project, tmp_path: Path
) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    (project.state / "claim-record").unlink()
    note = make_note(tmp_path)
    assert project.run("comment", "1", str(note)).code == 1
    held = claim_commit(project)
    again = project.run("check")
    assert again.code == 0 and "skipped" not in again.payload
    assert claim_commit(project) == held
    assert project.run("comment", "1", str(note)).code == 0


def test_unchanged_memory_pushes_nothing(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(load_claim(), "is_private", private_remote)
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]
    assert project.run("check").code == 0
    taken = claim_commit(project)
    assert project.finish().payload == {"finished": True}
    saved = claim_commit(project)
    assert saved != taken
    assert project.run("finish", "again").payload == {"finished": False}
    assert claim_commit(project) == saved


def test_an_unreachable_origin_stops_the_run(project: Project) -> None:
    git(project.main, "remote", "set-url", "origin", str(project.main.parent / "gone"))
    calls = len(project.fake.calls)
    failed = project.run("check")
    assert failed.code == 1
    assert "origin" in str(failed.payload["error"])
    assert len(project.fake.calls) == calls
    assert not (project.state / "lease").exists()


def test_only_a_github_remote_can_be_private(
    project: Project, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    claim = load_claim()
    place = importlib.import_module("trello_board.secrets").locate(project.main)
    folder = tmp_path / "bin"
    folder.mkdir()
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")
    answers = []
    for answer in ("PRIVATE", "PUBLIC", ""):
        (folder / "gh").write_text(f"#!/bin/sh\necho '{answer}'\n")
        (folder / "gh").chmod(0o755)
        answers.append(claim.is_private(place))
    assert answers == [False, False, False]
    git(project.main, "remote", "set-url", "origin", "https://github.com/o/r.git")
    answers = []
    for answer in ("PRIVATE", "PUBLIC", "", "INTERNAL"):
        (folder / "gh").write_text(f"#!/bin/sh\necho '{answer}'\n")
        answers.append(claim.is_private(place))
    assert answers == [True, False, False, False]


def test_state_saves_atomically(
    project: Project, mods: Mods, monkeypatch: pytest.MonkeyPatch
) -> None:
    mods.state.save_state(project.state, {"checkedAt": "before"})
    names = sorted(path.name for path in project.state.iterdir())

    def fail(*_: object) -> None:
        raise OSError("disk full")

    with monkeypatch.context() as patch:
        patch.setattr(mods.state.os, "replace", fail)
        with pytest.raises(OSError):
            mods.state.save_state(project.state, {"checkedAt": "after"})
    assert json.loads((project.state / "state.json").read_text()) == {
        "checkedAt": "before"
    }
    assert sorted(path.name for path in project.state.iterdir()) == names


def sections(text: str) -> dict[str, str]:
    parts = re.split(r"^## ", text, flags=re.MULTILINE)[1:]
    return {part.splitlines()[0]: part for part in parts}


def first_cells(section: str) -> list[str]:
    return re.findall(r"^\| `(.+?)` +\|", section, flags=re.MULTILINE)


def test_cli_matches_the_reference_contract(mods: Mods) -> None:
    parts = sections((SKILL / "references/commands.md").read_text())
    _, subcommands = mods.commands.build_parser()
    documented = {}
    for cell in first_cells(parts["Commands"]):
        tokens = cell.replace("\\|", "|").split()
        bracket = next(
            (i for i, token in enumerate(tokens) if token.startswith(("[", "--"))),
            len(tokens),
        )
        positional = [token for token in tokens[1:bracket] if token != "..."]
        documented[tokens[0]] = (len(positional), set(re.findall(r"--[a-z-]+", cell)))
    assert (
        set(subcommands)
        == set(documented)
        == {*mods.commands.HANDLERS, "finish", "save-secret", "takeover"}
    )
    for name, (count, flags) in documented.items():
        actions = subcommands[name]._actions
        assert len([a for a in actions if not a.option_strings]) == count, name
        options = {s for a in actions for s in a.option_strings if s.startswith("--")}
        assert options - {"--help", "--dry-run"} == flags, name
    assert set(first_cells(parts["`trello.json`"])) == set(mods.config.FIELDS)
    assert tuple(first_cells(parts["`check` report"])) == (
        mods.report.FIELDS + mods.report.WAKE_FIELDS
    )
    assert set(mods.report.CHECKS) == set(mods.report.FIELDS)
    timing_row = next(
        line
        for line in parts["`trello.json`"].splitlines()
        if line.startswith("| `timing`")
    )
    assert set(re.findall(r"`(\w+)`", timing_row.split("|")[2])) == set(
        mods.config.TIMING_FIELDS
    )


def test_refused_token_is_reported_once(project: Project) -> None:
    project.fake.cards = [make_card(1, "#1 Card", "l-doing")]

    def refused() -> Result:
        project.fake.rejections = [(401, {}, f"invalid token {TOKEN}")]
        return project.run("check")

    first = refused()
    assert first.code == 1
    assert first.payload == {
        "error": "Trello refused the token: it is revoked or expired",
        "tokenRefused": True,
        "firstReport": True,
    }
    assert TOKEN not in first.text
    assert not (project.state / "state.json").exists()
    assert refused().payload["firstReport"] is False
    assert project.run("check").code == 0
    project.finish()
    assert refused().payload["firstReport"] is True


def test_archive_links_the_original_and_closes_the_copy(project: Project) -> None:
    project.fake.cards = [
        make_card(1, "#1 Card", "l-doing"),
        make_card(2, "#1 Card copy", "l-doing", idLabels=["lb-sam"]),
    ]
    assert project.run("archive", "1", "--into", "sl1").code == 1
    assert project.run("archive", "sl2", "--into", "sl2").code == 1
    assert project.fake.writes == []
    done = project.run("archive", "sl2", "--into", "sl1")
    assert done.code == 0, done.text
    post, delete, close = project.fake.writes
    assert post.path == "/cards/card2/actions/comments"
    assert "https://trello.com/c/sl1" in post.form["text"]
    assert (delete.method, delete.path) == ("DELETE", "/cards/card2/idLabels/lb-sam")
    assert (close.method, close.path, close.form) == (
        "PUT",
        "/cards/card2",
        {"closed": "true"},
    )
    assert (project.state / "posted.log").read_text().split() == ["act-1"]
    planned = project.run("archive", "sl2", "--into", "sl1", "--dry-run")
    assert isinstance(planned.payload["dryRun"], list)
    assert len(project.fake.writes) == 3
