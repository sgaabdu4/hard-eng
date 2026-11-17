"""Measured screen quality: the red and fixed fixtures, each limit, and the ship checks."""

import hashlib
import json
import shutil
from collections import Counter
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import cast

import look
import pytest
import shipping
import ui_proof
from conftest import ux_rules_block
from plans import usability_rules
from test_shipping import (
    _PR_URL,
    _UI_BODY,
    _UNDO,
    FakeGitHub,
    Fixture,
    _check,
    _fixture,
    _native,
    _patch_gh,
    _pull,
)
from ui_capture import WIDTHS, capture

FIXTURES = Path(__file__).parent / "fixtures/ui_quality"


def pair(first: str, second: str) -> str:
    return f"<div>{button(first)}{button(second)}</div>"


def button(fill: str) -> str:
    return (
        "<button style='min-height:44px;min-width:44px;font-size:16px;"
        f"color:#fff;background:{fill};border:0'>Go</button>"
    )


LINK = (
    "<a href='#x' style='display:inline-block;width:10px;height:10px;"
    "font-size:16px;overflow:hidden'>a</a>"
)
FAULTS = {
    "text": ("<p style='font-size:12px'>Small words</p>", "text-size", 1),
    "tap": (
        "<button style='width:30px;height:30px;font-size:16px'>Go</button>",
        "tap-size",
        1,
    ),
    "link": (f"<p style='margin:0'>{LINK}{LINK}</p>", "link-size", 2),
    "competing": (f"<div>{pair('#b00', '#00b')}</div>", "competing-buttons", 1),
    "accents": (
        f"<div><p style='color:#b00'>a</p><p style='color:#060'>b</p>{pair('#00b', '#00b')}</div>",
        "accent-colours",
        1,
    ),
}


@pytest.mark.parametrize(("body", "rule", "count"), FAULTS.values(), ids=FAULTS)
def test_each_measured_limit_finds_one_fault(
    tmp_path: Path, site: str, browser: ModuleType, body: str, rule: str, count: int
) -> None:
    (tmp_path / "pages/limit.html").write_text(
        "<!doctype html><html lang=en><title>Limit</title>"
        f"<style>body{{margin:0;font:16px sans-serif}}</style><body>{body}</body>"
    )
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width] == Counter({rule: count}), (width, found[width])


def sample_record(images: int = 2, **changes: object) -> dict[str, object]:
    record: dict[str, object] = {
        "reviewer": "codex",
        "session": "a" * 64,
        "images": [
            {
                "name": f"image-{n}.png",
                "sha256": f"{n:x}" * 64,
                "read": True,
                "read_at": "2026-11-17T10:00:01Z",
            }
            for n in range(1, images + 1)
        ],
        "rules": [
            "Mistake-proof: Pass — looked",
            "Hierarchy: Pass — one filled button",
        ],
        "outcome": "clean",
    }
    return record | changes


def test_look_block_hashes_are_checked_in_ci() -> None:
    block = look.block_text(sample_record())
    assert look.block_problem(f"Summary\n\n{block}\n", 2) is None
    assert "local path" not in str(look.block_problem(block, 2))
    assert look.block_problem("Summary only", 2) is not None
    edited = block.replace("one filled button", "all fine")
    assert "does not match" in str(look.block_problem(edited, 2))
    assert "one hash line for each After" in str(look.block_problem(block, 3))
    failed = look.block_text(
        sample_record(rules=["Hierarchy: Fail — two fills"], outcome="findings")
    )
    assert "Fail" in str(look.block_problem(failed, 2))
    leaked = look.block_text(
        sample_record(rules=[f"Hierarchy: Pass — saw /{'Users'}/someone/x.png"])
    )
    assert "local path" in str(look.block_problem(leaked, 2))


