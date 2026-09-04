#!/usr/bin/env python3
"""Regression proof: build-step records gate every slice and the full pre-ship gate."""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
for directory in (ROOT / "skills" / "deterministic-checks" / "scripts", SCRIPT_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import plan_steps_regression as fixture
from plan_steps_regression import SLUG, STATE_SCRIPT, git, record_step, require, run, values
from script_runner import run_script

GATE_SCRIPT = ROOT / "skills/deterministic-checks/scripts/slice_gate.py"
EDGES = {"cases": [{"name": "empty input", "success_test": "test_empty_ok", "failure_test": "test_empty_refused"}]}
GREEN = {"command": ["python3", "-m", "pytest"], "exit": 0}
OPEN_FINDING = {"id": "R-1", "text": "missing null check", "status": "open"}
VALID_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk/x8AAusB9Wl2nS8AAAAASUVORK5CYII="
)


def review_round(sha: str, *findings: dict[str, str]) -> dict[str, object]:
    return {"reviewer": "fresh subagent", "packet_sha256": sha, "findings": list(findings)}


def review(sha: str, *findings: dict[str, str]) -> dict[str, object]:
    return {"rounds": [review_round(sha, *findings)]}


def packet(repo: Path, plan: Path, name: str = "S-1") -> tuple[int, dict[str, str]]:
    code, output = run(STATE_SCRIPT, "review-packet", "--repo", str(repo), "--plan", str(plan), "--slice", name)
    return code, values(output)


def record_build(repo: Path, plan: Path, name: str, step: str, payload: dict) -> tuple[int, str]:
    arguments = ("record-build", "--repo", str(repo), "--plan", str(plan), "--slice", name, "--step", step)
    return run(STATE_SCRIPT, *arguments, "--payload-file", "-", stdin=json.dumps(payload))


def checkpoint(repo: Path, plan: Path, *sets: str) -> tuple[int, str]:
    token = values(run(STATE_SCRIPT, "inspect", "--repo", str(repo), "--plan", str(plan))[1])["token"]
    arguments = ["checkpoint", "--repo", str(repo), "--plan", str(plan), "--expect-token", token]
    for assignment in sets:
        arguments += ["--set", assignment]
    return run(STATE_SCRIPT, *arguments)


def gate(repo: Path, plan: Path, *scope: str) -> tuple[int, str]:
    result = run_script(
        GATE_SCRIPT,
        [
            "run",
            "--repo",
            str(repo),
            "--plan",
            str(plan),
            *scope,
            "--timeout",
            "60",
            "--behavior",
            "records gate the slice",
            "--check",
            "targeted",
            "--e2e",
            "not-applicable:fixture",
            "--security",
            "not-applicable:fixture",
            "--review",
            "review record round 1",
        ],
        env=fixture.env(),
    )
    return result.returncode, result.output


