#!/usr/bin/env python3
"""Regression: uncited vendor tools block validate/approve in planning and manifest changes at the slice gate."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import external_claims
import plan_steps_regression as fixture
from plan_steps_regression import EVIDENCE_SCRIPT, GOOD_PAYLOADS, STATE_SCRIPT, git, record_step, require, run, values

TOOL_SOURCE = ("https://docs.fallow.tools/cli/audit", "3.22.0")
CLONE_SOURCE = ("https://github.com/kucherenko/jscpd", "5.1.1")


def make_planning_repo(base: Path, name: str) -> tuple[Path, Path]:
    repo, plan = fixture.make_repo(base, name)
    text = plan.read_text(encoding="utf-8")
    old = "- Existing policy remains canonical."
    require(old in text, "fixture brief must carry the decisions row")
    plan.write_text(text.replace(old, old + "\n- Gate = `fallow audit` on changed files only."), encoding="utf-8")
    git(repo, "commit", "-q", "-am", "name a vendor tool")
    settled = json.loads(json.dumps(GOOD_PAYLOADS["decisions"]))
    settled["decisions"][1].update(status="settled", settled_by="user reply 2026-09-02")
    for step, payload in (
        ("code-study", GOOD_PAYLOADS["code-study"]),
        ("edge-scan", GOOD_PAYLOADS["edge-scan"]),
        ("decisions", settled),
        ("slices", GOOD_PAYLOADS["slices"]),
        ("closing", GOOD_PAYLOADS["closing"]),
    ):
        code, output = record_step(repo, plan, step, payload)
        require(code == 0, f"{step} must record: {output}")
    return repo, plan


def record_external(repo: Path, plan: Path, *sources: tuple[str, str]) -> None:
    arguments = ["record-research", "--repo", str(repo), "--plan", str(plan), "--scope", "external"]
    arguments += ["--question", "Which vendor tools?", "--decision", "Use them.", "--fresh-until", "2099-12-31"]
    arguments += ["--verified", "docs read", "--unknown", "none"]
    for url, version in sources:
        arguments += ["--source", url, "--source-version", version]
    code, output = run(EVIDENCE_SCRIPT, *arguments)
    require(code == 0, f"external research must record: {output}")


def check_planning_claims(base: Path) -> None:
    repo, plan = make_planning_repo(base, "claims")
    fixture.record_research(repo, plan)
    code, output = run(STATE_SCRIPT, "validate", "--repo", str(repo), "--plan", str(plan))
    require(code != 0 and "`fallow`" in output and "Material decisions" in output, f"local-only research: {output}")
    code, output = fixture.approve(repo, plan)
    require(code != 0 and "`fallow`" in output, f"approve must name the uncited tool: {output}")
    (repo / "features" / fixture.SLUG / "receipts" / "note.txt").write_text(
        "fallow 3.22.0 remembered\n", encoding="utf-8"
    )
    code, output = fixture.approve(repo, plan)
    require(code != 0 and "`fallow`" in output, f"a memory note never counts as a source: {output}")
    (repo / "features" / fixture.SLUG / "receipts" / "note.txt").unlink()
    record_external(repo, plan, ("https://playwright.dev/docs/api/class-page", "1.0"))
    require("gh" not in external_claims.cited_tools(repo, plan), "a url merely containing gh letters never cites gh")
    record_external(repo, plan, TOOL_SOURCE)
    code, output = run(STATE_SCRIPT, "validate", "--repo", str(repo), "--plan", str(plan))
    require(code == 0 and values(output).get("ready_for_approval") == "yes", f"cited tool must validate: {output}")
    code, output = fixture.approve(repo, plan)
    require(code == 0, f"cited tool must approve: {output}")


def check_manifest_claims(base: Path) -> None:
    repo, plan = make_planning_repo(base, "manifest")
    record_external(repo, plan, TOOL_SOURCE)
    code, output = fixture.approve(repo, plan)
    require(code == 0, f"approve: {output}")
    manifest = json.loads((repo / "hard-eng.gates.json").read_text(encoding="utf-8"))
    manifest["families"]["clones"] = ["node_modules/.bin/jscpd", "--fail-on-new-clones", "."]
    (repo / "hard-eng.gates.json").write_text(json.dumps(manifest), encoding="utf-8")
    error = external_claims.manifest_claim_error(repo, plan)
    require(error is not None and "`jscpd`" in error, f"new manifest tool must be refused: {error}")
    gate = SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts" / "slice_gate.py"
    code, output = run(
        gate,
        "run",
        "--repo",
        str(repo),
        "--plan",
        str(plan),
        "--slice",
        "S-1",
        "--timeout",
        "60",
        "--behavior",
        "one behavior",
        "--check",
        "targeted",
        "--e2e",
        "not-applicable:cli",
        "--security",
        "not-applicable:cli",
        "--review",
        "none",
    )
    require(code != 0 and "`jscpd`" in output, f"slice gate must refuse the uncited manifest tool: {output}")
    record_external(repo, plan, TOOL_SOURCE, CLONE_SOURCE)
    require(external_claims.manifest_claim_error(repo, plan) is None, "cited manifest tool must pass")
    git(repo, "commit", "-q", "-am", "manifest with jscpd")
    manifest["families"]["python-lint"] = ["ruff", "check", "."]
    (repo / "hard-eng.gates.json").write_text(json.dumps(manifest), encoding="utf-8")
    error = external_claims.manifest_claim_error(repo, plan)
    require(error is not None and "`ruff`" in error, f"only newly introduced tools are checked: {error}")


def check_unwired_repo(base: Path) -> None:
    repo, plan = fixture.make_repo(base, "plain")
    manifest = json.loads((repo / "hard-eng.gates.json").read_text(encoding="utf-8"))
    del manifest["enforcement"]
    (repo / "hard-eng.gates.json").write_text(json.dumps(manifest), encoding="utf-8")
    require(external_claims.claim_error(repo, plan) is None, "unwired repository is never blocked")
    require(external_claims.manifest_claim_error(repo, plan) is None, "unwired manifest is never blocked")


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory).resolve()
        check_planning_claims(base)
        check_manifest_claims(base)
        check_unwired_repo(base)
    print("external-claims regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
