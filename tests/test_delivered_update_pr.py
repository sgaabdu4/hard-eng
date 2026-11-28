"""A merged Hard Eng update PR needs no screen evidence for the files that the update installs; a PR that also changes a project screen file still does."""

from pathlib import Path

import pytest
import shipping
from test_shipping_delivered import _PUSH_SUITE, _delivered_fake, _run_of, _verify

INSTALLED_PAGE: dict[str, object] = {
    "filename": ".agents/skills/client-report/assets/starter.html",
    "patch": "@@ -1 +1 @@\n-<p>a</p>\n+<p>b</p>",
}
PROJECT_PAGE: dict[str, object] = {
    "filename": "site/index.html",
    "patch": "@@ -1 +1 @@\n-<p>a</p>\n+<p>b</p>",
}


def delivered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: list[dict[str, object]]
) -> shipping.Shipment:
    fixture = _delivered_fake(
        tmp_path,
        monkeypatch,
        [_run_of(_PUSH_SUITE, 1, "success")],
        ui_paths=["**/*.html"],
        files=files,
    )
    return _verify(fixture)


def test_delivered_asks_no_screen_evidence_for_installed_files_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert delivered(tmp_path, monkeypatch, [INSTALLED_PAGE]).merged_sha


def test_delivered_still_asks_screen_evidence_for_an_installed_and_a_project_screen_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(shipping.ShippingError, match="UI evidence"):
        delivered(tmp_path, monkeypatch, [INSTALLED_PAGE, PROJECT_PAGE])
