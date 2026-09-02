#!/usr/bin/env python3
"""Jira Cloud push-mirror adapter: Epic + Story + Task issues, Blocks links, label status, Done transition."""

from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import tracker_probe
from tracker_http import TrackerError, expect

ISSUE_TYPES = {"epic": "Epic", "story": "Story", "task": "Task"}
DONE_TRANSITIONS = ("Done", "Closed", "Resolved")
API = "/rest/api/3"


def available(config: dict[str, str], creds: dict[str, str]) -> bool:
    return not tracker_probe.missing_names("jira", creds)


def _auth(creds: dict[str, str]) -> str:
    return tracker_probe.jira_authorization(creds)


def _url(creds: dict[str, str], path: str) -> str:
    return f"{tracker_probe.jira_base(creds)}{API}{path}"


def _key(ref: str) -> str:
    return ref.rstrip("/").rsplit("/", 1)[-1]


def adf(text: str) -> dict[str, object]:
    paragraphs = [block for block in text.split("\n\n") if block.strip()] or [text]
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": paragraph.strip()}]} for paragraph in paragraphs
        ],
    }


def create_ticket(
    config: dict[str, str],
    creds: dict[str, str],
    *,
    ticket_id: str,
    title: str,
    body: str,
    kind: str,
    parent: str | None,
    blocked_by: Iterable[str],
) -> str:
    fields: dict[str, object] = {
        "project": {"key": creds["JIRA_PROJECT"]},
        "issuetype": {"name": ISSUE_TYPES.get(kind, "Task")},
        "summary": title[:255],
        "description": adf(body),
        "labels": ["hard-eng", kind],
    }
    if parent:
        fields["parent"] = {"key": _key(parent)}
    created = expect(
        "POST", _url(creds, "/issue"), _auth(creds), creds, {"fields": fields}, label=f"create {ticket_id}"
    )
    key = created.get("key") if isinstance(created, dict) else None
    if not isinstance(key, str) or not key:
        raise TrackerError(f"Jira create returned no key for {ticket_id}")
    for blocker in blocked_by:
        link = {"type": {"name": "Blocks"}, "inwardIssue": {"key": _key(blocker)}, "outwardIssue": {"key": key}}
        expect("POST", _url(creds, "/issueLink"), _auth(creds), creds, link, label=f"link {key}")
    return f"{tracker_probe.jira_base(creds)}/browse/{key}"


def update_status(config: dict[str, str], creds: dict[str, str], tracker_ref: str, status: str) -> bool:
    payload = {"update": {"labels": [{"add": f"hard-eng-{status}"}]}}
    expect("PUT", _url(creds, f"/issue/{_key(tracker_ref)}"), _auth(creds), creds, payload, label="update-status")
    return True


def _comment(creds: dict[str, str], tracker_ref: str, text: str) -> None:
    url = _url(creds, f"/issue/{_key(tracker_ref)}/comment")
    expect("POST", url, _auth(creds), creds, {"body": adf(text)}, label="comment")


def close_ticket(config: dict[str, str], creds: dict[str, str], tracker_ref: str, reason: str) -> bool:
    key = _key(tracker_ref)
    _comment(creds, tracker_ref, reason)
    listing = expect("GET", _url(creds, f"/issue/{key}/transitions"), _auth(creds), creds, None, label="transitions")
    transitions = listing.get("transitions") if isinstance(listing, dict) else None
    entries = [item for item in transitions if isinstance(item, dict)] if isinstance(transitions, list) else []
    by_name = {str(item.get("name")): str(item.get("id")) for item in entries}
    chosen = next((by_name[name] for name in DONE_TRANSITIONS if name in by_name), None)
    if chosen is None:
        raise TrackerError(f"no Done/Closed/Resolved transition on {key}: {sorted(by_name)}")
    payload = {"transition": {"id": chosen}}
    expect("POST", _url(creds, f"/issue/{key}/transitions"), _auth(creds), creds, payload, label="transition")
    return True


def link_pr(config: dict[str, str], creds: dict[str, str], tracker_ref: str, pr_url: str) -> bool:
    _comment(creds, tracker_ref, f"Linked PR: {pr_url}")
    return True


def pull_drift(config: dict[str, str], creds: dict[str, str], tracker_refs: tuple[str, ...]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for ref in tracker_refs:
        url = _url(creds, f"/issue/{_key(ref)}?fields=status,summary,updated")
        payload = expect("GET", url, _auth(creds), creds, None, label="issue")
        fields = payload.get("fields", {}) if isinstance(payload, dict) else {}
        status = fields.get("status", {}) if isinstance(fields, dict) else {}
        rows.append(
            {
                "tracker_ref": ref,
                "remote_state": str(status.get("name", "")) if isinstance(status, dict) else "",
                "remote_title": str(fields.get("summary", "")) if isinstance(fields, dict) else "",
                "remote_updated_at": str(fields.get("updated", "")) if isinstance(fields, dict) else "",
            }
        )
    return rows
