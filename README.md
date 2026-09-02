<p align="center">
  <img src="assets/readme/hard-eng-hero.png" alt="Hard Eng: plan with one Feature Brief, build in an implement-verify loop, ship, and learn from evidence" width="100%">
</p>

> [!WARNING]
> **Alpha:** Hard Eng is evolving very quickly, so I do not recommend installing it yet. You are welcome to explore the code and take inspiration for your own setup.

# Hard Eng

Hard Eng gives OpenAI Codex, Claude Code, and GitHub Copilot CLI one shared set of rules, skills, and checks.

## What you get

| Part | What it gives you |
| --- | --- |
| Shared rules | The repository's own rules plus Hard Eng's engineering workflow |
| `skills/` | 28 focused skills for planning, building, testing, research, review, and delivery |
| Agent setup | The right files, hooks, and helpers for Codex, Claude, and Copilot |
| Checks | Repeatable formatting, linting, type, test, security, and delivery checks |

## Install globally

Run this from any directory:

```bash
npx -y github:sgaabdu4/hard-eng --global
```

This sets up Hard Eng once for this computer. Run the same command again to update to the newest release; an existing setup is repaired in place when it is already current.

The `npx` command runs the installer from the current `main` branch and then downloads the newest verified release. To pin the installer as well, use a release tag: `npx -y github:sgaabdu4/hard-eng#<tag> --global`.

## Set up one repository

Run this from the repository's root directory:

```bash
npx -y github:sgaabdu4/hard-eng --repo
```

This sets up Codex, Claude, and Copilot together. It creates and stages these files when they are missing:

- `AGENTS.md` for the repository's own rules;
- `CLAUDE.md` to load those rules; and
- `hard-eng.gates.json` to enable Hard Eng.

Hard Eng keeps its generated agent wiring out of `git status`. If a healthy global setup exists, the repository uses it; otherwise, Hard Eng adds a local copy.

### Repository folders

When there is no global setup, Hard Eng creates the folders each agent needs:

| Folder | Used for |
| --- | --- |
| `.agents/` | The shared skills and local Hard Eng copy |
| `.claude/` | Claude skills, helpers, hooks, and output style |
| `.codex/` | Codex helpers and hooks |
| `.github/` | Copilot helpers and hooks |

These folders are created automatically and stay privately ignored. When global Hard Eng is available, the repository uses that setup instead of creating duplicate folders.

Hard Eng also generates three private files so each agent reads both sets of rules: `AGENTS.override.md` for Codex (it reads that file instead of `AGENTS.md`, so it holds the repository rules first and the Hard Eng rules second), `CLAUDE.local.md` for Claude Code, and `.github/instructions/hard-eng.instructions.md` for Copilot. Keep your own rules in `AGENTS.md`; running `--repo` again refreshes the generated files and refuses to overwrite hand edits.

### Hooks and trust

The Hard Eng safety hooks stop destructive commands, such as discarding uncommitted work. Each agent only runs hooks it trusts:

- Codex asks you to review new hooks when you start it in the repository. `codex exec` skips hooks you have not reviewed unless you pass `--dangerously-bypass-hook-trust`, and Codex loads repository hooks only in projects you have trusted.
- Copilot runs repository hooks only in folders you have trusted. An interactive `copilot` session asks once; `copilot -p` never asks, so trust the folder first or add it to `trustedFolders` in `~/.copilot/config.json`. The user-level hook from the global setup runs everywhere.
- Claude Code runs the repository hooks in every mode, including `claude -p`.

### Keep the repository setup local

Use `--ignore` if you do not want the three files above added to Git:

```bash
npx -y github:sgaabdu4/hard-eng --repo --ignore
```

Existing tracked files stay tracked.

### Share the setup with every clone

Use `--shared` when teammates, CI, or cloud agents (Claude Code on the web, the Copilot cloud agent, Codex cloud) should get Hard Eng from a fresh clone with nothing installed:

```bash
npx -y github:sgaabdu4/hard-eng --repo --shared
```

This pins one Hard Eng release in `hard-eng.gates.json` (its tag and SHA-256 digests) and stages a small set of generated files for you to commit:

- `.hard-eng/bootstrap.sh`, which downloads and verifies exactly the pinned release into `.agents/hard-eng/` at session start;
- `.hard-eng/hook.sh`, the guard shim every tool call runs through;
- hook entries in `.claude/settings.json`, `.codex/hooks.json`, and `.github/hooks/hard-eng.json` (existing entries in those files are kept as they are); and
- the generated rule files `AGENTS.override.md` and `.github/instructions/hard-eng.instructions.md`.

