#!/usr/bin/env python3
"""Mutation ledger: every function is scored once, its survivors carry a verdict, and gates only read the file."""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import os
import re
import shutil
import sys
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import tomllib

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from bounded_run import run, run_captured
from git_env import git_env

LEDGER_FILE = "mutation-ledger.json"
SCHEMA_VERSION = 1
CLASS_SEPARATOR = "ǁ"
NEEDS_VERDICT = "needs-verdict"
VERDICTS = frozenset({NEEDS_VERDICT, "fixed", "equivalent", "invalid", "deferred"})
STALE_AFTER = timedelta(days=7)
BASE_ENV = "MUTATION_LEDGER_BASE"
VISIBILITY_ENV = "MUTATION_LEDGER_VISIBILITY"
GH_ENV = "MUTATION_LEDGER_GH"
DEFAULT_BASES = ("origin/main", "origin/develop")
KILLED = frozenset({1, 3, 37})
SURVIVED = frozenset({0})
NO_COVERAGE = frozenset({5, 33})
TIMEOUT = frozenset({36, 24, -24, 152, 255})
SKIPPED = frozenset({34})
TEST_FILE = re.compile(
    r"(^|/)(tests?|__tests__|spec)/|([-_]regression(_check)?|_test|\.test|\.spec|[-_]contract(-check)?|[-_]contracts?)\."
)
TOTAL_KEYS = ("killed", "survived", "no_coverage", "timeout", "skipped")


class LedgerError(ValueError):
    """The ledger, its inputs, or the repository state break the mutation contract."""


def _git(repo: Path, *args: str, timeout: float = 60) -> str:
    result = run_captured(["git", "-C", str(repo), *args], timeout, env=git_env())
    if result.returncode != 0:
        raise LedgerError(f"git {' '.join(args)} failed: {result.stderr.decode('utf-8', 'replace').strip()}")
    return result.stdout.decode("utf-8", "replace")


def _ref_exists(repo: Path, ref: str) -> bool:
    result = run_captured(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], 30, env=git_env()
    )
    return result.returncode == 0


def resolve_base(repo: Path, explicit: str | None) -> str:
    named = explicit or os.environ.get(BASE_ENV)
    if named:
        if not _ref_exists(repo, named):
            raise LedgerError(f"comparison base is not a commit: {named}")
        return _git(repo, "merge-base", "HEAD", named).strip()
    for candidate in ("@{upstream}", *DEFAULT_BASES):
        if _ref_exists(repo, candidate):
            return _git(repo, "merge-base", "HEAD", candidate).strip()
    raise LedgerError("no comparison base: pass --base, set MUTATION_LEDGER_BASE, or track origin/main|develop")


def changed_files(repo: Path, base: str) -> set[str]:
    listed = _git(repo, "diff", "--name-only", "--diff-filter=AMR", base).splitlines()
    return {line.strip() for line in listed if line.strip() and (repo / line.strip()).is_file()}


def ledger_path(repo: Path) -> Path:
    return repo / LEDGER_FILE


