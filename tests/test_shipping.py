"""Exercise the bounded Ship verifier with disposable Git repositories."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
import shipping
from conftest import plan_document


@dataclass(frozen=True)
class Fixture:
    root: Path
    plan: Path
    head: str


def _native(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _plan(target: str = "PR") -> str:
    return plan_document() + f"Delivery target: {target}\n"


def _fixture(
    tmp_path: Path,
    *,
    target: str = "PR",
    ui_paths: list[str] | None = None,
    delivery: list[dict[str, object]] | None = None,
) -> Fixture:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    _native(root, "config", "user.email", "test@example.invalid")
    _native(root, "config", "user.name", "Shipping Test")
    policy: dict[str, object] = {
        "base": "main",
        "checks": ["build"],
        "ui_paths": ui_paths or [],
        "ci_seconds": 180,
        "pre_push_seconds": 180,
        "delivery": delivery or [],
    }
    (root / "hard-eng.gates.json").write_text(
        json.dumps({"version": 1, "packages": [], "shared": [], "shipping": policy})
    )
    (root / "PLAN.md").write_text(_plan(target))
    (root / "source.txt").write_text("fixture\n")
    _native(root, "add", "--all")
    _native(root, "commit", "-qm", "fixture")
    _native(root, "branch", "-M", "main")
    _native(root, "switch", "-qc", "feature/shipping")
    _native(root, "remote", "add", "origin", "https://github.com/acme/widget.git")
    head = _native(root, "rev-parse", "HEAD")
    return Fixture(root, root / "PLAN.md", head)


_DIAGRAM = '```mermaid\nflowchart TD\n    A["old"] --> B["new"]\n```\n'
_UNDO = (
    "Undo: revert the PR's commits on main.\n"
    + _DIAGRAM * 2
    + "Not checked: None \u2014 fixture.\n"
)


def _pull(fixture: Fixture, **changes: object) -> dict[str, object]:
    pull: dict[str, object] = {
        "state": "open",
        "draft": False,
        "head": {
            "ref": "feature/shipping",
            "sha": fixture.head,
            "repo": {"full_name": "acme/widget"},
        },
        "base": {
            "ref": "main",
            "sha": "a" * 40,
            "repo": {"full_name": "acme/widget"},
        },
        "body": _UNDO,
        "mergeable": True,
        "mergeable_state": "clean",
        "merged": False,
        "merged_at": None,
        "merge_commit_sha": None,
        "commits": 1,
        "rebaseable": True,
    }
    pull.update(changes)
    return pull


def _check(revision: str, **changes: object) -> dict[str, object]:
    result: dict[str, object] = {
        "id": 1,
        "name": "build",
        "head_sha": revision,
        "status": "completed",
        "conclusion": "success",
        "started_at": "2026-09-10T10:00:00Z",
        "completed_at": "2026-09-10T10:00:10Z",
    }
    result.update(changes)
    return result


_OWNER = {"login": "owner", "permissions": {"push": True}}


def _run(
    database_id: object = 1,
    conclusion: object = "SUCCESS",
    *,
    name: str = "build",
    app: object = 15368,
    workflow: object = 1,
    status: str = "COMPLETED",
    suite: object = ...,
) -> dict[str, object]:
    suite_id = database_id if suite is ... else suite
    suite = {"databaseId": suite_id, "app": {"databaseId": app}}
    if workflow is not None:
        suite["workflowRun"] = {"workflow": {"databaseId": workflow}}
    return {
        "name": name,
        "databaseId": database_id,
        "status": status,
        "conclusion": conclusion,
        "checkSuite": suite,
    }


def _contexts(*nodes: object) -> dict[str, object]:
    return {"totalCount": len(nodes), "nodes": list(nodes)}


_ROLLUP_RUNS = {
    "SUCCESS": _run(),
    "FAILURE": _run(conclusion="FAILURE"),
    "PENDING": _run(conclusion=None, status="IN_PROGRESS"),
}


def _review(
    head: str, rollup: object = "SUCCESS", contexts: object = None, **changes: object
) -> object:
    empty = {"totalCount": 0, "nodes": []}
    run = _ROLLUP_RUNS.get(str(rollup), _run())
    checks = {"state": rollup, "contexts": contexts or _contexts(run)}
    pull: dict[str, object] = {
        "viewerDidAuthor": True,
        "viewerCanMergeAsAdmin": True,
        "reviewDecision": "REVIEW_REQUIRED",
        "isMergeQueueEnabled": False,
        "reviewThreads": empty,
        "baseRef": {"rules": empty},
        "commits": {"nodes": [{"commit": {"oid": head, "statusCheckRollup": checks}}]},
    }
    pull.update(changes)
    return {"data": {"viewer": {"login": "owner"}, "repository": {"pullRequest": pull}}}


class FakeGitHub:
    def __init__(
        self,
        pull: dict[str, object],
        checks: list[dict[str, object]],
        files: list[dict[str, object]] | None = None,
    ) -> None:
        self.pulls = [pull]
        self.check_payload: object = [
            {"total_count": len(checks), "check_runs": checks}
        ]
        self.file_payload: object = [files or []]
        no_runs: list[object] = []
        self.push_runs: object = [{"total_count": 0, "workflow_runs": no_runs}]
        self.review: object = _review("0" * 40, viewerDidAuthor=False)
        self.rules: object = None
        self.job: object = None
        self.collaborators: object = [[_OWNER]]
        self.codeowners: dict[str, str] = {}
        self.comparison: object = {"behind_by": 0}
        self.calls: list[tuple[str, ...]] = []
        self.setting_reads: list[tuple[str, ...]] = []
        self.rebase_merge_allowed: object = True
        self.attachment_response = (
            "HTTP/2 206 Partial Content\ncontent-type: image/png\n"
            "content-length: 1\ncontent-range: bytes 0-0/85098\n"
        )

    def _setting(self, args: tuple[str, ...]) -> str:
        if args[:2] != ("repo", "view"):
            raise AssertionError(args)
        self.setting_reads.append(args)
        return json.dumps({"rebaseMergeAllowed": self.rebase_merge_allowed})

    def __call__(self, _root: Path, *args: str) -> str:
        if args[0] != "api":
            return self._setting(args)
        self.calls.append(args)
        if args[1] == "graphql":
            return json.dumps(self.rules if "Administer" in args[-1] else self.review)
        if "--method" in args:
            if "HEAD" in args:
                raise shipping.ShippingError("gh query failed")
            return self.attachment_response
        endpoint = args[-1]
        path = endpoint.partition("/contents/")[2].partition("?")[0]
        if path:
            if path not in self.codeowners:
                raise shipping.ShippingError("gh query failed")
            return self.codeowners[path]
        payloads = {
            "/files?": self.file_payload,
            "/check-runs?": self.check_payload,
            "/actions/runs?": self.push_runs,
            "/collaborators?": self.collaborators,
            "/compare/": self.comparison,
            "/actions/jobs/": self.job,
        }
        for marker, payload in payloads.items():
            if marker in endpoint:
                return json.dumps(payload)
        if "/pulls/" in endpoint:
            index = min(len(self.calls) - 1, len(self.pulls) - 1)
            return json.dumps(self.pulls[index])
        raise AssertionError(endpoint)


def _patch_gh(monkeypatch: pytest.MonkeyPatch, fake: FakeGitHub) -> None:
    monkeypatch.setattr(shipping, "gh", fake)


_PR_URL = "https://github.com/acme/widget/pull/1"
_UI_BODY = (
    "Before: ![old](https://github.com/user-attachments/assets/old-image)\n"
    "After: ![new](https://github.com/user-attachments/assets/new-image)"
)
_NATIVE_VIDEO_BODY = "Before:\n\nhttps://github.com/user-attachments/assets/old-video\n\nAfter:\n\nhttps://github.com/user-attachments/assets/new-video"
_NATIVE_VIDEO_BODY_CRLF = _NATIVE_VIDEO_BODY.replace("\n", "\r\n")
_MIXED_UI_BODY = "Before: ![old](https://github.com/user-attachments/assets/old-image)\nAfter:\n\nhttps://github.com/user-attachments/assets/new-video"


def _ui_fake(fixture: Fixture, *, body: str = _UI_BODY) -> FakeGitHub:
    return FakeGitHub(
        _pull(fixture, body=f"{body}\n{_UNDO}"),
        [_check(fixture.head)],
        [{"filename": "src/App.tsx"}],
    )


def _ready_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Fixture, FakeGitHub]:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture), [_check(fixture.head)])
    _patch_gh(monkeypatch, fake)
    return fixture, fake


def test_ready_returns_identity_after_current_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, fake = _ready_fixture(tmp_path, monkeypatch)
    shipment = shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    assert shipment.root == fixture.root.resolve()
    assert shipment.plan == fixture.plan.resolve()
    assert shipment.repository == "acme/widget"
    assert shipment.remote == "origin"
    assert shipment.remote_url == "https://github.com/acme/widget.git"
    assert shipment.branch == "feature/shipping"
    assert shipment.head_sha == fixture.head
    assert shipment.base == "main"
    assert shipment.merged_sha is None
    assert shipment.delivery_target == "PR"
    assert sum("/pulls/1" in call[-1] for call in fake.calls) == 2
    assert any("check-runs" in call[-1] for call in fake.calls)


@pytest.mark.parametrize(
    ("diagrams", "passes"), [(0, False), (1, False), (2, True), (3, True)]
)
def test_ready_refuses_a_pr_body_with_no_before_and_after_diagrams(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, diagrams: int, passes: bool
) -> None:
    fixture = _fixture(tmp_path)
    body = (
        "Undo: revert the commits.\nNot checked: None \u2014 fixture.\n"
        + _DIAGRAM * diagrams
    )
    fake = FakeGitHub(_pull(fixture, body=body), [_check(fixture.head)])
    message = None if passes else "Before and after"
    _ready_outcome(fixture, fake, monkeypatch, message)


def test_configured_delivery_checks_refuse_merge_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(
        tmp_path,
        target="Merge",
        delivery=[{"name": "live", "command": [sys.executable, "-c", "pass"]}],
    )
    fake = FakeGitHub(_pull(fixture), [_check(fixture.head)])
    _patch_gh(monkeypatch, fake)
    with pytest.raises(shipping.ShippingError, match="need Delivery target: Deploy"):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    assert not fake.calls


@pytest.mark.parametrize("configured", [False, True])
def test_deploy_readiness_requires_verifier_without_running_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, configured: bool
) -> None:
    fixture = _fixture(
        tmp_path,
        target="Deploy",
        delivery=[
            {"name": "live", "command": [sys.executable, "-c", "raise SystemExit(1)"]}
        ]
        if configured
        else [],
    )
    fake = FakeGitHub(_pull(fixture), [_check(fixture.head)])
    _patch_gh(monkeypatch, fake)
    if configured:
        shipment = shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
        assert shipment.delivery_target == "Deploy"
    else:
        with pytest.raises(
            shipping.ShippingError, match="Deploy target requires configured delivery"
        ):
            shipping.verify(
                fixture.root,
                fixture.plan,
                _PR_URL,
                "ready",
            )
        assert not fake.calls


def test_ready_accepts_same_second_check_timestamps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(
        _pull(fixture),
        [
            _check(
                fixture.head,
                started_at="2026-09-10T10:00:00Z",
                completed_at="2026-09-10T10:00:00Z",
            )
        ],
    )
    _patch_gh(monkeypatch, fake)

    shipment = shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")

    assert shipment.head_sha == fixture.head


def test_ready_rejects_check_without_head_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    check = _check(fixture.head)
    del check["head_sha"]
    fake = FakeGitHub(_pull(fixture), [check])
    _patch_gh(monkeypatch, fake)

    with pytest.raises(shipping.ShippingError, match="stale"):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")


def test_ready_preserves_unowned_dirty_work_by_rejecting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, _ = _ready_fixture(tmp_path, monkeypatch)
    (fixture.root / "unowned.txt").write_text("keep\n")
    with pytest.raises(shipping.ShippingError, match="clean"):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    assert (fixture.root / "unowned.txt").read_text() == "keep\n"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"draft": True}, "open and ready"),
        ({"state": "closed"}, "open and ready"),
        (
            {"mergeable": False, "mergeable_state": "blocked"},
            "mergeability is not clean",
        ),
        ({"mergeable": None, "mergeable_state": "clean"}, "mergeability is not clean"),
        (
            {"base": {"ref": "develop", "repo": {"full_name": "acme/widget"}}},
            "base branch",
        ),
        (
            {"head": {"ref": "other", "repo": {"full_name": "acme/widget"}}},
            "does not match PR",
        ),
        (
            {"head": {"ref": "feature/shipping", "repo": {"full_name": "fork/widget"}}},
            "head repository",
        ),
    ],
)
def test_ready_rejects_pr_identity_and_mergeability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changes: dict[str, object],
    message: str,
) -> None:
    fixture = _fixture(tmp_path)
    head = changes.get("head")
    if isinstance(head, dict):
        head.setdefault("sha", fixture.head)
    fake = FakeGitHub(_pull(fixture, **changes), [_check(fixture.head)])
    fake.review = _review(fixture.head)
    _patch_gh(monkeypatch, fake)
    with pytest.raises(shipping.ShippingError, match=message):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")


def _ready_outcome(
    fixture: Fixture,
    fake: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
    message: str | None,
) -> shipping.Shipment | None:
    """The ready shipment, or None after `verify` refused it with the message."""
    _patch_gh(monkeypatch, fake)
    if message is None:
        return shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    with pytest.raises(shipping.ShippingError, match=message):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    return None


@pytest.mark.parametrize(
    ("state", "review", "others", "message"),
    [
        ("blocked", {}, [{"login": "reader", "permissions": {"push": False}}], None),
        ("clean", {}, [], None),
        ("blocked", {}, [{"login": "peer", "permissions": {"push": True}}], "another"),
        ("blocked", {"viewerDidAuthor": False}, [], "did not author"),
        ("blocked", {"viewerCanMergeAsAdmin": False}, [], "cannot bypass"),
        ("blocked", {"reviewDecision": "CHANGES_REQUESTED"}, [], "required review"),
        ("blocked", {"reviewDecision": None}, [], "required review"),
        ("blocked", {"rollup": "FAILURE"}, [], "head check"),
        ("blocked", {"rollup": "PENDING"}, [], "head check"),
        ("blocked", {"isMergeQueueEnabled": True}, [], "merge queue"),
        ("dirty", {}, [], "not clean"),
    ],
)
def test_ready_bypasses_only_a_review_nobody_but_the_author_can_give(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
    review: dict[str, object],
    others: list[object],
    message: str | None,
) -> None:
    fixture = _fixture(tmp_path)
    pull = _pull(fixture, mergeable_state=state, mergeable=state != "dirty")
    fake = FakeGitHub(pull, [_check(fixture.head)])
    fake.review = _review(fixture.head, **review)
    fake.collaborators = [[_OWNER, *others]]
    shipment = _ready_outcome(fixture, fake, monkeypatch, message)
    if shipment is not None:
        assert shipment.review_bypass is (state == "blocked")


@pytest.mark.parametrize("state", ["blocked", "unstable"])
@pytest.mark.parametrize(
    ("changes", "error", "message"),
    [
        ({"status": "in_progress"}, shipping.PendingCheck, "has not completed"),
        ({"conclusion": "failure"}, shipping.ShippingError, "not successful"),
    ],
)
def test_ready_names_a_pending_or_failed_check_before_the_review_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
    changes: dict[str, object],
    error: type[Exception],
    message: str,
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(
        _pull(fixture, mergeable_state=state), [_check(fixture.head, **changes)]
    )
    fake.review = _review(fixture.head, viewerCanMergeAsAdmin=False)
    _patch_gh(monkeypatch, fake)
    with pytest.raises(error, match=message):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"status": "in_progress"}, "has not completed"),
        ({"conclusion": "skipped"}, "was skipped; gate its steps, not the job: build"),
        ({"conclusion": "failure"}, "not successful"),
        ({"head_sha": "a" * 40}, "stale"),
        ({"truncated": True}, "truncated"),
        ({"completed_at": "2026-09-10T14:00:00Z"}, "CI budget"),
        ({"id": None}, "run identity"),
        ({"plan": "absent/PLAN.md"}, "check out the PR's head branch"),
    ],
)
def test_ready_rejects_noncurrent_or_unsuccessful_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changes: dict[str, object],
    message: str,
) -> None:
    fixture = _fixture(tmp_path)
    plan = fixture.root / str(changes.pop("plan", "PLAN.md"))
    fake = FakeGitHub(_pull(fixture), [_check(fixture.head, **changes)])
    _patch_gh(monkeypatch, fake)
    with pytest.raises(shipping.ShippingError, match=message):
        shipping.verify(fixture.root, plan, _PR_URL, "ready")


def test_required_check_that_has_not_started_is_pending_not_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    _patch_gh(monkeypatch, FakeGitHub(_pull(fixture), []))
    with pytest.raises(shipping.PendingCheck, match="required check missing: build"):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")


def test_failed_git_command_reports_its_own_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LC_ALL", "C")
    root = _fixture(tmp_path).root
    with pytest.raises(shipping.ShippingError, match=r"^git query failed: fatal: \S"):
        shipping.git(root, "rev-parse", "--verify", "missing")
    with pytest.raises(shipping.ShippingError, match=r"^git query failed$"):
        shipping.git(root, "rev-parse", "--verify", "--quiet", "missing")


def test_ready_rejects_invalid_provider_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)

    def invalid_json(_root: Path, *_args: str) -> str:
        return "not-json"

    monkeypatch.setattr(shipping, "gh", invalid_json)
    with pytest.raises(shipping.ShippingError, match="invalid JSON"):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")


@pytest.mark.parametrize("outcome", ["queued", "in_progress", "failure", "success"])
def test_newest_required_run_wins_over_later_finishing_old_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    fixture = _fixture(tmp_path)
    completed = outcome in {"failure", "success"}
    old = _check(
        fixture.head,
        id=101,
        conclusion="failure" if outcome == "success" else "success",
        started_at="2026-09-10T10:00:10Z",
        completed_at="2026-09-10T10:00:30Z",
    )
    new = _check(
        fixture.head,
        id=202,
        status="completed" if completed else outcome,
        conclusion=outcome if completed else None,
        started_at=None if outcome == "queued" else "2026-09-10T10:00:20Z",
        completed_at="2026-09-10T10:00:22Z" if completed else None,
    )
    _patch_gh(monkeypatch, FakeGitHub(_pull(fixture), [new, old]))
    if outcome == "success":
        shipment = shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
        assert shipment.head_sha == fixture.head
    else:
        error = shipping.ShippingError if completed else shipping.PendingCheck
        with pytest.raises(error, match="not successful|not completed"):
            shipping.verify(
                fixture.root,
                fixture.plan,
                _PR_URL,
                "ready",
            )


def test_ready_rejects_changed_pr_head_during_final_recheck(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    first = _pull(fixture)
    changed_head = {
        "ref": "feature/shipping",
        "sha": "b" * 40,
        "repo": {"full_name": "acme/widget"},
    }
    second = _pull(fixture, head=changed_head)
    fake = FakeGitHub(first, [_check(fixture.head)])
    fake.pulls = [first, second]
    _patch_gh(monkeypatch, fake)
    with pytest.raises(shipping.ShippingError, match="changed"):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")


@pytest.mark.parametrize(
    "answer",
    [
        {"status": "passed", "revision": "0" * 40},
        {"status": "failed", "revision": "1" * 40},
    ],
)
def test_a_delivery_check_must_report_passed_for_the_new_revision(
    tmp_path: Path, answer: dict[str, str]
) -> None:
    code = "import sys; print(sys.argv[1])"
    command = [sys.executable, "-c", code, json.dumps(answer)]
    _delivery_refusal(tmp_path, command, "did not prove revision: live")


def _delivery_refusal(tmp_path: Path, command: list[str], match: str) -> None:
    fixture = _fixture(
        tmp_path, target="Deploy", delivery=[{"name": "live", "command": command}]
    )
    policy = shipping.load_policy(fixture.root, required=True)
    assert policy is not None
    with pytest.raises(shipping.ShippingError, match=match):
        shipping._delivery(fixture.root, policy, "1" * 40, _PR_URL)


def test_a_failed_delivery_check_keeps_its_reason(tmp_path: Path) -> None:
    command = [sys.executable, "-c", "import sys; sys.exit('deploy not found')"]
    _delivery_refusal(tmp_path, command, "live.*deploy not found")


def test_delivered_deploy_rejects_old_live_revision_then_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deployed = tmp_path / "live-revision"
    code = (
        "import json, os, sys; actual=open("
        + repr(str(deployed))
        + ").read().strip(); "
        "expected=os.environ['HE_SHIP_REVISION']; "
        "sys.exit(1) if actual != expected else print(json.dumps({'status':'passed','revision':expected}))"
    )
    fixture = _fixture(
        tmp_path,
        target="Deploy",
        delivery=[{"name": "live", "command": [sys.executable, "-c", code]}],
    )
    deployed.parent.mkdir(exist_ok=True)
    deployed.write_text("0" * 40)
    pull = _pull(
        fixture,
        state="closed",
        merged=True,
        merged_at="2026-09-10T11:00:00Z",
        merge_commit_sha=fixture.head,
    )
    fake = FakeGitHub(pull, [_check(fixture.head)])
    _patch_gh(monkeypatch, fake)
    real_git = shipping.git

    def controlled_git(root: Path, *args: str) -> str:
        if args == (
            "ls-remote",
            "--heads",
            "https://github.com/acme/widget.git",
            "refs/heads/main",
        ):
            _native(
                root, "remote", "set-url", "origin", "https://github.com/other/repo.git"
            )
            return f"{fixture.head}\trefs/heads/main\n"
        if args == (
            "fetch",
            "--no-tags",
            "https://github.com/acme/widget.git",
            "refs/heads/main:refs/remotes/origin/main",
        ):
            return ""
        return real_git(root, *args)

    monkeypatch.setattr(shipping, "git", controlled_git)
    with pytest.raises(shipping.ShippingError, match="delivery check failed"):
        shipping.verify(
            fixture.root,
            fixture.plan,
            _PR_URL,
            "delivered",
        )
    deployed.write_text(fixture.head)
    _native(
        fixture.root,
        "remote",
        "set-url",
        "origin",
        "https://github.com/acme/widget.git",
    )
    _native(fixture.root, "branch", "-m", "feature/unrelated")
    shipment = shipping.verify(fixture.root, fixture.plan, _PR_URL, "delivered")
    assert shipment.merged_sha == fixture.head
    assert shipment.delivery_target == "Deploy"
    assert shipment.branch == "feature/shipping"
    assert shipment.remote_url == "https://github.com/acme/widget.git"
    assert (
        _native(fixture.root, "remote", "get-url", "origin")
        == "https://github.com/other/repo.git"
    )


def test_delivered_rejects_unmerged_or_unreachable_pr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path, target="Merge")
    fake = FakeGitHub(_pull(fixture), [_check(fixture.head)])
    _patch_gh(monkeypatch, fake)
    with pytest.raises(shipping.ShippingError, match="merged"):
        shipping.verify(
            fixture.root,
            fixture.plan,
            _PR_URL,
            "delivered",
        )

    pull = _pull(
        fixture,
        state="closed",
        merged=True,
        merged_at="2026-09-10T11:00:00Z",
        merge_commit_sha="b" * 40,
    )
    fake.pulls = [pull]
    real_git = shipping.git

    def missing_base(root: Path, *args: str) -> str:
        if args == (
            "ls-remote",
            "--heads",
            "https://github.com/acme/widget.git",
            "refs/heads/main",
        ):
            return f"{'a' * 40}\trefs/heads/main\n"
        if args == (
            "fetch",
            "--no-tags",
            "https://github.com/acme/widget.git",
            "refs/heads/main:refs/remotes/origin/main",
        ):
            return ""
        return real_git(root, *args)

    monkeypatch.setattr(shipping, "git", missing_base)
    with pytest.raises(shipping.ShippingError, match="reachable"):
        shipping.verify(
            fixture.root,
            fixture.plan,
            _PR_URL,
            "delivered",
        )


@dataclass
class MergedPush:
    root: Path
    base: str
    head: str
    responses: dict[str, object]
    pulls: list[dict[str, object]]


def _merged_push(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    method: str = "squash",
) -> MergedPush:
    fixture = _fixture(tmp_path)
    root = fixture.root
    base = _native(root, "rev-parse", "main")
    (root / "source.txt").write_text("changed\n")
    _native(root, "commit", "-qam", "Change the source")
    (root / "source.txt").write_text("changed again\n")
    _native(root, "commit", "-qam", "Change the source again")
    _native(root, "switch", "-q", "main")
    head = _native(root, "rev-parse", "feature/shipping")
    if method == "merge":
        _native(root, "merge", "-q", "--no-ff", "-m", "Merge feature", head)
    elif method == "rebase":
        _native(root, "cherry-pick", f"{base}..{head}")
    else:
        _native(root, "merge", "-q", "--squash", head)
        _native(
            root, "commit", "-qm", "Change the source (#7)", "-m", "* Change the source"
        )
    pulls: list[dict[str, object]] = [
        {
            "number": 7,
            "merged_at": "2026-10-07T10:00:00Z",
            "base": {"ref": "main"},
            "head": {"sha": head},
        }
    ]
    responses: dict[str, object] = {
        f"commits/{_native(root, 'rev-parse', 'HEAD')}/pulls": pulls,
        f"compare/{base}...{head}": {"status": "ahead"},
        f"git/commits/{head}": {
            "tree": {"sha": _native(root, "rev-parse", "HEAD^{tree}")}
        },
        f"commits/{head}/check-runs?per_page=100&filter=all": [
            {"total_count": 1, "check_runs": [_check(head)]}
        ],
    }

    def github(_root: Path, *args: str) -> str:
        endpoint = args[-1].removeprefix("repos/acme/widget/")
        if endpoint not in responses:
            raise shipping.ShippingError("gh query failed")
        return json.dumps(responses[endpoint])

    monkeypatch.setattr(shipping, "gh", github)
    for name, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REPOSITORY": "acme/widget",
    }.items():
        monkeypatch.setenv(name, value)
    return MergedPush(root, base, head, responses, pulls)


@pytest.mark.parametrize(
    ("conclusion", "expected"), [("success", True), ("failure", False)]
)
def test_branch_point_is_reused_only_after_its_checks_passed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, conclusion: str, expected: bool
) -> None:
    fixture = _fixture(tmp_path)
    point = _native(fixture.root, "rev-parse", "main")

    def github(_root: Path, *args: str) -> str:
        assert args[-1] == (
            f"repos/acme/widget/commits/{point}/check-runs?per_page=100&filter=all"
        )
        return json.dumps(
            [{"total_count": 1, "check_runs": [_check(point, conclusion=conclusion)]}]
        )

    monkeypatch.setattr(shipping, "gh", github)
    assert shipping.passed_branch_point(fixture.root) == (point if expected else None)


def test_the_clean_checkout_refusal_names_the_files(tmp_path: Path) -> None:
    _native(tmp_path, "init", "-q")
    (tmp_path / "tracked.py").write_text("x = 1\n")
    _native(tmp_path, "add", ".")
    _native(
        tmp_path,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-qm",
        "base",
    )
    shipping._clean(tmp_path)
    (tmp_path / "tracked.py").write_text("x = 2\n")
    for number in range(6):
        (tmp_path / f"extra{number}.py").write_text("y = 1\n")
    with pytest.raises(shipping.ShippingError) as refusal:
        shipping._clean(tmp_path)
    message = str(refusal.value)
    assert "tracked.py, extra0.py, extra1.py, extra2.py, extra3.py" in message
    assert "extra4.py" not in message and message.endswith("and 2 more")
