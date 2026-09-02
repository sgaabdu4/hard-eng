#!/usr/bin/env python3
"""Azure DevOps push-mirror adapter: Epic → Feature → User Story/Task with hierarchy + predecessor links."""

from __future__ import annotations

import html
import sys
import urllib.parse
from collections.abc import Iterable
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import tracker_probe
from tracker_http import TrackerError, expect

API_VERSION = tracker_probe.API_VERSION
WORK_ITEM_TYPES = {"epic": "Epic", "feature": "Feature", "story": "User Story", "task": "Task"}
PARENT_LINK = "System.LinkTypes.Hierarchy-Reverse"
PREDECESSOR_LINK = "System.LinkTypes.Dependency-Reverse"
CLOSED_STATES = ("Closed", "Done", "Resolved")
PATCH_TYPE = "application/json-patch+json"


def available(config: dict[str, str], creds: dict[str, str]) -> bool:
    return not tracker_probe.missing_names("azdo", creds)


def _auth(creds: dict[str, str]) -> str:
    return tracker_probe.azdo_authorization(creds)


def _project_url(creds: dict[str, str], path: str) -> str:
    return f"{tracker_probe.azdo_base(creds)}/{creds['AZDO_PROJECT']}/_apis/wit/{path}"


def _item_url(creds: dict[str, str], ref: str) -> str:
    identifier = ref.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    return f"{tracker_probe.azdo_base(creds)}/_apis/wit/workitems/{identifier}?api-version={API_VERSION}"


def _api_url(ref: str) -> str:
    return ref.split("?", 1)[0]


def _description(body: str) -> str:
    return "<pre>" + html.escape(body) + "</pre>"


def _create(creds: dict[str, str], work_item_type: str, title: str, body: str, relations: list[dict[str, str]]) -> str:
    patch: list[dict[str, object]] = [
        {"op": "add", "path": "/fields/System.Title", "value": title[:255]},
        {"op": "add", "path": "/fields/System.Description", "value": _description(body)},
        {"op": "add", "path": "/fields/System.Tags", "value": "hard-eng"},
    ]
    patch.extend({"op": "add", "path": "/relations/-", "value": relation} for relation in relations)
    url = _project_url(creds, f"workitems/${urllib.parse.quote(work_item_type)}?api-version={API_VERSION}")
    created = expect("POST", url, _auth(creds), creds, patch, label=f"create {work_item_type}", content_type=PATCH_TYPE)
    api_url = created.get("url") if isinstance(created, dict) else None
    if not isinstance(api_url, str) or not api_url:
        raise TrackerError(f"Azure DevOps create returned no url for {work_item_type}")
    return api_url


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
    if kind == "epic":
        epic_url = _create(creds, WORK_ITEM_TYPES["epic"], title, body, [])
        feature_title = title.replace("Epic:", "Feature:", 1)
        return _create(creds, WORK_ITEM_TYPES["feature"], feature_title, body, [{"rel": PARENT_LINK, "url": epic_url}])
    relations: list[dict[str, str]] = []
    if parent:
        relations.append({"rel": PARENT_LINK, "url": _api_url(parent)})
    relations.extend({"rel": PREDECESSOR_LINK, "url": _api_url(blocker)} for blocker in blocked_by)
    return _create(creds, WORK_ITEM_TYPES.get(kind, "Task"), title, body, relations)


def _patch(creds: dict[str, str], tracker_ref: str, patch: list[dict[str, object]], label: str) -> None:
    expect("PATCH", _item_url(creds, tracker_ref), _auth(creds), creds, patch, label=label, content_type=PATCH_TYPE)


def update_status(config: dict[str, str], creds: dict[str, str], tracker_ref: str, status: str) -> bool:
    _patch(creds, tracker_ref, [{"op": "add", "path": "/fields/System.Tags", "value": f"hard-eng; {status}"}], "status")
    return True


def close_ticket(config: dict[str, str], creds: dict[str, str], tracker_ref: str, reason: str) -> bool:
    last_error: TrackerError | None = None
    for state in CLOSED_STATES:
        patch: list[dict[str, object]] = [
            {"op": "add", "path": "/fields/System.State", "value": state},
            {"op": "add", "path": "/fields/System.History", "value": html.escape(reason)},
        ]
        try:
            _patch(creds, tracker_ref, patch, f"close {state}")
            return True
        except TrackerError as error:
            last_error = error
    raise TrackerError(f"no closing state accepted: {last_error}")


def link_pr(config: dict[str, str], creds: dict[str, str], tracker_ref: str, pr_url: str) -> bool:
    relation = {"rel": "Hyperlink", "url": pr_url, "attributes": {"comment": "Linked PR"}}
    _patch(creds, tracker_ref, [{"op": "add", "path": "/relations/-", "value": relation}], "link-pr")
    return True


def pull_drift(config: dict[str, str], creds: dict[str, str], tracker_refs: tuple[str, ...]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for ref in tracker_refs:
        url = _item_url(creds, ref) + "&fields=System.State,System.Title,System.ChangedDate"
        payload = expect("GET", url, _auth(creds), creds, None, label="work item")
        fields = payload.get("fields", {}) if isinstance(payload, dict) else {}
        values = fields if isinstance(fields, dict) else {}
        rows.append(
            {
                "tracker_ref": ref,
                "remote_state": str(values.get("System.State", "")),
                "remote_title": str(values.get("System.Title", "")),
                "remote_updated_at": str(values.get("System.ChangedDate", "")),
            }
        )
    return rows