BEFORE_BYTES = b"before-image-bytes"
VISIBLE_FILE: dict[str, object] = {
    "filename": "src/App.tsx",
    "patch": "@@ -1 +1 @@\n-<p>Hi</p>\n+<p>Hello</p>",
}
REAL_UX = (
    "Result: Passed\n"
    "Evidence: Synthetic capture contract for this test, not app acceptance.\n"
    "Surface: Existing — /account, rendered by app/account/page.tsx\n"
    "Before: ![Before](https://example.test/account-before.png)\n"
    "Proposed: ![Proposed](https://example.test/account-proposed.png)\n"
    "Controls: None — the fixture changes only wording.\n"
    "Capture: Native browser test account.spec.ts passed the route and screen assertions.\n"
    "Review: Inspected both account captures at the same viewport; only the proposed label differs.\n"
    + ux_rules_block()
)
NO_UX = "N/A — fixture commands have no visual interface."


def sha_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def look_record(head: str, after: bytes, **changes: object) -> dict[str, object]:
    record: dict[str, object] = {
        "head": head,
        "reviewer": "codex",
        "fresh_same_agent": False,
        "images": [
            {
                "name": "image-1.png",
                "sha256": sha_of(after),
                "read": True,
                "read_at": "2026-11-17T10:00:01Z",
            }
        ],
        "rules": [f"{name}: Pass — checked" for name, _ in usability_rules()],
        "outcome": "clean",
        "session": sha_of(b"session"),
    }
    return record | changes


def ship_setup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    ux: str = REAL_UX,
    files: list[dict[str, object]] | None = None,
    body_extra: str = "",
    committed: dict[str, str] | None = None,
    packages: list[dict[str, object]] | None = None,
) -> tuple[Fixture, FakeGitHub]:
    """A PR with one visible change and a Before and After pair; every proof is missing until the test adds it."""
    fixture = _fixture(tmp_path, ui_paths=["src/**", "app/**", "Sources/**"])
    root = fixture.root
    for name, text in (committed or {}).items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    if packages:
        gates = json.loads((root / "hard-eng.gates.json").read_text())
        gates["packages"] = packages
        (root / "hard-eng.gates.json").write_text(json.dumps(gates))
    (root / "PLAN.md").write_text((root / "PLAN.md").read_text().replace(NO_UX, ux))
    with (root / ".git/info/exclude").open("a") as exclude:
        exclude.write(".hard-eng/\n")
    _native(root, "add", "--all")
    _native(root, "commit", "-q", "--allow-empty", "-m", "plan")
    fixture = replace(fixture, head=_native(root, "rev-parse", "HEAD"))
    _native(
        root,
        "update-ref",
        "refs/remotes/origin/main",
        _native(root, "rev-parse", "main"),
    )
    fake = FakeGitHub(
        _pull(fixture, body=f"{_UI_BODY}\n{body_extra}\n{_UNDO}"),
        [_check(fixture.head)],
        files or [VISIBLE_FILE],
    )
    _patch_gh(monkeypatch, fake)
    return fixture, fake


def serve_attachments(monkeypatch: pytest.MonkeyPatch, after: bytes) -> None:
    served = {
        "https://github.com/user-attachments/assets/old-image": BEFORE_BYTES,
        "https://github.com/user-attachments/assets/new-image": after,
    }

    def download(_root: Path, url: str) -> bytes:
        return served[url]

    monkeypatch.setattr(ui_proof, "download", download)


def measured_after(
    root: Path,
    widths: tuple[int, ...] = WIDTHS,
    findings: list[dict[str, object]] | None = None,
) -> bytes:
    """Write one measured capture named after at each width; return the 390 image bytes."""
    import ui_measure

    folder = root / ".hard-eng/browser"
    folder.mkdir(parents=True, exist_ok=True)
    for width in widths:
        image = folder / f"after-{width}.png"
        image.write_bytes(b"after-%d" % width)
        ui_measure.write_record(root, image, width, findings or [])
    return b"after-390"


def write_look(
    root: Path, head: str, after: bytes, **changes: object
) -> dict[str, object]:
    record = look_record(head, after, **changes)
    images = cast(list[dict[str, object]], record["images"])
    path = look.record_path(root, head, [str(item["sha256"]) for item in images])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record))
    return record


def ready(root: Path, fixture: Fixture) -> None:
    shipping.verify(root, fixture.plan, _PR_URL, "ready")


