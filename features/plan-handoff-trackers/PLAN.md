# Feature Brief: Plan Handoff Trackers

<!-- hard-eng-state:v1 -->
- state_version = 1
- plan_id = plan-handoff-trackers-b6892db2
- lifecycle_status = building
- approval_status = approved
- approval_fingerprint = sha256:c0a82ed0afb70c630c68e6bb5bb22c5bf45c3aa56a7f0d4210c8379a84866c3b
- approval_provenance = ready-to-build
- green_artifact = none
- active_slice = none
- completed_slices = S-1,S-2,S-3,S-4,S-5,S-6
- next_action = Test-stub fix; rerun full gate.
- replan_reason = none
<!-- /hard-eng-state -->

## Outcome
- When a Feature Brief is complete, the plan stage always closes with one batched question (split into tickets? which tracker?), then prints a ready-for-handoff block: checkout path, branch, plan path, and one paste-ready prompt that starts the build; approval is refused by machine until every planning step has left its receipt (code study, outside research, edge-case scan, decision inventory, slice graph, closing answers); when tickets were chosen, epic and story items exist in the chosen tracker (GitHub, Jira Cloud, or Azure DevOps) with the right dependencies.

## Non-goals
- Pulling remote tracker changes back into local state stays report-only.
- OAuth or service-principal auth for Jira and Azure; API token and PAT only.
- Replacing the existing ticket claim, worktree, and integration flow.

## Material decisions
- The brief carries every planned vertical slice inside the last section, renamed `Vertical slices` in S-2, (`S-n = ... depends_on = ...`); `validate` checks the numbering and dependency graph; slices stay outside the frozen approval fingerprint, so re-slicing never needs re-approval; `First vertical slice` is replaced by that section.
- The closing question is asked in the same turn as the Ready-to-build ask, always, even for a one-slice feature; answers are recorded in the brief's Risk and rollback rows (`tickets = local|github|jira|azdo|none`), never in the frozen sections.
- Only trackers that pass a live probe right then are offered: `gh auth status` for GitHub, one authenticated GET for Jira and Azure; a failed probe lists the exact missing variable or login step instead of the option.
- Hierarchy = brief → epic, slice → story, ticket → task; the adapter contract keeps four operations, and `create-ticket` gains `kind` and `parent`; GitHub = parent issue + `gh issue create --parent` sub-issues + `--blocked-by`; Jira = Epic issue + Story with `parent`; Azure = Epic → Feature → User Story with a hierarchy link.
- Credentials come only from the environment or the checkout's `.env`: `JIRA_SITE`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT`; `AZDO_ORG`, `AZDO_PROJECT`, `AZDO_PAT`; `GITHUB_REPOSITORY` for GitHub; `hard-eng prepare` writes the names into `.env.example` and the feature setup env question offers `.env`; token values never enter receipts, plan files, logs, or tracker bodies.
- Every ticket and epic item is self-contained for a fresh agent: goal, why it exists, exact depends_on with what those deliver, files it may touch, acceptance examples it covers, definition of done, proof to run, and the claim + build prompt; the same text goes into the tracker body so GitHub, Jira, or Azure show the full instruction, not a title.
- Handoff = printed by `plan_state.py inspect` whenever status is `build-ready`: repository root, branch, plan path, and a prompt; in ticket mode one prompt per claimable ticket with its claim command; no new lifecycle state.
- Planning method is fixed and machine-checked: `plan_state.py` gains `record-step` for `code-study`, `research`, `edge-scan`, `decisions`, `slices`, `closing`; each writes `features/<slug>/receipts/plan-steps.json` bound to the plan id and HEAD; `validate` prints `plan_steps=<done>/<required>` and `approve` refuses with the first missing step; the decision inventory receipt lists every decision with status settled|user-decision|deferred|out-of-scope and who settled it; the edge-scan receipt has one line per axis (actors, empty/error/retry, data lifecycle, delivery form, external/concurrency, accessibility, rollout/rollback) with hit or none.
- ux_reference = n/a
- ux_reference_sources = n/a

## Acceptance examples
- Given a complete brief with three independent slices, when the plan owner asks for approval, then the same message asks split-or-not and lists only trackers whose probe passed, and after a plain yes `inspect` prints a handoff block with root, branch, plan path, and a build prompt.
- Given `tickets = github` and `gh` logged in, when decompose runs, then one epic issue and one sub-issue per story exist, blocked-by links match `depends_on`, each body holds goal, dependencies, touches, acceptance, done rule, and build prompt, and each ticket file records its `tracker_ref`.
- Given `tickets = jira` and a `.env` with the four Jira values, when decompose runs, then an Epic and child Stories exist in that project and the ticket files record their keys.
- Given `tickets = azdo` and a `.env` with the three Azure values, when decompose runs, then an Epic, one Feature, and child User Stories exist with hierarchy links.
- Given a missing `JIRA_API_TOKEN`, when the closing question is built, then Jira is not offered and the message names `JIRA_API_TOKEN` as the missing value.
- Given a brief with no decision inventory receipt, when `approve` runs, then it refuses naming `decisions` as the missing step, and after `record-step decisions` with every decision settled it passes.
- Given a brief whose slices contain a dependency loop, when `validate` runs, then it fails naming the loop.

## Affected canonical areas
- `skills/he/scripts/plan_state.py` + `plan_sections.py` + `plan_template.py` (slices section, validation, handoff output, closing-answer rows).
- `skills/he/scripts/ticket_decompose.py` + `ticket_state.py` + `tracker_github.py` + new `tracker_jira.py` + `tracker_azdo.py` + `tracker_probe.py`.
- `skills/he-plan/SKILL.md` + `references/feature-brief.md`; `skills/he/SKILL.md` + `references/tracker-adapter.md` + `references/tickets.md`; `runtime` prepare for `.env.example`; regression scripts beside each script; `PRODUCT.md`.

## Risk and rollback
- risk_level = critical
- critical_overlay = S-4 + S-5 + S-6 credential handling: tokens read only from env/.env, redacted in every output, one negative test per adapter proving a token never lands in a file or log
- rollback = remove the `tracker` key from `hard-eng.gates.json`; local ticket files stay the truth, so remote items can be closed by hand.
- deferred = Azure parent-link relation name; sharpens on the work-item update page during S-6.
- blocked_on = none

## Vertical slices
- S-1 = plan-step receipts (`record-step`, `plan_steps` in validate, approve refusal) + he-plan skill rewritten as a numbered method + handoff block printed by `inspect` at `build-ready` in single and ticket mode; depends_on = none
- proof = regression covering missing, stale-HEAD, complete receipts, and the handoff output on a fixture plan.
- S-2 = `Vertical slices` section + graph validation + closing question rows + plan skill docs; depends_on = none
- proof = validator regression with loop and gap cases.
- S-3 = tracker probe + credential names + `.env.example` writing + closing question offers only live trackers; depends_on = S-2
- proof = probe regression with missing variable cases.
- S-4 = GitHub epic + sub-issues + blocked-by through `gh` with self-contained bodies; depends_on = S-3
- proof = adapter regression against a fake `gh` on PATH.
- S-5 = Jira Cloud adapter; depends_on = S-3
- proof = adapter regression against a local HTTP stub + redaction test.
- S-6 = Azure DevOps adapter; depends_on = S-3
- proof = adapter regression against a local HTTP stub + redaction test.
