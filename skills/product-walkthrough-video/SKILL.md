---
name: product-walkthrough-video
description: Product walkthrough video workflow for fast, safe, deterministic happy-path captures of real UI with scoped coverage and actual-media QA. Use only when a user explicitly invokes product-walkthrough-video for walkthrough production or revision.
disable-model-invocation: true
---

# Product Walkthrough Video

## Contract

- Invocation = explicit human selection only; ask scope: `essential happy path | comprehensive` + narration: `captions only | ElevenLabs narrator | supplied human recording`.
- Owner = reusable orchestration + generic narration/render/QA actors + safety gates + receipts; project repository owns product facts + synthetic data + scene/media manifests + branded source visuals.
- Workflow = [canonical stages](references/workflow.md) + [job/scene contract](references/job-contract.md) + [narration security](references/narration-security.md).
- Runner = [run_workflow.py](scripts/run_workflow.py); no shell + no install + no retry + no hidden network call + immutable attempt/phase receipts.
- Regression = [run_workflow_regression_check.py](scripts/run_workflow_regression_check.py); current-job binding + attempt binding + failure-evidence red/green fixtures.
- Capture helpers = [playwright_capture.mjs](scripts/playwright_capture.mjs); project supplies product locators + synthetic routes.
- Media helpers = [media_pipeline.py](scripts/media_pipeline.py) + [media_manifest.py](scripts/media_manifest.py); one project media manifest drives cached ElevenLabs narration + silence-trimmed FFmpeg render + mechanical QA.
- Output = project-owned local artifacts + phase receipts + actual-media receipt + user review loop.

## Invariants

- UI = actual product owners; second UI only after an evidenced impossibility + explicit scope decision.
- Data = deterministic synthetic only + zero production data + zero client PII + zero production credential/token.
- Actions = local interception/read-only simulation; no production mutation + no real meeting/session link open.
- Default cut = friendly branded opening → requested successful actions → help/escalation → supportive close.
- Default exclusions = error/loading/admin/staff/edge states + implementation jargon unless explicitly requested.
- Coverage = enumerate the user-requested inclusion predicate → ledger only promised outcomes + explicit exclusions → zero unaccounted promises at final.
- Scene SSOT = route/state + locator + action + expected result + duration/hold + camera/zoom + caption + narration + coverage IDs + safety mode.
- Binding = every project phase through `qa` receives the exact current job path; attempt/package/approval paths derive from that job + never from a literal prior-attempt slug.
- Fast readiness = full non-paid current-job chain + zero-provider narration preflight + one representative browser smoke before full capture or paid narration.
- Reuse = successful scene/audio/render artifacts are content-hashed + attempt-owned + adoptable by a new immutable attempt; never repeat proven media after a later terminal failure.
- Browser = exact local dev socket + declared synthetic API responses classified; every other socket/request remains blocked + fatal; request body/header/cookie material stays unread.
- External = current primary-source research + explicit dependency decision before install/use.
- Voice = query the account-accessible inventory before approval; bind a current-tier voice + model + settings.
- Paid narration = exact script + voice/model/settings + chapter split + character/credit impact + external effect → explicit approval immediately before request.
- Paid failure = stop; changed/retried external attempt requires fresh approval.
- Secret source = user-selected generic Keychain item or explicitly selected project-owned ignored/untracked `.env.local`; probe presence without value + retrieve only in narration-process memory; never argument/chat/log/artifact/hash/commit.
- Failure = actor writes detailed sanitized receipt; missing actor receipt → runner writes generic sanitized fallback → validates/hashes → stop; changed execution = new attempt root + job/hash.
- Native/paid/external retry = media evidence → `e2e` isolated review when present → `deterministic-checks` retry-readiness → trace-first sentinel when needed → exact fresh approval → corrected recording.
- Render = generic actor resolves/probes installed FFmpeg/FFprobe + derives duration from narration/scene outputs + trims leading/trailing silence only + preserves natural internal speech pauses + uses short deliberate transitions + retimes visuals instead of padding dead air.
- Media = quick preview first → mechanical QA + canonical `e2e` review in parallel after final hash; bounded reviewer must persist a terminal receipt → user review → iterate.
- Delivery = local file only until separate publish/upload/send approval.

## Route

1. Read all three references.
2. Freeze the smallest essential happy-path ledger + scene manifest unless comprehensive scope was requested.
3. Validate the exact job + non-paid chain + capability probes; run one representative smoke.
4. Capture resumable scene shards; reuse/adopt every hash-proven success.
5. Pause at the exact paid narration gate when ElevenLabs is selected.
6. Run changed narration chapters once with the generic media actor → render once → mechanical QA + isolated review in parallel → user review.
7. Complete only after skill validation + accepted media + closed requested-outcome ledger.
