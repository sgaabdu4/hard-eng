"""A join merge lifts only the linear history rule of the base, merges with a merge commit and puts the saved protection back."""

import copy
import json
import os
import signal
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import join_merge
import pytest
import ship_actions
from conftest import init
from ship_record import record_ship
from shipping import Shipment, ShippingError

HEAD = "e" * 40
BASE = "https://api.github.com/repos/acme/widget/branches/develop/protection"
ENDPOINT = "repos/acme/widget/branches/develop/protection"
FLAGS = (
    "allow_force_pushes",
    "allow_deletions",
    "block_creations",
    "required_conversation_resolution",
    "lock_branch",
    "allow_fork_syncing",
)


def saved_protection(linear: bool = True) -> dict[str, object]:
    protection: dict[str, object] = {
        "url": BASE,
        "required_status_checks": {
            "url": BASE + "/required_status_checks",
            "strict": False,
            "contexts": ["hard-eng", "canary"],
            "contexts_url": BASE + "/required_status_checks/contexts",
            "checks": [
                {"context": "hard-eng", "app_id": 15368},
                {"context": "canary", "app_id": None},
            ],
        },
        "required_signatures": {"url": BASE + "/required_signatures", "enabled": False},
        "enforce_admins": {"url": BASE + "/enforce_admins", "enabled": True},
        "required_linear_history": {"enabled": linear},
    }
    protection.update({flag: {"enabled": False} for flag in FLAGS})
    return protection


def put_body(linear: bool) -> dict[str, object]:
    return {
        "required_status_checks": {
            "strict": False,
            "checks": [
                {"context": "hard-eng", "app_id": 15368},
                {"context": "canary", "app_id": -1},
            ],
        },
        "enforce_admins": True,
        "required_pull_request_reviews": None,
        "restrictions": None,
        "required_linear_history": linear,
        **{flag: False for flag in FLAGS},
    }


class FakeGitHub:
    def __init__(self, protection: dict[str, object] | None) -> None:
        self.protection = protection
        self.calls: list[tuple[str, ...]] = []
        self.bodies: list[dict[str, object]] = []
        self.linear_at_merge: list[object] = []
        self.merge_error: ShippingError | None = None
        self.put_failures = 0
        self.read_error: ShippingError | None = None
        self.drift = False

    def __call__(self, _root: Path, *args: str) -> str:
        self.calls.append(args)
        if args[:2] == ("pr", "merge"):
            self.linear_at_merge.append(
                (self.protection or {}).get("required_linear_history")
            )
            if self.merge_error:
                raise self.merge_error
            return ""
        assert args[0] == "api"
        if "--method" in args:
            return self._put(args)
        assert args[1] == ENDPOINT
        if self.read_error:
            raise self.read_error
        if self.protection is None:
            raise ShippingError("gh query failed: gh: Branch not protected (HTTP 404)")
        return json.dumps(self.protection)

    def _put(self, args: tuple[str, ...]) -> str:
        assert args[:4] == ("api", "--method", "PUT", ENDPOINT)
        body = json.loads(Path(args[args.index("--input") + 1]).read_text())
        self.bodies.append(body)
        if body["required_linear_history"] and self.put_failures:
            self.put_failures -= 1
            raise ShippingError("gh query failed: gh: Server Error (HTTP 502)")
        assert self.protection is not None
        updated = copy.deepcopy(self.protection)
        for key in ("required_linear_history", *FLAGS):
            updated[key] = {"enabled": body[key]}
        admins = updated["enforce_admins"]
        assert isinstance(admins, dict)
        admins["enabled"] = body["enforce_admins"] != self.drift
        self.protection = updated
        return json.dumps(updated)


@pytest.fixture
def shipment(tmp_path: Path) -> Shipment:
    root = tmp_path / "checkout"
    init(root)
    record_ship(root, 7, HEAD, "join")
    return Shipment(
        root=root,
        plan=None,
        pr_url="https://github.com/acme/widget/pull/7",
        repository="acme/widget",
        remote="origin",
        remote_url="https://github.com/acme/widget.git",
        branch="chore/join-main",
        head_sha=HEAD,
        base="develop",
        merged_sha=None,
        delivery_target="Merge",
        method="join",
    )


@pytest.fixture
def pause(monkeypatch: pytest.MonkeyPatch) -> Mock:
    sleeper = Mock()
    monkeypatch.setattr(join_merge.time, "sleep", sleeper)
    return sleeper


