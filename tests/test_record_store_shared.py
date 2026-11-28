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
