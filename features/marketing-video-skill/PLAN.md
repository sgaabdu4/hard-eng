# Marketing video skill

Status: Complete

## Outcome + scope

Add an explicit-only `marketing-video` skill that turns real product screens into a voiced, branded marketing or explainer video: script, screens from recordings or from app screenshots over made-up data (cursor, click, zoom), voice takes + transcription-based picking, deterministic GSAP render with diagrams and optional subtitles, music mix and review. Installed repositories receive it through the existing skill sync. No product-specific content (template colours are a neutral default), no new gates, no changes to other skills. The gate run surfaced one Hard Eng defect, fixed as its own commit: a GitHub response cut short crashed session start instead of reporting a failed update.

## Repository context

Owners: `.agents/skills/marketing-video/` (new). Lessons come from two user-approved videos: a partnership marketing video cut from recordings, and a staff explainer built from staged screenshots. Footage comes from the existing `.agents/skills/product-walkthrough-video/` recordings. `setup.py` already ships every `.agents/skills` folder; Biome, skill-link, deptry and gitleaks gates already cover skill packages.

## Decisions + authorization

Blockers: None
Authority: User asked for this skill in hard-eng, tested by Codex (`gpt-6-luna`, max reasoning) on other products, iterated until it works, then asked to fix all findings and open a PR. No merge without asking.

## Acceptance + steps

- [x] Recordings route runs end to end on a disposable work folder: clips → takes → pick → build → stills → render → mix → audit → mix transcript.
- [x] Staged-screenshot route runs end to end with groups, manifest targets, cursor clicks, zooms, flow and loop diagrams, subtitles, crossfades, backdrop and quiet music.
- [x] Mix keeps quiet music quiet: linear gain to −14 LUFS instead of dynamic loudnorm (music-only gaps sat ~5 dB under the voice before, ~10 dB after, same track and volume).
- [x] Guidance carries lessons from both videos without contradicting either: sample voice first, approved voice settings, plain name spelling, hand-placed zoom that keeps its box in frame, hard cuts or quick crossfades, sign-in only when access is the lesson, plain wording, private data never shown, real logos, copy approved designs, freeze approved parts, music licence stated.
- [x] Skill text holds no product, customer or backend names (`git grep` on the package is empty).
- [x] A fresh Codex `gpt-6-luna` run at max reasoning, given only the skill + a different product's footage, produces a video that passes the completion gate; failures feed back into the skill.
- [x] Routed layout: an agent given a recordings task loads `SKILL.md` + only the setup, script, recordings, voice and render references.
- [x] A cut-short GitHub response surfaces as a failed update (`OSError`), proven by the existing release-lookup test; the handoff test no longer reaches the network.
- [x] Biome, skill-link test and the full `hard-eng.py check` pass.

## Baseline + execution

Result: Passed
Evidence: `uv run python .hooks/hard-eng.py check --plan-stage Draft` with the new package moved aside exited 0; 18/18 gates passed.
Execution: One builder (this session). Codex runs as an independent tester in a scratch folder; product repositories are read-only inputs.

## Risks + recovery

Voice quality and pronunciation cannot be judged by an agent; the skill makes the human's listen a required step. Chatterbox and Whisper model downloads need network on first use. Recovery: remove the package folder; nothing else changes.

## ux_reference

N/A — skill guidance and scripts; the rendered video is the user's product output, reviewed through the skill's own audit.

## Verification

Result: Passed
Evidence: Three unattended Codex `gpt-6-luna` max-reasoning runs on a different product (a lettings portal), each delivering a draft with every machine-checkable gate item passed and human approval marked pending: (1) recordings route, 93 s; (2) staged screenshots from a running prototype, 122 s; (3) routed skill, recordings, 82 s, reading only the five matching references. Findings fixed in the skill: tall-phone layout, stale-clip refusal, long text scenes flagged, display weight, render template copied by `build.mjs`, capture waits for late images, kicker-less intro, scripts run from any directory, short-video shape, no repeated steps, unattended drafts never called complete. `hard-eng.py check --plan-stage Draft` exit 0, 18/18.
E2E: Passed — three Codex full runs on another product through the skill's commands, each final MP4 audited (sheets + stills + mix transcript).

Delivery target: PR
Delivery: Pending — PR checks.
