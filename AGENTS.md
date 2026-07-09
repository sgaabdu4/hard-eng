# Agent Rules

## Stops
- Destructive state needs approval; delete/remove/cleanup only approved scope. Broad cleanup, DB writes, reset/checkout, deletion scripts, temp/build cleanup -> ask
- Never edit `CHANGELOG.md`, `generated/`, `AUTO-GENERATED`; fix source
- Pre-commit: `git status --short`; `.env*`/keys/tokens/secrets -> stop
- No pass-through wrappers; adapters need validation/transform/owner/platform integration
- Do not weaken trust/security/a11y/data-loss checks
- Touched/connected files >700 lines must split unless marked large owners: hooks, scanners/parsers/regex, or dense contract/eval/behavior tests with focused coverage
- `SKILL.md`: no 3+ step workflows; move to `references/*.md` or scripts
- UI edits w/o design SSOT: create/import token/theme/style owner first
- Prod -> `PRODUCT.md`; design/UI/token -> `DESIGN.md` + token owner before handoff

## Core
- Read before claim/edit; uncited=unknown. Tool absent -> say once; fallback
- Fix root owner; prefer canonical behavior; delete concepts before modes/wrappers
- Validation >= scope; violation -> lint/scanner/gate; repeat -> run/add script/test/hook/eval; GH CI -> parallel logs/jobs, batch fixes, least reruns
- Commit msgs: no co-author, em dash, dash-prefix, decorative dashes
- Project AGENTS.md overrides global; repo facts only, <=600 o200k

## Tools
- `codebase-memory`, `context-mode`, `terse` are support tools, not stages
- Code map/callers/deps/routes -> `codebase-memory-mcp cli <tool> '<json>'`; missing/stale/corrupt -> `index_repository`; ok writes: CBM cache/status; fail -> rg
- Logs/output/docs/data -> sandbox/index; no dumps
- File edits: native tools/`apply_patch`; never context-mode
- Subagents -> exposed tools only; `tool_search`; else direct

## Evidence
- Code/diff/PR/commit/log/doc/review/summary: read evidence
- Diffs need hunks/functions/classes, not stat/name/subject/oneline
- Long summaries: split `Verified`/`Inferred`/`Unknown`; cite
- Semantic edits: blast radius + surrounding issues; check callers, cross-pkg, schema/index, cache/storage, tests/routes

## Skills
- Load matching skills before answer/edit; skills own workflow
- Flutter/Dart/Riverpod/Freezed/GoRouter/pubspec -> `building-flutter-apps`
- Appwrite/Auth/TablesDB/Storage/Functions/RT -> `appwrite-backend`
- Online/current/research -> `research` + web/search
- Repeats -> `repeated-failure-learning`; skills/evals -> `writing-great-skills`; search -> `find-skills`
- Workflow/next-step/router/onboarding/HE-vs-direct -> `workflow-help`
- Normal decisions/approach/tradeoffs/light plans -> `grill-me` align/lite; no HE unless escalated
- Serious feature/shipping workflow -> `he-plan`/`he-implement`/`he-verify`; ship:`he-ship`; learn:`he-learn`
- Bugs/failures/flakes/regressions -> `diagnosing-bugs`
- Boundaries/ownership/wrappers -> `codebase-design`
- Post-`grill-me`: `plan.md` owns spec, slices, blockers, frontier; sliced -> build; missing -> continue `grill-me`
- React/Next/perf/dupes -> `react-doctor` + `fallow` dupes + `vercel-react-best-practices`
- Tests/QA/mutation -> `test-quality`
- UI/components/design-system/tokens -> `atomic-ui` + `impeccable`
- Sentry/observability/issues/setup -> `sentry-workflow` only
- User-facing replies -> `terse`

## Impl
- Scope repo/root/rules/skills/owner/proof/risk
- `PASS`/`CONCERNS`/`FAIL`
- Scope expands -> `workflow-help` then `grill-me`/`codebase-design`/HE route as needed
- Tests -> `test-quality`; smallest verify/root cause
- Docs/rules: re-read + contract/symlink validation
- Report:
- Why: root cause/evidence
- What: files/behavior
- Risk: Direct callers; Cross-package; Schema/index; Cache/storage keys; Tests/fixtures; Routes/endpoints; Docs/config/agent assets
- Proof: tests/gaps
