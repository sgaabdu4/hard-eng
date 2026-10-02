# Gate untrusted JSON in JavaScript/TypeScript projects

Status: Complete

## Outcome + scope

JavaScript/TypeScript packages fail their gates when untrusted JSON is used before validation or when a type assertion (`x as T`, except `as const`) bypasses checking. Zod is the recommended fix. Setup and update apply it directly with no transition step: no warning phase, no manual tsconfig edit and no old gate left beside the new one. Existing projects then fail until their code migrates. The user accepted that cost on 2026-10-02.

Non-goals: migrating consumer projects (separate per-project work after update); untyped `any` from library types such as `node-appwrite` `Models.Document`; Python and Dart.

## Repository context

Owners:
- Cast ban: the `typing-style` check in [hard-eng.javascript.json](../../.agents/skills/he/templates/hard-eng.javascript.json). Before this change, update demoted a changed gate to `project-typing-style` and appended `strict-typing-style` ([setup.py `configure_typing_checks`](../../setup.py)). Now `strict_typing_rules` in [untrusted_input.py](../../.hooks/untrusted_input.py) adds the rule to the existing Biome `typing-style` gate in place, following the `strict_scanner_flags` precedent. The gate then matches the template and no duplicate remains.
- Unknown JSON: [.hooks/untrusted-input.d.ts](../../.hooks/untrusted-input.d.ts), shipped through [update.py `scaffold_files`](../../.hooks/update.py). It retypes `Body.json()` and `JSON.parse` as `unknown`, adapted from ts-reset 0.6.1 without adding a dependency. The reviver is typed without `any` through a method signature, so typed revivers cannot fall back to the `any` overload.
- Include enforcement: [hard-eng.py `validate_typescript`](../../.hooks/hard-eng.py) fails when `tsc --showConfig` omits the declaration. Setup/update add it to every JS/TS package `tsconfig.json` (`typescript_config` and `json_listed` in [untrusted_input.py](../../.hooks/untrusted_input.py), called from setup.py `configure_javascript`). The edit is a text insertion that keeps comments, trailing commas and layout, and is verified by re-parsing. New tsconfig files are written with it. A config that inherits its list through `extends` fails with the line to add.
- Fallow: Fallow reports any source file inside a hidden directory as skipped (`skipped-source-dotdir`), and Hard Eng's report check fails on that; found during the end-to-end run. Setup/update adds `.hooks/**` to the root Fallow config's `ignorePatterns` (`fallow_ignores_hooks`), mirroring the existing `.dart-decimaterc.json` `.agents/**` ignore. It writes `.fallowrc.json` when there is none and inserts into `.fallowrc.json`/`.jsonc` with the same editor. TOML, or `extends` without its own list, fails with the line to add, because a child list replaces the inherited one. `"!.hooks/**"` did not clear the diagnostic on Fallow 3.29.0.
- Decision record: [DECISION.md](../../DECISION.md) "Runtime validation". It keeps "no schema-library gate" and adds the type gate.
- Docs: the [README](../../README.md) gate-contract table names the gate. The [gates.md](../../.agents/skills/he/references/gates.md) "Untrusted input (JS/TS)" row gives the fix route: validate with a Zod schema (an existing validator or a type guard also passes) and never cast.

Evidence: research before planning, on 2026-10-02.
- In a scratch project (TypeScript 7.0.2, Biome 2.5.15), the declarations plus `biome lint --only=nursery/noUnsafeTypeAssertion` flagged an unchecked `request.json()` field read, `JSON.parse(...).id`, `fetch().json()` use, a cast helper and an inline cast.
- Zod `.parse` and a hand-written `typeof` check both passed. `as const` passed. A DOM cast (`as HTMLElement`) was flagged.
- `--only` runs the nursery rule without any Biome config.
- Declarations alone miss code that hides request bodies behind a cast, such as a generic `readJson<T>()` helper returning `body as T`, so the cast ban is the enforcing half.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Human-loop. The user asked for project-wide enforcement including older non-Zod projects and accepted the migration work. Decisions on 2026-10-02:
- Force the change on update with no transition. Setup/update edits each package tsconfig, replacing the earlier choice to fail until the include was added by hand.
- Add the rule to the existing typing-style gate in place.
- Use Biome's nursery `noUnsafeTypeAssertion` rule, not typescript-eslint.

The user approved this plan on 2026-10-02 and asked for the README tables to be updated too. The Fallow config edit was added during build inside that approved boundary (setup editing consumer config).

## Acceptance + steps