def use(monkeypatch: pytest.MonkeyPatch, fake: FakeGitHub) -> FakeGitHub:
    monkeypatch.setattr(join_merge, "gh", fake)
    return fake


def merge_call(shipment: Shipment) -> tuple[str, ...]:
    return ("pr", "merge", shipment.pr_url, "--merge", "--match-head-commit", HEAD)


def test_the_join_merge_lifts_only_the_linear_history_rule_and_puts_the_protection_back(
    monkeypatch: pytest.MonkeyPatch, shipment: Shipment, pause: Mock
) -> None:
    fake = use(monkeypatch, FakeGitHub(saved_protection()))
    join_merge.merge_join(shipment)
    assert [call[:4] if "--method" in call else call for call in fake.calls] == [
        ("api", ENDPOINT),
        ("api", "--method", "PUT", ENDPOINT),
        merge_call(shipment),
        ("api", "--method", "PUT", ENDPOINT),
        ("api", ENDPOINT),
    ]
    assert fake.bodies == [put_body(False), put_body(True)]
    assert fake.linear_at_merge == [{"enabled": False}]
    assert fake.protection == saved_protection()
    pause.assert_not_called()


def test_the_protection_is_put_back_when_the_merge_fails(
    monkeypatch: pytest.MonkeyPatch, shipment: Shipment, pause: Mock
) -> None:
    fake = use(monkeypatch, FakeGitHub(saved_protection()))
    fake.merge_error = ShippingError("gh query failed: not mergeable")
    with pytest.raises(ShippingError, match="not mergeable"):
        join_merge.merge_join(shipment)
    assert fake.bodies == [put_body(False), put_body(True)]
    assert fake.protection == saved_protection()


def test_a_failed_put_back_is_tried_again_and_the_merge_stays_done(
    monkeypatch: pytest.MonkeyPatch, shipment: Shipment, pause: Mock
) -> None:
    fake = use(monkeypatch, FakeGitHub(saved_protection()))
    fake.put_failures = 1
    join_merge.merge_join(shipment)
    assert fake.bodies == [put_body(False), put_body(True), put_body(True)]
    assert fake.protection == saved_protection()
    assert pause.call_count == 1


def test_a_put_back_that_never_works_fails_loudly_with_the_saved_protection(
    monkeypatch: pytest.MonkeyPatch, shipment: Shipment, pause: Mock
) -> None:
    fake = use(monkeypatch, FakeGitHub(saved_protection()))
    fake.put_failures = 99
    with pytest.raises(ShippingError, match="was merged") as raised:
        join_merge.merge_join(shipment)
    assert json.dumps(put_body(True)) in str(raised.value)
    assert len(fake.bodies) == 1 + join_merge.ATTEMPTS


def test_a_protection_that_differs_after_the_put_back_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, shipment: Shipment, pause: Mock
) -> None:
    fake = use(monkeypatch, FakeGitHub(saved_protection()))
    fake.drift = True
    with pytest.raises(ShippingError, match="differs from the saved copy"):
        join_merge.merge_join(shipment)


def test_a_pull_request_that_is_not_a_join_is_refused_with_no_call(
    monkeypatch: pytest.MonkeyPatch, shipment: Shipment
) -> None:
    fake = use(monkeypatch, FakeGitHub(saved_protection()))
    with pytest.raises(ShippingError, match="only for a join"):
        join_merge.merge_join(replace(shipment, method="merge"))
    assert fake.calls == []


def test_a_join_that_fails_ship_verification_makes_no_github_call(
    monkeypatch: pytest.MonkeyPatch, shipment: Shipment
) -> None:
    fake = use(monkeypatch, FakeGitHub(saved_protection()))
    monkeypatch.setattr(
        ship_actions, "verify", Mock(side_effect=ShippingError("required check failed"))
    )
    monkeypatch.setattr(ship_actions, "require_current", Mock())
    with pytest.raises(ShippingError, match="required check failed"):
        ship_actions.run(shipment.root, None, shipment.pr_url, "merge", None, "rebase")
    assert fake.calls == []


def test_a_stop_signal_during_the_merge_still_puts_the_protection_back(
    monkeypatch: pytest.MonkeyPatch, shipment: Shipment, pause: Mock
) -> None:
    fake = use(monkeypatch, FakeGitHub(saved_protection()))
    real = fake.__call__

    def stopped(root: Path, *args: str) -> str:
        if args[:2] == ("pr", "merge"):
            os.kill(os.getpid(), signal.SIGTERM)
        return real(root, *args)

    monkeypatch.setattr(join_merge, "gh", stopped)
    before = signal.getsignal(signal.SIGTERM)
    with pytest.raises(SystemExit):
        join_merge.merge_join(shipment)
    assert fake.bodies == [put_body(False), put_body(True)]
    assert fake.protection == saved_protection()
    assert signal.getsignal(signal.SIGTERM) == before


