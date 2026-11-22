# Single source of truth for host models, efforts, and fallback order

Status: Complete

## Outcome + scope

Add `.agents/models.json` as the single source of truth for Claude Code (`claude`), Codex (`codex`), and Antigravity (`agy`) model/effort/service-tier defaults (`reasoning`, `implementation`, `lookup`), cross-agent `challenge_order`, and `subagent_overflow`, with an optional machine-local overlay (`$XDG_CONFIG_HOME/hard-eng/models.json` or `~/.config/hard-eng/models.json`). Update `.hooks/challenge.py` and `.hooks/look.py` to load reviewer order and verified CLI flags through a shared `.hooks/models.py` loader (reading the base `.agents/models.json` from the default branch point when present so a feature branch cannot tamper with its own review config, and enforcing a full permutation of all other hosts in `challenge_order`), update `.claude/rules/model-roles.md`, `AGENTS.md`, `.hooks/agent_hooks.py`, and `.agents/skills/code-review/references/challenge.md` so all three hosts see the role and overflow rules without hardcoded model names in prose, and ship `.agents/models.json` via `.hooks/update.py` and `hard-eng.gates.json`. Non-goals: adding Antigravity (`agy`) as a `look.py` image reviewer (deferred because `look.py` requires a verified real session-file proof schema showing each opened image path, which currently exists only for Claude `stream-json` `Read` results and Codex rollout `ImageView` records); opening a release PR to `main`.

## Sources + coverage

Sources: N/A — the user's authorization and specification are the only sources.
Deliverables: None

## Repository context

