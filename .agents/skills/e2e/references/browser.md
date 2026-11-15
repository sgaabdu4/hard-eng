# Browser command

## Plain steps

- `python3 .hooks/hard-eng.py browser --session S <step>` runs one agent-browser step (`open`, `click`, `eval`, `console`, `errors`, `screenshot`, `close`, ...). `browser --session S --help` lists them.
- Plain steps run from `.hard-eng/browser/`, so relative file paths in a step resolve there.

## Capture

- `browser capture <url> --session S [--state FILE] [--ring SELECTOR] [--name NAME]` writes whole-page images at the standard widths, 390 and 1280 px, to `.hard-eng/browser/<name>-<width>.png` and prints their paths. Without `--name` the name is `capture`, so a second capture replaces the first: pass a name for each, such as `--name before` and `--name after`.
- `capture` loads `<url>` fresh at each width and closes its session at the end. It cannot show a state reached by clicks: use a URL that opens the state, or plain steps. A plain `screenshot` step hides nothing and draws no rings; add `--full` for the whole page, use fake data, and look at the image before you share it. Give `capture` and `signin` their own session name, not the one you click in.
- Red boxes go on each element that a `--ring` selector matches in the main page. Rings do not reach into shadow roots or frames. A `--ring` with no visible match at 390 or 1280 px stops the capture with an error, so ring only elements that show at both widths.
- Emails and phone numbers are hidden, also inside open shadow roots and same-origin frames. A frame that the command cannot read is covered grey. Hiding is a pattern match: it misses names and other personal data, so look at each image and use fake data before you share it.

## Sign in

- `browser signin <role> --session S` saves a sign-in to `.hard-eng/browser/state/<role>.json` and prints that path. Pass the printed path to `capture --state`, or to `--state` on the first plain step of a session.
- Roles come from `browser.roles` in `hard-eng.gates.json`: `url` (the login page), `username_env`, `password_env` and an optional `env_file`. The password goes to the tool on standard input only.

## Setup limits

- Codex in a workspace-write sandbox cannot start Chrome. Ask for approval, then run every `browser` call, `capture` and `signin` too, outside the sandbox.
- Never pass `--no-sandbox`; the command refuses it.
- On a Linux that limits user namespaces, the command refuses every call and prints a one-time root command. Do not run it yourself. Give it to the user as printed, and run the browser call again after the user confirms it is done.
