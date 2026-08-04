# Job + scene contract

## Job JSON

| Field | Contract |
|---|---|
| `schema_version` | integer `1` |
| `mode` | `preview` or `production` |
| `project.name` | non-empty display name |
| `project.root` | absolute repository path |
| `artifacts.root` | absolute attempt-owned path inside project root; basename = stable attempt ID |
| `artifacts.receipts` | absolute path inside artifact root |
| `coverage_ledger` | absolute project-owned Markdown ledger |
| `scene_manifest` | absolute project-owned JSON manifest |
| `media_manifest` | absolute project-owned JSON manifest when the generic narration/render/QA actor is used |
| `required_coverage_ids` | unique non-empty IDs present in ledger + scene manifest |
| `narration.mode` | `captions-only`, `elevenlabs`, or `supplied-human` |
| `safety` | exact zero-production boundary below |
| `phases` | phase map; each command = absolute argv + project-contained cwd + evidence paths |

## Generic media JSON

| Field | Contract |
|---|---|
| `schema_version` | integer `1` |
| `cache_dir` | project-relative ignored artifact/cache directory |
| `narration` | exact voice ID/name + model + settings + one explicit credential source |
| `render` | FFmpeg/FFprobe executable name or absolute path + H.264/AAC dimensions/rate/trim settings |
| `qa` | sample grid + maximum start/end/scene-boundary silence |
| `chapters` | ordered `id + exact text + visual` rows matching scene IDs/narration |

### Visual row

| Field | Contract |
|---|---|
| `kind` | `image` or `video` |
| `path` | project-relative regular source file |
| `sha256` | exact source hash |
| `minimum_duration_seconds` | non-negative client reading floor |
| `trim_start_seconds` | non-negative video start; image = `0` |

- Generic actor = `python3 -B scripts/media_pipeline.py <validate|preflight|narration|render|qa> --job <absolute-job>`.
- Narration = `--approval <absolute-receipt>` + exact current job/ordered-chapter-script/settings/characters binding.
- Cache key = exact text + voice + model + settings; cache hit = zero key read + zero provider request.
- Render mapping = only current narration audio + project source visual; old/source audio stays unmapped.
- Silence = trim leading/trailing chapter audio only; preserve internal speech pauses; QA rejects excessive start/end/chapter-boundary silence.
- Executable name = resolve through current PATH at validation; receipt/runtime uses exact resolved path.

## Safety JSON

```json
{
  "data_source": "synthetic-only",
  "allow_production_data": false,
  "allow_client_pii": false,
  "allow_production_credentials": false,
  "allow_production_mutation": false,
  "allow_external_session_links": false,
  "allow_upload": false
}
```

## Scene JSON

| Field | Contract |
|---|---|
| `id` | unique stable scene ID |
| `coverage_ids` | non-empty ledger ID list |
| `chapter` | client-facing chapter label |
| `route_state` | route + deterministic state |
| `target_locator` | stable role/label/test-id locator |
| `action` | one visible client action |
| `expected_result` | visible check after action |
| `duration_seconds` | positive planned duration |
| `hold_seconds` | non-negative reading hold |
| `camera_target` | element/region framing target |
| `zoom` | numeric value from `1` through `2.5` |
| `caption` | exact on-screen caption or empty string |
| `narration` | exact chapter text or empty string for silent preview |
| `safety_mode` | `synthetic-read-only` or `synthetic-intercepted-write` |

## Phase rules

- Preview order = discovery → scenario → storyboard → capture → render → qa.
- Production order = discovery → scenario → storyboard → script-approval → capture → narration → render → qa → review.
- `argv[0]` = absolute executable; no shell + no command string + no job-provided environment.
- Discovery through QA argv = exact resolved current job path; reusable project actors derive attempt/package/approval owners from current job + reject stale bindings.
- Evidence = regular file created/verified by phase command + project-contained path + SHA-256 receipt.
- Narration external effect = `paid`; every other phase = `none`.
- Runner binds `artifacts.root/attempt.json` to attempt ID + artifact root + exact job path/hash before execution.
- Target phase receipt + `<phase>-failure.json` must be absent before execution.
- Project actor nonzero = write detailed `artifacts.root/<phase>-failure.json` before exit.
- Missing actor receipt after nonzero = runner writes one generic sanitized receipt at the same path; invalid actor receipt stays immutable + FAIL.
- Runner validates/hashes failure evidence + writes one immutable phase receipt; phase remains FAIL.
- Existing attempt/phase/failure receipt = immutable; changed execution requires a new artifact root + job path/hash.
- Runner never retries a failed phase.
- Capture evidence may adopt ordered immutable scene media from prior failed attempts only through a new attempt-owned assembly receipt binding every source path/hash/bytes + prior failure receipt + safety classifier.
- Actor-declared expected synthetic non-2xx responses = exact method/path/status only; request body/header/cookie access + persistence forbidden.
- Render duration = derived from current scene/audio outputs + codec/container tolerance; fixed guessed final-duration windows forbidden.

## Attempt + failure evidence

| Field | Contract |
|---|---|
| `schema_version` | integer `1` |
| `attempt_id` + `phase` + `status` | artifact-root basename + current phase + `fail` |
| `last_completed_step_id` | stable ID or `null` |
| `failing_step_id` | stable non-empty ID |
| `error` | exact `type + message`; bounded redacted single-line strings |
| `same_origin_requests` | bounded `method + path + status`; path only, no origin/query |
| `page_errors` + `console_errors` | bounded `type + message` lists |
| `request_failures` | bounded `method + path + type + message` list |
| `server_logs` | at most 20 bounded redacted single lines |
| `cleanup` | non-empty `actor + status`; status = `not-started`, `closed`, `stopped`, or `failed` |
| `approach_fingerprint` + `original_violation` | bounded non-empty strings |
| `artifacts` | failed media/evidence absolute path + SHA-256 + bytes; each path inside attempt root |

- Exact fields only; stack + query + body + headers + cookies + secret values = omitted.
- Failure receipt ≤256 KiB; messages/log lines ≤512 characters; event/request lists ≤50; artifacts ≤20.
- Generic runner fallback = stable `<phase>.actor|evidence` step + bounded exit/runner error + explicit actor cleanup + empty runtime-event/artifact lists; raw actor output omitted.
- Parent/reviewer consumes receipt path/hash + canonical `e2e` artifact binding; raw media stays outside parent context.
