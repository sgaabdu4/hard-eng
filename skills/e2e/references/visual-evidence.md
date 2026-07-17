# Visual Evidence

## Boundary

- Canonical owner = this file.
- Applicability = screenshot/video requested OR produced as proof.
- Judgment gate = reviewer inspects actual media; semantics cannot be delegated to a validator.
- Mechanical gate = `python3 skills/e2e/scripts/visual_evidence.py --repo <root> --receipt <receipt>`.
- Template = [visual-review-receipt.template.json](../assets/visual-review-receipt.template.json).
- Executable examples = `scripts/visual_evidence_regression_check.py`.

## Evidence Classes

| Class | Proves | Cannot prove |
|---|---|---|
| automated | runner assertions | persisted/deployed/visual truth |
| persisted_state | durable owner read-back | UI/deployment truth |
| deployment | expected revision + environment | behavior/visual truth |
| visual | actual user-visible artifact | hidden persisted state |

- Class PASS ≠ another class PASS.
- Overall PASS = every required class PASS.
- Conflict = preserve both facts → overall FAIL → investigate artifact provenance.
- Runner exit + manifest/JSON claim + existence/filename + generated screenshot + recording-enabled assertion ≠ visual review.

## Artifact Binding

Each artifact → exact `path + sha256 + duration|dimensions + revision + environment + scenario_id + run_id + attempt_id + device|viewport`.

- `binding.revision` = artifact/source revision; every artifact revision must match it.
- Hard Eng `snapshot_id` = parent-owned repository snapshot; it is not `binding.revision`.
- Tracked receipt inside snapshot → embedding/equality with that snapshot hash = self-reference → forbidden.
- Exact-snapshot provenance = parent snapshot + current successful attempt + digest equality + receipt PASS + actual-media inspection PASS.
- Parent tuple = validator `--repository-snapshot <sha256:...>` output; never write it into the tracked receipt.
- `successful_test_attempt=true` + exact attempt binding required.
- Missing/unreadable/undecodable/stale/wrong-attempt/digest-mismatch artifact → FAIL.
- Validator = full media decode + metadata/digest/binding/receipt/status checks.
- Missing `ffmpeg`/`ffprobe` when media validation applies → FAIL.
- Validator PASS = mechanical completeness only; visual meaning still requires judgment gate PASS.

## Review Receipt

Each artifact review records:

- required user-visible steps → exact timestamp or frame evidence;
- observed start + final states;
- authentication/error screens;
- irrelevant/stalled/loading sections;
- overflow + clipping + spacing + responsive findings;
- reviewer conclusion.

Video review = full timeline + start/end + every required transition + samples ≤10s apart + continuous playback declaration.

- Short success segment never excuses failed/stalled/login/loading/error/irrelevant time.
- Login/loading/error-only OR partial workflow → visual FAIL.
- “watched”/“visually verified”/“production E2E passed” claim without actual media inspection = forbidden.

## Status

| Evidence | Overall |
|---|---|
| automated PASS + visual NOT_REVIEWED | CONCERNS |
| automated PASS + visual contradiction | FAIL |
| requested artifact missing/unreadable/stale/wrong attempt | FAIL |
| visual login/loading/error only | FAIL |
| required workflow partially visible | FAIL |
| every required class PASS | PASS |

- Required receipt absent/invalid/non-PASS → goal/build/ship/final PASS blocked.
- Completion owner consumes validator exit `0`; prose/manifest PASS cannot override nonzero.
