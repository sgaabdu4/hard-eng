#!/usr/bin/env python3
from pathlib import Path
import sys


REQUIRED = {
    "AGENTS.md": (
        "Explicit `fix all|everything|done/no regressions` scope = closure ledger",
        "`pre-existing` = provenance, never exclusion",
        "Workflow topology change = inventory last-green required stages",
        "Proof ladder = local/static + current primary contract",
        "Bug-fix implementation admission = preserved red-capable reproduction",
        "observable violation still red + accepted behavior still needed",
        "solution ladder = remove → reuse/repair existing owner",
        "External/native/paid failure = stop actor",
        "approach fingerprint (mechanism + dependency/tool + mode/target)",
        "same approach/variant forbidden",
        "any further external/native/paid attempt requires fresh user approval",
        "dependency/control/workflow existence ≠ necessity",
        "new security control = concrete asset + plausible threat + impact/requirement",
        "speculative hardening = YAGNI",
        "User-direction ledger = explicit outcome",
        "Collection scope = enumerate candidates",
        "Explicit terminal outcome = persistent completion contract",
        "Execution graph = dependency DAG",
        "Efficiency target = smallest correct maintainable outcome",
        "minimum concepts + files + steps + tokens/context + wall time + paid compute",
        "product-performance claim requires measurement",
        "reuse exact-tree proof/artifact",
        "duplicate equivalent setup/build/gate forbidden",
        "Alignment latency = one dependency frontier per turn",
        "`done|no regressions` claim = closure ledger empty",
    ),
    "skills/question-me/SKILL.md": (
        "Question cadence = one dependency frontier per turn",
        "batch every mutually independent material decision",
    ),
    "skills/research/SKILL.md": (
        "User-supplied source/claim/checklist = minimum coverage ledger",
        "External/runtime/platform-dependent solution selection or implementation",
        "External/runtime/dependency remedy = current primary contract + bounded public analogous-incident/remedy search before edit",
        "peer workaround = discovery, never authority",
        "First paid/native/external attempt = current primary-source receipt",
        "Contract-surprise failure = pause retry",
        "compatible parser/compiler/runner probe proves local semantics",
    ),
    "skills/diagnosing-bugs/SKILL.md": (
        "Reporter failures + constraints + examples + rejected remedies = immutable diagnosis ledger",
        "Problem admission = observable violation still reproduces",
        "Bug-fix implementation admission = preserved red-capable reproduction",
        "Solution admission = [fix.md](references/fix.md) ladder `PASS` before edit",
        "dependency/native packaging requires unique needed behavior",
        "External/runtime/platform assumption → `research`",
    ),
    "skills/diagnosing-bugs/references/fix.md": (
        "Solution ladder = remove → reuse/repair existing owner",
        "stop at first complete rung",
        "Record ladder receipt = considered rungs + selected rung",
    ),
    "skills/repeated-failure-learning/SKILL.md": (
        "Failed candidate + original violation remains",
        "same theory/variant mutation, retry, push, or publish = forbidden",
        "Comparable candidate fails twice → no third candidate",
    ),
    "skills/test-quality/SKILL.md": (
        "Interpreter/compiler/runner behavior seam = actual compatible tool execution",
    ),
    "skills/deterministic-checks/SKILL.md": (
        "| First paid/native/external attempt or retry | [Retry readiness](references/retry-readiness.md) |",
        "Gate efficiency = one execution per exact tree + actor + required seam",
        "rerun only after tree/environment/mechanism change or invalid receipt",
        "duplicate equivalent setup/build/gate = `FAIL`",
        "Compatible real-tool proof = interpreter/compiler/runner behavior",
        "Paid/native retry = [Retry readiness](references/retry-readiness.md) PASS first",
    ),
    "skills/deterministic-checks/references/retry-readiness.md": (
        "Run cheapest compatible real-tool parse/compile/execute sentinel",
        "Parallelize independent cheap checks",
        "Failure ends actor + retry approval",
        "approach fingerprint = mechanism + dependency/tool + mode/target",
        "Further paid/native/external attempt = fresh explicit user approval",
        "continuity or prior approval cannot substitute",
        "Static/grep/substring/AST intent check ≠ interpreter/compiler/runner semantic proof",
    ),
    "skills/he-learn/SKILL.md": (
        "Mechanically detectable prevention = executable rule/tool/fixture",
        "Prevention placement = before the expensive/failure boundary",
    ),
    "skills/he-build/SKILL.md": (
        "Working instruction ledger = accepted brief",
        "Before each mutation/resume = reconcile ledger",
        "Every instruction-ledger item = proven",
    ),
    "skills/he-ship/SKILL.md": (
        "Explicit terminal delivery outcome persists across recoverable build/CI failures",
        "one failed attempt never narrows the goal",
    ),
    "skills/he-ship/references/workflow.md": (
        "New deterministic failure/root → new `diagnosing-bugs` + `he-build` loop",
        "Explicit terminal artifact goal remains open",
    ),
    "skills/security-review/references/broad.md": (
        "Distributable binary/container/archive → preflight source defaults",
        "generated/extracted artifact",
    ),
    "skills/security-review/SKILL.md": (
        "Control admission = concrete asset + plausible threat actor/path",
        "simplest sufficient maintainable control",
        "preference/speculative hardening stays out of required scope",
        "Risk response = eliminate / mitigate / transfer / accept",
    ),
}


def validate(root: Path) -> list[str]:
    failures: list[str] = []
    for relative, anchors in REQUIRED.items():
        path = root / relative
        if not path.is_file():
            failures.append(f"missing {relative}")
            continue
        text = path.read_text()
        for anchor in anchors:
            if anchor not in text:
                failures.append(f"{relative} missing: {anchor}")
    return failures


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    failures = validate(root)
    if failures:
        for failure in failures:
            print(f"operating-contracts: FAIL: {failure}", file=sys.stderr)
        return 1
    print("operating-contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
