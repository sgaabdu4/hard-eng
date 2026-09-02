#!/usr/bin/env python3
"""Regression: Jira Cloud and Azure DevOps adapters against recording HTTP stubs; secrets never reach output."""

from __future__ import annotations

import base64
import contextlib
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import ticket_state_regression as fixture
import tracker_azdo
import tracker_jira

STUB = """
import http.server, json, sys
LOG, BASIC = sys.argv[2], sys.argv[3]
counter = {"n": 0}
class H(http.server.BaseHTTPRequestHandler):
    def _handle(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8") if length else ""
        record = {"method": self.command, "path": self.path, "auth": self.headers.get("Authorization", ""),
                  "content_type": self.headers.get("Content-Type", ""), "body": body}
        open(LOG, "a", encoding="utf-8").write(json.dumps(record) + "\\n")
        if record["auth"] != "Basic " + BASIC:
            self._reply(401, {"error": "unauthorized"})
            return
        counter["n"] += 1
        n = counter["n"]
        if self.path.endswith("/transitions") and self.command == "GET":
            self._reply(200, {"transitions": [{"id": "31", "name": "Done"}, {"id": "11", "name": "To Do"}]})
        elif "/_apis/wit/workitems/$" in self.path:
            self._reply(200, {"id": n, "url": f"http://127.0.0.1:{sys.argv[1]}/_apis/wit/workItems/{n}"})
        elif self.path.endswith("/rest/api/3/issue"):
            self._reply(201, {"id": str(n), "key": f"PROJ-{n}"})
        elif "fields=" in self.path:
            self._reply(200, {"fields": {"status": {"name": "Done"}, "summary": "t", "updated": "u",
                                        "System.State": "Closed", "System.Title": "t", "System.ChangedDate": "d"}})
        else:
            self._reply(200, {"ok": True})
    def _reply(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    do_GET = do_POST = do_PUT = do_PATCH = _handle
    def log_message(self, *a):
        pass
http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
"""


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_stub(base: Path, name: str, basic: str) -> tuple[subprocess.Popen, int, Path]:
    port = free_port()
    log = base / f"{name}.jsonl"
    script = base / f"{name}-stub.py"
    script.write_text(STUB, encoding="utf-8")
    process = subprocess.Popen([sys.executable, str(script), str(port), str(log), basic], stdin=subprocess.DEVNULL)
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return process, port, log
        except OSError:
            time.sleep(0.1)
    process.kill()
    fixture.fail(f"stub {name} did not start")


