# Short hook messages

Status: Complete

## Outcome + scope

Hook text the model reads gets much shorter for Claude and Codex, Claude is told to read a root `AGENTS.override.md`, and `AGENTS.md` asks for ~80% ASD-STE100 reports at no token increase. Non-goals: gate output content or `GATE_OUTPUT_LIMIT`, dropping the per-failure HE Learn event, subdirectory overrides, stored update result strings.

## Repository context

Owners: `.hooks/agent_hooks.py` (`session_context`, `learning_context`, `gate_status`, `completion`, `handle_event`), `.hooks/update_runner.py` (`start_update`, `freshness_note`, `failed_update`, `ready_message`, `update_blocker`), `.hooks/hook_chain.py` (`RESTORE`), `AGENTS.md` (shipped to every project by `configure_instructions`). Codex loads `AGENTS.override.md` instead of `AGENTS.md`; Claude loads only `AGENTS.md` (observed 2026-10-09). Parse-dependent text kept: `Hard Eng update failed` (`run_update` exit), `Hard Eng: planning checks passed` / `build checks passed` (`completion_notice`), `NOT_PUBLISHED`, `build in progress`, `Hard Eng: Planning incomplete`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User 2026-10-09: "ok, do it" for the override line + "have all our hook messages really really short and use symbols if possible"; "enforce this in agents.md but ensure we're not increasing token count". Standing merge-when-green for this repo.

## Acceptance + steps

- [x] Claude session in a root with `AGENTS.override.md` gets a read-it line; Codex session does not; no override → no line → `tests/test_agent_hooks.py` override test.
- [x] Session, failure and stop fixed text shorter for both agents, same JSON shape → hook output before/after measured in Verification; existing hook tests updated and passing.
- [x] Parse-dependent prefixes above unchanged → existing update/completion tests pass.
- [x] `AGENTS.md` carries the ASD-STE100 report rule with no Claude token increase → `claude -p` usage on 10 copies old vs new.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on untouched `9658dbec` → exit 0 (base commit passed CI; secret scan only, PASS).
Execution: One builder (this session); first slice is the shortened strings + override line with tests, then AGENTS.md.

## Risks + recovery

Shorter text could drop a needed instruction → each message keeps its action and boundary; AGENTS.md still carries the full rules. Recovery: revert the commit.

## ux_reference

N/A — no visual surface; hook text only.

## Verification

Result: Passed
Evidence: `hard-eng.py session|failure|stop <agent>` run in this repo before/after, additionalContext chars: session 673 → 314 (Codex) / 360 (Claude, + override line), failure 278 → 105, unchanged stop systemMessage 77 → 50. Claude `claude -p --model haiku` input tokens, 10 copies: session + failure text 325 → 168 tokens each; AGENTS.md 14 tokens smaller each. Codex `codex exec --json`, 7 copies (under its doc size cap): AGENTS.md 10 tokens smaller each. Hook tests 157 passed; first Ready gate failed format + 2 stale message tests, each fixed in its own commit. Live `claude -p` in a fixture with the session hook + an override holding a canary word: first wording ignored by Haiku; reworded line found it on claude-haiku-5-5 3/3, claude-sonnet-5-5 and claude-opus-5-5; no-hook control → NONE. Codex Desktop sessions in installed projects receive this hook context as a developer message (rollouts 2026-09-29/30); `codex exec` in an untrusted fixture skipped project hooks, so Codex live proof rests on that and unchanged JSON shape. AGENTS.md rule widened to all output; Claude tokens still 11 fewer per copy than before.
E2E: N/A — hook JSON output to agent CLIs; proof is hook runs for both agents plus tests and the gate.

Delivery target: Merge
Delivery: Pending — PR CI and merge.
