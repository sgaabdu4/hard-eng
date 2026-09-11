"""Exercise the bounded Ship verifier with disposable Git repositories."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
import shipping


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
    return f"""# Fixture shipping plan
Status: Complete
## Outcome + scope
Verify a disposable shipping fixture.
## Repository context
The test uses a temporary Git repository and controlled provider responses.
## Decisions + authorization
Blockers: None
This is an authorized disposable test.
## Acceptance + steps
- [x] Verify the fixture delivery boundary.
## Baseline + execution
Result: Passed
Evidence: The fixture baseline is committed before verification.
## Risks + recovery
N/A — the disposable repository is removed after the test.
## ux_reference
N/A — this fixture has no product interface.
## Verification
Result: Passed
Evidence: The verifier asserts the provider and command contracts.
Delivery target: {target}
"""


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
        "body": "",
        "mergeable": True,
        "mergeable_state": "clean",
        "merged": False,
        "merged_at": None,
        "merge_commit_sha": None,
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
        self.calls: list[tuple[str, ...]] = []
        self.head_response = (
            "HTTP/2 200 OK\ncontent-type: image/png\ncontent-length: 10\n"
        )

    def __call__(self, _root: Path, *args: str) -> str:
        self.calls.append(args)
        if args[0] != "api":
            raise AssertionError(args)
        if "--method" in args:
            return self.head_response
        endpoint = args[-1]
        if "/pulls/" in endpoint and "/files?" not in endpoint:
            index = min(len(self.calls) - 1, len(self.pulls) - 1)
            return json.dumps(self.pulls[index])
        if "/files?" in endpoint:
            return json.dumps(self.file_payload)
        if "/check-runs?" in endpoint:
            return json.dumps(self.check_payload)
        raise AssertionError(endpoint)


def _patch_gh(monkeypatch: pytest.MonkeyPatch, fake: FakeGitHub) -> None:
    monkeypatch.setattr(shipping, "gh", fake)


_UI_BODY = (
    "Before: ![old](https://github.com/user-attachments/assets/old-image)\n"
    "After: ![new](https://github.com/user-attachments/assets/new-image)"
)


def _ui_fake(fixture: Fixture, *, body: str = _UI_BODY) -> FakeGitHub:
    return FakeGitHub(
        _pull(fixture, body=body),
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


def _add_unknown(policy: dict[str, object]) -> None:
    policy.update(extra=True)


def _duplicate_checks(policy: dict[str, object]) -> None:
    policy.update(checks=["build", "build"])


def _boolean_budget(policy: dict[str, object]) -> None:
    policy.update(ci_seconds=False)


def _zero_budget(policy: dict[str, object]) -> None:
    policy.update(pre_push_seconds=0)


def _malformed_delivery(policy: dict[str, object]) -> None:
    policy.update(delivery=[{"name": "bad"}])


def test_load_policy_is_optional_only_when_absent(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    assert shipping.load_policy(root, required=False) is None
    with pytest.raises(shipping.ShippingError):
        shipping.load_policy(root)
    (root / "hard-eng.gates.json").write_text(
        json.dumps({"shipping": {"base": "main"}})
    )
    with pytest.raises(shipping.ShippingError):
        shipping.load_policy(root, required=False)


@pytest.mark.parametrize(
    "change",
    [
        _add_unknown,
        _duplicate_checks,
        _boolean_budget,
        _zero_budget,
        _malformed_delivery,
    ],
)
def test_load_policy_rejects_malformed_values(
    tmp_path: Path, change: Callable[[dict[str, object]], None]
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    policy: dict[str, object] = {
        "base": "main",
        "checks": ["build"],
        "ui_paths": [],
        "ci_seconds": 180,
        "pre_push_seconds": 180,
        "delivery": [],
    }
    change(policy)
    (root / "hard-eng.gates.json").write_text(json.dumps({"shipping": policy}))
    with pytest.raises(shipping.ShippingError):
        shipping.load_policy(root)


def test_ready_returns_identity_after_current_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, fake = _ready_fixture(tmp_path, monkeypatch)
    shipment = shipping.verify(
        fixture.root, fixture.plan, "https://github.com/acme/widget/pull/1", "ready"
    )
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

    shipment = shipping.verify(
        fixture.root, fixture.plan, "https://github.com/acme/widget/pull/1", "ready"
    )

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
        shipping.verify(
            fixture.root, fixture.plan, "https://github.com/acme/widget/pull/1", "ready"
        )


def test_ready_preserves_unowned_dirty_work_by_rejecting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, _ = _ready_fixture(tmp_path, monkeypatch)
    (fixture.root / "unowned.txt").write_text("keep\n")
    with pytest.raises(shipping.ShippingError, match="clean"):
        shipping.verify(
            fixture.root, fixture.plan, "https://github.com/acme/widget/pull/1", "ready"
        )
    assert (fixture.root / "unowned.txt").read_text() == "keep\n"


@pytest.mark.parametrize(
    "changes",
    [
        {"draft": True},
        {"state": "closed"},
        {"mergeable": False, "mergeable_state": "blocked"},
        {"mergeable": True, "mergeable_state": "blocked"},
        {"mergeable": None, "mergeable_state": "clean"},
        {"base": {"ref": "develop", "repo": {"full_name": "acme/widget"}}},
        {
            "head": {
                "ref": "other",
                "sha": "a" * 40,
                "repo": {"full_name": "acme/widget"},
            }
        },
        {
            "head": {
                "ref": "feature/shipping",
                "sha": "a" * 40,
                "repo": {"full_name": "fork/widget"},
            }
        },
    ],
)
def test_ready_rejects_pr_identity_and_mergeability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changes: dict[str, object]
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, **changes), [_check(fixture.head)])
    _patch_gh(monkeypatch, fake)
    with pytest.raises(shipping.ShippingError):
        shipping.verify(
            fixture.root, fixture.plan, "https://github.com/acme/widget/pull/1", "ready"
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "in_progress"},
        {"conclusion": "skipped"},
        {"conclusion": "failure"},
        {"head_sha": "a" * 40},
        {"truncated": True},
        {"completed_at": "2026-09-10T14:00:00Z"},
        {"id": None},
    ],
)
def test_ready_rejects_noncurrent_or_unsuccessful_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changes: dict[str, object],
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture), [_check(fixture.head, **changes)])
    _patch_gh(monkeypatch, fake)
    with pytest.raises(shipping.ShippingError):
        shipping.verify(
            fixture.root, fixture.plan, "https://github.com/acme/widget/pull/1", "ready"
        )


def test_ready_rejects_invalid_provider_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)

    def invalid_json(_root: Path, *_args: str) -> str:
        return "not-json"

    monkeypatch.setattr(shipping, "gh", invalid_json)
    with pytest.raises(shipping.ShippingError, match="invalid JSON"):
        shipping.verify(
            fixture.root, fixture.plan, "https://github.com/acme/widget/pull/1", "ready"
        )


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
        shipment = shipping.verify(
            fixture.root, fixture.plan, "https://github.com/acme/widget/pull/1", "ready"
        )
        assert shipment.head_sha == fixture.head
    else:
        with pytest.raises(shipping.ShippingError, match="not successful"):
            shipping.verify(
                fixture.root,
                fixture.plan,
                "https://github.com/acme/widget/pull/1",
                "ready",
            )


def test_ui_changes_require_and_head_check_distinct_attachments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path, ui_paths=["src/**"])
    fake = _ui_fake(fixture)
    _patch_gh(monkeypatch, fake)
    shipment = shipping.verify(
        fixture.root, fixture.plan, "https://github.com/acme/widget/pull/1", "ready"
    )
    assert shipment.delivery_target == "PR"
    heads = [call for call in fake.calls if "--method" in call]
    assert len(heads) == 2
    assert all("--include" in call for call in heads)


@pytest.mark.parametrize(
    "body",
    [
        "After: ![new](https://github.com/user-attachments/assets/new-image)",
        "Before: ![old](https://example.invalid/old)\nAfter: ![new](https://github.com/user-attachments/assets/new-image)",
        "Before: ![old](https://github.com/user-attachments/assets/same)\nAfter: ![new](https://github.com/user-attachments/assets/same)",
    ],
)
def test_ui_changes_reject_missing_foreign_or_duplicate_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    fixture = _fixture(tmp_path, ui_paths=["src/**"])
    fake = _ui_fake(fixture, body=body)
    _patch_gh(monkeypatch, fake)
    with pytest.raises(shipping.ShippingError):
        shipping.verify(
            fixture.root, fixture.plan, "https://github.com/acme/widget/pull/1", "ready"
        )


@pytest.mark.parametrize(
    "response",
    [
        "HTTP/2 404 Not Found\ncontent-type: image/png\ncontent-length: 10\n",
        "HTTP/2 200 OK\ncontent-type: text/plain\ncontent-length: 10\n",
        "HTTP/2 200 OK\ncontent-type: image/png\ncontent-length: 0\n",
    ],
)
def test_ui_changes_reject_unavailable_or_wrong_attachment_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, response: str
) -> None:
    fixture = _fixture(tmp_path, ui_paths=["src/**"])
    fake = _ui_fake(fixture)
    fake.head_response = response
    _patch_gh(monkeypatch, fake)
    with pytest.raises(shipping.ShippingError):
        shipping.verify(
            fixture.root, fixture.plan, "https://github.com/acme/widget/pull/1", "ready"
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
        shipping.verify(
            fixture.root, fixture.plan, "https://github.com/acme/widget/pull/1", "ready"
        )


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
            "https://github.com/acme/widget/pull/1",
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
    shipment = shipping.verify(
        fixture.root, fixture.plan, "https://github.com/acme/widget/pull/1", "delivered"
    )
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
            "https://github.com/acme/widget/pull/1",
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
            "https://github.com/acme/widget/pull/1",
            "delivered",
        )
