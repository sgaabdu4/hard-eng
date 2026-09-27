# Marketing video workflow

Workflow owner for the bundled clip, voice, build, render, mix and audit scripts. Run commands from this package directory. Reuse the existing runtime when available; install missing dependencies only within task authorization.

## Setup

```bash
cd /absolute/path/to/marketing-video
pnpm install --frozen-lockfile --ignore-scripts
pnpm exec playwright install chromium
brew install ffmpeg
```

On Linux, install FFmpeg with `sudo apt-get install -y ffmpeg` instead of Homebrew.

Voice + transcription run in their own Python environments, outside every repository. Reuse existing ones when the machine has them.

```bash
uv venv --python 3.11 ~/.cache/marketing-video-tts
uv pip install --python ~/.cache/marketing-video-tts/bin/python chatterbox-tts
export TTS_PYTHON=~/.cache/marketing-video-tts/bin/python
uv tool install mlx-whisper
```

- Chatterbox downloads its model weights from Hugging Face on first use. It runs on Apple GPU, CUDA or CPU.
- `mlx-whisper` needs Apple Silicon. Elsewhere: `uv tool install openai-whisper` and `export WHISPER_BIN=whisper`. `WHISPER_BIN` may also point at an existing `mlx_whisper` executable.
- Agent sandboxes that hide the GPU or block browser launch (for example Codex `workspace-write` on macOS) cannot run `takes.mjs`, `pick.mjs` or `render.mjs`. Request an unsandboxed run for those commands; with model weights already downloaded, also set `HF_HUB_OFFLINE=1`.

## Work folder

Keep one folder per video, outside this skill and out of version control (it holds footage, audio and renders).

| Path | Owner | Content |
| --- | --- | --- |
| `storyboard.json` | you | Brand, options and scenes; shape in [assets/storyboard.example.json](assets/storyboard.example.json) |
| `lines.json` | you | `[["01", "Voice line"], …]`; keys are scene ids, a scene's `line`, or a group's `line` |
| `brand/` | brand owner | Display font file (+ optional body font), logo files `a` (+ partner `b`) |
| `footage/` | recordings | Source MP4s of real product journeys (recordings route) |
| `shots/` | staging | Screen PNGs + optional `manifest.json` of named target boxes (staged route) |
| `music/` | human | Licensed music track |
| `render/` | template | `cp -R assets/template/. <work>/render/` once; customise only for approved designs |
| `clips/ vo/ audio/ out/ stills/ audit/` | scripts | Generated |

```bash
node scripts/clips.mjs <work>
node scripts/takes.mjs <work> [ids] [first-seed]
node scripts/pick.mjs <work>
node scripts/build.mjs <work>
node scripts/render.mjs <work> --stills 3 12.5
node scripts/render.mjs <work> <work>/out/silent.mp4
node scripts/mix.mjs <work> <work>/music/track.mp3 <work>/out/silent.mp4 <work>/out/final.mp4
node scripts/audit.mjs <work>/out/final.mp4 <work>/audit
node scripts/pick.mjs <work> <work>/out/final.mp4
```

`clips.mjs` is only for the recordings route. `build.mjs` runs before any voice exists and times missing lines by estimate, so layout can be checked first. The last command transcribes only the voiced spans of the finished mix, so music-only stretches cannot produce invented text.

## 1. Brief and inputs

Collect before writing anything:

