"""Ship refuses UI changes without real Before and After attachments."""

from __future__ import annotations

from pathlib import Path

import pytest
import shipping
from test_shipping import (
    _DIAGRAM,
    _MIXED_UI_BODY,
    _NATIVE_VIDEO_BODY,
    _NATIVE_VIDEO_BODY_CRLF,
    _PR_URL,
    _UI_BODY,
    _UNDO,
    FakeGitHub,
    _check,
    _fixture,
    _patch_gh,
    _pull,
    _ready_outcome,
    _ui_fake,
)


def test_unchanged_ui_needs_comparison_note_without_uploads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path, ui_paths=["src/**"])
    fake = _ui_fake(
        fixture,
        body=f"UI appearance: unchanged — inspected the same dashboard, state and viewport before/after; no visible difference.\n{_UNDO}",
    )
    _patch_gh(monkeypatch, fake)
    shipment = shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    assert shipment.delivery_target == "PR"
    assert not any("--method" in call for call in fake.calls)


def test_a_pr_that_changes_no_ui_file_needs_no_ui_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path, ui_paths=["src/**"])
    fake = FakeGitHub(
        _pull(fixture), [_check(fixture.head)], [{"filename": "README.md"}]
    )
    _patch_gh(monkeypatch, fake)
    shipment = shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    assert shipment.delivery_target == "PR"
    assert not any("--method" in call for call in fake.calls)


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        (_UI_BODY, "image/png"),
        (_NATIVE_VIDEO_BODY, "video/mp4"),
        (_NATIVE_VIDEO_BODY_CRLF, "video/mp4"),
        (_MIXED_UI_BODY, "image/png"),
        (_UI_BODY + "\n\n" + _NATIVE_VIDEO_BODY, "image/png"),
    ],
    ids=["images", "native-video", "native-video-crlf", "mixed", "two-pairs"],
)
def test_ui_changes_accept_image_video_and_mixed_attachments_that_reject_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str, content_type: str
) -> None:
    fixture = _fixture(tmp_path, ui_paths=["src/**"])
    fake = _ui_fake(fixture, body=body)
    fake.attachment_response = f"HTTP/2 206 Partial Content\ncontent-type: {content_type}\ncontent-length: 1\ncontent-range: bytes 0-0/85098\n"
    _patch_gh(monkeypatch, fake)
    shipment = shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    assert shipment.delivery_target == "PR"
    requests = [call for call in fake.calls if "--method" in call]
    assert len(requests) == body.count("user-attachments")
    assert all(
        call[:-1]
        == ("api", "--method", "GET", "--include", "--silent", "-H", "Range: bytes=0-0")
        for call in requests
    )


@pytest.mark.parametrize(
    "body",
    [
        _UI_BODY
        + "\nBefore: ![old](https://github.com/user-attachments/assets/other-old)",
        "UI appearance: unchanged — ",
        "UI appearance: unchanged — compared dashboard\nUI appearance: unchanged — compared dashboard",
        "UI appearance: unchanged — compared dashboard\n" + _UI_BODY,
        "UI appearance: unchanged — compared dashboard\n" + _NATIVE_VIDEO_BODY,
        "After: ![new](https://github.com/user-attachments/assets/new-image)",
        "Before: ![old](https://example.invalid/old)\nAfter: ![new](https://github.com/user-attachments/assets/new-image)",
        "Before: ![old](https://github.com/user-attachments/assets/same)\nAfter: ![new](https://github.com/user-attachments/assets/same)",
        "Before:\n\nhttps://github.com/user-attachments/assets/old-video",
        "Before:\n\nhttps://example.invalid/old-video\n\nAfter:\n\nhttps://github.com/user-attachments/assets/new-video",
        "Before:\n\nhttps://github.com/user-attachments/assets/old-video\n\nBefore:\n\nhttps://github.com/user-attachments/assets/extra-video\n\nAfter:\n\nhttps://github.com/user-attachments/assets/new-video",
        "Before:\n\nhttps://github.com/user-attachments/assets/old-video?query\n\nAfter:\n\nhttps://github.com/user-attachments/assets/new-video",
        "https://github.com/user-attachments/assets/old-video\n\nhttps://github.com/user-attachments/assets/new-video",
    ],
)
def test_ui_changes_reject_missing_foreign_or_duplicate_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    fixture = _fixture(tmp_path, ui_paths=["src/**"])
    fake = _ui_fake(fixture, body=body)
    _patch_gh(monkeypatch, fake)
    with pytest.raises(shipping.ShippingError):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")


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
    fake.attachment_response = response
    _patch_gh(monkeypatch, fake)
    with pytest.raises(shipping.ShippingError):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")


def test_ui_evidence_falls_back_to_a_plain_get_when_the_ranged_request_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path, ui_paths=["src/**"])
    fake = _ui_fake(fixture)
    plain = "HTTP/1.1 200 OK\ncontent-type: image/png\ncontent-length: 85098\n"

    def answer(root: Path, *args: str) -> str:
        if "Range: bytes=0-0" in args:
            fake.calls.append(args)
            raise shipping.ShippingError("gh query failed: gh: HTTP 504")
        if "--method" in args:
            fake.calls.append(args)
            return plain
        return fake(root, *args)

    monkeypatch.setattr(shipping, "gh", answer)
    assert shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    requests = [call for call in fake.calls if "--method" in call]
    assert [("-H" in call) for call in requests] == [True, False, True, False]

    plain = "HTTP/1.1 504 Gateway Timeout\n"
    with pytest.raises(shipping.ShippingError, match="assets/old-image"):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")


def test_missing_ui_evidence_names_the_upload_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path, ui_paths=["src/**"])
    _patch_gh(monkeypatch, _ui_fake(fixture, body="Pictures to follow."))
    with pytest.raises(shipping.ShippingError, match="gh pr edit .*--attach"):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")


@pytest.mark.parametrize(("labels", "passes"), [("**{}**", True), ("{}:", False)])
def test_bold_diagram_labels_are_no_ui_evidence_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, labels: str, passes: bool
) -> None:
    fixture = _fixture(tmp_path, ui_paths=["src/**"])
    note = "UI appearance: unchanged — inspected the same dashboard, state and viewport before/after; no visible difference."
    before, after = labels.format("Before"), labels.format("After")
    body = f"{note}\n{before}\n\n{_DIAGRAM}\n{after}\n\n{_DIAGRAM}"
    message = None if passes else "no Before/After attachments"
    _ready_outcome(fixture, _ui_fake(fixture, body=body), monkeypatch, message)