def full_ship(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    widths: tuple[int, ...] = WIDTHS,
    findings: list[dict[str, object]] | None = None,
) -> tuple[Fixture, FakeGitHub, bytes]:
    """A ready PR whose After image is a generated measured capture."""
    fixture, fake = ship_setup(tmp_path, monkeypatch)
    after = measured_after(fixture.root, widths, findings)
    record = write_look(fixture.root, fixture.head, after)
    fake.pulls[0]["body"] = f"{_UI_BODY}\n{look.block_text(record)}\n{_UNDO}"
    serve_attachments(monkeypatch, after)
    return fixture, fake, after


def captured_ship(
    tmp_path: Path,
    site: str,
    browser: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    page: str,
    folder: str = "ship",
) -> tuple[Fixture, dict[int, Counter[str]]]:
    """A ready PR that changes the page `page`, with the real capture of that page taken in the PR's own checkout at its head."""
    ship = tmp_path / folder
    ship.mkdir()
    text = (FIXTURES / f"{page}.html").read_text()
    change = file_change("src/shot.html", "-<p>old</p>\n+<p>new</p>")
    fixture, fake = ship_setup(
        ship, monkeypatch, files=[change], committed={"src/shot.html": text}
    )
    shutil.copy(FIXTURES / f"{page}.html", tmp_path / "pages/shot.html")
    found = capture(browser, fixture.root, site, "shot")
    after = (fixture.root / ".hard-eng/browser/shot-390.png").read_bytes()
    record = write_look(fixture.root, fixture.head, after)
    fake.pulls[0]["body"] = f"{_UI_BODY}\n{look.block_text(record)}\n{_UNDO}"
    serve_attachments(monkeypatch, after)
    return fixture, found


def test_a_measured_clean_after_image_with_a_clean_look_passes_ship(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, _, _ = full_ship(tmp_path, monkeypatch)
    ready(fixture.root, fixture)


@pytest.mark.parametrize(
    ("widths", "findings", "words"),
    [
        (WIDTHS, [{"rule": "text-size", "at": "p"}], "findings"),
        ((390, 1280), [], "768"),
        ((), [], "matches no measured capture"),
    ],
    ids=["findings", "missing-width", "no-capture"],
)
def test_ship_refuses_an_unmeasured_after_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    widths: tuple[int, ...],
    findings: list[dict[str, object]],
    words: str,
) -> None:
    fixture, _, _ = full_ship(tmp_path, monkeypatch, widths=widths, findings=findings)
    if not widths:
        serve_attachments(monkeypatch, b"after-390")
    with pytest.raises(shipping.ShippingError, match=words):
        ready(fixture.root, fixture)


def test_a_ring_drawn_after_the_capture_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, _, _ = full_ship(tmp_path, monkeypatch)
    serve_attachments(monkeypatch, b"after-390 with a ring drawn on it")
    with pytest.raises(shipping.ShippingError, match="matches no measured capture"):
        ready(fixture.root, fixture)


@pytest.mark.parametrize(
    "change",
    [
        {"outcome": "findings"},
        {"outcome": "not done: the reviewer did not open image-1.png"},
        {"rules": ["Hierarchy: Fail — two fills"], "outcome": "findings"},
        {"images": []},
        {
            "images": [
                {
                    "name": "image-1.png",
                    "sha256": "0" * 64,
                    "read": True,
                    "read_at": "t",
                }
            ]
        },
        None,
    ],
    ids=["findings", "not-done", "fail-line", "no-images", "other-hash", "no-record"],
)
def test_pr_with_pairs_needs_clean_look_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: dict[str, object] | None
) -> None:
    fixture, fake, after = full_ship(tmp_path, monkeypatch)
    for path in (fixture.root / ".git/hard-eng/look").glob("*.json"):
        path.unlink()
    if change is not None:
        write_look(fixture.root, fixture.head, after, **change)
    with pytest.raises(shipping.ShippingError, match="[Ll]ook"):
        ready(fixture.root, fixture)
    fake.pulls[0]["body"] = f"{_UI_BODY}\n{_UNDO}"
    with pytest.raises(shipping.ShippingError, match="Look review"):
        ready(fixture.root, fixture)