Until the download has finished and been verified, the shim denies every tool call and tells the agent to run the bootstrap. The download comes from the GitHub release of `sgaabdu4/hard-eng`; set `HARD_ENG_RELEASE_BASE_URL` to serve the same assets from a mirror. Skill links, `CLAUDE.local.md`, and the downloaded copy stay privately ignored, so a clone's `git status` stays clean.

On a computer with a healthy global setup the shim stands aside and the global hook checks each tool call once. The pin never moves on its own: run the same `--repo --shared` command again (or `hard-eng update --shared` with a global install) to move it to the newest allowed release, review the diff, and commit. `hard-eng uninstall --shared` removes the pin and the generated files and leaves any foreign hook entries in place; without a global install, run it as `python3 .agents/hard-eng/current/bin/hard-eng uninstall --shared`.

Codex and Copilot still apply their own trust rules to repository hooks (see above). Claude Code on the web reads only `.claude/settings.json`, so shared wiring is the way to get Hard Eng there.

To share Hard Eng with many repositories, run `scripts/rollout-shared.py --repository <clone URL>` once per repository: it clones the repository into a fresh directory, runs the shared setup, commits, and pushes the default branch. When that push is refused, it pushes the `hard-eng-shared-wiring` branch and opens a pull request instead.

## Skills

Hard Eng connects these skills automatically. The agent chooses the ones needed for the work.

| Skill | What it helps with |
| --- | --- |
| `adversarial-review` | [Challenge a plan or change before it ships.](skills/adversarial-review/SKILL.md) |
| `appwrite-backend` | [Handle Appwrite backend work safely.](skills/appwrite-backend/SKILL.md) |
| `atomic-ui` | [Keep design tokens and reusable UI consistent.](skills/atomic-ui/SKILL.md) |
| `building-flutter-apps` | [Guide Riverpod Flutter work and Windows delivery.](skills/building-flutter-apps/SKILL.md) |
| `code-review` | [Review a real branch, commit, or working diff.](skills/code-review/SKILL.md) |
| `codebase-design` | [Review module boundaries, APIs, and ownership.](skills/codebase-design/SKILL.md) |
| `deterministic-checks` | [Run repeatable project checks.](skills/deterministic-checks/SKILL.md) |
| `diagnose-flutter-mobile-runtime` | [Investigate Flutter failures that appear only on a device.](skills/diagnose-flutter-mobile-runtime/SKILL.md) |
| `diagnosing-bugs` | [Find a reproducible root cause.](skills/diagnosing-bugs/SKILL.md) |
| `e2e` | [Prove behavior in the real browser or device.](skills/e2e/SKILL.md) |
| `handoff` | [Carry clear evidence into another agent or session.](skills/handoff/SKILL.md) |
| `he` | [Choose the right workflow for the work.](skills/he/SKILL.md) |
| `he-build` | [Build and prove one working slice at a time.](skills/he-build/SKILL.md) |
| `he-learn` | [Turn a proven process failure into prevention.](skills/he-learn/SKILL.md) |
| `he-plan` | [Create one living feature brief.](skills/he-plan/SKILL.md) |
| `he-ship` | [Deliver one exact green revision.](skills/he-ship/SKILL.md) |
| `plain-english` | [Keep user-facing writing clear and direct.](skills/plain-english/SKILL.md) |
| `product-walkthrough-video` | [Create a verified product walkthrough video.](skills/product-walkthrough-video/SKILL.md) |
| `question-me` | [Ask focused questions when a real decision is needed.](skills/question-me/SKILL.md) |
| `repeated-failure-learning` | [Check whether repeated failures share one cause.](skills/repeated-failure-learning/SKILL.md) |
| `research` | [Check current primary sources before relying on an outside contract.](skills/research/SKILL.md) |
| `security-review` | [Review authentication, data, secrets, dependencies, and injection risks.](skills/security-review/SKILL.md) |
| `sentry` | [Investigate Sentry through its CLI.](skills/sentry/SKILL.md) |
| `sentry-fix-loop` | [Carry a Sentry issue through diagnosis and proof.](skills/sentry-fix-loop/SKILL.md) |
| `test-quality` | [Design tests that catch the real failure.](skills/test-quality/SKILL.md) |
| `vercel-react-best-practices` | [Apply Vercel's React and Next.js guidance.](skills/vercel-react-best-practices/SKILL.md) |
| `writing-artifacts` | [Create useful written deliverables.](skills/writing-artifacts/SKILL.md) |
| `writing-great-skills` | [Create short and predictable agent skills.](skills/writing-great-skills/SKILL.md) |

## Requirements

Use macOS or Linux with Node.js 26.0+, Python 3.12+, Git, GitHub CLI, npm, Perl, `curl`, and `tar`. Codex is required; Claude Code and Copilot CLI are supported when installed.
