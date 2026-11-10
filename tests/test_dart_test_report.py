"""A failing Flutter widget test gives its reason and its file."""

import json
from pathlib import Path

import dart_test_report

FLUTTER_LINE = (
    "Test failed. See exception logs above.\nThe test description was: shows hello"
)


def write(path: Path, events: list[dict[str, object]]) -> Path:
    path.write_text("\n".join(json.dumps(event) for event in events))
    return path


def widget_events(*, root: bool = True) -> list[dict[str, object]]:
    test: dict[str, object] = {"id": 7, "name": "shows hello", "line": 40, "url": "x"}
    if root:
        test |= {"root_line": 5, "root_url": "file:///app/test/fail_test.dart"}
    return [
        {"type": "testStart", "test": test},
        {
            "type": "print",
            "testID": 7,
            "messageType": "print",
            "message": "Expected: exactly one matching candidate",
        },
        {"type": "print", "testID": 8, "message": "from another test"},
        {"type": "error", "testID": 7, "error": FLUTTER_LINE, "isFailure": True},
        {"type": "testDone", "testID": 7, "result": "failure"},
    ]


def test_a_failing_widget_test_gives_its_reason_and_file(tmp_path: Path) -> None:
    summary = dart_test_report.failure_summary(
        write(tmp_path / "tests.jsonl", widget_events())
    )
    assert summary is not None
    assert "Expected: exactly one matching candidate" in summary
    assert "fail_test.dart:5" in summary
    assert "from another test" not in summary


def test_a_widget_test_without_a_root_location_uses_its_own(tmp_path: Path) -> None:
    summary = dart_test_report.failure_summary(
        write(tmp_path / "tests.jsonl", widget_events(root=False))
    )
    assert summary is not None
    assert "x:40" in summary


def test_the_print_messages_are_bounded(tmp_path: Path) -> None:
    events = widget_events()
    noise: list[dict[str, object]] = [
        {"type": "print", "testID": 7, "message": f"line {n} " + "x" * 400}
        for n in range(50)
    ]
    events[1:1] = noise
    summary = dart_test_report.failure_summary(write(tmp_path / "tests.jsonl", events))
    assert summary is not None
    assert len(summary) < 1500


def test_a_plain_test_failure_keeps_its_own_text(tmp_path: Path) -> None:
    events = widget_events()
    events[3]["error"] = "Expected: <5> Actual: <4>"
    summary = dart_test_report.failure_summary(write(tmp_path / "tests.jsonl", events))
    assert summary == "Dart test failure: shows hello: Expected: <5> Actual: <4>"