- [x] An unvalidated field read from `request.json()`, `fetch().json()` or `JSON.parse()` fails `types` → fixture check: `types` FAIL with only `src/routes.ts(5,16): error TS18046: 'body' is of type 'unknown'`. A Node-only scratch project also failed `fetch().json()` and `JSON.parse` reads.
- [x] Any `as T` assertion other than `as const` fails `typing-style` → fixture check: `typing-style` FAIL with only `src/routes.ts:9:38 lint/nursery/noUnsafeTypeAssertion`, and the fixture's `as const` passed. Tests and UI code are covered because the rule runs on every JS/TS file Biome receives.
- [x] A Zod-validated body and a hand-written type guard both pass `types` and `typing-style` → fixture after migration: both PASS.
- [x] Update adds the declaration to an existing tsconfig, keeping its other settings, comments and trailing commas, for root and nested packages; a new tsconfig is written with it → `test_update_adds_untrusted_input_to_an_existing_tsconfig` (4 layouts, idempotent rerun), `test_nested_package_tsconfig_reaches_the_root_declarations`, `test_fresh_install_ships_and_includes_the_untrusted_input_declarations`.
- [x] A tsconfig that inherits its file list fails setup naming the line to add → `test_inherited_file_list_names_the_line_to_add`. Commented tsconfig files are now edited, not refused.
- [x] A tsconfig that later drops the declaration fails `types` → `test_typescript_check_requires_the_untrusted_input_declarations`.
- [x] Updating a project whose `typing-style` gate was the previous template rewrites that gate in place → `test_update_adds_the_cast_rule_to_the_installed_typing_style_gate`. Real update: an install from `main` (`026866c`), then setup from this branch with `--previous-source`, left one `typing-style` gate carrying the rule.
- [x] The declaration ships to installed projects → the fresh-install test asserts the shipped bytes; `scaffold_files` owns refresh and retirement.
- [x] A Node-only package (`lib: ["es2022"]`, `@types/node` 26.6.3) type-checks with the declaration, and `JSON.parse` stays `unknown`, including with typed and untyped revivers → scratch `tsc` run.
- [x] `dead-code-duplicates` passes with the declaration installed → `test_fallow_config_skips_the_hidden_hard_eng_declarations` (new, tab-indented JSON, JSONC with comments, `{}`; idempotent), `test_fallow_config_setup_cannot_edit_names_the_line_to_add` (TOML, `extends`), and fixture `dead-code-duplicates` PASS.
- [x] DECISION.md, gates.md and the README gate table state the gate and the Zod-first fix route → reviewed in the diff.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on this branch at `026866c` (plan only) → exit 0, 18/18 gates PASS.
Execution: one builder, then a fresh verifier reviewed the diff. The verifier's findings were all fixed in `08097d6`:
- A commented tsconfig blocked setup; the editor now keeps comments.
- `extends` in a Fallow config dropped inherited ignores; setup now names the line to add instead.
- `any` in the declaration; it is now `any`-free.
- A missing assertion for the Fallow config call; the fresh-install test now checks it.

Solution-style tsconfig files (`files: []` plus `references`) already fail the existing production-files check, so they are unchanged.

## Risks + recovery

- **The rule is experimental.** Biome's nursery rule may change or be renamed. The fixture check pins today's behaviour. If it changes, swap the `--only=` name or move to typescript-eslint. Recovery: revert the template line.
- **Every JS/TS consumer fails pre-push after update until migrated.** The user accepted this. The update still commits, since it validates gate configuration, not project code.
- **Inserted entries go first.** The declaration and `.hooks/**` are inserted at the start of the existing list, in the file's own spacing. A project formatter may reflow them. Recovery: revert the update commit in the consumer.
- **Customised typing-style gates.** A project gate that is not a Biome `--only=` command is left as is, and the template gate is added beside it, which is the existing behaviour for custom gates.
- **Projects running their own Biome over `.hooks`.** The declaration has no `any`, so it passes Biome's recommended lint rules. A project formatter with different settings may still report its spacing; Hard Eng's own Biome gates skip `.hooks`.

## ux_reference

N/A — gate configuration and type declarations with no visual surface.

## Verification

Result: Passed
Evidence: Hard Eng and a disposable fixture, as below.
- Hard Eng: `uv run pytest -q` → 1193 passed on `bcf5655`; after the review fixes and the module split, `tests/test_untrusted_input.py` → 16 passed. `python3 .hooks/hard-eng.py check --plan-stage Complete` runs every gate on the final commit.
- Fixture: TypeScript 7.0.2, Biome and Fallow 3.29.0 run by the installed runner. The fixture's `tests` and `performance` scripts are stubs that write no reports, so those two gates FAIL there; they are not evidence for this change.
E2E: Passed — this branch installed into a fresh fixture with a commented `tsconfig.json` and unchecked, cast, Zod-validated and hand-guarded routes.
- Before migration: `types` failed only on line 5 and `typing-style` only on line 9; format-lint, focused-tests and dead-code-duplicates passed.
- After Zod migration: `types`, `typing-style`, format-lint and dead-code-duplicates all passed.
- Update path: `main` install → this branch → same failures on the same lines, with one typing-style gate.

Delivery target: Merge
Delivery: Pending — PR checks green, squash-merged when green, main CI green after merge.
