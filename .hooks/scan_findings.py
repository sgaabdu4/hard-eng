"""Read the findings of a failed scanner gate from its report, one line each."""

import json
from pathlib import Path

from dart_test_report import failure_summary
from fallow_report import located

PRINTED_ELSEWHERE = {"deptry", "lighthouse-ci", "osv", "osv-image", "performance-junit"}
READ_ERRORS = (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError)


def one_line(text: object) -> str:
    return " ".join(str(text).split())


def semgrep_findings(path: Path) -> list[str]:
    try:
        return [
            f"{located(item['path'], item['start']['line'])} {item['check_id']} "
            f"{one_line(item['extra']['message'])}"
            for item in json.loads(path.read_text())["results"]
        ]
    except READ_ERRORS:
        return []


def trivy_findings(path: Path) -> list[str]:
    try:
        return [
            f"{located(result['Target'], (item.get('CauseMetadata') or {}).get('StartLine'))} "
            f"{item['ID']} {one_line(item['Title'])}"
            for result in json.loads(path.read_text())["Results"]
            for item in result.get("Misconfigurations", [])
            if item["Status"] != "PASS"
        ]
    except READ_ERRORS:
        return []


def decimate_findings(path: Path) -> list[str]:
    try:
        return [
            f"{located(item['path'], item.get('line'))} {item['rule_id']} "
            f"{one_line(item['message'])}"
            for item in json.loads(path.read_text())["findings"]
        ]
    except READ_ERRORS:
        return []


def jscpd_findings(path: Path) -> list[str]:
    try:
        return [
            "copied code "
            + " ".join(
                f"{copy['name']}:{copy['start']}-{copy['end']}"
                for copy in (clone["firstFile"], clone["secondFile"])
            )
            for clone in json.loads(path.read_text())["duplicates"]
        ]
    except READ_ERRORS:
        return []


def import_linter_findings(path: Path) -> list[str]:
    try:
        text = path.read_text()
    except (OSError, ValueError):
        return []
    lines = [
        line.rstrip()
        for line in text.splitlines()
        if line.strip() and set(line.strip()) != {"-"}
    ]
    if "Broken contracts" in lines:
        return lines[lines.index("Broken contracts") + 1 :]
    return [] if any(line.startswith("Contracts:") for line in lines) else lines[:1]


def dart_performance_findings(path: Path) -> list[str]:
    summary = failure_summary(path)
    return [summary] if summary else []
