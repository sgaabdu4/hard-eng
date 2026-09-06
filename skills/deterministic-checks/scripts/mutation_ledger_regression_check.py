#!/usr/bin/env python3
"""Regression proof: the mutation ledger scores each function once and gates only on the committed rows."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "skills/deterministic-checks/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from git_env import scrub_environ
from regression_fixture import checker, git
from script_runner import ScriptResult, run_script

scrub_environ(ceiling=tempfile.gettempdir())

LEDGER_SCRIPT = SCRIPTS / "mutation_ledger.py"
SOURCE = "pkg/owner.py"
FUNCTION = f"{SOURCE}::add"
METHOD = f"{SOURCE}::Box.size"
FUNCTION_PREFIX = "pkg.owner.x_add__mutmut_"
METHOD_PREFIX = "pkg.owner.xǁBoxǁsize__mutmut_"
ORIGINAL = "def add(a, b):\n    return a + b\n\n\nclass Box:\n    def size(self):\n        return 3\n"
REFORMATTED = "def add(a,   b):\n\n    return a+b\n\n\nclass Box:\n    def size(self):\n        return 3\n"
CHANGED = "def add(a, b):\n    return a + b + 0\n\n\nclass Box:\n    def size(self):\n        return 3\n"
FAKE_MUTMUT = """#!/usr/bin/env python3
import json, pathlib, sys
if sys.argv[1] == "--version":
    print("mutmut, version 9.9.9"); raise SystemExit(0)
patterns = sys.argv[2:]
meta = pathlib.Path("mutants/pkg/owner.py.meta")
meta.parent.mkdir(parents=True, exist_ok=True)
codes = {}
for pattern in patterns:
    prefix = pattern[: -len("*")]
    codes[prefix + "1"] = 1
    codes[prefix + "2"] = 0 if "x_add" in prefix else 1