def test_red_fixture_fails_measurement_and_ship(
    tmp_path: Path, site: str, browser: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, found = captured_ship(tmp_path, site, browser, monkeypatch, "red")
    for width in WIDTHS:
        assert set(found[width]) >= {
            "contrast",
            "label",
            "text-size",
            "tap-size",
            "competing-buttons",
            "shared-edge",
            "accent-colours",
        }, (width, found[width])
    with pytest.raises(shipping.ShippingError, match="has findings"):
        ready(fixture.root, fixture)


def test_fixed_fixture_passes_measurement_and_ship(
    tmp_path: Path, site: str, browser: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, found = captured_ship(tmp_path, site, browser, monkeypatch, "fixed")
    assert found == {width: Counter() for width in WIDTHS}
    ready(fixture.root, fixture)


@pytest.mark.parametrize(
    "changes",
    [{"commit": "0" * 40}, {"dirty": True}],
    ids=["another-commit", "dirty-tree"],
)
def test_an_after_capture_must_come_from_the_head_of_a_clean_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changes: dict[str, object]
) -> None:
    fixture, _, _ = full_ship(tmp_path, monkeypatch)
    for path in (fixture.root / ".hard-eng/browser").glob("*.json"):
        path.write_text(json.dumps(json.loads(path.read_text()) | changes))
    with pytest.raises(shipping.ShippingError, match="head"):
        ready(fixture.root, fixture)


def no_problem(*_arguments: object) -> None:
    return None


NO_FILES: dict[str, str] = {}


def file_change(name: str, patch: str) -> dict[str, object]:
    return {"filename": name, "patch": f"@@ -1 +1 @@\n{patch}"}


DART_HELPER = "Widget helper(Widget child) {\n  return child;\n}\n"
SWIFT_VIEW = "struct Card: View {\n  var body: some View { Text(title) }\n}\n"
VISIBLE_CHANGES = {
    "markup": (file_change("src/App.tsx", "-<p>Hi</p>\n+<p>Hello</p>"), NO_FILES),
    "removal-only": (file_change("src/App.tsx", "-<button>Decline</button>"), NO_FILES),
    "style": (file_change("src/app.css", "-a{color:red}\n+a{color:blue}"), NO_FILES),
    "image": ({"filename": "src/logo.svg"}, NO_FILES),
    "theme": (
        file_change("src/theme/colors.ts", "-const a = 1\n+const a = 2"),
        NO_FILES,
    ),
    "catalog": (file_change("src/l10n/app_en.arb", '-"a": "x"\n+"a": "y"'), NO_FILES),
    "dart-helper-removal": (
        file_change("app/lib/helpers.dart", "-  return Padding(child: child);"),
        {"app/lib/helpers.dart": DART_HELPER},
    ),
    "dart-button-removal": (
        file_change("app/lib/ui/card.dart", "-  IconButton(onPressed: onDelete),"),
        {"app/lib/ui/card.dart": "final a = 1;\n"},
    ),
    "lit-template-removal": (
        file_change("src/card.ts", "-<button @click=${this.no}>Decline</button>"),
        NO_FILES,
    ),
    "dart-string": (
        file_change("app/lib/label.dart", "-  const a = 1;\n+  final a = 'Save';"),
        {"app/lib/label.dart": "final a = 'Save';\n"},
    ),
    "swift-view": (
        file_change("Sources/Card.swift", "-  Text(title)\n+  Text(name)"),
        {"Sources/Card.swift": SWIFT_VIEW},
    ),
    "js-page-write": (
        file_change("src/page.js", "-el.id = 1\n+el.textContent = x"),
        NO_FILES,
    ),
}
NONVISUAL_CHANGES = {
    "test-file": (file_change("src/App.test.tsx", "-a\n+b"), NO_FILES),
    "typescript-logic": (
        file_change("src/api.ts", "-const a = 1\n+const a = 2"),
        NO_FILES,
    ),
    "dart-logic": (
        file_change("app/lib/logic.dart", "+int g(int a) => a + 1;"),
        {"app/lib/logic.dart": "int g(int a) => a + 1;\n"},
    ),
    "typescript-generic": (
        file_change(
            "src/api.ts", "-const a: Array<string> = []\n+const a: Map<string, number>"
        ),
        NO_FILES,
    ),
    "comment-only": (
        file_change("src/App.tsx", "-// old note\n+// new note"),
        NO_FILES,
    ),
    "blank-line": (file_change("src/App.tsx", "-\n+"), NO_FILES),
}


def no_ux_setup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: dict[str, object],
    committed: dict[str, str],
) -> Fixture:
    fixture, _ = ship_setup(
        tmp_path, monkeypatch, ux=NO_UX, files=[change], committed=committed
    )
    serve_attachments(monkeypatch, b"after-390")
    return fixture


