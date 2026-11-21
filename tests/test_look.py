"""The fresh image review: what the reviewer gets, and the proof that it opened every image."""

import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest
from conftest import SOURCE, commit, git, init
from plans import usability_rules

FIXTURES = SOURCE / "tests/fixtures/ui_quality"
PNG = b"\x89PNG\r\n\x1a\n"
CLAUDE_SCRIPT = """#!/usr/bin/env python3
import json, sys
from pathlib import Path

here = Path.cwd()
Path({log!r}).write_text(json.dumps({{"argv": sys.argv[1:], "cwd": str(here), "files": sorted(p.name for p in here.iterdir())}}))
template = Path({template!r}).read_text().splitlines()
answer = Path({answer!r}).read_text()
images = sorted(here.glob("image-*.png"))[: {reads}]
for line in template:
    if '"tool_use"' in line or '"tool_result"' in line:
        for number, image in enumerate(images):
            print(line.replace("{{path}}", str(image)).replace("toolu_012rkCioFwxYQFdLRLn2qXSt", "toolu_" + str(number)))
    else:
        print(line.replace("{{answer}}", json.dumps(answer)[1:-1]).replace("{{thread}}", "claude-session-0001"))
"""
CODEX_SCRIPT = """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

args = sys.argv[1:]
here = Path(args[args.index("--cd") + 1]) if "--cd" in args else Path.cwd()
Path({log!r}).write_text(json.dumps({{"argv": args, "cwd": str(here), "files": sorted(p.name for p in here.iterdir())}}))
thread = "019a0000-0000-7000-8000-000000000001"
answer = Path({answer!r}).read_text()
for line in Path({stream!r}).read_text().splitlines():
    print(line.replace("{{thread}}", thread).replace("{{answer}}", json.dumps(answer)[1:-1]))
folder = Path(os.environ["CODEX_HOME"]) / "sessions/2026/11/17"
folder.mkdir(parents=True, exist_ok=True)
rows = Path({session!r}).read_text().splitlines()
text = rows[0].replace("{{thread}}", thread).replace("{{time}}", "2026-11-17T10:00:00.000Z") + "\\n"
for image in sorted(here.glob("image-*.png"))[: {reads}]:
    text += rows[1].replace("{{thread}}", thread).replace("{{time}}", "2026-11-17T10:00:01.000Z").replace("{{path}}", str(image)) + "\\n"
(folder / ("rollout-2026-11-17T10-00-00-" + thread + ".jsonl")).write_text(text)
"""


def good_answer(images: int) -> str:
    rules = [f"- {name}: Pass — looked at it" for name, _ in usability_rules()]
    details = [
        f"Image image-{n}.png: a card with a title" for n in range(1, images + 1)
    ]
    return "\n".join([*rules, *details, "VERDICT: clean"])


def install_agent(tmp_path: Path, name: str, reads: int, answer: str) -> Path:
    folder = tmp_path / "bin"
    folder.mkdir(exist_ok=True)
    log = tmp_path / f"{name}.log"
    answer_file = tmp_path / f"{name}.answer"
    answer_file.write_text(answer)
    if name == "claude":
        script = CLAUDE_SCRIPT.format(
            log=str(log),
            template=str(FIXTURES / "claude-stream.jsonl"),
            answer=str(answer_file),
            reads=reads,
        )
    else:
        script = CODEX_SCRIPT.format(
            log=str(log),
            stream=str(FIXTURES / "codex-stream.jsonl"),
            session=str(FIXTURES / "codex-session.jsonl"),
            answer=str(answer_file),
            reads=reads,
        )
    path = folder / name
    path.write_text(script)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return log


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "project"
    init(root)
    (root / "README.md").write_text("project\n")
    commit(root, "init")
    only_fakes = os.pathsep.join(
        [str(tmp_path / "bin"), str(Path(sys.executable).parent), "/usr/bin", "/bin"]
    )
    monkeypatch.setenv("PATH", only_fakes)
    (tmp_path / "bin").mkdir()
    (tmp_path / "codex-home").mkdir()
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    return root


def make_images(root: Path, count: int) -> list[Path]:
    folder = root / ".hard-eng/browser"
    folder.mkdir(parents=True)
    images = []
    for number in range(count):
        image = folder / f"after-{number}.png"
        image.write_bytes(PNG + bytes([number]) * 20)
        images.append(image)
    return images


def run_look(root: Path, host: str, images: list[Path]) -> dict[str, object]:
    import look

    code = look.look_command(root, ["--host", host, *map(str, images)])
    head = git(root, "rev-parse", "HEAD").strip()
    hashes = [hashlib.sha256(image.read_bytes()).hexdigest() for image in images]
    record: dict[str, object] = json.loads(
        look.record_path(root, head, hashes).read_text()
    )
    assert (code == 0) == (record["outcome"] == "clean")
    return record


OTHER = {"claude": "codex", "codex": "claude"}


def listed(record: dict[str, object], key: str) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], record[key])


