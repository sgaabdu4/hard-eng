# Marketing video skill

Status: Draft

## Outcome + scope

Add an explicit-only `marketing-video` skill that turns real product screens into a voiced, branded marketing or explainer video: script, screens from recordings or from app screenshots over made-up data (cursor, click, zoom), voice takes + transcription-based picking, deterministic GSAP render with diagrams and optional subtitles, music mix and review. Installed repositories receive it through the existing skill sync. No product-specific content, no new gates, no changes to other skills.

## Repository context

Owners: `.agents/skills/marketing-video/` (new). Lessons come from two user-approved videos: a partnership marketing video cut from recordings, and a staff explainer built from staged screenshots. Footage comes from the existing `.agents/skills/product-walkthrough-video/` recordings. `setup.py` already ships every `.agents/skills` folder; Biome, skill-link, deptry and gitleaks gates already cover skill packages.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User asked for this skill in hard-eng, tested by Codex (`gpt-6-luna`, max reasoning) on other products, iterated until it works. Local branch commit only; no push or PR without asking.

## Acceptance + steps

- [x] Recordings route runs end to end on a disposable work folder: clips → takes → pick → build → stills → render → mix → audit → mix transcript.
- [x] Staged-screenshot route runs end to end with groups, manifest targets, cursor clicks, zooms, flow and loop diagrams, subtitles, crossfades, backdrop and quiet music.
- [x] Mix keeps quiet music quiet: linear gain to −14 LUFS instead of dynamic loudnorm (music-only gaps sat ~5 dB under the voice before, ~10 dB after, same track and volume).
- [x] Guidance carries lessons from both videos without contradicting either: sample voice first, approved voice settings, plain name spelling, hand-placed zoom that keeps its box in frame, hard cuts or quick crossfades, sign-in only when access is the lesson, plain wording, private data never shown, real logos, copy approved designs, freeze approved parts, music licence stated.
- [x] Skill text holds no product, customer or backend names (`git grep` on the package is empty).
- [ ] A fresh Codex `gpt-6-luna` run at max reasoning, given only the skill + a different product's footage, produces a video that passes the completion gate; failures feed back into the skill.
- [ ] Biome, skill-link test and the full `hard-eng.py check` pass.

## Baseline + execution

Result: Passed
Evidence: `uv run python .hooks/hard-eng.py check --plan-stage Draft` with the new package moved aside exited 0; 18/18 gates passed.
Execution: One builder (this session). Codex runs as an independent tester in a scratch folder; product repositories are read-only inputs.

## Risks + recovery

Voice quality and pronunciation cannot be judged by an agent; the skill makes the human's listen a required step. Chatterbox and Whisper model downloads need network on first use. Recovery: remove the package folder; nothing else changes.

## ux_reference

N/A — skill guidance and scripts; the rendered video is the user's product output, reviewed through the skill's own audit.

## Verification

Result: Pending
Evidence: Pending
E2E: Required — Codex full run on another product through the skill's commands, final MP4 audited.