def load_ledger(repo: Path) -> dict:
    path = ledger_path(repo)
    if not path.is_file():
        return {"schema_version": SCHEMA_VERSION, "functions": {}}
    try:
        return parse_ledger(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise LedgerError(f"{LEDGER_FILE} is unreadable: {error}") from error


def parse_ledger(text: str) -> dict:
    try:
        data = json.loads(text)
    except ValueError as error:
        raise LedgerError(f"{LEDGER_FILE} is unreadable: {error}") from error
    functions = data.get("functions") if isinstance(data, dict) else None
    if data.get("schema_version") != SCHEMA_VERSION or not isinstance(functions, dict):
        raise LedgerError(f"{LEDGER_FILE} must carry schema_version {SCHEMA_VERSION} and a functions object")
    for key, row in functions.items():
        _validate_row(key, row)
    return data


def _validate_row(key: str, row: object) -> None:
    if not isinstance(row, dict) or not isinstance(row.get("hash"), str) or not isinstance(row.get("survivors"), list):
        raise LedgerError(f"{LEDGER_FILE} row {key} needs hash + survivors")
    for survivor in row["survivors"]:
        if not isinstance(survivor, dict) or survivor.get("verdict") not in VERDICTS:
            raise LedgerError(f"{LEDGER_FILE} row {key} has a survivor without a known verdict")
        if survivor["verdict"] == NEEDS_VERDICT and not isinstance(survivor.get("since"), str):
            raise LedgerError(f"{LEDGER_FILE} row {key} has a needs-verdict survivor without a since date")


def save_ledger(repo: Path, data: dict) -> None:
    data["functions"] = dict(sorted(data["functions"].items()))
    ledger_path(repo).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def mutmut_config(repo: Path) -> dict | None:
    pyproject = repo / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        config = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("tool", {}).get("mutmut")
    except (OSError, ValueError) as error:
        raise LedgerError(f"pyproject.toml is unreadable: {error}") from error
    return config if isinstance(config, dict) else None


def python_source_files(repo: Path, config: dict) -> list[str]:
    skip = [str(pattern) for pattern in config.get("do_not_mutate", [])]
    files: set[str] = set()
    for source_path in config.get("source_paths", []):
        directory = repo / str(source_path)
        for path in directory.rglob("*.py"):
            relative = path.relative_to(repo).as_posix()
            if TEST_FILE.search(relative) or any(fnmatch.fnmatch(relative, pattern) for pattern in skip):
                continue
            files.add(relative)
    return sorted(files)


def python_functions(repo: Path, relative: str) -> dict[str, str]:
    try:
        tree = ast.parse((repo / relative).read_text(encoding="utf-8"), filename=relative)
    except (OSError, SyntaxError, UnicodeError) as error:
        raise LedgerError(f"cannot parse {relative}: {error}") from error
    functions: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[f"{relative}::{node.name}"] = _node_hash(node)
        elif isinstance(node, ast.ClassDef):
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions[f"{relative}::{node.name}.{member.name}"] = _node_hash(member)
    return functions


def _node_hash(node: ast.AST) -> str:
    return "sha256:" + hashlib.sha256(ast.dump(node).encode("utf-8")).hexdigest()


def mutant_prefix(key: str) -> str:
    relative, qualname = key.split("::", 1)
    module = relative[: -len(".py")].replace("/", ".")
    if "." in qualname:
        class_name, method = qualname.split(".", 1)
        return f"{module}.x{CLASS_SEPARATOR}{class_name}{CLASS_SEPARATOR}{method}"
    return f"{module}.x_{qualname}"


def mutant_pattern(key: str) -> str:
    return f"{mutant_prefix(key)}__mutmut_*"


def scope_functions(repo: Path, config: dict, base: str | None) -> dict[str, str]:
    files = python_source_files(repo, config)
    if base is not None:
        changed = changed_files(repo, base)
        files = [relative for relative in files if relative in changed]
    functions: dict[str, str] = {}
    for relative in files:
        functions.update(python_functions(repo, relative))
    return functions


def unscored(ledger: dict, functions: dict[str, str]) -> dict[str, str]:
    rows = ledger["functions"]
    return {key: digest for key, digest in functions.items() if rows.get(key, {}).get("hash") != digest}


def seed_rows(repo: Path, ref: str, functions: dict[str, str]) -> int:
    try:
        branch = parse_ledger(_git(repo, "show", f"{ref}:{LEDGER_FILE}"))["functions"]
    except LedgerError:
        return 0
    ledger = load_ledger(repo)
    rows = ledger["functions"]
    copied = 0
    for key, digest in functions.items():
        row = branch.get(key)
        if row is None or row["hash"] != digest or rows.get(key, {}).get("hash") == digest:
            continue
        rows[key] = row
        copied += 1
    if copied:
        save_ledger(repo, ledger)
    return copied


def planned(repo: Path, base: str | None) -> dict[str, str]:
    config = mutmut_config(repo)
    if config is None:
        return {}
    return unscored(load_ledger(repo), scope_functions(repo, config, base))


def results_dir(repo: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo / path


def read_meta(results: Path, relative: str) -> dict[str, int | None]:
    path = results / f"{relative}.meta"
    if not path.is_file():
        return {}
    try:
        codes = json.loads(path.read_text(encoding="utf-8")).get("exit_code_by_key")
    except (OSError, ValueError) as error:
        raise LedgerError(f"mutmut results file is unreadable: {path}: {error}") from error
    return codes if isinstance(codes, dict) else {}


def score(codes: dict[str, int | None], key: str) -> tuple[dict[str, int], list[str]] | None:
    prefix = mutant_prefix(key)
    matching = {name: code for name, code in codes.items() if name.rsplit("__mutmut_", 1)[0] == prefix}
    if not matching:
        return None
    if any(code is None for code in matching.values()):
        return None
    totals: dict[str, int] = {key: 0 for key in TOTAL_KEYS}
    survivors: list[str] = []
    for name, code in sorted(matching.items()):
        assert code is not None
        if code in KILLED:
            totals["killed"] += 1
        elif code in TIMEOUT:
            totals["timeout"] += 1
        elif code in SKIPPED:
            totals["skipped"] += 1
        elif code in NO_COVERAGE:
            totals["no_coverage"] += 1
            survivors.append(name)
        elif code in SURVIVED:
            totals["survived"] += 1
            survivors.append(name)
        else:
            raise LedgerError(f"unknown mutmut exit code {code} for {name}")
    return totals, survivors


def load_verdicts(path: str | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise LedgerError(f"verdict file is unreadable: {error}") from error
    if not isinstance(data, dict):
        raise LedgerError("verdict file must map mutant name to {verdict, reason}")
    for mutant, entry in data.items():
        if not isinstance(entry, dict) or entry.get("verdict") not in VERDICTS - {NEEDS_VERDICT}:
            raise LedgerError(f"verdict for {mutant} must be one of fixed|equivalent|invalid|deferred")
        if not str(entry.get("reason", "")).strip():
            raise LedgerError(f"verdict for {mutant} needs a reason")
    return data


def record_rows(
    repo: Path, results: Path, version: str, targets: dict[str, str], verdicts: dict[str, dict[str, str]], today: date
) -> tuple[list[str], list[str]]:
    ledger = load_ledger(repo)
    recorded: list[str] = []
    skipped: list[str] = []
    metas: dict[str, dict[str, int | None]] = {}
    for key, digest in targets.items():
        relative = key.split("::", 1)[0]
        codes = metas.setdefault(relative, read_meta(results, relative))
        scored = score(codes, key)
        if scored is None:
            skipped.append(key)
            continue
        totals, survivors = scored
        ledger["functions"][key] = {
            "hash": digest,
            "runner": "mutmut",
            "version": version,
            "scored_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "totals": totals,
            "survivors": [_survivor_row(name, verdicts.get(name), today) for name in survivors],
        }
        recorded.append(key)
    if recorded:
        save_ledger(repo, ledger)
    return recorded, skipped


def _survivor_row(name: str, verdict: dict[str, str] | None, today: date) -> dict[str, str]:
    if verdict is None:
        return {"mutant": name, "verdict": NEEDS_VERDICT, "reason": "", "since": today.isoformat()}
    return {"mutant": name, "verdict": verdict["verdict"], "reason": verdict["reason"].strip()}


def stale_survivors(ledger: dict, today: date) -> list[str]:
    stale: list[str] = []
    for key, row in ledger["functions"].items():
        for survivor in row["survivors"]:
            if survivor["verdict"] != NEEDS_VERDICT:
                continue
            try:
                since = date.fromisoformat(survivor["since"])
            except ValueError as error:
                raise LedgerError(f"{LEDGER_FILE} row {key} has an invalid since date") from error
            if today - since > STALE_AFTER:
                stale.append(f"{key} {survivor['mutant']} (since {since.isoformat()})")
    return stale


def resolve_visibility(repo: Path, explicit: str | None) -> tuple[str, str]:
    choice = explicit or os.environ.get(VISIBILITY_ENV) or "auto"
    if choice in {"public", "private"}:
        return choice, "declared"
    if choice != "auto":
        raise LedgerError(f"visibility must be auto|public|private, not {choice}")
    gh = os.environ.get(GH_ENV) or shutil.which("gh")
    if gh is None:
        return "private", "gh unavailable; treating the repository as private"
    try:
        result = run_captured(
            [gh, "repo", "view", "--json", "isPrivate", "--jq", ".isPrivate"], 30, cwd=str(repo), env=git_env()
        )
    except OSError:
        return "private", "gh could not start; treating the repository as private"
    answer = result.stdout.decode("utf-8", "replace").strip()
    if result.returncode != 0 or answer not in {"true", "false"}:
        return "private", "gh could not read the repository; treating it as private"
    return ("private" if answer == "true" else "public"), "gh repo view"


def parse_today(value: str | None) -> date:
    if value is None:
        return datetime.now(timezone.utc).date()
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise LedgerError(f"--today must be YYYY-MM-DD, not {value}") from error


def command_plan(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    base = resolve_base(repo, args.base) if args.base is not None or args.changed_only else None
    targets = planned(repo, base)
    if base is not None:
        print(f"base={base}")
    for key in sorted(targets):
        print(f"function={key}")
        print(f"pattern={mutant_pattern(key)}")
    print(f"count={len(targets)}")
    return 0


def command_record(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    config = mutmut_config(repo)
    if config is None:
        raise LedgerError("pyproject.toml has no [tool.mutmut] table; nothing to record")
    base = resolve_base(repo, args.base) if args.base is not None or args.changed_only else None
    targets = unscored(load_ledger(repo), scope_functions(repo, config, base))
    if args.function:
        missing = sorted(set(args.function) - set(targets))
        if missing:
            raise LedgerError("not an unscored function in scope: " + ", ".join(missing))
        targets = {key: targets[key] for key in args.function}
    recorded, skipped = record_rows(
        repo,
        results_dir(repo, args.results),
        args.version,
        targets,
        load_verdicts(args.verdicts),
        parse_today(args.today),
    )
    for key in recorded:
        print(f"recorded={key}")
    for key in skipped:
        print(f"skipped={key}")
    print(f"recorded_count={len(recorded)}")
    print(f"skipped_count={len(skipped)}")
    return 0


def command_verdict(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    ledger = load_ledger(repo)
    row = ledger["functions"].get(args.function)
    if row is None:
        raise LedgerError(f"no ledger row for {args.function}")
    if not args.reason.strip():
        raise LedgerError("verdict needs a reason")
    for survivor in row["survivors"]:
        if survivor["mutant"] == args.mutant:
            survivor.clear()
            survivor.update({"mutant": args.mutant, "verdict": args.verdict, "reason": args.reason.strip()})
            save_ledger(repo, ledger)
            print(f"verdict={args.verdict}")
            return 0
    raise LedgerError(f"{args.mutant} is not a survivor of {args.function}")


def command_check(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    ledger = load_ledger(repo)
    today = parse_today(args.today)
    failures: list[str] = []
    stale = stale_survivors(ledger, today)
    failures.extend(f"needs-verdict older than {STALE_AFTER.days} days: {item}" for item in stale)
    print(f"rows={len(ledger['functions'])}")
    print(f"stale={len(stale)}")
    config = mutmut_config(repo)
    if config is None:
        print("runners=none")
    else:
        visibility, reason = resolve_visibility(repo, args.visibility)
        base = resolve_base(repo, args.base)
        functions = scope_functions(repo, config, base)
        missing = sorted(unscored(ledger, functions))
        print("runners=mutmut")
        print(f"visibility={visibility} ({reason})")
        print(f"base={base}")
        print(f"changed_functions={len(functions)}")
        print(f"unscored={len(missing)}")
        for key in missing:
            print(f"unscored_function={key}")
        if missing and visibility == "private":
            failures.append(
                "private repository: score these changed functions locally before push (mutation_ledger.py run): "
                + ", ".join(missing)
            )
    for failure in failures:
        print(f"mutation-ledger: FAIL {failure}")
    if failures:
        return 1
    print("mutation-ledger: PASS")
    return 0


def command_run(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    config = mutmut_config(repo)
    if config is None:
        raise LedgerError("pyproject.toml has no [tool.mutmut] table; wire the runner first (mutation.md)")
    base = resolve_base(repo, args.base) if args.base is not None or args.changed_only else None
    functions = scope_functions(repo, config, base)
    print(f"seeded={seed_rows(repo, args.seed_ref, functions) if args.seed_ref else 0}")
    targets = unscored(load_ledger(repo), functions)
    print(f"planned={len(targets)}")
    if not targets:
        print("mutation-ledger: nothing to score")
        return 0
    mutmut = args.mutmut or str(repo / ".venv-mutation" / "bin" / "mutmut")
    version = run_captured([mutmut, "--version"], 60, cwd=str(repo), env=git_env())
    if version.returncode != 0:
        raise LedgerError(f"{mutmut} --version failed: {version.stderr.decode('utf-8', 'replace').strip()}")
    version_text = version.stdout.decode("utf-8", "replace").strip().split()[-1]
    results = results_dir(repo, args.results)
    shutil.rmtree(results / "tests", ignore_errors=True)
    patterns = [mutant_pattern(key) for key in sorted(targets)]
    outcome = run([mutmut, "run", *patterns], args.budget_minutes * 60, 10, cwd=str(repo), env=git_env())
    print(f"mutmut_exit={outcome.returncode}")
    print(f"budget_exhausted={'no' if outcome.terminal else 'yes'}")
    recorded, skipped = record_rows(repo, results, version_text, targets, {}, parse_today(None))
    print(f"recorded_count={len(recorded)}")
    print(f"skipped_count={len(skipped)}")
    if not recorded and outcome.returncode != 0:
        print("mutation-ledger: FAIL mutmut recorded nothing")
        return 1
    print("mutation-ledger: recorded")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    def scoped(name: str) -> argparse.ArgumentParser:
        sub = commands.add_parser(name)
        sub.add_argument("--repo", required=True)
        sub.add_argument("--base", help="commit or ref; functions in files unchanged since it are out of scope")
        sub.add_argument("--changed-only", action="store_true", help="resolve the base from upstream or origin")
        return sub

    scoped("plan")
    record = scoped("record")
    record.add_argument("--results", default="mutants", help="mutmut results directory")
    record.add_argument("--version", required=True, help="mutmut version that produced the results")
    record.add_argument("--verdicts", help="JSON: mutant name -> {verdict, reason}")
    record.add_argument("--function", action="append", help="limit to these unscored functions")
    record.add_argument("--today")
    run_command = scoped("run")
    run_command.add_argument("--budget-minutes", type=int, required=True)
    run_command.add_argument("--mutmut", help="mutmut executable; default .venv-mutation/bin/mutmut")
    run_command.add_argument("--results", default="mutants")
    run_command.add_argument(
        "--seed-ref", help="ref whose mutation-ledger.json fills gaps for functions with the same hash"
    )
    verdict = commands.add_parser("verdict")
    verdict.add_argument("--repo", required=True)
    verdict.add_argument("--function", required=True)
    verdict.add_argument("--mutant", required=True)
    verdict.add_argument("--verdict", required=True, choices=sorted(VERDICTS - {NEEDS_VERDICT}))
    verdict.add_argument("--reason", required=True)
    check = commands.add_parser("check")
    check.add_argument("--repo", required=True)
    check.add_argument("--base")
    check.add_argument("--visibility", choices=("auto", "public", "private"))
    check.add_argument("--today")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    actions = {
        "plan": command_plan,
        "record": command_record,
        "verdict": command_verdict,
        "check": command_check,
        "run": command_run,
    }
    try:
        return actions[args.command](args)
    except LedgerError as error:
        print(f"mutation-ledger: FAIL {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