def test_a_base_without_the_rule_is_merged_with_no_protection_write(
    monkeypatch: pytest.MonkeyPatch, shipment: Shipment
) -> None:
    fake = use(monkeypatch, FakeGitHub(saved_protection(linear=False)))
    join_merge.merge_join(shipment)
    assert fake.calls == [("api", ENDPOINT), merge_call(shipment)]


def test_a_base_with_no_protection_is_merged_with_no_protection_write(
    monkeypatch: pytest.MonkeyPatch, shipment: Shipment
) -> None:
    fake = use(monkeypatch, FakeGitHub(None))
    join_merge.merge_join(shipment)
    assert fake.calls == [("api", ENDPOINT), merge_call(shipment)]


def test_a_failed_protection_read_stops_before_any_write(
    monkeypatch: pytest.MonkeyPatch, shipment: Shipment
) -> None:
    fake = use(monkeypatch, FakeGitHub(saved_protection()))
    fake.read_error = ShippingError("gh query failed: gh: Server Error (HTTP 502)")
    with pytest.raises(ShippingError, match="502"):
        join_merge.merge_join(shipment)
    assert fake.calls == [("api", ENDPOINT)]


@pytest.mark.parametrize(
    "change",
    [
        {"required_pull_request_reviews": {"required_approving_review_count": 1}},
        {"restrictions": {"users": [], "teams": [], "apps": []}},
        {"required_signatures": {"enabled": True}},
        {"required_deployments": {"enabled": True}},
        {"required_status_checks": {"strict": False, "checks": []}},
        {"required_status_checks": {"contexts": [], "checks": []}},
        {
            "required_status_checks": {
                "strict": False,
                "contexts": [],
                "checks": [],
                "extra": 1,
            }
        },
    ],
    ids=[
        "reviews",
        "restrictions",
        "signatures",
        "unknown-field",
        "no-contexts",
        "no-strict",
        "extra-check-field",
    ],
)
def test_a_protection_that_the_put_cannot_copy_stops_before_any_write(
    monkeypatch: pytest.MonkeyPatch, shipment: Shipment, change: dict[str, object]
) -> None:
    fake = use(monkeypatch, FakeGitHub(saved_protection() | change))
    with pytest.raises(ShippingError, match="cannot copy"):
        join_merge.merge_join(shipment)
    assert fake.calls == [("api", ENDPOINT)]


def test_ship_merge_sends_a_join_through_the_protection_step_and_a_release_around_it(
    monkeypatch: pytest.MonkeyPatch, shipment: Shipment, pause: Mock
) -> None:
    fake = use(monkeypatch, FakeGitHub(saved_protection()))
    plain = Mock(return_value="")
    monkeypatch.setattr(ship_actions, "gh", plain)
    monkeypatch.setattr(ship_actions, "verify", Mock(return_value=shipment))
    ship_actions.merge(shipment.root, None, shipment, "join")
    assert fake.bodies == [put_body(False), put_body(True)]
    plain.assert_not_called()
    release = replace(shipment, method="merge")
    ship_actions.merge(shipment.root, None, release, "merge")
    assert plain.call_args.args[-3:] == ("--merge", "--match-head-commit", HEAD)
    assert len(fake.bodies) == 2


@pytest.mark.parametrize(
    ("method", "expected"), [("join", "merge refused"), ("merge", "rebase advice")]
)
def test_only_a_join_keeps_its_own_error_when_the_pull_request_cannot_be_rebased(
    monkeypatch: pytest.MonkeyPatch,
    shipment: Shipment,
    pause: Mock,
    method: str,
    expected: str,
) -> None:
    fake = use(monkeypatch, FakeGitHub(saved_protection()))
    fake.merge_error = ShippingError("merge refused")
    monkeypatch.setattr(ship_actions, "gh", Mock(side_effect=fake.merge_error))
    monkeypatch.setattr(
        ship_actions, "_pull", Mock(return_value=Mock(rebaseable=False))
    )
    monkeypatch.setattr(
        ship_actions, "rebase_problem", Mock(return_value="rebase advice")
    )
    with pytest.raises(ShippingError, match=expected):
        ship_actions.merge(
            shipment.root, None, replace(shipment, method=method), method
        )
