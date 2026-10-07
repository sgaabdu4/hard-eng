"""A small change ships without a plan; a big one without a plan is refused."""

from pathlib import Path

import pytest
import shipping
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


def test_ready_without_a_plan_only_for_a_small_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    (fixture.root / "source.txt").write_text("fixture\nsmall fix\n")
    _native(fixture.root, "commit", "-qam", "small fix")
    fixture = Fixture(
        fixture.root, fixture.plan, _native(fixture.root, "rev-parse", "HEAD")
    )
    _patch_gh(monkeypatch, FakeGitHub(_pull(fixture), [_check(fixture.head)]))
    shipment = shipping.verify(fixture.root, None, _PR_URL, "ready")
    assert shipment.plan is None
    assert shipment.delivery_target == "Merge"
    (fixture.root / "added.txt").write_text("new file\n")
    _native(fixture.root, "add", "added.txt")
    _native(fixture.root, "commit", "-qm", "big change")
    fixture = Fixture(
        fixture.root, fixture.plan, _native(fixture.root, "rev-parse", "HEAD")
    )
    _patch_gh(monkeypatch, FakeGitHub(_pull(fixture), [_check(fixture.head)]))
    with pytest.raises(shipping.ShippingError, match="big change needs a plan"):
        shipping.verify(fixture.root, None, _PR_URL, "ready")
