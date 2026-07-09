#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import tiktoken


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
SKILL_DIR = REPO_ROOT / "skills" / "terse"
EVALS_PATH = SCRIPT_DIR / "evals.json"
SCHEMA_PATH = SCRIPT_DIR / "eval-output-schema.json"
ENCODING = tiktoken.get_encoding("o200k_base")

GLOBAL_FORBIDDEN = [
    "let's dive in",
    "here's what you need to know",
    "of course",
    "great question",
    "i hope this helps",
    "as an ai",
    "terse mode",
    "normal-answer recap",
]


def token_count(text):
    return len(ENCODING.encode(text))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_prompt(skill_text, item):
    return f"""You are running an automated eval for this Codex skill.

Read and follow the skill exactly. If it points to a local reference file, read
that file from the repo before answering. Return only JSON matching the schema.

Skill text:
```markdown
{skill_text}
```

Eval id: {item["id"]}

User-facing task:
{item["prompt"]}

Expected behavior:
{item["expected_output"]}

Return:
{{
  "eval_id": "{item["id"]}",
  "reply": "<final assistant reply only>"
}}
"""


def collect_usage(log_text):
    totals = {}

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key.endswith("tokens") and isinstance(child, int):
                    totals[key] = max(totals.get(key, 0), child)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for line in log_text.splitlines():
        try:
            walk(json.loads(line))
        except json.JSONDecodeError:
            continue
    return totals


def human_writing_read_evidence(log_text):
    for line in log_text.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item")
        if not isinstance(item, dict):
            continue
        if item.get("type") != "command_execution" or item.get("status") != "completed":
            continue
        command = item.get("command", "")
        output = item.get("aggregated_output", "")
        if "human-writing.md" in command and "# Human Writing Guide" in output:
            return f"read via `{command}`"
    return ""


def run_codex(model, skill_text, item, run_dir, timeout):
    result_path = run_dir / f"{item['id']}.json"
    log_path = run_dir / f"{item['id']}.jsonl"
    prompt = build_prompt(skill_text, item)
    command = [
        "codex",
        "exec",
        "-m",
        model,
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--ephemeral",
        "--json",
        "--color",
        "never",
        "-C",
        str(REPO_ROOT),
        "--output-schema",
        str(SCHEMA_PATH),
        "-o",
        str(result_path),
        prompt,
    ]

    start = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        duration_ms = round((time.monotonic() - start) * 1000)
        log_text = completed.stdout + completed.stderr
        log_path.write_text(log_text, encoding="utf-8")
    except subprocess.TimeoutExpired as error:
        duration_ms = round((time.monotonic() - start) * 1000)
        log_text = (error.stdout or "") + (error.stderr or "")
        log_path.write_text(log_text, encoding="utf-8")
        return {
            "eval_id": item["id"],
            "exit_code": None,
            "duration_ms": duration_ms,
            "reply": "",
            "usage": collect_usage(log_text),
            "checks": [
                {
                    "text": f"codex completed within {timeout}s",
                    "passed": False,
                    "evidence": f"timed out after {duration_ms}ms",
                }
            ],
            "overall_pass": False,
            "result_path": str(result_path),
            "log_path": str(log_path),
        }

    try:
        output = read_json(result_path)
        reply = output.get("reply", "")
    except (OSError, json.JSONDecodeError) as error:
        reply = ""
        output = {"parse_error": str(error)}

    checks = grade_reply(item, reply, log_text)
    checks.insert(
        0,
        {
            "text": "codex exited successfully",
            "passed": completed.returncode == 0,
            "evidence": f"exit_code={completed.returncode}",
        },
    )
    return {
        "eval_id": item["id"],
        "exit_code": completed.returncode,
        "duration_ms": duration_ms,
        "reply": reply,
        "output": output,
        "usage": collect_usage(log_text),
        "reply_tokens": token_count(reply),
        "checks": checks,
        "overall_pass": all(check["passed"] for check in checks),
        "result_path": str(result_path),
        "log_path": str(log_path),
    }


