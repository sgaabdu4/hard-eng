"""An After image that several capture sets share is judged by the sets taken at the head, not by the first record that has its hash."""

import json
from pathlib import Path

import pytest
import ui_proof
from test_ui_quality import full_ship, ready
from ui_proof import sha256

HEAD = "h" * 40
OLD = "o" * 40
IMAGE = b"same-screen-bytes"
WIDTHS = (390, 768, 1280)


def write_set(
    root: Path,
    stem: str,
    commit: str,
    findings: list[dict[str, object]] | None = None,
) -> None:
    folder = root / ".hard-eng/browser"
    folder.mkdir(parents=True, exist_ok=True)
    for width in WIDTHS:
        name = f"{stem}-{width}.png"
        data = IMAGE if width == WIDTHS[-1] else IMAGE + str(width).encode()
        (folder / name).write_bytes(data)
        (folder / f"{stem}-{width}.json").write_text(
            json.dumps(
                {
                    "image": name,
                    "sha256": sha256(data),
                    "width": width,
                    "findings": findings or [],
                    "commit": commit,
                    "dirty": False,
                }
            )
        )


def test_an_earlier_clean_capture_with_the_same_image_does_not_hide_findings(
    tmp_path: Path,
) -> None:
    write_set(tmp_path, "a-first", HEAD)
    write_set(tmp_path, "b-later", HEAD, [{"rule": "tap-size"}])
    problem = ui_proof.measured_problem(tmp_path, HEAD, [IMAGE])
    assert problem is not None and "tap-size" in problem


def test_a_capture_of_an_older_commit_with_the_same_image_does_not_refuse_the_current_one(
    tmp_path: Path,
) -> None:
    write_set(tmp_path, "a-old", OLD)
    write_set(tmp_path, "b-current", HEAD)
    assert ui_proof.measured_problem(tmp_path, HEAD, [IMAGE]) is None


def test_a_capture_of_an_older_commit_alone_is_still_refused(tmp_path: Path) -> None:
    write_set(tmp_path, "a-old", OLD)
    problem = ui_proof.measured_problem(tmp_path, HEAD, [IMAGE])
    assert problem is not None and "not taken at the head" in problem


def test_a_set_refreshed_at_one_width_with_a_finding_is_not_hidden_by_a_clean_set(
    tmp_path: Path,
) -> None:
    write_set(tmp_path, "a-part", OLD)
    refreshed = tmp_path / ".hard-eng/browser/a-part-390.json"
    record = json.loads(refreshed.read_text())
    refreshed.write_text(
        json.dumps({**record, "commit": HEAD, "findings": [{"rule": "tap-size"}]})
    )
    write_set(tmp_path, "b-current", HEAD)
    problem = ui_proof.measured_problem(tmp_path, HEAD, [IMAGE])
    assert problem is not None and "tap-size" in problem


def test_an_older_capture_with_the_same_bytes_does_not_hide_the_fresh_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, _, _ = full_ship(tmp_path, monkeypatch)
    folder = fixture.root / ".hard-eng/browser"
    (folder / "aaa-390.png").write_bytes((folder / "after-390.png").read_bytes())
    stale = json.loads((folder / "after-390.json").read_text())
    (folder / "aaa-390.json").write_text(
        json.dumps({**stale, "image": "aaa-390.png", "commit": "0" * 40})
    )
    ready(fixture.root, fixture)


def test_unchanged_pair_uses_pr_base_sha_after_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    import shipping
    from test_shipping import _PR_URL, _UNDO, _check, _native, _patch_gh, _pull
    from test_ui_quality import UNCHANGED_NOTE, UNCHANGED_UX, ship_setup, write_pair

    fixture, fake = ship_setup(tmp_path, monkeypatch, ux=UNCHANGED_UX)
    base = _native(fixture.root, "rev-parse", "origin/main")
    (fixture.root / "PLAN.md").write_text(
        (fixture.root / "PLAN.md")
        .read_text()
        .replace("Delivery target: PR", "Delivery target: Merge")
    )
    _native(fixture.root, "add", "PLAN.md")
    _native(fixture.root, "commit", "-q", "-m", "merge target")
    head = _native(fixture.root, "rev-parse", "HEAD")
    fixture = replace(fixture, head=head)
    write_pair(fixture.root, base, head)
    _native(fixture.root, "checkout", "-q", "main")
    (fixture.root / "BASE_MOVE.txt").write_text("base moved before merge\n")
    _native(fixture.root, "add", "BASE_MOVE.txt")
    _native(fixture.root, "commit", "-q", "-m", "advance main before merge")
    newer_base = _native(fixture.root, "rev-parse", "HEAD")
    assert newer_base != base
    _native(fixture.root, "merge", "-q", "--no-ff", head, "-m", "merge pr")
    merged_main = _native(fixture.root, "rev-parse", "HEAD")
    _native(fixture.root, "update-ref", "refs/remotes/origin/main", merged_main)
    _native(fixture.root, "checkout", "-q", "feature/shipping")
    pull = _pull(
        fixture,
        body=f"{UNCHANGED_NOTE}\n{_UNDO}",
        state="closed",
        merged=True,
        merged_at="2026-11-22T12:00:00Z",
        merge_commit_sha=merged_main,
    )
    base_obj = pull["base"]
    assert isinstance(base_obj, dict)
    pull["base"] = {**base_obj, "sha": newer_base}
    fake.pulls = [pull]
    fake.check_payload = [{"total_count": 1, "check_runs": [_check(merged_main)]}]
    _patch_gh(monkeypatch, fake)
    real_git = shipping.git

    def controlled_git(root: Path, *args: str) -> str:
        if args[:2] == ("ls-remote", "--heads"):
            return f"{merged_main}\trefs/heads/main\n"
        if args[:2] == ("fetch", "--no-tags"):
            return ""
        return real_git(root, *args)

    monkeypatch.setattr(shipping, "git", controlled_git)
    shipment = shipping.verify(fixture.root, fixture.plan, _PR_URL, "delivered")
    assert shipment.merged_sha == merged_main

    pull_without_base_sha = dict(pull)
    pull_without_base_sha["base"] = {k: v for k, v in base_obj.items() if k != "sha"}
    fake.pulls = [pull_without_base_sha]
    with pytest.raises(shipping.ShippingError, match="Before taken at the base"):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "delivered")
