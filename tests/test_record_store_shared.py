import json
from pathlib import Path

import look
import look_records
from challenge import store
from conftest import commit, git, init


def test_a_record_made_in_a_task_worktree_outlives_it(tmp_path: Path) -> None:
    main = tmp_path / "main"
    init(main)
    (main / "README.md").write_text("project\n")
    commit(main, "init")
    head = git(main, "rev-parse", "HEAD").strip()
    task = tmp_path / "task"
    git(main, "worktree", "add", "-q", "-b", "task", str(task), "HEAD")
    challenged = store(task, head).with_suffix(".json")
    looked = look.record_path(task, head, ["aa"])
    for path in (challenged, looked):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"head": head, "outcome": "clean"}))
    git(main, "worktree", "remove", "--force", str(task))
    assert (
        json.loads(store(main, head).with_suffix(".json").read_text())["head"] == head
    )
    assert look_records.records_for(main, head) == [{"head": head, "outcome": "clean"}]


def test_a_fail_record_of_another_branch_is_no_recheck_item(tmp_path: Path) -> None:
    from test_look import judged_rule_names

    main = tmp_path / "main"
    init(main)
    (main / "README.md").write_text("project\n")
    commit(main, "init")
    first = tmp_path / "first"
    other = tmp_path / "other"
    git(main, "worktree", "add", "-q", "-b", "first", str(first), "HEAD")
    git(main, "worktree", "add", "-q", "-b", "other", str(other), "HEAD")
    (first / "a.txt").write_text("a\n")
    commit(first, "first work")
    (other / "b.txt").write_text("b\n")
    commit(other, "other work")
    first_head = git(first, "rev-parse", "HEAD").strip()
    other_head = git(other, "rev-parse", "HEAD").strip()
    rule = judged_rule_names()[0]
    path = look.record_path(first, first_head, ["aa"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "head": first_head,
                "outcome": "findings",
                "images": [{"name": "image-1.png", "file": "after-0.png"}],
                "rules": [f"{rule}: Fail — image-1.png: a flaw Fix: change it"],
            }
        )
    )
    pairs = [("image-1.png", "after-0.png", "bb")]
    git(first, "commit", "--allow-empty", "-qm", "next")
    next_head = git(first, "rev-parse", "HEAD").strip()
    items, _ = look_records.earlier_findings(first, next_head, pairs, [rule], {})
    assert len(items) == 1
    unrelated, _ = look_records.earlier_findings(other, other_head, pairs, [rule], {})
    assert unrelated == []