meta.write_text(json.dumps({"exit_code_by_key": codes, "hash_by_function_name": {}}))
pathlib.Path("mutants/patterns.json").write_text(json.dumps(patterns))
"""


fail, require = checker("mutation-ledger-check")


LEDGER_ENV = ("MUTATION_LEDGER_BASE", "MUTATION_LEDGER_VISIBILITY", "MUTATION_LEDGER_GH")


def ledger(repo: Path, *args: str, env: dict[str, str] | None = None, cwd: Path | None = None) -> ScriptResult:
    inherited = {key: value for key, value in os.environ.items() if key not in LEDGER_ENV}
    return run_script(LEDGER_SCRIPT, args, cwd=cwd or repo, env={**inherited, **(env or {})})


def values(output: str) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            rows.setdefault(key, []).append(value)
    return rows


def write_meta(repo: Path, codes: dict[str, int | None]) -> None:
    meta = repo / "mutants" / f"{SOURCE}.meta"
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(json.dumps({"exit_code_by_key": codes, "hash_by_function_name": {}}), encoding="utf-8")


def make_repo(base: Path) -> Path:
    repo = base / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pyproject.toml").write_text(
        '[tool.mutmut]\nsource_paths = ["pkg"]\ndo_not_mutate = ["pkg/*_regression.py"]\n', encoding="utf-8"
    )
    (repo / SOURCE).write_text(ORIGINAL, encoding="utf-8")
    (repo / "pkg" / "owner_regression.py").write_text("def check():\n    return 1\n", encoding="utf-8")
    (repo / "tests" / "test_owner.py").write_text("def test_add():\n    assert True\n", encoding="utf-8")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "branch", "-q", "origin/main")
    git(repo, "checkout", "-q", "-b", "feature")
    return repo


def check_plan_and_scope(repo: Path) -> None:
    result = ledger(repo, "plan", "--repo", str(repo))
    rows = values(result.output)
    require(result.returncode == 0 and rows["count"] == ["2"], f"plan lists both unscored functions: {result.output}")
    require(FUNCTION in rows["function"] and METHOD in rows["function"], f"plan keys: {rows['function']}")
    require(f"{FUNCTION_PREFIX}*" in rows["pattern"] and f"{METHOD_PREFIX}*" in rows["pattern"], f"patterns: {rows}")
    require(not any("regression" in key or "tests/" in key for key in rows["function"]), "tests never enter scope")
    result = ledger(repo, "plan", "--repo", str(repo), "--changed-only")
    require(values(result.output)["count"] == ["0"], f"nothing changed against origin/main: {result.output}")


def check_check_before_rows(repo: Path) -> None:
    (repo / SOURCE).write_text(CHANGED, encoding="utf-8")
    result = ledger(repo, "check", "--repo", str(repo), "--visibility", "private")
    rows = values(result.output)
    require(result.returncode == 1 and rows["unscored"] == ["2"], f"private changed functions refuse: {result.output}")
    require(FUNCTION in result.output and "score these changed functions locally" in result.output, result.output)
    result = ledger(repo, "check", "--repo", str(repo), "--visibility", "public")
    require(result.returncode == 0 and "mutation-ledger: PASS" in result.output, f"public passes: {result.output}")
    require(values(result.output)["unscored"] == ["2"], f"public still reports unscored: {result.output}")
    result = ledger(repo, "check", "--repo", str(repo), env={"MUTATION_LEDGER_VISIBILITY": "private"})
    require(result.returncode == 1, f"visibility from the environment: {result.output}")
    result = ledger(repo, "check", "--repo", str(repo), "--visibility", "private", "--base", "no-such-ref")
    require(result.returncode == 1 and "not a commit" in result.output, f"bad base fails: {result.output}")
    result = ledger(
        repo, "check", "--repo", str(repo), "--visibility", "auto", env={"MUTATION_LEDGER_GH": str(repo / "no-gh")}
    )
    require(
        "visibility=private (gh could not start" in result.output, f"unknown visibility fails closed: {result.output}"
    )
    (repo / SOURCE).write_text(ORIGINAL, encoding="utf-8")


def check_record(repo: Path) -> None:
    write_meta(repo, {f"{FUNCTION_PREFIX}1": 1, f"{FUNCTION_PREFIX}2": None, f"{METHOD_PREFIX}1": 3})
    result = ledger(repo, "record", "--repo", str(repo), "--version", "3.7.0", "--today", "2026-09-01", cwd=repo.parent)
    rows = values(result.output)
    require(
        result.returncode == 0 and rows["recorded"] == [METHOD],
        f"results resolve against the repository: {result.output}",
    )
    require(rows["skipped"] == [FUNCTION], f"function with a pending mutant waits: {result.output}")
    write_meta(
        repo, {f"{FUNCTION_PREFIX}1": 1, f"{FUNCTION_PREFIX}2": 0, f"{FUNCTION_PREFIX}3": 5, f"{METHOD_PREFIX}1": 3}
    )
    verdicts = repo / "verdicts.json"
    verdicts.write_text(json.dumps({f"{FUNCTION_PREFIX}2": {"verdict": "equivalent", "reason": "same value"}}))
    result = ledger(
        repo, "record", "--repo", str(repo), "--version", "3.7.0", "--today", "2026-09-01", "--verdicts", str(verdicts)
    )
    require(result.returncode == 0 and values(result.output)["recorded"] == [FUNCTION], f"record: {result.output}")
    data = json.loads((repo / "mutation-ledger.json").read_text(encoding="utf-8"))
    row = data["functions"][FUNCTION]
    require(row["totals"] == {"killed": 1, "survived": 1, "no_coverage": 1, "timeout": 0, "skipped": 0}, str(row))
    by_name = {item["mutant"]: item for item in row["survivors"]}
    require(by_name[f"{FUNCTION_PREFIX}2"]["verdict"] == "equivalent", f"verdict file applied: {row}")
    uncovered = by_name[f"{FUNCTION_PREFIX}3"]
    require(
        uncovered["verdict"] == "needs-verdict" and uncovered["since"] == "2026-09-01", f"uncovered = survivor: {row}"
    )
    require(data["functions"][METHOD]["totals"]["killed"] == 1, "method row kept")
    result = ledger(repo, "plan", "--repo", str(repo))
    require(values(result.output)["count"] == ["0"], f"scored functions leave the plan: {result.output}")
    bad = repo / "bad.json"
    bad.write_text(json.dumps({f"{FUNCTION_PREFIX}2": {"verdict": "needs-verdict", "reason": "x"}}))
    result = ledger(repo, "record", "--repo", str(repo), "--version", "3.7.0", "--verdicts", str(bad))
    require(result.returncode == 1 and "fixed|equivalent|invalid|deferred" in result.output, result.output)


def check_stale_and_verdict(repo: Path) -> None:
    result = ledger(repo, "check", "--repo", str(repo), "--visibility", "private", "--today", "2026-09-08")
    require(result.returncode == 0 and values(result.output)["stale"] == ["0"], f"seven days is fresh: {result.output}")
    result = ledger(repo, "check", "--repo", str(repo), "--visibility", "public", "--today", "2026-09-09")
    require(result.returncode == 1 and "older than 7 days" in result.output, f"day eight is stale: {result.output}")
    require(f"{FUNCTION_PREFIX}3" in result.output, f"stale output names the mutant: {result.output}")
    result = ledger(
        repo,
        "verdict",
        "--repo",
        str(repo),
        "--function",
        FUNCTION,
        "--mutant",
        f"{FUNCTION_PREFIX}3",
        "--verdict",
        "deferred",
        "--reason",
        "covered by the next slice",
    )
    require(result.returncode == 0 and "verdict=deferred" in result.output, f"verdict records: {result.output}")
    result = ledger(repo, "check", "--repo", str(repo), "--visibility", "public", "--today", "2026-09-09")
    require(result.returncode == 0, f"a verdict clears the stale row: {result.output}")
    result = ledger(
        repo,
        "verdict",
        "--repo",
        str(repo),
        "--function",
        FUNCTION,
        "--mutant",
        "nope",
        "--verdict",
        "fixed",
        "--reason",
        "x",
    )
    require(result.returncode == 1 and "not a survivor" in result.output, result.output)


def check_hash_follows_meaning(repo: Path) -> None:
    (repo / SOURCE).write_text(REFORMATTED, encoding="utf-8")
    result = ledger(repo, "check", "--repo", str(repo), "--visibility", "private")
    rows = values(result.output)
    require(result.returncode == 0 and rows["changed_functions"] == ["2"] and rows["unscored"] == ["0"], result.output)
    (repo / SOURCE).write_text(CHANGED, encoding="utf-8")
    result = ledger(repo, "check", "--repo", str(repo), "--visibility", "private")
    rows = values(result.output)
    require(result.returncode == 1 and rows["unscored_function"] == [FUNCTION], f"only add changed: {result.output}")
    git(repo, "commit", "-q", "-am", "change add")
    result = ledger(repo, "check", "--repo", str(repo), "--visibility", "private")
    require(
        result.returncode == 1 and "unscored_function" in result.output,
        f"committed change still counts: {result.output}",
    )
    result = ledger(repo, "check", "--repo", str(repo), "--visibility", "private", "--base", "HEAD")
    require(result.returncode == 0 and values(result.output)["changed_functions"] == ["0"], result.output)


def check_run(repo: Path) -> None:
    fake = repo / "fake-mutmut.py"
    fake.write_text(FAKE_MUTMUT, encoding="utf-8")
    fake.chmod(0o755)
    (repo / "mutants" / "tests").mkdir(parents=True, exist_ok=True)
    result = ledger(
        repo,
        "run",
        "--repo",
        str(repo),
        "--changed-only",
        "--budget-minutes",
        "1",
        "--mutmut",
        str(fake),
        cwd=repo.parent,
    )
    rows = values(result.output)
    require(result.returncode == 0 and rows["planned"] == ["1"] and rows["recorded_count"] == ["1"], result.output)
    patterns = json.loads((repo / "mutants" / "patterns.json").read_text(encoding="utf-8"))
    require(patterns == [f"{FUNCTION_PREFIX}*"], f"one mutmut run over exactly the unscored patterns: {patterns}")
    require(not (repo / "mutants" / "tests").exists(), "stale test copy removed before the run")
    data = json.loads((repo / "mutation-ledger.json").read_text(encoding="utf-8"))
    row = data["functions"][FUNCTION]
    require(row["version"] == "9.9.9" and row["survivors"][0]["verdict"] == "needs-verdict", str(row))
    result = ledger(repo, "run", "--repo", str(repo), "--changed-only", "--budget-minutes", "1", "--mutmut", str(fake))
    require("nothing to score" in result.output, f"second run finds nothing: {result.output}")
    result = ledger(repo, "check", "--repo", str(repo), "--visibility", "private")
    require(
        result.returncode == 0 and "mutation-ledger: PASS" in result.output, f"private push now passes: {result.output}"
    )
    check_seed(repo, fake)


def seeded_run(repo: Path, fake: Path, ref: str) -> dict[str, list[str]]:
    args = (
        "run",
        "--repo",
        str(repo),
        "--changed-only",
        "--budget-minutes",
        "1",
        "--mutmut",
        str(fake),
        "--seed-ref",
        ref,
    )
    result = ledger(repo, *args)
    require(result.returncode == 0, f"seeded run failed: {result.output}")
    return values(result.output)


def check_seed(repo: Path, fake: Path) -> None:
    empty = '{"functions": {}, "schema_version": 1}\n'
    patterns = repo / "mutants" / "patterns.json"
    git(repo, "add", "mutation-ledger.json")
    git(repo, "commit", "-q", "-m", "scored")
    git(repo, "branch", "-q", "seed")
    (repo / "mutation-ledger.json").write_text(empty, encoding="utf-8")
    patterns.unlink()
    rows = seeded_run(repo, fake, "seed")
    require(rows["seeded"] == ["2"] and rows["planned"] == ["0"], f"branch rows fill every gap: {rows}")
    require(not patterns.exists(), "seeded functions are not scored again")
    (repo / SOURCE).write_text(CHANGED.replace("+ 0", "+ 1"), encoding="utf-8")
    (repo / "mutation-ledger.json").write_text(empty, encoding="utf-8")
    rows = seeded_run(repo, fake, "seed")
    require(rows["seeded"] == ["1"] and rows["planned"] == ["1"], f"a changed function is scored again: {rows}")
    require(
        json.loads(patterns.read_text(encoding="utf-8")) == [f"{FUNCTION_PREFIX}*"], "only the changed function runs"
    )
    rows = seeded_run(repo, fake, "nope")
    require(rows["seeded"] == ["0"] and rows["planned"] == ["0"], f"a missing ref seeds nothing: {rows}")
    check_shards(repo, fake)


def shard_run(repo: Path, fake: Path, shard: str) -> ScriptResult:
    return ledger(repo, "run", "--repo", str(repo), "--budget-minutes", "1", "--mutmut", str(fake), "--shard", shard)


def check_shards(repo: Path, fake: Path) -> None:
    empty = '{"functions": {}, "schema_version": 1}\n'
    ledger_file = repo / "mutation-ledger.json"
    kept: list[Path] = []
    for shard in ("0/2", "1/2"):
        ledger_file.write_text(empty, encoding="utf-8")
        result = shard_run(repo, fake, shard)
        rows = values(result.output)
        require(
            result.returncode == 0 and rows["planned"] == ["1"], f"shard {shard} scores one function: {result.output}"
        )
        patterns = json.loads((repo / "mutants" / "patterns.json").read_text(encoding="utf-8"))
        require(len(patterns) == 1, f"shard {shard} runs mutmut over its own function only: {patterns}")
        kept.append(repo / f"shard-{shard[0]}.json")
        kept[-1].write_text(ledger_file.read_text(encoding="utf-8"), encoding="utf-8")
    scored = {json.loads(path.read_text(encoding="utf-8"))["functions"].popitem()[0] for path in kept}
    require(scored == {FUNCTION, METHOD}, f"the shards split every unscored function between them: {scored}")
    result = shard_run(repo, fake, "2/2")
    require(result.returncode == 1 and "index below count" in result.output, f"bad shard refused: {result.output}")
    ledger_file.write_text(empty, encoding="utf-8")
    args = [item for path in kept for item in ("--from", str(path))]
    result = ledger(repo, "merge", "--repo", str(repo), *args)
    require(result.returncode == 0 and "merged=2" in result.output, f"merge unions the shard rows: {result.output}")
    data = json.loads(ledger_file.read_text(encoding="utf-8"))
    require(set(data["functions"]) == {FUNCTION, METHOD}, f"merged ledger holds both rows: {sorted(data['functions'])}")
    result = ledger(repo, "merge", "--repo", str(repo), *args)
    require("merged=0" in result.output, f"a second merge changes nothing: {result.output}")


def check_workflow() -> None:
    text = (ROOT / ".github/workflows/mutation-nightly.yml").read_text(encoding="utf-8")
    matrix = re.search(r"shard: \[([^\]]*)\]", text)
    divisor = re.search(r'--shard "\$\{\{ matrix\.shard \}\}/(\d+)"', text)
    if matrix is None or divisor is None:
        fail("the nightly workflow lists its shards as a matrix and divides by that size")
    count = len([item for item in matrix.group(1).split(",") if item.strip()])
    require(int(divisor.group(1)) == count, f"every shard divides by the matrix size {count}")
    for needle in (
        f"failed_shards == {count}",
        f"$FAILED_SHARDS of {count} shards failed",
        "fail-fast: false",
        "continue-on-error: true",
        "name: ledger-${{ matrix.shard }}",
        "pattern: ledger-*",
        "if: always() && needs.visibility.result == 'success'",
        "mutation_ledger.py merge --repo .",
        'git diff --quiet "origin/$default_branch" "origin/$LEDGER_BRANCH" -- mutation-ledger.json',
    ):
        require(needle in text, f"the nightly workflow keeps: {needle}")


def check_no_runner(base: Path) -> None:
    bare = base / "bare"
    bare.mkdir()
    git(bare, "init", "-q", "-b", "main")
    (bare / "README.md").write_text("x\n", encoding="utf-8")
    git(bare, "add", ".")
    git(bare, "commit", "-q", "-m", "base")
    result = ledger(bare, "check", "--repo", str(bare))
    require(result.returncode == 0 and "runners=none" in result.output, f"no runner configured: {result.output}")
    (bare / "mutation-ledger.json").write_text('{"schema_version": 1, "functions": {"a::b": {}}}', encoding="utf-8")
    result = ledger(bare, "check", "--repo", str(bare))
    require(
        result.returncode == 1 and "needs hash + survivors" in result.output, f"broken ledger fails: {result.output}"
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mutation-ledger-check-") as directory:
        base = Path(directory).resolve()
        repo = make_repo(base)
        check_plan_and_scope(repo)
        check_check_before_rows(repo)
        check_record(repo)
        check_stale_and_verdict(repo)
        check_hash_follows_meaning(repo)
        check_run(repo)
        check_no_runner(base)
    check_workflow()
    print("mutation-ledger regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
