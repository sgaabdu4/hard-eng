#!/usr/bin/env python3
"""Regression: planning-step receipts gate approval, and the handoff block prints after approval."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NoReturn

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import plan_state
import ticket_parser
import ticket_template
from git_env import git_env, scrub_environ

scrub_environ(ceiling=tempfile.gettempdir())

STATE_SCRIPT = SCRIPT_DIR / "plan_state.py"
EVIDENCE_SCRIPT = SCRIPT_DIR / "execution_evidence.py"
SLUG = "steps-demo"


def fail(message: str) -> NoReturn:
    raise SystemExit(f"FAIL: {message}")


def require(condition: bool, label: str) -> None:
    if not condition:
        fail(label)


def env() -> dict[str, str]:
    value = git_env()
    value["GIT_CONFIG_GLOBAL"] = os.devnull
    return value


def git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=env(),
    )
    return result.stdout.strip()


def run(script: Path, *arguments: str, stdin: str | None = None) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(script), *arguments], check=False, capture_output=True, text=True, env=env(), input=stdin
    )
    return result.returncode, result.stdout + result.stderr


def values(output: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            parsed[key] = value
    return parsed


def filled_brief(slug: str) -> str:
    text = plan_state.template(slug, f"{slug}-test")
    replacements = {
        "## Outcome\n- TBD": "## Outcome\n- A user receives one observable result.",
        "## Non-goals\n- TBD": "## Non-goals\n- Adjacent workflow changes are excluded.",
        "## Material decisions\n- TBD": "## Material decisions\n- Existing policy remains canonical.",
        "- ux_reference = TBD": "- ux_reference = n/a",
        "- ux_reference_sources = TBD": "- ux_reference_sources = n/a",
        "## Acceptance examples\n- TBD": "## Acceptance examples\n- Given a user, when they act, then the result shows.",
        "## Affected canonical areas\n- TBD": "## Affected canonical areas\n- Existing command owner and route.",
        "- rollback = TBD": "- rollback = disable the route and preserve stored state.",
        "## Vertical slices\n- S-1 = TBD; depends_on = none\n- proof = TBD": (
            "## Vertical slices\n- S-1 = command to stored result to visible response.\n- proof = focused test."
        ),
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def make_repo(base: Path, name: str) -> tuple[Path, Path]:
    repo = base / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    manifest = {
        "schema_version": 1,
        "enforcement": {"schema_version": 1},
        "families": {"targeted": [sys.executable, "-c", "pass"]},
    }
    (repo / "hard-eng.gates.json").write_text(json.dumps(manifest), encoding="utf-8")
    (repo / "owner.py").write_text("print('owner')\n", encoding="utf-8")
    plan = repo / "features" / SLUG / "PLAN.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(filled_brief(SLUG), encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "seed")
    return repo, plan


def record_research(repo: Path, plan: Path) -> None:
    code, output = run(
        EVIDENCE_SCRIPT,
        "record-research",
        "--repo",
        str(repo),
        "--plan",
        str(plan),
        "--scope",
        "local",
        "--question",
        "Which owner?",
        "--decision",
        "Use owner.py.",
        "--source",
        "owner.py",
        "--verified",
        "owner.py prints owner",
        "--fresh-until",
        "2099-12-31",
        "--unknown",
        "none",
    )
    require(code == 0, f"research receipt must record: {output}")


def record_step(repo: Path, plan: Path, step: str, payload: dict) -> tuple[int, str]:
    return run(
        STATE_SCRIPT,
        "record-step",
        "--repo",
        str(repo),
        "--plan",
        str(plan),
        "--step",
        step,
        "--payload-file",
        "-",
        stdin=json.dumps(payload),
    )


def token(repo: Path, plan: Path) -> str:
    code, output = run(STATE_SCRIPT, "inspect", "--repo", str(repo), "--plan", str(plan))
    require(code == 0, f"inspect must pass: {output}")
    return values(output)["token"]


def approve(repo: Path, plan: Path) -> tuple[int, str]:
    return run(
        STATE_SCRIPT,
        "approve",
        "--repo",
        str(repo),
        "--plan",
        str(plan),
        "--expect-token",
        token(repo, plan),
        "--approval-reply",
        "yes go",
    )


GOOD_PAYLOADS = {
    "code-study": {"owners": ["owner.py"], "callers": [], "notes": "owner.py is the only caller."},
    "edge-scan": {
        "axes": {
            "actors": "single signed-in user",
            "empty-error-retry": "none",
            "data-lifecycle": "none",
            "delivery-form": "repository",
            "external-concurrency": "none",
            "accessibility": "none",
            "rollout-rollback": "revert commit",
        }
    },
    "decisions": {
        "decisions": [
            {"id": "D-1", "decision": "keep existing policy", "status": "settled", "settled_by": "evidence"},
            {"id": "D-2", "decision": "colour of the button", "status": "user-decision", "settled_by": "pending"},
        ]
    },
    "slices": {"slices": [{"id": "S-1", "depends_on": []}, {"id": "S-2", "depends_on": ["S-1"]}]},
    "closing": {"tickets": "local", "tracker": "not-probed", "reply": "no split"},
}


def check_single_plan(base: Path) -> None:
    repo, plan = make_repo(base, "single")
    code, output = run(STATE_SCRIPT, "validate", "--repo", str(repo), "--plan", str(plan))
    parsed = values(output)
    require(parsed.get("plan_steps") == "0/6", f"fresh brief must show zero steps: {output}")
    require(parsed.get("ready_for_approval") == "no", f"complete brief without steps is not ready: {output}")
    code, output = approve(repo, plan)
    require(code != 0 and "planning step not recorded: code-study" in output, f"approve must name code-study: {output}")

    record_research(repo, plan)
    for step, payload in GOOD_PAYLOADS.items():
        code, output = record_step(repo, plan, step, payload)
        require(code == 0 and f"recorded_step={step}" in output, f"{step} must record: {output}")
    code, output = approve(repo, plan)
    require(code != 0 and "D-2" in output, f"open user decision must block approval: {output}")

    settled = json.loads(json.dumps(GOOD_PAYLOADS["decisions"]))
    settled["decisions"][1].update(status="settled", settled_by="user reply 2026-09-02")
    code, output = record_step(repo, plan, "decisions", settled)
    require(code == 0, f"settled decisions must record: {output}")

    (repo / "owner.py").write_text("print('owner v2')\n", encoding="utf-8")
    git(repo, "commit", "-q", "-am", "move HEAD")
    record_research(repo, plan)
    code, output = approve(repo, plan)
    require(code != 0 and "stale" in output and "code-study" in output, f"moved HEAD must stale code-study: {output}")
    code, output = record_step(repo, plan, "code-study", GOOD_PAYLOADS["code-study"])
    require(code == 0, f"code-study must re-record: {output}")

    code, output = run(STATE_SCRIPT, "validate", "--repo", str(repo), "--plan", str(plan))
    parsed = values(output)
    require(parsed.get("plan_steps") == "6/6" and "plan_steps_missing" not in parsed, f"all steps done: {output}")
    require(parsed.get("ready_for_approval") == "yes", f"complete steps must be ready: {output}")
    code, output = approve(repo, plan)
    require(code == 0, f"complete plan must approve: {output}")
    parsed = values(output)
    require(parsed.get("handoff") == "ready", f"approval must print the handoff block: {output}")
    require(parsed.get("handoff_root") == str(repo) and parsed.get("handoff_branch") == "main", str(parsed))
    require(parsed.get("handoff_plan") == f"features/{SLUG}/PLAN.md", str(parsed))
    prompt = parsed.get("handoff_prompt", "")
    require("S-1" in prompt and "setup_state.py verify" in prompt and str(repo) in prompt, f"prompt: {prompt}")
    require("plan_steps=" not in output, "approved plan must not keep printing planning steps")

    code, output = record_step(repo, plan, "closing", GOOD_PAYLOADS["closing"])
    require(code != 0 and "planning brief" in output, "record-step after approval must refuse")


def check_bad_payloads(base: Path) -> None:
    repo, plan = make_repo(base, "payloads")
    cases = [
        ("edge-scan", {"axes": {"actors": "one"}}, "missing"),
        ("slices", {"slices": [{"id": "S-1", "depends_on": ["S-2"]}, {"id": "S-2", "depends_on": ["S-1"]}]}, "loop"),
        ("slices", {"slices": [{"id": "S-1"}, {"id": "S-3"}]}, "without gaps"),
        ("closing", {"tickets": "trello", "tracker": "x", "reply": "y"}, "tickets must be one of"),
        ("code-study", {"owners": ["../etc/passwd"], "notes": "x"}, "repository-relative"),
        ("decisions", {"decisions": [{"id": "D-1", "decision": "x", "status": "maybe", "settled_by": "y"}]}, "status"),
        ("bogus", {}, "step must be one of"),
    ]
    for step, payload, expected in cases:
        code, output = record_step(repo, plan, step, payload)
        require(code != 0 and expected in output, f"{step} payload must fail with {expected!r}: {output}")
    receipt = plan.parent / "receipts" / "plan-steps.json"
    require(not receipt.exists(), "rejected payloads must not write a receipt")


def ticket_text(ticket_id: str, plan_id: str, fingerprint: str, depends_on: str, status: str) -> str:
    text = ticket_template.render(
        ticket_id,
        plan_id,
        fingerprint,
        depends_on,
        f"S-{ticket_id[2:]}" if ticket_id != "T-int" else "none",
        "A-1",
        "Do the thing.",
        "Given, when, then.",
        "skills/",
        ticket_parser.TICKET_STATE_START,
        ticket_parser.TICKET_STATE_END,
    )
    changes = {"status": status}
    if status == "shipped":
        changes.update(
            claimed_by="session-fixture",
            claimed_at="2026-09-02T00:00:00Z",
            completed_slices=f"S-{ticket_id[2:]}",
            green_artifact="sha256:" + "a" * 64,
            delivery="https://example.invalid/pr/1@" + "b" * 40,
        )
    return ticket_parser.render_state(text, changes)


def check_ticket_handoff(base: Path) -> None:
    repo, plan = make_repo(base, "tickets")
    text = plan.read_text(encoding="utf-8")
    text = text.replace(
        "- S-1 = command to stored result to visible response.", "- S-1 = first.\n- S-2 = second.\n- S-3 = third."
    )
    fingerprint = plan_state.frozen_fingerprint(plan_state.parse_sections(text))
    text = plan_state.render_state(
        text,
        {
            "lifecycle_status": "building",
            "approval_status": "approved",
            "approval_fingerprint": fingerprint,
            "approval_provenance": "ready-to-build",
            "next_action": "Claim tickets.",
        },
    )
    text = text.replace("- state_version = 1\n", "- state_version = 2\n").replace(
        "- replan_reason = none\n", "- replan_reason = none\n- execution_mode = tickets\n"
    )
    plan.write_text(text, encoding="utf-8")
    plan_id = f"{SLUG}-test"
    tickets = plan.parent / "tickets"
    tickets.mkdir()
    (tickets / "T-1.md").write_text(ticket_text("T-1", plan_id, fingerprint, "none", "shipped"), encoding="utf-8")
    (tickets / "T-2.md").write_text(ticket_text("T-2", plan_id, fingerprint, "T-1", "todo"), encoding="utf-8")
    (tickets / "T-3.md").write_text(ticket_text("T-3", plan_id, fingerprint, "T-2", "todo"), encoding="utf-8")
    record_research(repo, plan)
    plan_state.authorize_execution(repo, plan, fingerprint, "yes go", [])
    code, output = run(STATE_SCRIPT, "inspect", "--repo", str(repo), "--plan", str(plan))
    require(code == 0, f"ticket inspect must pass: {output}")
    parsed = values(output)
    require(parsed.get("handoff_ticket_1") == "T-2", f"only the ticket whose dependency shipped is ready: {output}")
    require("handoff_ticket_2" not in parsed, "ticket behind an unshipped dependency must not be offered")
    require("claim" in parsed.get("handoff_ticket_1_prompt", "") and "T-2" in parsed["handoff_ticket_1_prompt"], output)
    require("handoff_prompt" not in parsed, "ticket mode must not print the single-slice prompt")


def set_slices(plan: Path, rows: str) -> None:
    text = plan.read_text(encoding="utf-8")
    head, _ = text.split("## Vertical slices\n")
    plan.write_text(head + "## Vertical slices\n" + rows, encoding="utf-8")


def check_brief_slices(base: Path) -> None:
    repo, plan = make_repo(base, "slices")
    cases = [
        ("- S-1 = a; depends_on = S-2\n- S-2 = b; depends_on = S-1\n", "loop"),
        ("- S-1 = a; depends_on = none\n- S-3 = c; depends_on = none\n", "without gaps"),
        ("- S-1 = a; depends_on = S-9\n", "unknown slice S-9"),
        ("- proof = nothing\n", "at least one"),
    ]
    for rows, expected in cases:
        set_slices(plan, rows)
        code, output = run(STATE_SCRIPT, "validate", "--repo", str(repo), "--plan", str(plan))
        require(code != 0 and expected in output, f"slice rows {rows!r} must fail with {expected!r}: {output}")
    set_slices(
        plan,
        "- S-1 = a; depends_on = none\n- proof = t\n- S-2 = b; depends_on = S-1\n- S-3 = c; depends_on = S-1, S-2\n",
    )
    code, output = run(STATE_SCRIPT, "validate", "--repo", str(repo), "--plan", str(plan))
    require(code == 0, f"valid slice graph must validate: {output}")
    record_research(repo, plan)
    code, output = record_step(repo, plan, "slices", {})
    require(code == 0, f"slices step must read the brief graph: {output}")
    receipt = json.loads((plan.parent / "receipts" / "plan-steps.json").read_text(encoding="utf-8"))
    recorded = receipt["steps"]["slices"]["slices"]
    require(recorded[2] == {"id": "S-3", "depends_on": ["S-1", "S-2"]}, f"recorded graph drifted: {recorded}")
    code, output = record_step(repo, plan, "closing", {"tickets": "local", "tracker": "local files", "reply": "split"})
    require(code == 0, f"closing must record: {output}")
    text = plan.read_text(encoding="utf-8")
    require("- tickets = local\n- tracker = local files\n" in text, f"closing rows must land in the brief: {text}")
    require(text.count("- tickets = ") == 1, "closing rows must not duplicate")
    code, output = record_step(repo, plan, "closing", {"tickets": "none", "tracker": "n/a", "reply": "no"})
    text = plan.read_text(encoding="utf-8")
    require(code == 0 and text.count("- tickets = ") == 1 and "- tickets = none" in text, "closing rows must replace")
    code, output = run(STATE_SCRIPT, "validate", "--repo", str(repo), "--plan", str(plan))
    require(code == 0, f"brief with closing rows must validate: {output}")
    text = text.replace("- tickets = none", "- tickets = trello")
    plan.write_text(text, encoding="utf-8")
    code, output = run(STATE_SCRIPT, "validate", "--repo", str(repo), "--plan", str(plan))
    require(code != 0 and "tickets must be one of" in output, f"bad tickets row must fail: {output}")


class _StubHandler(__import__("http.server").server.BaseHTTPRequestHandler):
    expected_basic = ""

    def do_GET(self) -> None:
        ok = self.headers.get("Authorization", "") == "Basic " + self.expected_basic
        self.send_response(200 if ok else 401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}' if ok else b'{"error": "nope"}')

    def log_message(self, *arguments: object) -> None:
        pass


class StubServer:
    def __init__(self, expected_basic: str) -> None:
        import http.server
        import threading

        handler = type("Handler", (_StubHandler,), {"expected_basic": expected_basic})
        self.server = http.server.HTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def kill(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def wait(self) -> None:
        self.thread.join(timeout=5)


def start_stub(base: Path, port: int, expected_basic: str) -> StubServer:
    return StubServer(expected_basic)


def free_port() -> int:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def fake_gh(base: Path, exit_code: int) -> str:
    bin_dir = base / f"gh-bin-{exit_code}"
    bin_dir.mkdir(exist_ok=True)
    script = bin_dir / "gh"
    script.write_text(f"#!/bin/sh\necho 'stub gh auth' >&2\nexit {exit_code}\n", encoding="utf-8")
    script.chmod(0o755)
    return f"{bin_dir}:{os.environ.get('PATH', '')}"


def probe(repo: Path, plan: Path, path_value: str, extra_env: dict[str, str], *flags: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(STATE_SCRIPT), "probe-trackers", "--repo", str(repo), "--plan", str(plan), *flags],
        check=False,
        capture_output=True,
        text=True,
        env={**env(), **extra_env, "PATH": path_value},
    )
    return result.returncode, result.stdout + result.stderr


def check_tracker_probe(base: Path) -> None:
    import base64

    repo, plan = make_repo(base, "probe")
    record_research(repo, plan)
    clean = {name: "" for names in __import__("tracker_probe").CREDENTIAL_NAMES.values() for name in names}
    code, output = probe(repo, plan, fake_gh(base, 1), clean)
    parsed = values(output)
    require(code == 0, f"probe must not fail the command: {output}")
    require(parsed.get("tracker_1_available") == "no" and "stub gh auth" in parsed.get("tracker_1_detail", ""), output)
    require(parsed.get("tracker_2_available") == "no" and "JIRA_SITE" in parsed.get("tracker_2_detail", ""), output)
    require(parsed.get("tracker_3_available") == "no" and "AZDO_ORG" in parsed.get("tracker_3_detail", ""), output)
    code, output = record_step(repo, plan, "closing", {"tickets": "jira", "reply": "jira please"})
    require(code != 0 and "JIRA_SITE" in output, f"closing must name the missing variable: {output}")
    code, output = record_step(repo, plan, "closing", {"tickets": "github", "reply": "gh"})
    require(code != 0 and "not available" in output, f"closing must refuse an unavailable tracker: {output}")

    jira_basic = base64.b64encode(b"me@example.invalid:jira-secret-token").decode()
    azdo_basic = base64.b64encode(b":azdo-secret-pat").decode()
    servers = [start_stub(base, 0, jira_basic), start_stub(base, 0, azdo_basic)]
    jira_port, azdo_port = servers[0].port, servers[1].port
    try:
        (repo / ".env").write_text(
            f"JIRA_SITE=http://127.0.0.1:{jira_port}\nJIRA_EMAIL=me@example.invalid\n"
            "JIRA_API_TOKEN='jira-secret-token'\nJIRA_PROJECT=PROJ\n"
            f"export AZDO_ORG=http://127.0.0.1:{azdo_port}\nAZDO_PROJECT=Demo\nAZDO_PAT=azdo-secret-pat\n",
            encoding="utf-8",
        )
        code, output = probe(repo, plan, fake_gh(base, 0), clean, "--write-env-example")
        parsed = values(output)
        require(parsed.get("tracker_1_available") == "yes", f"gh exit 0 must be available: {output}")
        require(parsed.get("tracker_2_available") == "yes", f".env Jira credentials must pass: {output}")
        require(parsed.get("tracker_3_available") == "yes", f".env Azure credentials must pass: {output}")
        require(parsed.get("env_example") == "written", output)
        example = (repo / ".env.example").read_text(encoding="utf-8")
        require("JIRA_API_TOKEN=\n" in example and "AZDO_PAT=\n" in example and "secret" not in example, example)
        code, output = probe(repo, plan, fake_gh(base, 0), clean, "--write-env-example")
        require(values(output).get("env_example") == "current", "second write must be idempotent")
        require((repo / ".env.example").read_text(encoding="utf-8") == example, "env example must not duplicate")
        receipt = (plan.parent / "receipts" / "plan-steps.json").read_text(encoding="utf-8")
        require("jira-secret-token" not in receipt and "azdo-secret-pat" not in receipt, "secrets leaked to receipt")
        require(jira_basic not in receipt and azdo_basic not in receipt, "base64 secrets leaked to receipt")
        code, output = record_step(repo, plan, "closing", {"tickets": "jira", "reply": "jira please"})
        require(code == 0 and "- tickets = jira" in plan.read_text(encoding="utf-8"), f"closing jira: {output}")

        (repo / ".env").write_text(
            f"JIRA_SITE=http://127.0.0.1:{jira_port}\nJIRA_EMAIL=me@example.invalid\n"
            "JIRA_API_TOKEN=wrong-token\nJIRA_PROJECT=PROJ\n",
            encoding="utf-8",
        )
        code, output = probe(repo, plan, fake_gh(base, 0), clean)
        parsed = values(output)
        require(parsed.get("tracker_2_available") == "no" and "401" in parsed.get("tracker_2_detail", ""), output)
        require("wrong-token" not in output, "token must be redacted from probe output")
    finally:
        for server in servers:
            server.kill()
            server.wait()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="plan-steps-regression-") as directory:
        base = Path(directory).resolve()
        check_single_plan(base)
        check_bad_payloads(base)
        check_ticket_handoff(base)
        check_brief_slices(base)
        check_tracker_probe(base)
    print("plan-steps regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
