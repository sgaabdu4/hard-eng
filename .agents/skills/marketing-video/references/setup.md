# Setup + commands

Load when the runtime is missing or before the first command. Reuse existing environments; install only within task authorization.

## Runtime

```bash
cd /absolute/path/to/marketing-video
pnpm install --frozen-lockfile --ignore-scripts
pnpm exec playwright install chromium
brew install ffmpeg
```

Linux FFmpeg = `sudo apt-get install -y ffmpeg`.

Voice + transcription = own Python environments, outside every repository:

```bash
uv venv --python 3.11 ~/.cache/marketing-video-tts
uv pip install --python ~/.cache/marketing-video-tts/bin/python chatterbox-tts
export TTS_PYTHON=~/.cache/marketing-video-tts/bin/python
uv tool install mlx-whisper
```

- Chatterbox downloads weights from Hugging Face on first use; runs on Apple GPU, CUDA or CPU.
- `mlx-whisper` = Apple Silicon only. Elsewhere: `uv tool install openai-whisper` + `export WHISPER_BIN=whisper`. `WHISPER_BIN` may point at an existing `mlx_whisper`.
- Sandbox hides the GPU or blocks browser launch (e.g. Codex `workspace-write` on macOS) → `takes.mjs`, `pick.mjs`, `render.mjs` fail. Request an unsandboxed run; weights already downloaded → `HF_HUB_OFFLINE=1`.

## Work folder

One per video, outside this skill + out of version control (outside the repository or git-ignored): it holds footage, audio and renders.

| Path | Owner | Content |
| --- | --- | --- |
| `storyboard.json` | you | Brand, options, scenes; shape = [storyboard.example.json](../assets/storyboard.example.json) |
| `lines.json` | you | `[["01", "Voice line"], …]`; key = scene id, scene `line` or group `line` |
| `brand/` | brand owner | Display font (+ optional body font), logos `a` (+ partner `b`) |
| `footage/` | recordings | Source MP4s (recordings route) |
| `shots/` | staging | Screen PNGs + optional `manifest.json` (staged route) |
| `music/` | human | Licensed track |
| `render/` | template | `cp -R assets/template/. <work>/render/` once; customise only for approved designs |
| `clips/ vo/ audio/ out/ stills/ audit/` | scripts | Generated |

## Commands

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

- `clips.mjs` = recordings route only. `build.mjs` refuses clips whose storyboard range changed since the last `clips.mjs`.
- `build.mjs` runs before any voice exists (estimates missing lines) → check layout first.
- Last command transcribes only the voiced spans of the mix → music-only stretches cannot invent text.
