# Hard Eng Demo Script

Use this to replace the illustrative walkthrough GIF with a reviewer-openable 60-second terminal GIF from a real `codex` CLI session on macOS. Do not mock the transcript.

## Goal

Show that Hard Eng is an opt-in shipping lane: normal small fixes follow `AGENTS.md`, while `/he:plan` starts the stateful plan -> implement -> verify flow.

## Output

- Primary asset: terminal GIF
- Final path to replace: `docs/media/hard-eng-terminal-flow.gif`
- Keep this script linked until the checked-in GIF is a real CLI recording

## Shot List

- Show `codex --version`
- Show the README opening, opt-in wording, and Codex plus macOS tested scope
- Run `bash setup.sh --safe --dry-run`
- Start `codex` CLI in a clean demo repo or sanitized fixture
- Type `/he:plan ship login redirect fix`
- Show the agent reading context, naming the owner, and updating `he-state.json`
- Type `/he:implement`
- Show the owner file change and deterministic owner guard
- Type `/he:verify`
- Show tests or another proof command and the recorded evidence
- End on the stage receipt with `Next: ready for /he:ship: yes/no`

## Recording Recipe

Use any terminal GIF recorder that can hide the cursor path and crop the window. One simple path is:

```sh
mkdir -p docs/media
asciinema rec /tmp/hard-eng-terminal-flow.cast
agg /tmp/hard-eng-terminal-flow.cast docs/media/hard-eng-terminal-flow.gif
```

If `asciinema` or `agg` is not installed, record the terminal with another local tool and export a compressed GIF to `docs/media/hard-eng-terminal-flow.gif`.

## Acceptance

- Keep the final cut near 60 seconds
- Show real terminal output from `codex` CLI
- Do not expose local paths, secrets, customer data, private repo names, or tokens
- Use a committed compressed GIF or reviewer-openable URL when it is added
- Update README from this script link to the final GIF only after the GIF exists