Owners: `.agents/models.json` (canonical host model/effort/service-tier, `challenge_order`, and `subagent_overflow` defaults), `.hooks/models.py` (schema validation, trusted-base loading, optional local overlay merge, CLI flag generation, and non-Claude `SessionStart` note), `.hooks/challenge.py` (`host_for`, `reviewers_for`, `reviewer_for`, `command`, `challenge`), `.hooks/look.py` (`choose_reviewer`, `command`, `run_reviewer`, `review`), `.hooks/agent_hooks.py` (`handle_event` `SessionStart` delivery), `.hooks/update.py` (`scaffold_files`, `maybe_installed`), `.claude/rules/model-roles.md` and `AGENTS.md` (cross-agent role and overflow guidance), `.agents/skills/code-review/references/challenge.md` (challenge model documentation), `hard-eng.gates.json` (`shipped-format`), `pyproject.toml` (`deptry` `known_first_party`).
Same cause: N/A — new configuration single source of truth replacing scattered defaults (`REVIEWER_ORDER` in `.hooks/challenge.py`, implicit CLI defaults in `challenge.py`/`look.py`, and hardcoded model names in `.claude/rules/model-roles.md`).
Single source: `.agents/models.json` owns all default host role models, efforts, Codex `service_tier`, `challenge_order`, and `subagent_overflow`; `.hooks/models.py` is the single loader, validator, overlay merger, and CLI flag builder shared by `challenge.py`, `look.py`, and `agent_hooks.py`; `.hooks/update.py::scaffold_files` and `maybe_installed` own scaffold distribution of `.agents/models.json`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Review declined: .agents/skills/code-review/references/challenge.md:8 contains pre-existing Review declined: guidance :: line 8 was already on develop before this branch (only line 3 changed) and documents Hard Eng's intentional, tested Review declined: protocol in .hooks/challenge.py and tests/test_challenge.py, which still requires reopening with named new evidence.
Review declined: .agents/skills/code-review/references/challenge.md:3 lacks a separate Reader subagent check :: this implementation ran as a child worker prohibited from spawning subagents; the single changed phrase on line 3 ("with the reasoning model and effort from .agents/models.json") was inspected directly and by the independent Codex challenge reviewer. Stated limit.
Review declined: .hooks/models.py:82 falls back to SHIPPED_MODELS when the base branch lacks .agents/models.json on this introducing PR :: _read_trusted_base now falls back strictly to SHIPPED_MODELS (never an untrusted target repository's unmerged .agents/models.json); on the one-time PR introducing .agents/models.json into Hard Eng itself, SHIPPED_MODELS shares the same trust boundary as executing .hooks/challenge.py from the checkout. Stated limit.
Review declined: .hooks/challenge.py:105 relies on default_branch_point() which reads shipping.base from hard-eng.gates.json :: default_branch_point() in .hooks/plans.py:745 is Hard Eng's pre-existing shared branch-point owner already used by .hooks/challenge.py:313 for git diff and shipping_note(); altering shipping.base to the feature branch already empties the review diff and is out of scope for .agents/models.json, with shipping/CI verifying the PR base against shipping.base. Stated limit.
Authority: Autonomous — the user approved the schema, latest-version defaults, and Autonomous delivery in chat on 2026-11-22, scoped to a PR against `develop` (release `develop` -> `main` handled separately).
Decisions:

1. `.agents/models.json` pins newest-version Claude aliases (`opus`/`sonnet`/`haiku`), explicit Codex models (`gpt-6.2-sol`/`gpt-6-luna`) with `service_tier: "default"`, and Antigravity models (`gemini-4-neon`/`gemini-3.8-flash`), plus `challenge_order` and `subagent_overflow`.
2. Optional local overrides live outside the repository at `$XDG_CONFIG_HOME/hard-eng/models.json` (when `XDG_CONFIG_HOME` is absolute) or `~/.config/hard-eng/models.json`, are deep-merged partially per role/section, and reject unknown keys, invalid efforts, unsafe model/tier strings, TOML literal tiers, non-Codex `service_tier`, or incomplete/self-challenging `challenge_order` lists.
3. For independent reviews (`challenge.py` and `look.py`), `.hooks/models.py` reads the base `.agents/models.json` from the default branch point when present (falling back to the checkout or shipped copy only when the base branch does not yet carry the file) before applying the reviewer machine's local overlay, so a branch cannot tamper with its own review order or model flags.
4. Verified CLI flags against installed binaries (`codex-cli 0.166.0`, `Claude Code 2.1.330`, `agy 1.5.14`): `codex exec` receives `-m <model> -c model_reasoning_effort=<effort> -c service_tier=<service_tier>`, `claude --print` receives `--model <model> --effort <effort>`, and `agy -p` receives `--model <model> --effort <effort>`.
5. `.hooks/look.py` consumes `challenge_order` and `cli_flags` from `.hooks/models.py` for supported image reviewers (`claude`, `codex`), supports `--host agy` choosing `codex` then `claude`, falls back to the actual running host with `fresh_same_agent: true` only when that host supports image review, and defers `agy` as a `look` image reviewer until a verified real `agy` session image-read proof schema is captured.
6. Cross-agent visibility: `.claude/rules/model-roles.md` removes hardcoded model names and documents `.agents/models.json` + default same-host + `subagent_overflow` on quota limits; `AGENTS.md` (within the 3921-byte cap) points all three hosts to both files; `SessionStart` in `.hooks/agent_hooks.py` surfaces `.agents/models.json` and `.claude/rules/model-roles.md` to `codex` and `agy` when `.agents/models.json` exists.

## Acceptance + steps

- [x] `.agents/models.json` holds the agreed host role defaults, `challenge_order`, and `subagent_overflow`, and `.hooks/models.py` loads and emits verified CLI flags for `codex`, `claude`, and `agy` → `tests/test_models.py::test_shipped_models_json_loads_with_expected_defaults_and_flags`
- [x] `.hooks/models.py` merges partial machine-local overrides from `$XDG_CONFIG_HOME/hard-eng/models.json` / `~/.config/hard-eng/models.json` and rejects malformed or incomplete base/overlay configs → `tests/test_models.py::test_local_overlay_merges_partially_and_respects_xdg_config_home`, `tests/test_models.py::test_invalid_overlay_payloads_are_rejected`, `tests/test_models.py::test_invalid_base_models_json_and_unknown_accessors_raise`
- [x] `.hooks/challenge.py` reads `challenge_order` and `reasoning` CLI flags from `.hooks/models.py` using the trusted base revision (or `SHIPPED_MODELS` when the base lacks the file) plus local overlay so a branch cannot weaken its own review → `tests/test_challenge.py::test_claude_host_runs_codex_read_only_without_user_plugins_and_closed_stdin`, `tests/test_challenge.py::test_codex_host_runs_claude_with_read_only_tools_and_no_git_write_flags`, `tests/test_challenge.py::test_agy_reviewer_runs_read_only_with_session_settings`, `tests/test_challenge.py::test_challenge_honors_local_models_overlay_for_order_and_flags`, `tests/test_challenge.py::test_branch_models_json_edit_cannot_override_trusted_base_for_challenge`
- [x] `.hooks/look.py` passes model/effort/service-tier CLI flags from `.hooks/models.py`, selects supported reviewers from `challenge_order`, and falls back accurately without mislabeling `fresh_same_agent` → `tests/test_look.py::test_look_passes_models_json_flags_and_supports_agy_host_fallback`
- [x] `.claude/rules/model-roles.md`, `AGENTS.md`, and `SessionStart` for `codex` and `agy` surface `.agents/models.json` and the same-host/overflow rules without hardcoded model names in prose and within the `AGENTS.md` size cap → `tests/test_models.py::test_model_roles_rule_references_ssot_without_hardcoded_models`, `tests/test_models.py::test_codex_and_agy_session_start_surface_models_config_and_rules`, `tests/test_agent_hooks.py::test_shared_agent_rules_stay_within_the_released_size`
- [x] `.hooks/update.py` ships, installs, protects against silent local overwrite, and updates `.agents/models.json` as a verified scaffold file → `tests/test_models.py::test_models_json_is_shipped_installed_and_updated_by_scaffold`, `tests/test_models.py::test_update_refreshes_models_json_as_verified_scaffold_update`

## Baseline + execution

Result: Passed
Evidence: Starting commit `0eadec61` on `origin/develop` is the latest merged commit on `develop`.
Execution: Single builder on branch `feat/models-ssot`.

## Risks + recovery

- A machine-local `~/.config/hard-eng/models.json` with bad schema or unsupported CLI values would break `challenge` or `look`; strict validation in `.hooks/models.py` fails fast with a clear path and field message.
- Recovery: revert the commits on `feat/models-ssot` (or remove `.agents/models.json` and `.hooks/models.py` and restore the previous `challenge.py`, `look.py`, `update.py`, `agent_hooks.py`, `model-roles.md`, and `AGENTS.md`).

## ux_reference

N/A — no visual UI changes; CLI flags, configuration schema, hooks, and rules only.

## Verification

Result: Passed
Delivery target: PR
Delivery: Pending — push `feat/models-ssot` and open a `pr-text`-compliant PR against `develop`.
Evidence: Focused tests passed (`tests/test_models.py`, `tests/test_challenge.py`, `tests/test_look.py`, `tests/test_agent_hooks.py`, `tests/test_updates.py`, `tests/test_skill_links.py`, `tests/test_shipped_shapes.py`, `tests/test_scaffold_replay.py`, `tests/test_gate_tools.py`). Static gates passed (`ruff format`, `ruff check`, `complexity`, `annotations`, `pyrefly` 0 diagnostics, `vulture` 0 findings, `jscpd` 0 duplicates, `hot-paths` 0 findings, `deptry` 0 issues; `AGENTS.md` 3901/3921 bytes; `.hooks/agent_hooks.py` 998/1000 lines). CLI flags verified against `codex-cli 0.166.0`, `Claude Code 2.1.330`, and `agy 1.5.14` `--help` output; live `python3 .hooks/hard-eng.py challenge --host agy` proved `codex exec` end-to-end with `-m gpt-6.2-sol -c model_reasoning_effort=high -c service_tier=default` (stated limit: live `agy` reviewer invocation is not runnable locally because `agy` CLI is not signed in). Full `python3 .hooks/hard-eng.py check --base origin/develop --plan-stage Complete` runs on the final clean commit.
E2E: N/A — no visual UI journey; live `hard-eng.py challenge --host agy` proves the `codex` reviewer CLI invocation end-to-end, while `claude` and `agy` CLI flags are verified against `--help` and fake-CLI integration tests (`agy` CLI is unsigned locally).
Real service: N/A — no outside network service is called by the unit suite; live `challenge --host agy` exercises the local Codex reviewer CLI directly.
Retro: (1) Class-based `TypedDict` triggered Vulture unused-variable findings at 60% confidence → switched to functional `TypedDict(...)` matching `.hooks/gate_config.py`. (2) Adding a `SessionStart` note directly inside `.hooks/agent_hooks.py::handle_event` risked complexity/length limits (996 lines) → placed `session_note()` in `.hooks/models.py` so `agent_hooks.py` stayed at 998 lines with unchanged complexity. (3) Initial `jscpd` caught a 7-line SessionStart test setup duplicate between `tests/test_agent_hooks.py` and `tests/test_models.py` → extracted `session_start_context` helper in `tests/test_agent_hooks.py`. (4) Round-1 Codex challenge caught that an untrusted branch could shorten or tamper with `.agents/models.json` for its own review, that `look.py::choose_reviewer` could mislabel `fresh_same_agent` when falling back, and that the draft plan included private chat references and a local worktree path → enforced full-permutation `challenge_order` + trusted-base loading in `.hooks/models.py`, fixed `look.py::choose_reviewer` via `host_for()`, sanitized the plan before pushing, and added regression tests for each.