@pytest.mark.parametrize(
    ("change", "committed"), VISIBLE_CHANGES.values(), ids=VISIBLE_CHANGES
)
def test_visible_change_refuses_ux_reference_na(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: dict[str, object],
    committed: dict[str, str],
) -> None:
    fixture = no_ux_setup(tmp_path, monkeypatch, change, committed)
    with pytest.raises(shipping.ShippingError, match="ux_reference says N/A"):
        ready(fixture.root, fixture)


@pytest.mark.parametrize(
    ("change", "committed"), NONVISUAL_CHANGES.values(), ids=NONVISUAL_CHANGES
)
def test_nonvisual_ui_paths_change_keeps_ux_reference_na(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: dict[str, object],
    committed: dict[str, str],
) -> None:
    fixture = no_ux_setup(tmp_path, monkeypatch, change, committed)
    monkeypatch.setattr(ui_proof, "evidence_problem", no_problem)
    ready(fixture.root, fixture)


UNCHANGED_UX = (
    "N/A — unchanged: ![Before](.hard-eng/browser/before-390.png) "
    "![After](.hard-eng/browser/after-390.png) — the card at rest"
)
UNCHANGED_NOTE = "UI appearance: unchanged — the card at rest looks the same"


def write_pair(
    root: Path,
    base: str,
    head: str,
    *,
    after_bytes: bytes = b"same-screen",
    after_commit: str | None = None,
    after_dirty: bool = False,
    widths: tuple[int, ...] = WIDTHS,
) -> None:
    folder = root / ".hard-eng/browser"
    folder.mkdir(parents=True, exist_ok=True)
    for name, data, commit_sha, dirty in (
        ("before", b"same-screen", base, False),
        ("after", after_bytes, after_commit or head, after_dirty),
    ):
        for width in widths:
            image = folder / f"{name}-{width}.png"
            image.write_bytes(data)
            image.with_suffix(".json").write_text(
                json.dumps(
                    {
                        "image": image.name,
                        "sha256": sha_of(data),
                        "width": width,
                        "findings": [],
                        "commit": commit_sha,
                        "dirty": dirty,
                    }
                )
            )


def unchanged_ship(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, note: bool = True
) -> tuple[Fixture, str]:
    fixture, fake = ship_setup(tmp_path, monkeypatch, ux=UNCHANGED_UX)
    base = _native(fixture.root, "rev-parse", "origin/main")
    if note:
        fake.pulls[0]["body"] = f"{UNCHANGED_NOTE}\n{_UNDO}"
    return fixture, base


@pytest.mark.parametrize(
    ("after_bytes", "at_base", "dirty", "widths", "words"),
    [
        (b"same-screen", False, False, WIDTHS, None),
        (b"a different screen", False, False, WIDTHS, "differ"),
        (b"same-screen", True, False, WIDTHS, "head"),
        (b"same-screen", False, True, WIDTHS, "uncommitted"),
        (b"same-screen", False, False, (390, 1280), "768"),
    ],
    ids=["equal", "bytes-differ", "both-at-base", "dirty-checkout", "missing-width"],
)
def test_unchanged_pair_needs_equal_captures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    after_bytes: bytes,
    at_base: bool,
    dirty: bool,
    widths: tuple[int, ...],
    words: str | None,
) -> None:
    fixture, base = unchanged_ship(tmp_path, monkeypatch)
    write_pair(
        fixture.root,
        base,
        fixture.head,
        after_bytes=after_bytes,
        after_commit=base if at_base else None,
        after_dirty=dirty,
        widths=widths,
    )
    if words is None:
        ready(fixture.root, fixture)
        return
    with pytest.raises(shipping.ShippingError, match=words):
        ready(fixture.root, fixture)


