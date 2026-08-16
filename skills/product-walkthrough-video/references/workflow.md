# Canonical workflow

## Modes

| Mode | Purpose | Allowed terminal point |
|---|---|---|
| `preview` | Low-cost silent/caption draft + camera/cursor proof | `qa` receipt + user review request |
| `production` | Approved narration + final render | accepted media + closed coverage |

## Default delivery

- Scope default = essential happy path; comprehensive state inventory requires explicit request.
- Sequence = brand welcome + requested successful actions + help/escalation + supportive close.
- Omit = errors + loading + unavailable/admin/staff/edge states + internal implementation terms unless requested.
- Copy = friendly + concrete + client-facing; describe what to choose + what happens next.
- Discovery/storyboard/source review = parallel where owners are independent; job mutation + browser/server + provider + final render = one owner.

## Stages

| Stage | Action | Checkable exit |
|---|---|---|
| Discovery | Inspect actual UI owners + enumerate user-requested inclusion predicate + classify exclusions | ledger has unique promised-outcome IDs + evidence owner + planned disposition |
| Scenario | Define deterministic synthetic auth/data + intercepted writes + blocked external navigation | safety contract = all false for production data/PII/mutations/uploads/external links |
| Storyboard | Bind every scene to real route/state/locator/action/result + camera/caption/narration | scene validator PASS + required coverage IDs mapped |
| Script approval | Show exact narration + voice/model/settings + chapter characters/credits + external effect | user approval receipt bound to exact job/script hashes |
| Capture | Prove one smoke scene → run resumable scene shards with deliberate cursor/click/camera actions | attempt binding + execution-boundary classification + ordered source manifest + capture receipt + source/failure media hashes |
| Narration | `captions-only` skip + supplied recording import + approved ElevenLabs per-chapter cache | verified sidecar request/audio/format identity + ordered chapter hashes + no secret output; failure stops retry authority |
| Render | Compose capture + captions + approved audio + chapter holds | decodable local MP4 + ffprobe receipt |
| QA | Start canonical `e2e` judgment + `deterministic-checks` mechanical media/schema/hash gates in parallel after final-media hash | isolated review receipt PASS + validator PASS for legibility/framing/motion/cursor/timing/clipping/loading/sync/audio/privacy/coverage |
| Review | Show local draft + request focused user review + loop only on accepted feedback | explicit final acceptance + zero open ledger IDs |

## Invocation

- Explicit agent invocation = `product-walkthrough-video` + absolute project job path.
- Deterministic invocation = `python3 -B scripts/run_workflow.py validate --job /absolute/job.json` → `run --phase ...`.
- Generic media invocation = `python3 -B scripts/media_pipeline.py validate --job /absolute/job.json` → phase preflight → approved narration → render → QA.
- Receipt = skill path/hash + job path/hash + attempt ID/root/binding + mode + phase + success/failure evidence hashes + separate safety declaration + measured execution boundary.
- Project command = approved absolute executable hash + typed exact argv + project-contained cwd/evidence + synthetic endpoints + runner-owned environment; shell strings/job env forbidden.
- Declarative containment = visibly unenforced; enforced-local containment = supported backend proof + network deny + artifact-root-only writes; unsupported host = FAIL without downgrade.
- Project phases through `qa` = exact current job path in argv; actor derives current attempt/package/approval owners from it; literal attempt-specific paths in reusable actor source forbidden.
- Reusable project kit = coverage ledger + scene manifest + media manifest + brand sources + successful synthetic clips; failed-attempt adapters/receipts/raw media stay outside canonical source.

## Preview exception

- Preview may omit script approval + narration only when job mode = `preview`.
- Preview media = visibly draft/silent or captions-only + never reusable as paid approval evidence.
- Production capture = fixed order + exact script approval before capture.

## Capture isolation

- Local synthetic/capture route = third-party analytics + telemetry disabled at the canonical product owner before browser capture.
- Any observed external request = blocked + fatal; provider/domain allowlists are forbidden.
- Exact local dev/HMR socket = source-proven + classified separately; every other socket = blocked + fatal.
- Declared synthetic non-2xx response = fixture-owned expected event; classify by method + path + status without reading/persisting body + headers + cookies.

## Fast readiness + reuse

- Before full capture = current-job validate + all non-paid prerequisites + fixture-contract checks + telemetry suppression proof + installed browser/FFmpeg capability probe.
- Before paid narration = current-job/package/approval hash chain + account-accessible voice proof + zero-provider actor dry preflight.
- Smoke = one representative scene through ready/action/result/cleanup; success unlocks remaining capture.
- Scene output = write-once media + content hash + ordered source manifest; resume with a new attempt that adopts hash-proven sources.
- Terminal failure after complete valid media = preserve failure truth + classify the exact final predicate + create non-native adoption receipt; recapture/rerender forbidden when source set + safety proof are complete.
- Independent final checks = mechanical decode/silence/contact-sheet + isolated visual/audio review launch together.

## Failure + review route

- Project command nonzero = actor receipt or runner-owned generic [sanitized failure evidence](job-contract.md#attempt--failure-evidence) before phase receipt; discarded stdout/stderr is never the diagnostic owner.
- Failed attempt = immutable receipt + media/hash + cleanup + approach fingerprint + original violation.
- Media exists = exactly one isolated depth-1 reviewer through `e2e` when available; fallback = dedicated bounded review session.
- Reviewer deadline = reserve finalization time + write PASS/CONCERNS/FAIL receipt from gathered evidence before timeout; missing receipt = CONCERNS, never inferred PASS.
- Mechanically green draft may be shown for user review while review receipt is CONCERNS; acceptance does not convert missing visual evidence into PASS.
- Parent context = canonical review receipt + artifact binding only; raw frames stay in reviewer scope.
- Retry = `deterministic-checks` retry-readiness + trace-first/no-recording sentinel when cause is unknown + exact fresh approval + new attempt root/job/hash.
- Diagnostic + corrected recording under unknown cause = forbidden.

## Completion

- Skill package validator PASS + forward proof receipt.
- Project job/scene validation PASS + all phase receipts current for exact hashes.
- Canonical `e2e` actual-media receipt PASS + user acceptance.
- Requested-outcome ledger terminal + zero `Unknown` + zero unaccounted promised IDs; excluded product states stay excluded.
