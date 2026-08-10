# Visual Evidence

## Boundary

- Canonical owner = this file.
- Applicability = screenshot/video requested OR produced as proof.
- Judgment gate = reviewer inspects actual media; semantics cannot be delegated to a validator.
- Reviewer = isolated media reader (depth-1 subagent when available, else dedicated bounded session); output = Review Receipt fields + verdict; parent context receives receipt + `path + sha256` only.
- Unchanged `sha256` + current-schema same-target receipt PASS = no re-inspection; changed bytes/target → new review.
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

- Default retention = local lifecycle evidence + final display/link; Git delivery = forbidden unless user explicitly accepts the media as a product asset.
- `binding.revision` = artifact/source revision; every artifact revision must match it.
- `repository_snapshot_id` = parent-owned exact repository snapshot; it is not `binding.revision`.
- Exact-artifact provenance = repository snapshot + source revision + current successful attempt + digest equality + receipt PASS + actual-media inspection PASS.
- Tracked receipt inside the snapshot cannot embed/equal that snapshot hash; parent provenance supplies it after receipt validation.
- `successful_test_attempt=true` + exact attempt binding required.
- Missing/unreadable/undecodable/stale/wrong-attempt/digest-mismatch artifact → FAIL.
- Validator = full media decode + metadata/digest/binding/receipt/status checks.
- Missing `ffmpeg`/`ffprobe` when media validation applies → FAIL.
- Validator PASS = mechanical completeness only; visual meaning still requires judgment gate PASS.

## Proof Target

- Before capture/reuse = current request → one `proof_target.id + surface + visible_claims + forbidden_visible_states`.
- Claim text exists once in `proof_target.visible_claims`; artifacts + review frames reference claim IDs.
- Runner = assert the target state immediately before capture; unrelated earlier/later state ≠ proof.
- Artifact + review `proof_target_id` must match; reviewer receives the target + records `subject_match + observed_subject` from actual media.
- Unchanged digest + receipt reuse = valid only for the same target; related feature/scenario ≠ same visible subject.
- `visual.delivery_artifact_sha256s` = exact reviewed artifacts intended for the final response; every target claim must be covered by that set.
- Final response = attach only delivery-listed digests using their receipt paths; unlisted/path-swapped/unreviewed media → FAIL.
- Runtime cost = target/delivery schema checks only; no visual path → no receipt, reviewer, media decode, or added gate.

## Review Receipt

Each artifact review records:

- exact proof target + actual visible subject + subject-match verdict;
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
- Final handoff = delivery-listed media attached/linked from exact receipt paths; omitted/substituted media = incomplete.