def test_the_unchanged_note_on_a_visible_change_needs_the_plan_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, fake = ship_setup(tmp_path, monkeypatch)
    fake.pulls[0]["body"] = f"{UNCHANGED_NOTE}\n{_UNDO}"
    with pytest.raises(shipping.ShippingError, match="stands only beside"):
        ready(fixture.root, fixture)


GUIDELINE_TEST = (
    "import 'package:shop/ui/card.dart';\n"
    "void main() { testWidgets('a', (t) async {\n"
    "  await expectLater(t, meetsGuideline(textContrastGuideline));\n"
    "  await expectLater(t, meetsGuideline(labeledTapTargetGuideline));\n"
    "  await expectLater(t, meetsGuideline(iOSTapTargetGuideline));\n"
    "  await expectLater(t, meetsGuideline(androidTapTargetGuideline));\n"
    "}); }\n"
)
FLUTTER_PACKAGE: list[dict[str, object]] = [
    {"name": "shop", "path": "app", "language": "dart", "checks": []}
]
CARD_CHANGE = file_change("app/lib/ui/card.dart", "-  Text('Old')\n+  Text('New')")


def flutter_ship(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tests: dict[str, str]
) -> tuple[Fixture, FakeGitHub]:
    tmp_path.mkdir()
    committed = {
        "app/pubspec.yaml": "name: shop\ndependencies:\n  flutter:\n    sdk: flutter\n",
        "app/lib/ui/card.dart": "Widget card() => Text('New');\n",
        **{f"app/test/{name}": text for name, text in tests.items()},
    }
    return ship_setup(
        tmp_path,
        monkeypatch,
        files=[CARD_CHANGE],
        committed=committed,
        packages=FLUTTER_PACKAGE,
    )


def native_ready(
    fixture: Fixture, fake: FakeGitHub, monkeypatch: pytest.MonkeyPatch
) -> None:
    after = b"native-after-image"
    record = write_look(fixture.root, fixture.head, after)
    fake.pulls[0]["body"] = f"{_UI_BODY}\n{look.block_text(record)}\n{_UNDO}"
    serve_attachments(monkeypatch, after)


def test_flutter_screen_needs_guideline_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, fake = flutter_ship(tmp_path / "a", monkeypatch, {})
    native_ready(fixture, fake, monkeypatch)
    with pytest.raises(shipping.ShippingError, match="meetsGuideline"):
        ready(fixture.root, fixture)
    partial = GUIDELINE_TEST.replace("androidTapTargetGuideline", "other")
    fixture, fake = flutter_ship(
        tmp_path / "b", monkeypatch, {"card_test.dart": partial}
    )
    native_ready(fixture, fake, monkeypatch)
    with pytest.raises(shipping.ShippingError, match="androidTapTargetGuideline"):
        ready(fixture.root, fixture)
    elsewhere = GUIDELINE_TEST.replace("ui/card.dart", "ui/other.dart")
    fixture, fake = flutter_ship(
        tmp_path / "c", monkeypatch, {"o_test.dart": elsewhere}
    )
    native_ready(fixture, fake, monkeypatch)
    with pytest.raises(shipping.ShippingError, match="meetsGuideline"):
        ready(fixture.root, fixture)
    fixture, fake = flutter_ship(
        tmp_path / "d", monkeypatch, {"card_test.dart": GUIDELINE_TEST}
    )
    native_ready(fixture, fake, monkeypatch)
    ready(fixture.root, fixture)