def read_log(log: Path) -> list[dict[str, str]]:
    text = log.read_text(encoding="utf-8") if log.exists() else ""
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def run_epic(base: Path, name: str, slug: str, adapter: str, env_text: str) -> tuple[Path, Path]:
    repo, plan = fixture.setup_epic(base, name, slug, fixture.behaves("S-1", "S-2", "S-3"))
    manifest = json.loads((repo / "hard-eng.gates.json").read_text(encoding="utf-8"))
    manifest["tracker"] = {"adapter": adapter}
    (repo / "hard-eng.gates.json").write_text(json.dumps(manifest), encoding="utf-8")
    (repo / ".env").write_text(env_text, encoding="utf-8")
    (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
    fixture.commit_all(repo, "configure tracker")
    chained = fixture.three_way_tickets()
    chained[1] = {**chained[1], "depends_on": ("T-1",)}
    fixture.run_decompose(repo, plan, chained)
    return repo, plan


def check_jira(base: Path) -> None:
    secret = "jira-secret-token-value"
    basic = base64.b64encode(f"me@example.invalid:{secret}".encode()).decode()
    process, port, log = start_stub(base, "jira", basic)
    try:
        env_text = f"JIRA_SITE=http://127.0.0.1:{port}\nJIRA_EMAIL=me@example.invalid\nJIRA_API_TOKEN={secret}\nJIRA_PROJECT=PROJ\n"
        repo, plan = run_epic(base, "jira-mirror", "jiramirror", "jira", env_text)
        calls = read_log(log)
        creates = [call for call in calls if call["path"].endswith("/rest/api/3/issue") and call["method"] == "POST"]
        fixture.require(len(creates) == 5, f"epic + 3 stories + task: {len(creates)}")
        bodies = [json.loads(call["body"])["fields"] for call in creates]
        fixture.require(bodies[0]["issuetype"]["name"] == "Epic" and "parent" not in bodies[0], str(bodies[0]))
        fixture.require(bodies[0]["project"]["key"] == "PROJ", "project key from .env")
        for fields in bodies[1:4]:
            fixture.require(
                fields["issuetype"]["name"] == "Story" and fields["parent"] == {"key": "PROJ-1"}, str(fields)
            )
        fixture.require(bodies[4]["issuetype"]["name"] == "Task", "integration ticket is a Task")
        fixture.require(bodies[2]["description"]["type"] == "doc", "description is Atlassian document format")
        text = json.dumps(bodies[2])
        for anchor in ("## Goal", "## Depends on", "## Definition of done", "## Start here"):
            fixture.require(anchor in text, f"Jira body missing {anchor!r}")
        links = [json.loads(call["body"]) for call in calls if call["path"].endswith("/issueLink")]
        fixture.require(
            any(
                link["inwardIssue"] == {"key": "PROJ-2"} and link["outwardIssue"] == {"key": "PROJ-3"} for link in links
            ),
            str(links),
        )
        fixture.require(all(link["type"] == {"name": "Blocks"} for link in links), "blocker links use Blocks")
        ref = fixture.read_ticket_state(repo, "jiramirror", "T-2")["tracker_ref"]
        fixture.require(ref.endswith("/browse/PROJ-3"), f"ticket ref: {ref}")
        receipt = (plan.parent / "receipts" / "tracker.json").read_text(encoding="utf-8")
        fixture.require("PROJ-1" in receipt and secret not in receipt and basic not in receipt, "epic receipt")

        creds = {
            "JIRA_SITE": f"http://127.0.0.1:{port}",
            "JIRA_EMAIL": "me@example.invalid",
            "JIRA_API_TOKEN": secret,
            "JIRA_PROJECT": "PROJ",
        }
        log.unlink()
        tracker_jira.update_status({}, creds, ref, "building")
        tracker_jira.link_pr({}, creds, ref, "https://example.invalid/pr/9")
        tracker_jira.close_ticket({}, creds, ref, "shipped")
        rows = tracker_jira.pull_drift({}, creds, (ref,))
        fixture.require(rows[0]["remote_state"] == "Done", str(rows))
        ops = [(call["method"], call["path"].rsplit("/", 1)[-1]) for call in read_log(log)]
        fixture.require(("PUT", "PROJ-3") in ops and ("POST", "comment") in ops, str(ops))
        fixture.require(("GET", "transitions") in ops and ("POST", "transitions") in ops, str(ops))
        transition = next(
            json.loads(call["body"])
            for call in read_log(log)
            if call["method"] == "POST" and call["path"].endswith("/transitions")
        )
        fixture.require(transition == {"transition": {"id": "31"}}, f"Done transition chosen: {transition}")

        bad = {**creds, "JIRA_API_TOKEN": "wrong-secret"}
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            try:
                tracker_jira.update_status({}, bad, ref, "building")
            except Exception as error:
                message = str(error)
            else:
                fixture.fail("wrong token must fail")
        fixture.require("401" in message and "wrong-secret" not in message, f"redacted failure: {message}")
    finally:
        process.kill()
        process.wait()


def check_azdo(base: Path) -> None:
    secret = "azdo-secret-pat-value"
    basic = base64.b64encode(f":{secret}".encode()).decode()
    process, port, log = start_stub(base, "azdo", basic)
    try:
        env_text = f"AZDO_ORG=http://127.0.0.1:{port}\nAZDO_PROJECT=Demo\nAZDO_PAT={secret}\n"
        repo, plan = run_epic(base, "azdo-mirror", "azdomirror", "azdo", env_text)
        calls = read_log(log)
        creates = [call for call in calls if "/_apis/wit/workitems/$" in call["path"]]
        types = [urllib.parse.unquote(call["path"].split("$", 1)[1].split("?", 1)[0]) for call in creates]
        fixture.require(types == ["Epic", "Feature", "User Story", "User Story", "User Story", "Task"], str(types))
        fixture.require(all(call["content_type"] == "application/json-patch+json" for call in creates), "json patch")
        fixture.require(
            all("api-version=7.1" in call["path"] and "/Demo/_apis/" in call["path"] for call in creates), "project url"
        )
        patches = [json.loads(call["body"]) for call in creates]
        feature_relations = [op["value"] for op in patches[1] if op["path"] == "/relations/-"]
        fixture.require(
            feature_relations
            == [{"rel": tracker_azdo.PARENT_LINK, "url": f"http://127.0.0.1:{port}/_apis/wit/workItems/1"}],
            str(feature_relations),
        )
        story_relations = [op["value"] for op in patches[3] if op["path"] == "/relations/-"]
        fixture.require(
            {"rel": tracker_azdo.PARENT_LINK, "url": f"http://127.0.0.1:{port}/_apis/wit/workItems/2"}
            in story_relations,
            str(story_relations),
        )
        fixture.require(
            {"rel": tracker_azdo.PREDECESSOR_LINK, "url": f"http://127.0.0.1:{port}/_apis/wit/workItems/3"}
            in story_relations,
            str(story_relations),
        )
        title = next(op["value"] for op in patches[3] if op["path"] == "/fields/System.Title")
        fixture.require(title.startswith("T-2:"), title)
        description = next(op["value"] for op in patches[3] if op["path"] == "/fields/System.Description")
        fixture.require(
            "## Start here" in description and "&lt;" not in description[:5], "description carries the body"
        )
        ref = fixture.read_ticket_state(repo, "azdomirror", "T-2")["tracker_ref"]
        fixture.require(ref.endswith("/workItems/4"), f"ticket ref: {ref}")

        creds = {"AZDO_ORG": f"http://127.0.0.1:{port}", "AZDO_PROJECT": "Demo", "AZDO_PAT": secret}
        log.unlink()
        tracker_azdo.update_status({}, creds, ref, "building")
        tracker_azdo.link_pr({}, creds, ref, "https://example.invalid/pr/9")
        tracker_azdo.close_ticket({}, creds, ref, "shipped")
        rows = tracker_azdo.pull_drift({}, creds, (ref,))
        fixture.require(rows[0]["remote_state"] == "Closed", str(rows))
        later = read_log(log)
        fixture.require(
            all(call["path"].startswith("/_apis/wit/workitems/4?api-version=7.1") for call in later), str(later)
        )
        close = json.loads(later[2]["body"])
        fixture.require({"op": "add", "path": "/fields/System.State", "value": "Closed"} in close, str(close))
        fixture.require(
            secret not in json.dumps(later) or all(call["auth"].startswith("Basic ") for call in later), "auth only"
        )
        receipt = (plan.parent / "receipts" / "tracker.json").read_text(encoding="utf-8")
        fixture.require(secret not in receipt and basic not in receipt, "epic receipt leaks")
    finally:
        process.kill()
        process.wait()


def main() -> int:
    os.environ.pop("FAKE_GH_LOG", None)
    with tempfile.TemporaryDirectory(prefix="tracker-http-regression-") as directory:
        base = Path(directory).resolve()
        check_jira(base)
        check_azdo(base)
    print("tracker-http regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