@pytest.mark.parametrize("reviewer", ["claude", "codex"])
def test_look_refuses_an_unopened_image(
    tmp_path: Path, project: Path, reviewer: str
) -> None:
    images = make_images(project, 2)
    install_agent(tmp_path, reviewer, 1, good_answer(2))
    record = run_look(project, OTHER[reviewer], images)
    assert str(record["outcome"]).startswith("not done")
    assert "image-2.png" in str(record["outcome"])
    assert [item["read"] for item in listed(record, "images")] == [True, False]
    install_agent(tmp_path, reviewer, 2, good_answer(2))
    record = run_look(project, OTHER[reviewer], images)
    assert record["outcome"] == "clean"
    assert [item["sha256"] for item in listed(record, "images")] == [
        hashlib.sha256(image.read_bytes()).hexdigest() for image in images
    ]


def test_look_reads_codex_image_views_from_the_session_file(
    tmp_path: Path, project: Path
) -> None:
    images = make_images(project, 2)
    install_agent(tmp_path, "codex", 2, good_answer(2))
    record = run_look(project, "claude", images)
    assert record["outcome"] == "clean"
    assert record["reviewer"] == "codex"
    assert all(item["read"] for item in listed(record, "images"))
    install_agent(tmp_path, "codex", 0, good_answer(2))
    assert str(run_look(project, "claude", images)["outcome"]).startswith("not done")


def test_look_prompt_holds_only_images_and_rules(tmp_path: Path, project: Path) -> None:
    images = make_images(project, 2)
    log = install_agent(tmp_path, "claude", 2, good_answer(2))
    run_look(project, "codex", images)
    seen = json.loads(log.read_text())
    prompt = " ".join(seen["argv"])
    assert seen["files"] == ["image-1.png", "image-2.png"]
    for forbidden in (str(project), "PLAN", "diff", "Pass line", "after-0", "builder"):
        assert forbidden not in prompt, forbidden
    assert all(name in prompt for name, _ in usability_rules())
    assert project.name not in seen["cwd"]


def test_look_falls_back_to_a_fresh_same_agent_session(
    tmp_path: Path, project: Path
) -> None:
    images = make_images(project, 1)
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    record = run_look(project, "claude", images)
    assert record["reviewer"] == "claude"
    assert record["fresh_same_agent"] is True
    assert json.loads(log.read_text())["argv"]


def test_look_block_holds_no_session_id_and_no_local_path(
    tmp_path: Path, project: Path
) -> None:
    import look

    images = make_images(project, 1)
    install_agent(tmp_path, "claude", 1, good_answer(1))
    record = run_look(project, "codex", images)
    block = look.block_text(record)
    assert "claude-session-0001" not in block
    assert record["session"] == hashlib.sha256(b"claude-session-0001").hexdigest()
    assert look.block_problem(block, 1) is None
    assert str(project) not in block and str(tmp_path) not in block


def test_the_look_command_is_listed_in_the_runner_help() -> None:
    done = subprocess.run(
        [sys.executable, str(SOURCE / ".hooks/hard-eng.py"), "look", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "images" in done.stdout and "--host" in done.stdout


def test_review_text_names_the_look_command() -> None:
    review = (SOURCE / ".agents/skills/code-review/references/review.md").read_text()
    assert "hard-eng.py look" in review
    assert "Do not accept a typed Pass line in place of a `look` block" in review


def test_a_second_look_run_at_the_same_commit_keeps_the_first_record(
    tmp_path: Path, project: Path
) -> None:
    import look

    images = make_images(project, 2)
    install_agent(tmp_path, "codex", 1, good_answer(1))
    first = run_look(project, "claude", images[:1])
    install_agent(tmp_path, "codex", 1, good_answer(1))
    second = run_look(project, "claude", images[1:])
    assert first["images"] != second["images"]
    head = git(project, "rev-parse", "HEAD").strip()
    assert len(look.records_for(project, head)) == 2
    first_hash = hashlib.sha256(images[0].read_bytes()).hexdigest()
    assert any(
        item["sha256"] == first_hash
        for record in look.records_for(project, head)
        for item in listed(record, "images")
    )


def test_look_reads_the_rule_lines_and_image_lines_a_reviewer_actually_writes(
    tmp_path: Path, project: Path
) -> None:
    images = make_images(project, 1)
    rules = [f"- **{name}**: Pass — looked at it" for name, _ in usability_rules()]
    rules[1] = "- Least effort (clicks: 0): N/A — nothing to click"
    rules[4] = "- No clutter (kept: 20, removed: 0): Pass — one secondary line"
    answer = "\n".join(
        [
            "Review of the image:",
            *rules,
            "- Image image-1.png: a card with a title",
            "- Overall: a plain card",
            "VERDICT: clean",
        ]
    )
    install_agent(tmp_path, "claude", 1, answer)
    record = run_look(project, "codex", images)
    assert record["outcome"] == "clean", record["outcome"]
    assert len(listed(record, "images")) == 1
    assert "image-1.png" in cast(dict[str, str], record["details"])


def test_look_reads_a_real_claude_answer() -> None:
    import look

    answer = (FIXTURES / "claude-answer.txt").read_text()
    outcome, rules, details = look.judge(answer, ["image-1.png"], {"image-1.png": True})
    assert outcome == "findings"
    assert len(rules) == len(usability_rules())
    assert "image-1.png" in details