def test_swift_after_image_needs_look_but_no_measurement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, fake = ship_setup(
        tmp_path,
        monkeypatch,
        files=[file_change("Sources/Card.swift", "-  Text(title)\n+  Text(name)")],
        committed={"Sources/Card.swift": SWIFT_VIEW},
    )
    serve_attachments(monkeypatch, b"native-after-image")
    with pytest.raises(shipping.ShippingError, match="Look review"):
        ready(fixture.root, fixture)
    native_ready(fixture, fake, monkeypatch)
    ready(fixture.root, fixture)


def ci_problem(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    body: str,
    files: list[dict[str, object]],
    plans: dict[str, str] | None = None,
) -> str | None:
    """What the CI pr text job says about a PR; it holds only the hooks, so it reads the plan from the API."""
    from pr_text import event_problem
    from test_pr_text import _event, _project

    tmp_path.mkdir()
    root = _project(tmp_path, ui_paths=["src/**"])
    (tmp_path / "pull").mkdir()
    fake = FakeGitHub(_pull(_fixture(tmp_path / "pull")), [], files)
    fake.codeowners.update(plans or {})
    _patch_gh(monkeypatch, fake)
    return event_problem(_event(tmp_path, body), root)


def test_ci_refuses_pairs_without_a_look_block_and_a_visible_na_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_pr_text import _VALID

    pairs = f"{_UI_BODY}\n{_VALID}"
    visible: list[dict[str, object]] = [VISIBLE_FILE]
    assert "Look review" in str(ci_problem(tmp_path / "a", monkeypatch, pairs, visible))
    block = look.block_text(sample_record(1))
    assert (
        ci_problem(
            tmp_path / "b", monkeypatch, f"{_UI_BODY}\n{block}\n{_VALID}", visible
        )
        is None
    )
    plan = f"## ux_reference\n{NO_UX}\n\n## Verification\n"
    with_plan: list[dict[str, object]] = [
        VISIBLE_FILE,
        {"filename": "features/x/PLAN.md", "status": "modified"},
    ]
    problem = ci_problem(
        tmp_path / "c",
        monkeypatch,
        f"{_UI_BODY}\n{block}\n{_VALID}",
        with_plan,
        {"features/x/PLAN.md": plan},
    )
    assert "ux_reference says N/A" in str(problem)
    nonvisual: list[dict[str, object]] = [
        file_change("src/api.ts", "-a\n+b"),
        with_plan[1],
    ]
    assert (
        ci_problem(
            tmp_path / "d",
            monkeypatch,
            f"{_UI_BODY}\n{block}\n{_VALID}",
            nonvisual,
            {"features/x/PLAN.md": plan},
        )
        is None
    )


UI_MODULES = (
    "ui_measure",
    "ui_proof",
    "look",
    "merge_guard",
    "ship_record",
    "plan_controls",
)


