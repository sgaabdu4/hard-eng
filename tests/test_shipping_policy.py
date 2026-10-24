"""Strict loading of the shipping policy in hard-eng.gates.json."""

import json
from pathlib import Path

import pytest
import shipping


def _write(root: Path, **changes: object) -> None:
    policy: dict[str, object] = {
        "base": "main",
        "checks": ["build"],
        "ui_paths": [],
        "ci_seconds": 180,
        "pre_push_seconds": 180,
        "delivery": [],
    }
    root.mkdir(exist_ok=True)
    (root / "hard-eng.gates.json").write_text(
        json.dumps({"shipping": policy | changes})
    )


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
        {"extra": True},
        {"checks": ["build", "build"]},
        {"ci_seconds": False},
        {"pre_push_seconds": 0},
        {"pre_push_mutation_seconds": -1},
        {"pre_push_mutation_seconds": False},
        {"delivery": [{"name": "bad"}]},
    ],
)
def test_load_policy_rejects_malformed_values(
    tmp_path: Path, change: dict[str, object]
) -> None:
    _write(tmp_path / "project", **change)
    with pytest.raises(shipping.ShippingError):
        shipping.load_policy(tmp_path / "project")


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ({}, 120.0),
        ({"pre_push_mutation_seconds": 0}, 0.0),
        ({"pre_push_mutation_seconds": 30}, 30.0),
    ],
)
def test_load_policy_defaults_and_accepts_the_mutation_budget(
    tmp_path: Path, configured: dict[str, object], expected: float
) -> None:
    _write(tmp_path / "project", **configured)
    loaded = shipping.load_policy(tmp_path / "project")
    assert loaded is not None
    assert loaded["pre_push_mutation_seconds"] == expected
