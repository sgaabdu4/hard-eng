import json
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
    ago,
    comment,
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
    project.fake.rejections = [(401, {}, f"invalid token {TOKEN}")]
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


def test_config_defaults_and_role_provider(project: Project) -> None:
    config = project.mods.config.load_config(project.main)
    assert (config.every_minutes, config.chase_hours) == (15, 24)
    assert (config.promise_hours, config.done_grace_hours) == (6, 72)
    roles = {role: {"model": "m", "why": "w"} for role in ROLES}
    roles["builder"] = {"model": "m", "why": "w", "provider": "codex"}
    timing = {
        "chaseHours": 12,
        "quietHours": "22:00-07:00",
        "timeZone": "Europe/London",
    }
    project.configure(roles=roles, timing=timing)
    assert project.mods.config.load_config(project.main).chase_hours == 12
    for bad in (
        {"quietHours": "late"},
        {"timeZone": "Nowhere/Land"},
        {"chaseHours": 0},
    ):
        project.configure(timing=bad)
        with pytest.raises(project.mods.api.TrelloError):
            project.mods.config.load_config(project.main)


@pytest.mark.parametrize(
    "command", ["comment", "move", "label", "upload", "update", "check"]
)
def test_wrong_account_is_refused(
    project: Project, tmp_path: Path, command: str
) -> None:
    note = tmp_path / "note.txt"
    note.write_text("hello")
    arguments = {
        "comment": ["1", str(note)],
        "move": ["1", "doing"],
        "label": ["1", "add", "Needs Sam"],
        "upload": ["1", str(note)],
        "update": ["1", "--name", "New"],
        "check": [],
    }
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
    ]
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
    assert set(report) == set(project.mods.report.FIELDS)
    expected = {
        "requests": {"1"},
        "information": {"2"},
        "owner": {"3"},
        "promises": {"4"},
        "silent": {"5"},
        "badTags": {"6"},
        "labels": {"5", "10"},
        "waitsOnUs": {"7"},
        "unnumbered": {"sl8"},
        "overdue": {"9"},
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
    ]
    project.fake.actions = [
        move_action("m1", 1, done, 100),
        comment("a1", 1, "m-sam", "One more thing", 1),
        move_action("m2", 2, done, 10),
        comment("a2", 2, "m-sam", "One more thing", 1),
        comment("a3", 3, "m-sam", "Forgotten for a month", 24 * 30),
    ]
    report = project.report()
    assert refs(report["requests"]) == {"2", "3"}


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
    assert [c.method for c in project.fake.writes] == ["POST"] * 3
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


def test_testing_move_needs_proof(project: Project, tmp_path: Path) -> None:
    project.fake.cards = [make_card(5, "#5 Move", "l-doing")]
    proof = tmp_path / "proof.png"
    proof.write_bytes(b"fake image")
    refused = project.run("move", "5", "testing")
    assert refused.code == 1
    assert "proof" in str(refused.payload["error"])
    assert project.fake.writes == []
    moved = project.run("move", "5", "testing", "--proof", str(proof))
    assert moved.code == 0, moved.text
    attach, put = project.fake.writes
    assert (attach.method, attach.path) == ("POST", "/cards/card5/attachments")
    assert (put.method, put.path) == ("PUT", "/cards/card5")
    assert put.form == {"idList": "l-testing", "pos": "top"}


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
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"fake image")
    uploaded = project.run("upload", "1", str(shot))
    assert (
        json.dumps(uploaded.payload).count(
            "![shot.png](https://files.example.test/att-1.png)"
        )
        == 1
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
    parser, subcommands = mods.commands.build_parser()
    documented = {}
    for cell in first_cells(parts["Commands"]):
        tokens = cell.replace("\\|", "|").split()
        bracket = next(
            (i for i, token in enumerate(tokens) if token.startswith("[")), len(tokens)
        )
        positional = [token for token in tokens[1:bracket] if token != "..."]
        documented[tokens[0]] = (len(positional), set(re.findall(r"--[a-z-]+", cell)))
    assert set(subcommands) == set(documented) == {*mods.commands.HANDLERS, "finish"}
    for name, (count, flags) in documented.items():
        actions = subcommands[name]._actions
        assert len([a for a in actions if not a.option_strings]) == count, name
        options = {s for a in actions for s in a.option_strings if s.startswith("--")}
        assert options - {"--help", "--dry-run"} == flags, name
        assert ("--dry-run" in options) == (
            name in ("comment", "move", "label", "upload", "update", "detach")
        )
    assert set(first_cells(parts["`trello.json`"])) == set(mods.config.FIELDS)
    assert tuple(first_cells(parts["`check` report"])) == mods.report.FIELDS
    assert set(mods.report.CHECKS) == set(mods.report.FIELDS)
    timing_row = next(
        line
        for line in parts["`trello.json`"].splitlines()
        if line.startswith("| `timing`")
    )
    assert set(re.findall(r"`(\w+)`", timing_row.split("|")[2])) == set(
        mods.config.TIMING_FIELDS
    )
    assert parser.prog == "trello.py"


def test_skill_states_scheduling_roles_and_simplify_loop() -> None:
    hosts = (SKILL / "references/hosts.md").read_text()
    headings = {line for line in hosts.splitlines() if line.startswith("## ")}
    assert {"## T3 Code", "## Claude Code", "## Codex", "## Roles + models"} <= headings
    assert "unavailable" in hosts
    run = (SKILL / "references/run.md").read_text()
    assert "## Simplify" in run.splitlines()