@pytest.mark.parametrize(
    "argv", [["stop", "claude"], ["session", "claude"], ["check", "--quick"]]
)
def test_quick_check_runs_no_ui_proof(
    tmp_path: Path, argv: list[str], completed_plan: str
) -> None:
    import subprocess
    import sys

    from conftest import SOURCE, commit, init

    project = tmp_path / "project"
    init(project)
    (project / "a.txt").write_text("a\n")
    (project / "features/x").mkdir(parents=True)
    (project / "features/x/PLAN.md").write_text(completed_plan)
    commit(project, "first")
    shutil.copytree(
        SOURCE / ".hooks",
        project / ".hooks",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    done = subprocess.run(
        [sys.executable, "-X", "importtime", ".hooks/hard-eng.py", *argv],
        cwd=project,
        input="{}",
        capture_output=True,
        text=True,
        check=False,
    )
    loaded = {line.rsplit("|", 1)[-1].strip() for line in done.stderr.splitlines()}
    assert len(loaded) > 20
    assert not loaded.intersection(UI_MODULES), done.stderr


def plan_proof_kinds() -> dict[str, set[str]]:
    """The kinds that the plan's gate table gives each Usability rule, read from its rows."""
    plan = (FIXTURES.parents[2] / "features/ui-quality-enforcement/PLAN.md").read_text()
    table = plan.split("### What the gate enforces")[1].split("### Coverage")[0]
    kinds: dict[str, set[str]] = {name: set() for name, _ in usability_rules()}
    for line in table.splitlines():
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not line.startswith("|") or len(cells) < 2:
            continue
        found = {
            word
            for word, label in (
                ("measured", "measured"),
                ("judgement", "judgement"),
                ("test", "tests"),
            )
            if label in cells[1].lower()
        }
        for name in kinds:
            if name in cells[0]:
                kinds[name] |= found
    return kinds


def test_every_usability_rule_has_a_proof_kind_that_matches_the_plan_table() -> None:
    from ui_measure import PROOF_KINDS

    assert {name: set(kinds) for name, kinds in PROOF_KINDS.items()} == (
        plan_proof_kinds()
    )


def test_ux_text_names_the_gap_items() -> None:
    reference = (
        FIXTURES.parents[2] / ".agents/skills/he-plan/references/ux.md"
    ).read_text()
    for words in (
        "think and remember as little as possible",
        "Alignment:",
        "Spacing:",
        "Design system:",
        "plain, calm and positive",
        "phone 390, tablet 768 and desktop 1280 px",
        "A Pass you type is a record, not proof",
    ):
        assert words in reference, words


def test_ux_text_states_the_measured_limits() -> None:
    from ui_measure import LIMITS

    reference = (
        FIXTURES.parents[2] / ".agents/skills/he-plan/references/ux.md"
    ).read_text()
    assert f"text at least {LIMITS['text_px']} px" in reference
    assert f"at most {LIMITS['accent_colours']} accent colours" in reference
    assert f"{LIMITS['control_px']} × {LIMITS['control_px']} px on the web" in reference
    assert f"{LIMITS['link_px']} × {LIMITS['link_px']} px (WCAG" in reference
    assert f"over {LIMITS['secondary_words']} words" in reference


def test_red_to_fixed_journey_end_to_end(
    tmp_path: Path, site: str, browser: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, ships in (("red", False), ("fixed", True)):
        fixture, _ = captured_ship(
            tmp_path, site, browser, monkeypatch, name, folder=f"ship-{name}"
        )
        if ships:
            ready(fixture.root, fixture)
        else:
            with pytest.raises(shipping.ShippingError, match="has findings"):
                ready(fixture.root, fixture)


def test_a_video_after_alone_is_refused_on_a_visible_web_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, fake = ship_setup(tmp_path, monkeypatch)
    fake.attachment_response = (
        "HTTP/2 206 Partial Content\ncontent-type: video/mp4\ncontent-length: 1\n"
        "content-range: bytes 0-0/85098\n"
    )
    with pytest.raises(shipping.ShippingError, match="video"):
        ready(fixture.root, fixture)


@pytest.mark.parametrize(
    "name", ["dart-button-removal", "lit-template-removal", "markup"]
)
def test_ci_refuses_na_for_the_visible_changes_that_ship_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    from test_pr_text import _VALID

    block = look.block_text(sample_record(1))
    plan = f"## ux_reference\n{NO_UX}\n\n## Verification\n"
    change = VISIBLE_CHANGES[name][0]
    moved: dict[str, object] = dict(change)
    moved["filename"] = str(change["filename"]).replace("app/", "src/")
    plan_file: dict[str, object] = {
        "filename": "features/x/PLAN.md",
        "status": "modified",
    }
    files = [moved, plan_file]
    problem = ci_problem(
        tmp_path / "ci",
        monkeypatch,
        f"{_UI_BODY}\n{block}\n{_VALID}",
        files,
        {"features/x/PLAN.md": plan},
    )
    assert "ux_reference says N/A" in str(problem)


def test_ci_refuses_the_unchanged_note_on_a_visible_change_with_no_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_pr_text import _VALID

    problem = ci_problem(
        tmp_path / "ci",
        monkeypatch,
        f"{_VALID}\n{UNCHANGED_NOTE}",
        [VISIBLE_FILE],
    )
    assert "UI appearance: unchanged" in str(problem)