def contains_casefold(text, term):
    return term.casefold() in text.casefold()


def grade_reply(item, reply, log_text):
    checks = []
    reply_lines = [line for line in reply.splitlines() if line.strip()]
    first_line = reply_lines[0] if reply_lines else ""

    for term in item.get("required_terms", []):
        checks.append(
            {
                "text": f"includes `{term}`",
                "passed": contains_casefold(reply, term),
                "evidence": "found" if contains_casefold(reply, term) else "missing",
            }
        )

    any_terms = item.get("required_any_terms", [])
    if any_terms:
        found = [term for term in any_terms if contains_casefold(reply, term)]
        checks.append(
            {
                "text": f"includes one of {any_terms}",
                "passed": bool(found),
                "evidence": ", ".join(found) if found else "missing all",
            }
        )

    forbidden = GLOBAL_FORBIDDEN + item.get("forbidden_terms", [])
    for term in forbidden:
        present = contains_casefold(reply, term)
        checks.append(
            {
                "text": f"omits `{term}`",
                "passed": not present,
                "evidence": "present" if present else "absent",
            }
        )

    if item.get("requires_bullets"):
        bullet_count = len(re.findall(r"(?m)^\s*-\s+", reply))
        checks.append(
            {
                "text": "uses markdown bullets",
                "passed": bullet_count >= 2,
                "evidence": f"bullet_count={bullet_count}",
            }
        )

    human_evidence = human_writing_read_evidence(log_text)
    if item.get("requires_human_writing"):
        checks.append(
            {
                "text": "reads human-writing.md for paste-ready artifact",
                "passed": bool(human_evidence),
                "evidence": human_evidence or "no successful human-writing.md read found",
            }
        )
    if item.get("forbids_human_writing"):
        checks.append(
            {
                "text": "does not read human-writing.md for non-artifact reply",
                "passed": not human_evidence,
                "evidence": human_evidence or "no human-writing.md read",
            }
        )

    limit = item.get("max_output_tokens")
    if limit:
        count = token_count(reply)
        checks.append(
            {
                "text": f"reply is at most {limit} o200k_base tokens",
                "passed": count <= limit,
                "evidence": f"reply_tokens={count}",
            }
        )

    checks.append(
        {
            "text": "reply is non-empty",
            "passed": bool(reply.strip()),
            "evidence": first_line[:120] if first_line else "empty",
        }
    )
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.environ.get("TERSE_EVAL_MODEL", "gpt-5.6-luna"))
    parser.add_argument("--label", default="run")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--skill-path", default=str(SKILL_DIR / "SKILL.md"))
    parser.add_argument("--output-root", default=os.environ.get("TERSE_EVAL_ROOT", "/tmp/terse-evals"))
    parser.add_argument("ids", nargs="*")
    args = parser.parse_args()

    evals = read_json(EVALS_PATH)["evals"]
    selected = [item for item in evals if not args.ids or item["id"] in args.ids]
    if not selected:
        print("No matching eval ids.", file=sys.stderr)
        return 1

    skill_path = Path(args.skill_path).resolve()
    skill_text = skill_path.read_text(encoding="utf-8")
    run_dir = Path(args.output_root) / f"{time.strftime('%Y%m%d-%H%M%S')}-{args.label}"
    run_dir.mkdir(parents=True, exist_ok=False)

    results = []
    for item in selected:
        print(f"START {item['id']}")
        result = run_codex(args.model, skill_text, item, run_dir, args.timeout)
        results.append(result)
        print(f"DONE {item['id']} pass={result['overall_pass']} reply_tokens={result.get('reply_tokens', 0)}")

    passed = sum(1 for result in results if result["overall_pass"])
    summary = {
        "skill_name": "terse",
        "model": args.model,
        "skill_path": str(skill_path),
        "skill_tokens_o200k_base": token_count(skill_text),
        "run_dir": str(run_dir),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if passed == len(results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
