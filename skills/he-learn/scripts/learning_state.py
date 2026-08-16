#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path
from typing import NoReturn


NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
STATUSES = {"open", "resolved", "deferred", "non-candidate"}
TRIGGERS = {
    "recurrence",
    "engineering-correction",
    "false-passing-check",
    "protected-boundary-gap",
    "repeated-manual-waste",
}
NON_CANDIDATE_TRIGGERS = {"personal-correction", "one-off-implementation"}
KINDS = {"deterministic", "skill", "none"}
RUNTIMES = {
    "codex": ("agents/he-learn/codex.toml", ".codex/agents/he-learn.toml"),
    "claude": ("agents/he-learn/claude.md", ".claude/agents/he-learn.md"),
    "copilot": ("agents/he-learn/copilot.agent.md", ".copilot/agents/he-learn.agent.md"),
}


class LearningError(ValueError):
    pass


def fail(message: str) -> NoReturn:
    raise LearningError(message)


def repository(value: str) -> Path:
    repo = Path(value).expanduser().resolve()
    if not (repo / ".git").exists():
        fail(f"not a Git repository: {repo}")
    return repo


def regular_root(value: str) -> Path:
    root = Path(value).expanduser().resolve()
    if not root.is_dir() or root.is_symlink():
        fail(f"Hard Eng root must be a regular directory: {root}")
    return root


def home_path(value: str) -> Path:
    home = Path(value).expanduser().resolve()
    if home.exists() and (not home.is_dir() or home.is_symlink()):
        fail(f"home must be a regular directory: {home}")
    return home


def text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{field} must be a non-empty string")
    return value.strip()


def summary(value: object, field: str) -> str:
    result = text(value, field)
    if "\n" in result or len(result) > 500:
        fail(f"{field} must be one line of at most 500 characters")
    return result


def relative_path(repo: Path, value: object, field: str, *, must_exist: bool) -> Path:
    raw = text(value, field)
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts or raw in {".", ""}:
        fail(f"{field} must be a repository-relative path")
    path = repo / candidate
    if must_exist and not path.exists():
        fail(f"{field} does not exist: {raw}")
    if path.exists():
        resolved = path.resolve()
        try:
            resolved.relative_to(repo)
        except ValueError:
            fail(f"{field} escapes the repository: {raw}")
    return path


def markdown_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        fail(f"missing YAML frontmatter: {path}")
    try:
        end = lines.index("---", 1)
    except ValueError:
        fail(f"unterminated YAML frontmatter: {path}")
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        if ":" not in line:
            fail(f"invalid YAML frontmatter line in {path}: {line}")
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip("'\"")
    return fields, "\n".join(lines[end + 1 :]).strip()


def validate_skill(skill: Path) -> None:
    if not skill.is_dir() or skill.is_symlink():
        fail(f"canonical skill must be a regular directory: {skill}")
    if not NAME.fullmatch(skill.name):
        fail(f"invalid skill directory name: {skill.name}")
    definition = skill / "SKILL.md"
    if not definition.is_file() or definition.is_symlink():
        fail(f"canonical skill must contain a regular SKILL.md: {skill}")
    fields, body = markdown_frontmatter(definition)
    if fields.get("name") != skill.name:
        fail(f"skill name must match its directory: {skill}")
    text(fields.get("description"), f"{definition}: description")
    if not body:
        fail(f"skill body must not be empty: {definition}")


def canonical_skills(repo: Path) -> list[Path]:
    root = repo / ".agents/skills"
    if not root.exists():
        return []
    if not root.is_dir() or root.is_symlink():
        fail(f"canonical skills root must be a regular directory: {root}")
    skills = sorted(path for path in root.iterdir() if not path.name.startswith("."))
    for skill in skills:
        validate_skill(skill)
    return skills


