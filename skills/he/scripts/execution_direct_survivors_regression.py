#!/usr/bin/env python3
"""Regression checks that kill the surviving mutants of execution_direct.py."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills/deterministic-checks/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from git_env_survivors_regression_check import make_checker
from regression_fixture import git as fixture_git

fail, require = make_checker("execution-direct-survivors")

import execution_direct as ed
from evidence_lib import (
    STOP_BEFORE,
    EvidenceError,
    action_digest,
    direct_receipt_path,
    protected_binding_digest,
    repository_context,
    text_digest,
    utc_now,
    utc_text,
)

DIGEST = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def make_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    repo = repo.resolve()
    fixture_git(repo, "init", "-q")
    (repo / "AGENTS.md").write_text("# rules\n", encoding="utf-8")
    (repo / "adir").mkdir()
    (repo / "adir" / "keep.txt").write_text("keep\n", encoding="utf-8")
    (repo / "skills" / "sample-skill").mkdir(parents=True)
    (repo / "skills" / "sample-skill" / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    fixture_git(repo, "add", "-A")
    fixture_git(repo, "commit", "-qm", "init")
    return repo


def expect_fail(message: str, func, *args, **kwargs) -> None:
    try:
        func(*args, **kwargs)
    except EvidenceError as error:
        require(str(error) == message, f"expected {message!r}, got {error!r}")
        return
    fail(f"expected failure {message!r} but none was raised")


def capture(func, *args, **kwargs) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        func(*args, **kwargs)
    return buffer.getvalue().rstrip("\n")


def sha_hex(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_validate_external_actions() -> None:
    valid_entry = {"tool_name": "mcp__x__y", "action_digest": DIGEST, "effect": "do the thing"}
    require(ed.validate_external_actions(None) == [], "None external actions must yield an empty list")
    expect_fail("direct-route external actions must be a list", ed.validate_external_actions, "not-a-list")
    expect_fail(
        "direct-route external actions require tool_name, action_digest, and effect",
        ed.validate_external_actions,
        [frozenset({"action_digest", "effect", "tool_name"})],
    )
    expect_fail(
        "direct-route external actions require tool_name, action_digest, and effect",
        ed.validate_external_actions,
        [{"tool_name": "x", "effect": "y"}],
    )
    expect_fail(
        "direct-route external action tool names must be canonical",
        ed.validate_external_actions,
        [{**valid_entry, "tool_name": ""}],
    )
    expect_fail(
        "direct-route external action tool names must be canonical",
        ed.validate_external_actions,
        [{**valid_entry, "tool_name": "MCP__X__Y"}],
    )
    expect_fail(
        "direct-route external action digest is invalid",
        ed.validate_external_actions,
        [{**valid_entry, "action_digest": "not-a-digest"}],
    )
    expect_fail(
        "direct-route external action effect must be readable text",
        ed.validate_external_actions,
        [{**valid_entry, "effect": " leading space"}],
    )
    expect_fail(
        "direct-route external action effect must be readable text",
        ed.validate_external_actions,
        [{**valid_entry, "effect": ""}],
    )
    expect_fail(
        "direct-route external action effect must be readable text",
        ed.validate_external_actions,
        [{**valid_entry, "effect": "a" * 501}],
    )
    expect_fail(
        "direct-route external action effect must be readable text",
        ed.validate_external_actions,
        [{**valid_entry, "effect": "bad\x07text"}],
    )
    expect_fail(
        "direct-route external action effect must be readable text",
        ed.validate_external_actions,
        [{**valid_entry, "effect": 123}],
    )
    long_effect_entry = {**valid_entry, "effect": "a" * 500}
    require(ed.validate_external_actions([long_effect_entry]) == [long_effect_entry], "a 500-char effect must pass")
    require(ed.validate_external_actions([valid_entry]) == [valid_entry], "a well-formed action must pass unchanged")
    expect_fail(
        "direct-route external action is duplicated",
        ed.validate_external_actions,
        [valid_entry, {**valid_entry, "effect": "different"}],
    )
    other_entry = {"tool_name": "mcp__other__tool", "action_digest": DIGEST_B, "effect": "other effect"}
    require(
        ed.validate_external_actions([valid_entry, other_entry]) == [valid_entry, other_entry],
        "two distinct actions must both be preserved and not treated as duplicates",
    )


def test_parse_external_actions() -> None:
    valid_raw = json.dumps({"tool_name": "MCP__X", "action_digest": DIGEST, "effect": "do it"})
    parsed = ed.parse_external_actions([valid_raw])
    require(
        parsed == [{"tool_name": "mcp__x", "action_digest": DIGEST, "effect": "do it"}],
        f"tool_name must be casefolded and the structure preserved, got {parsed!r}",
    )
    expect_fail("external-action must be a JSON object", ed.parse_external_actions, ["not json"])
    expect_fail(
        "direct-route external actions require tool_name, action_digest, and effect",
        ed.parse_external_actions,
        ["[1, 2, 3]"],
    )
    two = [valid_raw, json.dumps({"tool_name": "mcp__other", "action_digest": DIGEST_B, "effect": "other"})]
    require(len(ed.parse_external_actions(two)) == 2, "two distinct entries must both survive parsing")


def protected_args(**overrides) -> argparse.Namespace:
    base = {
        "repo": "unused",
        "action_digest": DIGEST,
        "target": "repo/file.py",
        "effect": "Delete the obsolete file.",
        "tool_name": "Bash",
        "approval_reply": "yes",
        "kind": STOP_BEFORE[0],
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def test_protected_receipt() -> None:
    expect_fail(
        "action digest must look like sha256:<64 hex digits>",
        ed.protected_receipt,
        protected_args(action_digest="not-a-digest"),
        plan_fingerprint="direct",
        plan_id_value="direct",
    )
    expect_fail(
        "protected authorization requires exact target, effect, and tool name",
        ed.protected_receipt,
        protected_args(target="   "),
        plan_fingerprint="direct",
        plan_id_value="direct",
    )
    expect_fail(
        "protected authorization requires exact target, effect, and tool name",
        ed.protected_receipt,
        protected_args(effect="   "),
        plan_fingerprint="direct",
        plan_id_value="direct",
    )
    expect_fail(
        "protected authorization requires the user's literal approval reply",
        ed.protected_receipt,
        protected_args(approval_reply="   "),
        plan_fingerprint="direct",
        plan_id_value="direct",
    )
    value = ed.protected_receipt(protected_args(), plan_fingerprint="direct", plan_id_value="direct")
    require(value["target"] == "repo/file.py", "target must be preserved stripped")
    require(value["tool_name"] == "bash", "tool_name must be casefolded")
    require(value["approval_digest"] == text_digest("yes"), "approval_digest must hash the literal reply")
    require(isinstance(value.get("authorized_at"), str) and bool(value["authorized_at"]), "authorized_at must be set")
    require(
        value["binding_digest"] == protected_binding_digest(value), "binding_digest must match its own recomputation"
    )
    expected_keys = {
        "action_digest",
        "approval_digest",
        "approval_kind",
        "authorized_at",
        "binding_digest",
        "effect",
        "plan_fingerprint",
        "plan_id",
        "schema_version",
        "status",
        "target",
        "tool_name",
    }
    require(set(value) == expected_keys, f"unexpected receipt shape: {sorted(value)}")


def test_protected_receipt_matches() -> None:
    args = protected_args()
    value = ed.protected_receipt(args, plan_fingerprint="direct", plan_id_value="direct")
    require(
        ed.protected_receipt_matches(value, args, plan_fingerprint="direct", plan_id_value="direct"),
        "an identical receipt must match",
    )
    expect_fail(
        "action digest must look like sha256:<64 hex digits>",
        ed.protected_receipt_matches,
        value,
        protected_args(action_digest="not-a-digest"),
        plan_fingerprint="direct",
        plan_id_value="direct",
    )


def base_value(repo: Path, **overrides) -> dict[str, object]:
    value: dict[str, object] = {
        "allowed": ["reversible-local-work"],
        "created_at": utc_text(utc_now()),
        "decision": "Decision text.",
        "external_actions": [],
        "fresh_until": utc_now().date().isoformat(),
        "intended_paths": [{"path": "AGENTS.md", "scope": "file"}],
        "question": "Question text?",
        "repository_context": repository_context(repo),
        "route": "direct",
        "schema_version": 2,
        "scope": "local",
        "source_versions": [sha_hex(repo / "AGENTS.md")],
        "sources": ["AGENTS.md"],
        "stop_before": STOP_BEFORE,
        "unknown": [],
        "verified": ["ok"],
        "write_nonce": "sha256:" + "c" * 64,
    }
    value.update(overrides)
    return value


def test_validate_direct_receipt(repo: Path) -> None:
    local_value = base_value(repo)
    require(
        ed.validate_direct_receipt(repo, value=local_value) == local_value,
        "a valid local receipt must round-trip unchanged",
    )
    external_value = base_value(
        repo, scope="external", sources=["https://example.test/doc"], source_versions=["sha256:" + "d" * 64]
    )
    require(
        ed.validate_direct_receipt(repo, value=external_value) == external_value,
        "a valid external receipt must round-trip unchanged",
    )
    belongs = "direct-route receipt does not belong to this repository"
    expect_fail(belongs, ed.validate_direct_receipt, repo, value=base_value(repo, schema_version=3))
    expect_fail(belongs, ed.validate_direct_receipt, repo, value=base_value(repo, route="other"))
    expect_fail(belongs, ed.validate_direct_receipt, repo, value=base_value(repo, repository_context="not-a-dict"))
    tampered = base_value(repo)
    tampered_context = cast("dict[str, object]", tampered["repository_context"])
    tampered["repository_context"] = {**tampered_context, "checkout_digest": "sha256:" + "0" * 64}
    expect_fail(belongs, ed.validate_direct_receipt, repo, value=tampered)

    versions_msg = "direct-route receipt requires source versions"
    expect_fail(versions_msg, ed.validate_direct_receipt, repo, value=base_value(repo, sources=42))
    expect_fail(versions_msg, ed.validate_direct_receipt, repo, value=base_value(repo, sources=[], source_versions=[]))
    expect_fail(
        versions_msg,
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, sources=[""], source_versions=["sha256:" + "a" * 64]),
    )
    expect_fail(
        versions_msg,
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, sources=["s1", "s2"], source_versions="ab"),
    )
    expect_fail(
        versions_msg,
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, sources=["AGENTS.md"], source_versions=["v1", "v2"]),
    )
    expect_fail(
        versions_msg,
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, sources=[123], source_versions=["sha256:" + "a" * 64]),
    )
    expect_fail(
        versions_msg,
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, sources=["AGENTS.md"], source_versions=[123]),
    )
    expect_fail(
        "external direct research requires HTTPS primary sources",
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, scope="external", sources=["ftp://nope"], source_versions=["sha256:" + "a" * 64]),
    )
    expect_fail(
        "local direct research source is invalid: adir",
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, sources=["adir"], source_versions=["sha256:" + "a" * 64]),
    )
    expect_fail(
        "local direct research source must be repository-relative: ../outside",
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, sources=["../outside"], source_versions=["sha256:" + "a" * 64]),
    )
    expect_fail(
        "local direct research source changed: AGENTS.md",
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, source_versions=["sha256:" + "0" * 64]),
    )
    expect_fail(
        "direct-route receipt has an invalid research scope",
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, scope="bogus"),
    )
    expect_fail(
        "direct-route receipt requires intended paths",
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, intended_paths=[]),
    )
    skill_gap_msg = "skill content requires an external HTTPS primary source: skills/sample-skill/SKILL.md"
    expect_fail(
        skill_gap_msg,
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, intended_paths=[{"path": "skills/sample-skill/SKILL.md", "scope": "file"}]),
    )
    skill_external = base_value(
        repo,
        scope="external",
        sources=["https://example.test/doc"],
        source_versions=["sha256:" + "d" * 64],
        intended_paths=[{"path": "skills/sample-skill/SKILL.md", "scope": "file"}],
    )
    require(
        ed.validate_direct_receipt(repo, value=skill_external) == skill_external,
        "an external receipt with an HTTPS source may cover skill content",
    )
    expect_fail(
        "direct-route intended paths must be objects",
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, intended_paths=["AGENTS.md"]),
    )
    expect_fail(
        "direct-route intended path is not canonical",
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, intended_paths=[{"scope": "file"}]),
    )
    expect_fail(
        "direct-route intended path has an invalid scope",
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, intended_paths=[{"path": "AGENTS.md", "scope": "bogus"}]),
    )
    expect_fail(
        "direct intended path must be repository-relative: ../outside",
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, intended_paths=[{"path": "../outside", "scope": "file"}]),
    )
    expect_fail(
        "direct-route external actions must be a list",
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, external_actions="not-a-list"),
    )
    expect_fail(
        "direct-route receipt has an invalid action scope",
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, allowed=["something-else"]),
    )
    subagents = base_value(repo, allowed=["reversible-local-work", "parallel-subagents"])
    require(
        ed.validate_direct_receipt(repo, value=subagents) == subagents,
        "the allow-subagents variant of allowed must also validate",
    )
    expect_fail(
        "direct-route stop boundary drifted",
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, stop_before=["wrong"]),
    )
    expect_fail(
        "direct-route receipt requires a one-use write nonce",
        ed.validate_direct_receipt,
        repo,
        value=base_value(repo, write_nonce="not-a-nonce"),
    )
    expect_fail(
        "direct-route receipt requires question", ed.validate_direct_receipt, repo, value=base_value(repo, question="")
    )
    expect_fail(
        "direct-route receipt requires decision", ed.validate_direct_receipt, repo, value=base_value(repo, decision="")
    )


def start_args(repo: Path, **overrides) -> argparse.Namespace:
    base = {
        "repo": str(repo),
        "intended_path": ["AGENTS.md"],
        "scope": "local",
        "question": "What should happen?",
        "decision": "Do the safe thing.",
        "source": ["AGENTS.md"],
        "source_version": [],
        "verified": ["confirmed"],
        "unknown": ["none"],
        "fresh_until": utc_now().date().isoformat(),
        "allow_subagents": False,
        "external_action": [],
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def read_receipt(repo: Path) -> dict[str, object]:
    return json.loads(direct_receipt_path(repo).read_text(encoding="utf-8"))


def read_receipt_after(repo: Path, args: argparse.Namespace) -> dict[str, object]:
    ed.command_start_direct(args)
    return read_receipt(repo)


def test_command_check_direct(repo: Path) -> None:
    ed.command_start_direct(start_args(repo))
    stored = read_receipt(repo)
    printed = capture(ed.command_check_direct, argparse.Namespace(repo=str(repo)))
    require(
        printed == json.dumps(stored, sort_keys=True, separators=(",", ":")),
        f"check-direct must print the exact canonical receipt, got {printed!r}",
    )


def test_command_consume_direct(repo: Path) -> None:
    ed.command_start_direct(start_args(repo))
    nonce = read_receipt(repo)["write_nonce"]
    path = direct_receipt_path(repo)
    path.write_bytes(b"not json")
    expect_fail(
        "direct-route receipt is invalid",
        ed.command_consume_direct,
        argparse.Namespace(repo=str(repo), write_nonce=nonce),
    )
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    expect_fail(
        "direct-route receipt is invalid",
        ed.command_consume_direct,
        argparse.Namespace(repo=str(repo), write_nonce=nonce),
    )
    ed.command_start_direct(start_args(repo))
    nonce = read_receipt(repo)["write_nonce"]
    expect_fail(
        "direct-route write nonce does not match",
        ed.command_consume_direct,
        argparse.Namespace(repo=str(repo), write_nonce="sha256:" + "9" * 64),
    )
    require(direct_receipt_path(repo).exists(), "a wrong nonce must not consume the receipt")
    printed = capture(ed.command_consume_direct, argparse.Namespace(repo=str(repo), write_nonce=nonce))
    require(printed == "direct-route-consume: PASS", f"unexpected consume output: {printed!r}")
    require(not direct_receipt_path(repo).exists(), "a correct consume must remove the receipt")


def test_command_authorize_protected_direct(repo: Path) -> None:
    args = protected_args(repo=str(repo))
    printed = capture(ed.command_authorize_protected_direct, args)
    require(
        printed == f"protected-action: PASS plan=direct kind={args.kind} target={args.target}",
        f"unexpected authorize output: {printed!r}",
    )
    stored = json.loads(ed.protected_direct_path(repo).read_text(encoding="utf-8"))
    require(stored["target"] == args.target, "authorize must persist the exact target")


def protected_consume_fixture(repo: Path) -> tuple[argparse.Namespace, Path, bytes]:
    authorize_args = protected_args(repo=str(repo))
    ed.command_authorize_protected_direct(authorize_args)
    consume_args = argparse.Namespace(
        repo=str(repo),
        action_digest=authorize_args.action_digest,
        tool_name=authorize_args.tool_name,
        kind=authorize_args.kind,
    )
    path = ed.protected_direct_path(repo)
    original = path.read_bytes()
    return consume_args, path, original


def test_command_consume_protected_direct(repo: Path) -> None:
    consume_args, path, original = protected_consume_fixture(repo)
    path.write_bytes(b"not json")
    expect_fail("direct protected authorization is invalid", ed.command_consume_protected_direct, consume_args)
    path.write_bytes(original)
    mismatched = argparse.Namespace(
        repo=str(repo), action_digest=DIGEST_B, tool_name=consume_args.tool_name, kind=consume_args.kind
    )
    expect_fail(
        "protected authorization does not match the current action", ed.command_consume_protected_direct, mismatched
    )
    require(path.exists(), "a mismatched consume must not remove the receipt")
    printed = capture(ed.command_consume_protected_direct, consume_args)
    require(printed == "protected-action-consume: PASS", f"unexpected consume output: {printed!r}")
    require(not path.exists(), "a correct consume must remove the receipt")


def test_command_action_digest() -> None:
    old_stdin = sys.stdin
    tool_input: dict[str, object] = {"table": "events", "value": "x"}
    try:
        sys.stdin = io.StringIO("not json")
        expect_fail(
            "action-digest requires the exact tool_input as JSON on stdin",
            ed.command_action_digest,
            argparse.Namespace(tool_name="Bash"),
        )
        sys.stdin = io.StringIO("[1, 2, 3]")
        expect_fail(
            "action-digest requires a JSON object tool_input",
            ed.command_action_digest,
            argparse.Namespace(tool_name="Bash"),
        )
        sys.stdin = io.StringIO(json.dumps(tool_input))
        printed = capture(ed.command_action_digest, argparse.Namespace(tool_name="Bash"))
        require(printed == action_digest("Bash", tool_input), f"unexpected action digest output: {printed!r}")
    finally:
        sys.stdin = old_stdin


def test_command_start_direct(repo: Path) -> None:
    printed = capture(ed.command_start_direct, start_args(repo))
    stored = read_receipt(repo)
    require(
        printed == f"direct-route: PASS repo={repo} paths={len(cast('list[object]', stored['intended_paths']))}",
        f"unexpected start-direct output: {printed!r}",
    )
    require(stored["unknown"] == [], "unknown=['none'] must collapse to an empty list")
    require(
        len(cast(str, stored["write_nonce"])) == len("sha256:") + 64, "write_nonce must be a full sha256 fingerprint"
    )

    dedup = read_receipt_after(repo, start_args(repo, intended_path=["AGENTS.md", "AGENTS.md"]))
    require(
        dedup["intended_paths"] == [{"path": "AGENTS.md", "scope": "file"}],
        "duplicate intended paths must collapse to one entry",
    )
    tree_receipt = read_receipt_after(repo, start_args(repo, intended_path=["newdir/"]))
    require(
        tree_receipt["intended_paths"] == [{"path": "newdir", "scope": "tree"}],
        "a trailing slash on a non-existent path must still be a tree scope",
    )
    other_receipt = read_receipt_after(repo, start_args(repo, unknown=["something-else"]))
    require(other_receipt["unknown"] == ["something-else"], "any other unknown list must be kept as-is")

    literal = json.dumps({"tool_name": "Bash", "action_digest": DIGEST, "effect": "run it"})
    literal_receipt = read_receipt_after(repo, start_args(repo, external_action=[literal]))
    require(
        literal_receipt["external_actions"] == [{"tool_name": "bash", "action_digest": DIGEST, "effect": "run it"}],
        "external actions must be parsed and stored",
    )

    external_receipt = read_receipt_after(
        repo,
        start_args(
            repo,
            scope="external",
            source=["https://example.test/a", "https://example.test/a"],
            source_version=["sha256:" + "e" * 64],
        ),
    )
    require(external_receipt["sources"] == ["https://example.test/a"], "duplicate sources must collapse to one entry")
    require(
        external_receipt["source_versions"] == ["sha256:" + "e" * 64],
        "external source_versions must be stored as given",
    )

    expect_fail(
        "direct intended path must be repository-relative: ../outside",
        ed.command_start_direct,
        start_args(repo, intended_path=["../outside"]),
    )
    expect_fail(
        "direct intended path cannot be the whole repository",
        ed.command_start_direct,
        start_args(repo, intended_path=["."]),
    )
    expect_fail(
        "direct route requires at least one intended path", ed.command_start_direct, start_args(repo, intended_path=[])
    )
    expect_fail(
        "skill content requires an external HTTPS primary source: skills/sample-skill/SKILL.md",
        ed.command_start_direct,
        start_args(repo, intended_path=["skills/sample-skill/SKILL.md"], source=["AGENTS.md"]),
    )
    ed.command_start_direct(
        start_args(
            repo,
            intended_path=["skills/sample-skill/SKILL.md"],
            scope="external",
            source=["https://example.test/doc"],
            source_version=["sha256:" + "f" * 64],
        )
    )
    expect_fail("fresh-until must use YYYY-MM-DD", ed.command_start_direct, start_args(repo, fresh_until="not-a-date"))
    expect_fail(
        "direct research freshness cannot already be expired",
        ed.command_start_direct,
        start_args(repo, fresh_until=(utc_now().date() - timedelta(days=1)).isoformat()),
    )
    ed.command_start_direct(start_args(repo, fresh_until=utc_now().date().isoformat()))
    expect_fail(
        "external direct research requires HTTPS primary sources",
        ed.command_start_direct,
        start_args(repo, scope="external", source=["ftp://nope"], source_version=["sha256:" + "a" * 64]),
    )
    expect_fail(
        "external direct research requires one source-version per source",
        ed.command_start_direct,
        start_args(repo, scope="external", source=["https://a", "https://b"], source_version=["sha256:" + "a" * 64]),
    )
    expect_fail(
        "local direct research source must be repository-relative: ../outside",
        ed.command_start_direct,
        start_args(repo, source=["../outside"]),
    )
    expect_fail(
        "local direct research source is invalid: adir", ed.command_start_direct, start_args(repo, source=["adir"])
    )
    required_msg = "direct route requires question, decision, source, and verified result"
    expect_fail(required_msg, ed.command_start_direct, start_args(repo, question="   "))
    expect_fail(required_msg, ed.command_start_direct, start_args(repo, verified=[]))
    expect_fail(required_msg, ed.command_start_direct, start_args(repo, source=[]))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="execution-direct-survivors-") as temporary:
        repo = make_repo(Path(temporary))
        test_validate_external_actions()
        test_parse_external_actions()
        test_protected_receipt()
        test_protected_receipt_matches()
        test_validate_direct_receipt(repo)
        test_command_check_direct(repo)
        test_command_consume_direct(repo)
        test_command_authorize_protected_direct(repo)
        test_command_consume_protected_direct(repo)
        test_command_action_digest()
        test_command_start_direct(repo)
    print("execution-direct-survivors: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