def evidence(repo: Path, name: str, body: bytes | None = None) -> dict[str, str]:
    path = repo / "features" / SLUG / "receipts" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body if body is not None else json.dumps({"state": name}).encode("utf-8"))
    return {"path": str(path.relative_to(repo)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def video_evidence(repo: Path) -> dict[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    require(ffmpeg is not None, "ffmpeg is required to prove the walkthrough video path")
    path = repo / "features" / SLUG / "receipts" / "walkthrough.mp4"
    source = "color=size=64x48:duration=1"
    subprocess.run(
        [str(ffmpeg), "-v", "error", "-y", "-f", "lavfi", "-i", source, "-pix_fmt", "yuv420p", str(path)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    return {"path": str(path.relative_to(repo)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def verify_packet(repo: Path, plan: Path, name: str = "S-1") -> str:
    code, output = run(STATE_SCRIPT, "verify-packet", "--repo", str(repo), "--plan", str(plan), "--slice", name)
    require(code == 0, f"verify packet must build: {output}")
    return values(output)["packet_sha256"]


def verify_payload(repo: Path, plan: Path, name: str = "S-1", **overrides: object) -> dict[str, object]:
    evidence(repo, "fakes.log", b"api.example.test GET /v1/items -> fake 200\n")
    payload: dict[str, object] = {
        "mode": "logic",
        "packet_sha256": verify_packet(repo, plan, name),
        "fakes": [{"host": "api.example.test", "log": f"features/{SLUG}/receipts/fakes.log"}],
        "outside_calls": ["api.example.test"],
        "before": [evidence(repo, "before.json")],
        "after": [evidence(repo, "after.json")],
        "edge_cases": ["empty input"],
    }
    payload.update(overrides)
    return payload


def building_plan(base: Path) -> tuple[Path, Path]:
    repo, plan = fixture.make_repo(base, "build")
    fixture.record_research(repo, plan)
    settled = json.loads(json.dumps(fixture.GOOD_PAYLOADS))
    settled["decisions"]["decisions"][1].update(status="settled", settled_by="user reply 2026-09-02")
    for step, payload in settled.items():
        code, output = record_step(repo, plan, step, payload)
        require(code == 0, f"{step} must record: {output}")
    code, output = record_build(repo, plan, "S-1", "edges", EDGES)
    require(code != 0 and "building brief" in output, f"record-build before build must refuse: {output}")
    code, output = fixture.approve(repo, plan)
    require(code == 0, f"plan must approve: {output}")
    code, output = checkpoint(repo, plan, "lifecycle_status=building", "active_slice=S-1")
    require(code == 0, f"plan must start building: {output}")
    return repo, plan


def check_slice_records(base: Path) -> tuple[Path, Path]:
    repo, plan = building_plan(base)
    receipt = plan.parent / "receipts" / "S-1.json"
    code, output = gate(repo, plan, "--slice", "S-1")
    require(code != 0 and "no edges record" in output and "S-1" in output, f"gate must name edges: {output}")
    require(not receipt.exists(), "refused gate must write no receipt")

    broken = {"cases": [{"name": "empty input", "success_test": "test_empty_ok", "failure_test": ""}]}
    code, output = record_build(repo, plan, "S-1", "edges", broken)
    require(code != 0 and "empty input lacks its failure_test" in output, f"edge without failure test: {output}")
    code, output = record_build(repo, plan, "S-1", "edges", EDGES)
    require(code == 0 and "recorded_build=S-1:edges" in output, f"edges must record: {output}")
    code, output = record_build(repo, plan, "S-1", "green", {"command": ["pytest"], "exit": 1})
    require(code != 0 and "exit 0" in output, f"red green record must refuse: {output}")
    code, output = record_build(repo, plan, "S-1", "green", GREEN)
    require(code == 0, f"green must record: {output}")
    code, output = record_build(repo, plan, "S-1", "review", review("0" * 64, OPEN_FINDING))
    require(code != 0 and "no packet" in output, f"review without a packet must refuse: {output}")
    code, parsed = packet(repo, plan)
    require(code == 0 and parsed.get("packet_round") == "1", f"packet must build: {parsed}")
    packet_text = (repo / "features" / SLUG / "receipts" / "S-1-review-1.txt").read_text(encoding="utf-8")
    for needle in ("## Acceptance examples", "## Edge list", "empty input", "## Diff", "```diff"):
        require(needle in packet_text, f"packet must carry {needle}")
    require("## Risk" not in packet_text, "packet must not carry sections outside the reviewer contract")
    code, output = record_build(repo, plan, "S-1", "review", review("0" * 64, OPEN_FINDING))
    require(code != 0 and "packet_sha256 does not match" in output, f"wrong packet hash must refuse: {output}")
    code, output = record_build(repo, plan, "S-1", "review", review(parsed["packet_sha256"], OPEN_FINDING))
    require(code == 0, f"open review must record: {output}")
    code, output = record_build(
        repo, plan, "S-1", "verify", verify_payload(repo, plan, outside_calls=["real.example.com"])
    )
    require(code != 0 and "real.example.com" in output, f"real outside call must refuse naming host: {output}")
    quiet = evidence(
        repo,
        "quiet.log",
        b"API.example.test:8443 GET /v1 -> fake 200\n127.0.0.1 - - [04/Sep/2026] GET /\nv1.2.3 fake started\n",
    )
    code, output = record_build(
        repo,
        plan,
        "S-1",
        "verify",
        verify_payload(repo, plan, fakes=[{"host": "api.example.test", "log": quiet["path"]}]),
    )
    require(code == 0, f"case, port, loopback, and version tokens are not real hosts: {output}")
    leaky = evidence(
        repo, "leaky.log", b"api.example.test GET /v1/items -> fake 200\nreal.example.com:443 GET /x -> 200\n"
    )
    code, output = record_build(
        repo,
        plan,
        "S-1",
        "verify",
        verify_payload(repo, plan, fakes=[{"host": "api.example.test", "log": leaky["path"]}]),
    )
    require(
        code != 0 and "real.example.com" in output and "leaky.log" in output,
        f"host seen only in the fake log must refuse naming host and log: {output}",
    )
    code, output = record_build(repo, plan, "S-1", "verify", verify_payload(repo, plan, edge_cases=["unknown case"]))
    require(code != 0 and "unknown case" in output, f"unknown edge case must refuse: {output}")
    code, output = record_build(repo, plan, "S-1", "verify", verify_payload(repo, plan, packet_sha256="0" * 64))
    require(code != 0 and "packet_sha256 does not match" in output, f"wrong verify packet must refuse: {output}")
    missing_log = [{"host": "api.example.test", "log": "features/lean-loop/receipts/absent.log"}]
    code, output = record_build(repo, plan, "S-1", "verify", verify_payload(repo, plan, fakes=missing_log))
    require(code != 0 and "fake log is missing" in output, f"missing fake log must refuse: {output}")
    screenshot = [evidence(repo, "before.png", VALID_PNG)]
    code, output = record_build(repo, plan, "S-1", "verify", verify_payload(repo, plan, before=screenshot))
    require(code != 0 and "logic evidence must be" in output, f"logic mode with a screenshot must refuse: {output}")
    code, output = record_build(repo, plan, "S-1", "verify", verify_payload(repo, plan, mode="ui"))
    require(code != 0 and "ui evidence must be a screenshot" in output, f"ui mode with JSON must refuse: {output}")
    broken_image = [evidence(repo, "broken.png", b"not a png")]
    code, output = record_build(
        repo, plan, "S-1", "verify", verify_payload(repo, plan, mode="ui", before=broken_image, after=broken_image)
    )
    require(code != 0 and "not a decodable image" in output, f"undecodable screenshot must refuse: {output}")
    code, output = record_build(
        repo, plan, "S-1", "verify", verify_payload(repo, plan, mode="ui", before=screenshot, after=screenshot)
    )
    require(code == 0, f"ui verify with real screenshots must record: {output}")
    packet_text = (repo / "features" / SLUG / "receipts" / "S-1-verify.txt").read_text(encoding="utf-8")
    for needle in (
        "## Scope",
        "## Acceptance examples",
        "## Edge list",
        "empty input",
        "## Rules",
        "real outside call",
    ):
        require(needle in packet_text, f"verifier packet must carry {needle}")
    code, output = record_build(repo, plan, "S-1", "verify", verify_payload(repo, plan))
    require(code == 0, f"verify must record: {output}")
    code, output = gate(repo, plan, "--slice", "S-1")
    require(code != 0 and "open finding: R-1" in output, f"open finding must block the gate: {output}")
    code, output = run(STATE_SCRIPT, "inspect", "--repo", str(repo), "--plan", str(plan))
    shown = values(output)
    require(shown.get("build_steps") == "S-1:4/4", f"inspect must count records: {output}")
    require("R-1" in shown.get("build_steps_open_finding", ""), f"inspect must print the open finding: {output}")
    require("R-1" in shown.get("next_action", ""), f"inspect must make the open finding the next action: {output}")
    code, output = record_build(repo, plan, "S-1", "review", review(parsed["packet_sha256"]))
    require(code == 0, f"clean review must record: {output}")
    code, output = gate(repo, plan, "--slice", "S-1")
    require(code == 0 and receipt.is_file(), f"complete records must pass the gate: {output}")
    fourth = {"rounds": [{"reviewer": "x", "packet_sha256": parsed["packet_sha256"], "findings": []}] * 4}
    code, output = record_build(repo, plan, "S-1", "review", fourth)
    require(code != 0 and "at most 3 rounds" in output, f"fourth round must refuse: {output}")

    (repo / "owner.py").write_text("print('owner v3')\n", encoding="utf-8")
    code, output = gate(repo, plan, "--slice", "S-1")
    require(code != 0 and "stale" in output and "edges" in output, f"tree change must stale records: {output}")
    fixture.record_research(repo, plan)
    (repo / "notes.txt").write_text("second review round\n", encoding="utf-8")
    first = parsed["packet_sha256"]
    code, parsed = packet(repo, plan)
    require(code == 0 and parsed.get("packet_round") == "2", f"second packet must be round 2: {parsed}")
    two_rounds = {"rounds": [review_round(first), review_round(parsed["packet_sha256"])]}
    for step, payload in (("edges", EDGES), ("green", GREEN), ("review", two_rounds)):
        code, output = record_build(repo, plan, "S-1", step, payload)
        require(code == 0, f"{step} must re-record: {output}")
    code, output = record_build(repo, plan, "S-1", "verify", verify_payload(repo, plan))
    require(code == 0, f"verify must re-record: {output}")
    code, output = gate(repo, plan, "--slice", "S-1")
    require(code == 0, f"fresh records must pass the gate: {output}")
    return repo, plan


def check_full_gate(repo: Path, plan: Path) -> None:
    code, output = checkpoint(repo, plan, "completed_slices=S-1", "active_slice=none")
    require(code == 0, f"slice must complete: {output}")
    code, output = gate(repo, plan, "--full")
    require(code != 0 and "full gate has no verify record" in output, f"full gate must name verify: {output}")
    code, output = run(STATE_SCRIPT, "inspect", "--repo", str(repo), "--plan", str(plan))
    shown = values(output)
    require(shown.get("build_steps") == "full:0/1", f"full scope counts only the verify record: {output}")
    require(shown.get("build_steps_missing") == "verify", f"full scope misses only verify: {output}")
    require(
        "final pre-ship gate" in shown.get("handoff_prompt", ""),
        f"no remaining slice means the pre-ship gate: {output}",
    )
    code, output = record_build(repo, plan, "full", "edges", EDGES)
    require(code != 0 and "only the verify record" in output, f"full accepts verify only: {output}")
    code, output = record_build(repo, plan, "full", "verify", verify_payload(repo, plan, "full", edge_cases=[]))
    require(code == 0, f"full verify must record: {output}")
    code, values_out = packet(repo, plan, "full")
    require(code == 0, f"full review packet must build: {values_out}")
    full_packet_path = plan.parent / "receipts" / "full-review-1.txt"
    packet_body = full_packet_path.read_text(encoding="utf-8")
    require("whole feature" in packet_body, f"full review packet must scope to the whole feature: {packet_body}")
    require(
        "every slice edge list applies" in packet_body,
        f"full review packet must not require a full edges record: {packet_body}",
    )
    code, output = gate(repo, plan, "--full")
    require(code == 0, f"full gate must pass with records: {output}")
    code, output = checkpoint(repo, plan, "lifecycle_status=green")
    require(code != 0 and "walkthrough=yes|no" in output, f"green must ask the closing question: {output}")
    code, output = checkpoint(repo, plan, "lifecycle_status=green", "walkthrough=yes")
    require(code != 0 and "requires a video" in output, f"walkthrough yes needs a video: {output}")
    code, output = checkpoint(repo, plan, "walkthrough=maybe")
    require(code != 0 and "pending, yes, or no" in output, f"walkthrough value must be checked: {output}")
    report = repo / "features" / SLUG / "BUILD.md"
    require(not report.exists(), "BUILD.md must wait for green")
    after = [evidence(repo, "full-after.json"), video_evidence(repo)]
    payload = verify_payload(repo, plan, "full", edge_cases=[], after=after)
    code, output = record_build(repo, plan, "full", "verify", payload)
    require(code == 0, f"full verify with a video must record: {output}")
    code, output = gate(repo, plan, "--full")
    require(code == 0, f"full gate must pass again on the video tree: {output}")
    code, output = checkpoint(repo, plan, "lifecycle_status=green", "walkthrough=yes")
    require(code == 0, f"green checkpoint with a video must pass: {output}")
    body = report.read_text(encoding="utf-8")
    require(
        "## S-1" in body and "- edge cases = " in body and "round 1" in body, f"BUILD.md must list S-1 records: {body}"
    )
    require("walkthrough.mp4" in body, f"BUILD.md must list the walkthrough video: {body}")
    code, output = run(STATE_SCRIPT, "inspect", "--repo", str(repo), "--plan", str(plan))
    rows = values(output)
    require(
        rows.get("handoff") == "ship" and rows.get("walkthrough") == "yes", f"green must hand off to ship: {output}"
    )
    require("BUILD.md" in rows.get("handoff_prompt", ""), f"ship prompt must name the report: {output}")


def check_unwired_repo(base: Path) -> None:
    repo, plan = fixture.make_repo(base, "unwired")
    manifest = json.loads((repo / "hard-eng.gates.json").read_text(encoding="utf-8"))
    del manifest["enforcement"]
    (repo / "hard-eng.gates.json").write_text(json.dumps(manifest), encoding="utf-8")
    git(repo, "commit", "-q", "-am", "unwired")
    fixture.record_research(repo, plan)
    for step, payload in fixture.GOOD_PAYLOADS.items():
        record_step(repo, plan, step, payload)
    code, output = run(STATE_SCRIPT, "inspect", "--repo", str(repo), "--plan", str(plan))
    require(code == 0 and "build_steps=" not in output, f"unwired repo prints no build steps: {output}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="build-steps-regression-") as directory:
        base = Path(directory).resolve()
        repo, plan = check_slice_records(base)
        check_full_gate(repo, plan)
        check_unwired_repo(base)
    print("build-steps regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
