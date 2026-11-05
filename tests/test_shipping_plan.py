"""The plan's delivery target must match the project's delivery checks; a small change ships without a plan."""

import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
import shipping
from plans import validate_plans
from shipping import ShippingPolicy
from test_shipping import (
    _PR_URL,
    FakeGitHub,
    Fixture,
    _check,
    _fixture,
    _native,
    _patch_gh,
    _pull,
)


@pytest.mark.parametrize(("delivery", "target"), [(False, "Merge"), (True, "Deploy")])
def test_ready_without_a_plan_only_for_a_small_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, delivery: bool, target: str
) -> None:
    check: dict[str, object] = {
        "name": "live",
        "command": [sys.executable, "-c", "pass"],
    }
    fixture = _fixture(tmp_path, delivery=[check] if delivery else [])
    (fixture.root / "source.txt").write_text("fixture\nsmall fix\n")
    _native(fixture.root, "commit", "-qam", "small fix")
    fixture = Fixture(
        fixture.root, fixture.plan, _native(fixture.root, "rev-parse", "HEAD")
    )
    _patch_gh(monkeypatch, FakeGitHub(_pull(fixture), [_check(fixture.head)]))
    shipment = shipping.verify(fixture.root, None, _PR_URL, "ready")
    assert shipment.plan is None
    assert shipment.delivery_target == target
    (fixture.root / "added.txt").write_text("new file\n")
    _native(fixture.root, "add", "added.txt")
    _native(fixture.root, "commit", "-qm", "big change")
    fixture = Fixture(
        fixture.root, fixture.plan, _native(fixture.root, "rev-parse", "HEAD")
    )
    _patch_gh(monkeypatch, FakeGitHub(_pull(fixture), [_check(fixture.head)]))
    with pytest.raises(shipping.ShippingError, match="big change needs a plan"):
        shipping.verify(fixture.root, None, _PR_URL, "ready")


@pytest.mark.parametrize("stage", ["Ready", "Complete"])
def test_deploy_plan_requires_verifier_before_handoff(
    runner: ModuleType, shipping_policy: ShippingPolicy, stage: str
) -> None:
    root = runner.ROOT
    plan = root / "PLAN.md"
    plan.write_text(
        plan.read_text().replace("Status: Complete", f"Status: {stage}")
        + "\nDelivery target: Deploy\nDelivery: Pending\n"
    )
    config = root / "hard-eng.gates.json"
    config.write_text(json.dumps({"shipping": shipping_policy}))
    with pytest.raises(ValueError, match="Deploy target requires configured delivery"):
        validate_plans(root, base="0" * 40, stage=stage)
    shipping_policy["delivery"] = [
        {"name": "production", "command": [sys.executable, "-c", "raise SystemExit(1)"]}
    ]
    config.write_text(json.dumps({"shipping": shipping_policy}))
    assert validate_plans(root, base="0" * 40, stage=stage) == stage


@pytest.mark.parametrize("stage", ["Ready", "Complete"])
@pytest.mark.parametrize("target", ["PR", "Merge", "Deploy"])
def test_configured_delivery_checks_need_deploy_target(
    runner: ModuleType, shipping_policy: ShippingPolicy, stage: str, target: str
) -> None:
    root = runner.ROOT
    plan = root / "PLAN.md"
    plan.write_text(
        plan.read_text().replace("Status: Complete", f"Status: {stage}")
        + f"\nDelivery target: {target}\nDelivery: Pending\n"
    )
    shipping_policy["delivery"] = [
        {"name": "production", "command": [sys.executable, "-c", "pass"]}
    ]
    (root / "hard-eng.gates.json").write_text(json.dumps({"shipping": shipping_policy}))
    if target == "Merge":
        with pytest.raises(ValueError, match="need Delivery target: Deploy"):
            validate_plans(root, base="0" * 40, stage=stage)
    else:
        assert validate_plans(root, base="0" * 40, stage=stage) == stage
