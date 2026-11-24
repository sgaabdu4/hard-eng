"""A Flutter localization file is a native change: it needs a native pair, never a browser capture."""

from pathlib import Path

import local_ui_proof
import pytest
import shipping
import ui_proof
from conftest import commit, git
from test_local_ui_proof import clear_ci, flutter_app_root
from test_ui_quality import (
    GUIDELINE_TEST,
    NO_UX,
    REAL_UX,
    VISIBLE_FILE,
    file_change,
    flutter_ship,
    native_ready,
    ready,
    ship_setup,
    write_look,
)

ARB_CHANGE = file_change("app/lib/l10n/app_en.arb", '-"title": "Old"\n+"title": "New"')


def test_a_flutter_change_with_a_localization_file_needs_only_the_native_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, fake = flutter_ship(
        tmp_path / "a", monkeypatch, {"card_test.dart": GUIDELINE_TEST}, [ARB_CHANGE]
    )
    native_ready(fixture, fake, monkeypatch)
    ready(fixture.root, fixture)


def test_a_web_change_with_a_localization_file_still_needs_a_browser_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, fake = ship_setup(tmp_path, monkeypatch, files=[VISIBLE_FILE, ARB_CHANGE])
    native_ready(fixture, fake, monkeypatch)
    with pytest.raises(shipping.ShippingError, match="matches no measured capture"):
        ready(fixture.root, fixture)


def test_a_localization_file_alone_is_a_native_change() -> None:
    assert ui_proof.is_native(["app/lib/l10n/app_en.arb"])
    assert ui_proof.is_native(["app/lib/ui/card.dart", "app/lib/l10n/app_en.arb"])
    assert not ui_proof.is_native(["src/App.tsx", "app/lib/l10n/app_en.arb"])


def test_the_local_complete_check_takes_a_localization_file_as_native(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_ci(monkeypatch)
    root = flutter_app_root(tmp_path)
    (root / "app/lib/l10n").mkdir(parents=True)
    (root / "app/test/card_test.dart").write_text(GUIDELINE_TEST)
    (root / "app/lib/l10n/app_en.arb").write_text('{\n  "title": "Old"\n}\n')
    commit(root, "base")
    git(root, "branch", "-f", "main", "HEAD")
    git(root, "update-ref", "refs/remotes/origin/main", git(root, "rev-parse", "main"))
    (root / "app/lib/ui/card.dart").write_text("Widget card() => Text('New');\n")
    (root / "app/lib/l10n/app_en.arb").write_text('{\n  "title": "New"\n}\n')
    (root / "PLAN.md").write_text(
        (root / "PLAN.md").read_text().replace(NO_UX, REAL_UX)
    )
    commit(root, "native change with a localization file")
    head = git(root, "rev-parse", "HEAD").strip()
    write_look(root, head, b"native-shot")
    assert local_ui_proof.local_ui_proof_problem(root, "origin/main") is None