- audience and goal: buyers (marketing, default 2–2.5 min) or users learning the product (explainer, as long as covering every function needs, typically 3–4 min);
- where it will be shown, and whether it must work with the sound off (then turn on subtitles);
- brand owner's display font file, logo files for every party, colours;
- an approved design source for explanatory graphics (deck, website section);
- screens: recordings of the real journeys, or a way to render the app over made-up data (see [3. Screens](#3-screens));
- the product's own claims (deck, site, docs); the script may say nothing they do not support;
- music: the human picks or supplies a track and accepts its licence, and says how loud ("very light" ≈ `music.volume` 0.12; default 0.42). Never lift a track from another project's folder. If the licence is unknown, say so in the delivery note. The agent never accepts terms or ticks licence attestations.

## 2. Script

Scene types:

| Type | Fields | Use |
| --- | --- | --- |
| `intro` | `title` + `kicker` (one brand) or none (logo `a` × `b`) | Opening |
| `statement` | `title`, optional `sub`, `cards` `[{tag, text}]`, `bands` | Problem, offer, why |
| `title` | `text`, optional `card: true` + `kicker` | Bridge or section title |
| `app` | `num`, `label`, optional `who`, and `clips` or `groups` | One chapter per journey |
| `flow` | `text`, `nodes` `[{name, note, hero, logo, rows, badge}]` | How data or work moves (2–4 nodes) |
| `loop` | `text`, `nodes` (strings), `you` (index), `badge` | A repeating cycle |
| `collage` | `text`, `shots` (paths relative to the work folder) | Recap |
| `outro` | `title` + `kicker`, or logos; `text`, `cta` | Close |

- Default marketing shape: intro → problem statement → offer → bridge title → 6–9 chapters → collage → outro. Explainer: intro → why → flow → one chapter per function, grouped under section titles → loop or recap → outro.
- One voice line per non-app scene (key = `line` or scene id), ≤ 25 words. Clip chapters take one line; staged chapters take one line per group.
- Open on something specific, e.g. "Acme meets Globex." or "This is the Acme claims desk. It's where…". "A and B, working together" is filler.
- Plain spoken English, like a colleague showing the product. No hype words (seamless, powerful, smarter, magic), no slogans, no rule-of-three taglines.
- Name integrations and features exactly as the product ships them. Captions name the action ("Take this claim", "Plan published").
- Show the full script to the human before any voice work.

## 3. Screens

### Recordings

Per clip in an `app` scene's `clips`: `video`, `from`/`to` (source seconds), `speed`, `caption`, optional `focus`, optional `hold` (seconds to linger on the last frame).

- Pick the moment that proves the step: the form being filled, then the confirmation. Skip navigation, spinners and empty states.
- Speed: typing and scrolling 3–4.5×; decisions and confirmations 1.6–2.5×. A speed tag appears on screen from 3×.
- End each chapter on a confirmation state; add `hold` (≈1.4 s) when the last clip ends too soon to read it.
- `blankCrop` = the content region in source pixels, excluding persistent navigation, so loading frames are detected and dropped (`blankInk` threshold, default 0.012).
- `focus`: `{ "from", "to", "box": [x, y, w, h] }` in source seconds + pixels, for the last 1–3 s of a payoff state. Zoom is capped at 1.45 and eased; everything else plays full frame.

### Staged screenshots

An `app` scene's `groups`: `[{ "line": "06-1", "shots": [{ "file", "caption", "click", "zoom", "dur" }] }]`.

- Render each screen from the real app over made-up records: a widget or component test that paints the whole app at 2× (for example Flutter `RepaintBoundary.toImage(pixelRatio: 2)` at 1440×900), or Playwright screenshots of a local build seeded with fake data. Run any harness from a temporary copy and remove it from the repository afterwards.
- Have the harness write `shots/manifest.json`: `[{ "file", "targets": [{ "label", "x", "y", "w", "h" }] }]` in logical pixels. `click`/`zoom` then name a target (`"click": "Sign in"`) or give a box. Set `shotFrame` to the logical width (1440 for 2880-pixel PNGs).
- `click` glides a cursor to the target, presses and ripples. `zoom` pushes in on the box (up to 2.2×) and keeps all of it in frame; a box too large to gain 1.15× is shown unzoomed.
- Shots last 2.6 s or longer (more with a click or zoom) and stretch so each group's voice line fits. Repeating the same `file` with a new `zoom` moves the camera without a cut.
- Check every shot in a contact sheet before building: the menu open, the right tab, the state the caption names.

## 4. Voice

1. `node scripts/takes.mjs <work> 01` — one line first. Send that take to the human and wait for their verdict on voice, pace and name pronunciation.
2. Then all lines: six seeds each, whole line per generation, at `storyboard.voice` (default `{ "exaggeration": 0.7, "cfg": 0.4 }`). Change these only after the human hears a sample.
3. `node scripts/pick.mjs <work>` transcribes every take with Whisper and keeps the lowest word-error take per line (ties → the take that fits its scene). A line marked `REGENERATE` has no clean take: check the script's wording, then try six fresh seeds with `node scripts/takes.mjs <work> <id> 7` (seeds 7–12) and pick again.
4. Names: keep plain spelling. When Whisper consistently hears a close variant of a correctly pronounced name, map it in `vo/heard-as.json` (`{"heard": "script"}`) instead of respelling the script. Respell only after the human hears a wrong pronunciation, and send 2–3 spellings as a sample first.
5. A take the human liked stays: keep its file in `vo/takes/` (any `<id>_<label>.wav` competes) and regenerate only the lines whose text changed.

## 5. Build, render and mix

- `build.mjs` times every scene from its clips, shots and voice lines, writes `render/scenes.js` + `audio/placement.json`, and fails when a line is missing, used twice, or runs into the next one.
- Storyboard options: `subtitles: true` (sentence subtitles under the picture), `transitions: "fade"` (0.4 s crossfade between scenes; default `"cut"`), `backdrop: true` (dot grid + slow blurred colour blobs in `tint`), `music.volume`.
- Stills first: every graphic scene, each chapter card, each click and zoom. Fix layout before a full render.
- `render.mjs` captures 30 fps deterministically from the paused GSAP timeline and fails on any page error or missing asset.
- `mix.mjs` loops the music with crossfades, ducks it under the voice, fades in/out and normalises to −14 LUFS.

Design defaults in the template: display type 800 weight at 96–184 px with a word-mask reveal; numbered chapter card that wipes up; dark caption slab with a clip-path wipe; screens in a rounded frame with depth; chapter pill on staged screens; diagrams that draw on with a travelling dot; four-shot collage; logo outro with a CTA pill. Colours and fonts come from `brand` in the storyboard.

## 6. Review

Inspect the exact file you will deliver:

1. `audit.mjs`: open every contact sheet (one frame per second). Look for sign-in or secret screens, spinners, cropped content, overlapping elements, typed-out logos, zooms that cut off the thing named.
2. Flat-frame runs must only be deliberate (the first ~0.25 s of a scene before its text reveals).
3. Stills at every click, zoom and graphic scene: nothing important cut off, headings not covered, logos crisp.
4. Transcript of the mix: every line present, in order, names recognisable. For timing, trust `audio/placement.json`; Whisper timestamps drift.
5. Report per artifact what was checked and what was not (voice quality is the human's).

## 7. Deliver

- Name drafts `<Title> – product demo (draft N).mp4`; keep earlier drafts.
- Chat apps often cap uploads near 30 MB. Keep the full render and also send a smaller copy: `ffmpeg -i final.mp4 -vf scale=1280:-2 -c:v libx264 -crf 28 -preset slow -c:a aac -b:a 128k -movflags +faststart final-small.mp4`.
- Summarise what changed since the previous draft, the checks run, and anything the human must confirm (music licence, claims).

## Revisions

- Apply exactly the named changes. "Everything else is fine" freezes everything else: script lines, takes, timings, captions and designs.
- Voice feedback → change one thing, sample it, get a verdict, then roll it out.
- Design feedback on a graphic → rebuild it from the brand's approved source, not a new invention.
- Re-run the review for every scene whose timing or pixels changed.

## Likely mistakes

| Mistake | Replacement |
| --- | --- |
| Pointer-following or automatic zoom; zooms on things the voice does not name | Hand-placed boxes on the named element only, whole box in frame |
| Slow fades to black between scenes | Hard cuts, or 0.4 s crossfades |
| Sign-in or password screens "for context" | Start each chapter signed in; show access rules only in a training video |
| Real customer or patient data in shots | Demo accounts or made-up records |
| Brand name typed in a font | The brand's own logo file |
| New card, chip or tinted-panel designs | Copy the approved deck or site design, or the template's defaults |
| Splitting lines per sentence, higher exaggeration, picking "livelier" takes by pitch | Whole-line takes at the approved settings; the human judges by ear |
| Phonetic respelling of names by default | Plain spelling + `heard-as.json`; respell only after the human hears it |
| Hype words, slogans, rule-of-three taglines | Plain words that name what the screen shows |
| Rewriting the whole script after one complaint | Change only the named lines |
| Voice says one thing, caption shows another | Update caption + screen together with the line |

## Completion gate

Complete only when all hold on the exact delivered file:

- script approved by the human, every claim backed by product material;
- `build.mjs` passes and `render.mjs` reported no page errors;
- every audit sheet opened, flat runs explained, stills checked at clicks, zooms and graphic scenes;
- mix transcript contains every line in order;
- delivered with a draft number and a change summary; voice quality stated as the human's judgment, not the agent's; music licence status stated.