def load_record(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        fail(f"learning record must be a regular JSON file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        fail(f"invalid learning record {path}: {error}")
    if not isinstance(value, dict):
        fail(f"learning record must be a JSON object: {path}")
    return value


def validate_record(repo: Path, path: Path) -> None:
    value = load_record(path)
    if value.get("schema_version") != 1:
        fail(f"unsupported schema_version in {path}")
    learning_id = text(value.get("learning_id"), f"{path}: learning_id")
    if not NAME.fullmatch(learning_id) or path.name != f"{learning_id}.json":
        fail(f"learning_id must match the record filename: {path}")
    status = text(value.get("status"), f"{path}: status")
    if status not in STATUSES:
        fail(f"invalid status in {path}: {status}")
    trigger = text(value.get("trigger"), f"{path}: trigger")
    if trigger not in TRIGGERS:
        fail(f"invalid trigger in {path}: {trigger}")
    summary(value.get("failure"), f"{path}: failure")
    summary(value.get("root_cause"), f"{path}: root_cause")
    evidence = value.get("evidence")
    if not isinstance(evidence, list) or not evidence or any(
        not isinstance(item, str) or not item.strip() for item in evidence
    ):
        fail(f"evidence must be a non-empty string list in {path}")
    for item in evidence:
        summary(item, f"{path}: evidence")
    occurrences = value.get("occurrences")
    if not isinstance(occurrences, int) or isinstance(occurrences, bool) or occurrences < 1:
        fail(f"occurrences must be a positive integer in {path}")
    prevention = value.get("prevention")
    if not isinstance(prevention, dict):
        fail(f"prevention must be an object in {path}")
    kind = text(prevention.get("kind"), f"{path}: prevention.kind")
    if kind not in KINDS:
        fail(f"invalid prevention.kind in {path}: {kind}")
    resolved = status == "resolved"
    if status in {"open", "deferred"}:
        next_action = summary(value.get("next_action"), f"{path}: next_action")
        if next_action == "none":
            fail(f"{status} learning requires a real next_action in {path}")
    if status == "deferred":
        summary(value.get("deferred_owner"), f"{path}: deferred_owner")
    helper = value.get("helper")
    if status == "open":
        if not isinstance(helper, dict):
            fail(f"open learning requires one selected helper in {path}")
        if helper.get("name") != "he-learn" or helper.get("selections") != 1:
            fail(f"open learning requires exactly one he-learn helper selection in {path}")
        if helper.get("state") not in {"selected", "launched"}:
            fail(f"open learning helper must be selected or launched in {path}")
    elif helper is not None:
        if not isinstance(helper, dict):
            fail(f"helper must be an object in {path}")
        if helper.get("name") != "he-learn" or helper.get("selections") != 1:
            fail(f"learning may contain only one he-learn helper selection in {path}")
        if helper.get("state") not in {"selected", "launched"}:
            fail(f"learning helper has an invalid state in {path}")
    if status == "non-candidate":
        if kind != "none":
            fail(f"non-candidate learning must use prevention.kind=none in {path}")
        summary(value.get("disposition_reason"), f"{path}: disposition_reason")
    if resolved and kind == "none":
        fail(f"resolved learning requires deterministic prevention or a skill in {path}")
    if kind == "skill":
        errors: list[str] = []
        if occurrences < 2:
            errors.append("skill fallback requires at least two occurrences")
        deterministic_limit = prevention.get("deterministic_limit")
        if not isinstance(deterministic_limit, str) or not deterministic_limit.strip():
            errors.append("skill fallback requires deterministic_limit evidence")
        if errors:
            fail(f"{path}: " + "; ".join(errors))
    if kind != "none":
        owner = relative_path(
            repo,
            prevention.get("owner"),
            f"{path}: prevention.owner",
            must_exist=resolved,
        )
        if kind == "skill":
            expected = repo / ".agents/skills" / learning_id
            if owner != expected:
                fail(f"skill prevention owner must be .agents/skills/{learning_id} in {path}")
            if resolved:
                validate_skill(owner)
        if resolved:
            for field in ("violation_fixture", "valid_fixture", "proof"):
                relative_path(
                    repo,
                    prevention.get(field),
                    f"{path}: prevention.{field}",
                    must_exist=True,
                )
    if "source_kind" in value and value.get("source_kind") != "historical":
        fail(f"invalid source_kind in {path}")


def records(repo: Path) -> list[Path]:
    root = repo / ".agents/learning"
    if not root.exists():
        return []
    if not root.is_dir() or root.is_symlink():
        fail(f"learning root must be a regular directory: {root}")
    found = sorted(root.glob("*.json"))
    extra = sorted(
        path
        for path in root.iterdir()
        if not path.name.startswith(".") and path.suffix != ".json"
    )
    if extra:
        fail(f"learning root contains an unsupported entry: {extra[0]}")
    return found


def validate_records(repo: Path, *, closure: bool = False) -> int:
    found = records(repo)
    for record in found:
        validate_record(repo, record)
        if closure and load_record(record).get("status") == "open":
            fail(f"open learning must be resolved or assigned before closure: {record}")
    return len(found)


def open_records(repo: Path) -> list[Path]:
    validate_records(repo)
    return [
        path
        for path in records(repo)
        if load_record(path).get("status") == "open"
    ]


def start_learning(args: argparse.Namespace) -> tuple[str, Path | None]:
    repo = repository(args.repo)
    learning_id = summary(args.learning_id, "learning_id")
    if not NAME.fullmatch(learning_id):
        fail(f"invalid learning_id: {learning_id}")
    trigger = args.trigger
    if trigger in NON_CANDIDATE_TRIGGERS:
        return "NON_CANDIDATE", None
    occurrences = args.occurrences
    if occurrences < 1:
        fail("occurrences must be a positive integer")
    if trigger in {"recurrence", "repeated-manual-waste"} and occurrences < 2:
        fail(f"{trigger} requires at least two occurrences")
    evidence = [summary(item, "evidence") for item in args.evidence]
    record: dict[str, object] = {
        "schema_version": 1,
        "learning_id": learning_id,
        "status": "open",
        "trigger": trigger,
        "failure": summary(args.failure, "failure"),
        "evidence": evidence,
        "root_cause": summary(args.root_cause, "root_cause"),
        "occurrences": occurrences,
        "prevention": {"kind": "none"},
        "next_action": summary(args.next_action, "next_action"),
        "helper": {"name": "he-learn", "selections": 1, "state": "selected"},
    }
    if args.historical:
        record["source_kind"] = "historical"
    root = repo / ".agents/learning"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{learning_id}.json"
    try:
        with path.open("x", encoding="utf-8") as output:
            json.dump(record, output, indent=2, sort_keys=True)
            output.write("\n")
    except FileExistsError:
        existing = load_record(path)
        identity = (
            "schema_version",
            "learning_id",
            "trigger",
            "failure",
            "evidence",
            "root_cause",
            "occurrences",
            "source_kind",
        )
        if any(existing.get(field) != record.get(field) for field in identity):
            fail(f"learning record conflicts with existing evidence: {path}")
        validate_record(repo, path)
        return "EXISTS", path
    validate_record(repo, path)
    return "CREATED", path


def check_link(link: Path, target: Path, label: str) -> None:
    if not link.is_symlink():
        if link.exists():
            fail(f"{label} must be a symlink, not a copy: {link}")
        fail(f"{label} is missing: {link}")
    if link.resolve() != target.resolve():
        fail(f"{label} points to the wrong target: {link}")


def install_link(link: Path, target: Path, label: str) -> None:
    if link.is_symlink():
        check_link(link, target, label)
        return
    if link.exists():
        fail(f"{label} must be a symlink, not a copy: {link}")
    parent = link.parent
    if parent.exists() and (not parent.is_dir() or parent.is_symlink()):
        fail(f"{label} parent must be a regular directory: {parent}")
    parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(os.path.relpath(target, parent))


def install_repo(repo: Path) -> int:
    validate_records(repo)
    skills = canonical_skills(repo)
    for skill in skills:
        install_link(
            repo / ".claude/skills" / skill.name,
            skill,
            "Claude repository skill",
        )
    return len(skills)


def uninstall_repo(repo: Path) -> int:
    validate_records(repo)
    count = 0
    for skill in canonical_skills(repo):
        link = repo / ".claude/skills" / skill.name
        check_link(link, skill, "Claude repository skill")
        link.unlink()
        count += 1
    return count


def check_repo(repo: Path) -> tuple[int, int]:
    records = validate_records(repo)
    skills = canonical_skills(repo)
    for skill in skills:
        check_link(
            repo / ".claude/skills" / skill.name,
            skill,
            "Claude repository skill",
        )
        for shadow_root in (repo / ".codex/skills", repo / ".copilot/skills"):
            shadow = shadow_root / skill.name
            if shadow.exists() or shadow.is_symlink():
                fail(
                    "runtime shadow skill duplicates canonical "
                    f".agents/skills/{skill.name}: {shadow}"
                )
    return records, len(skills)


def validate_adapter_sources(root: Path) -> None:
    for runtime, (source_name, _) in RUNTIMES.items():
        source = root / source_name
        if not source.is_file() or source.is_symlink():
            fail(f"{runtime} adapter must be a regular repository file: {source}")
        content = source.read_text(encoding="utf-8")
        for repeated_policy in ("repeated-failure-learning", "deterministic prevention", ".agents/skills"):
            if repeated_policy in content:
                fail(f"{runtime} adapter repeats canonical learning policy: {source}")
        if runtime == "codex":
            try:
                value = tomllib.loads(content)
            except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
                fail(f"invalid Codex adapter {source}: {error}")
            for field in ("name", "description", "developer_instructions"):
                text(value.get(field), f"{source}: {field}")
            if value.get("sandbox_mode") != "workspace-write":
                fail(f"Codex learning adapter must use workspace-write: {source}")
        else:
            fields, body = markdown_frontmatter(source)
            if fields.get("name") != "he-learn":
                fail(f"{runtime} adapter name must be he-learn: {source}")
            text(fields.get("description"), f"{source}: description")
            if "he-learn" not in body or ".agents" not in body:
                fail(
                    f"{runtime} adapter must point to the canonical learning contract: {source}"
                )


def install_global(root: Path, home: Path) -> int:
    validate_adapter_sources(root)
    count = 0
    for runtime, (source_name, link_name) in RUNTIMES.items():
        install_link(
            home / link_name,
            root / source_name,
            f"{runtime} learning adapter",
        )
        count += 1
    return count


def check_global(root: Path, home: Path) -> int:
    validate_adapter_sources(root)
    for runtime, (source_name, link_name) in RUNTIMES.items():
        check_link(
            home / link_name,
            root / source_name,
            f"{runtime} learning adapter",
        )
    return len(RUNTIMES)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Validate repository-owned Hard Eng learning"
    )
    commands = value.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--repo", required=True)
    validate.add_argument("--closure", action="store_true")
    for name in ("list-open", "repo-install", "repo-uninstall", "repo-check"):
        command = commands.add_parser(name)
        command.add_argument("--repo", required=True)
    start = commands.add_parser("start")
    start.add_argument("--repo", required=True)
    start.add_argument("--learning-id", required=True)
    start.add_argument(
        "--trigger",
        required=True,
        choices=sorted(TRIGGERS | NON_CANDIDATE_TRIGGERS),
    )
    start.add_argument("--failure", required=True)
    start.add_argument("--evidence", required=True, action="append")
    start.add_argument("--root-cause", required=True)
    start.add_argument("--occurrences", required=True, type=int)
    start.add_argument("--next-action", required=True)
    start.add_argument("--historical", action="store_true")
    for name in ("global-install", "global-check"):
        command = commands.add_parser(name)
        command.add_argument("--root", required=True)
        command.add_argument("--home", required=True)
    return value


def main() -> None:
    args = parser().parse_args()
    if args.command == "validate":
        repo = repository(args.repo)
        print(
            f"learning-state: PASS records={validate_records(repo, closure=args.closure)} "
            f"repo={repo}"
        )
    elif args.command == "list-open":
        repo = repository(args.repo)
        for path in open_records(repo):
            print(path.relative_to(repo))
    elif args.command == "start":
        result, path = start_learning(args)
        helper = "he-learn" if result == "CREATED" else "none"
        location = path.relative_to(repository(args.repo)) if path else "none"
        print(f"learning-start: {result} record={location} helper={helper}")
    elif args.command == "repo-install":
        repo = repository(args.repo)
        print(f"learning-repo-install: PASS skills={install_repo(repo)} repo={repo}")
    elif args.command == "repo-uninstall":
        repo = repository(args.repo)
        print(
            f"learning-repo-uninstall: PASS skills={uninstall_repo(repo)} repo={repo}"
        )
    elif args.command == "repo-check":
        repo = repository(args.repo)
        records, skills = check_repo(repo)
        print(
            f"learning-repo-check: PASS records={records} skills={skills} repo={repo}"
        )
    elif args.command == "global-install":
        root, home = regular_root(args.root), home_path(args.home)
        print(
            f"learning-global-install: PASS adapters={install_global(root, home)} "
            f"home={home}"
        )
    else:
        root, home = regular_root(args.root), home_path(args.home)
        print(
            f"learning-global-check: PASS adapters={check_global(root, home)} "
            f"home={home}"
        )


if __name__ == "__main__":
    try:
        main()
    except LearningError as error:
        print(f"learning-state: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
