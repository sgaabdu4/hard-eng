# Ask the project type in an empty repository

Status: Complete

## Outcome + scope

Setup in a repository with no supported manifest tells the agent to ask the user which project type to create (Python, Flutter, Next.js or OpenNext on Cloudflare) unless the request already says, create it with that stack's official scaffold command and rerun setup. New Flutter apps use Riverpod through Building Flutter Apps. A successful install tells the user to start a new agent session so installed skills load. No new file, command, prompt or scaffolding code.

## Repository context

Owner: `setup.py` `gate_config` already raised "No supported project manifest found" before writing anything; `install` prints the post-install steps. HE Plan owns setup/adoption guidance, and the README setup table and flowchart described a "new-project scaffold" setup never created. Building Flutter Apps is a canonical submodule; its description targets existing Riverpod apps, so the Riverpod rule is stated in HE Plan instead of changing the upstream skill. Evidence: a greenfield Flutter session created a plain `flutter create --empty` app with no Riverpod, and its skill listing was captured at session start before setup linked the skills.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked for these changes with YAGNI and confirmed the four project types. Commit and PR follow the user's usual go-ahead.

## Acceptance + steps

- [x] Empty repository → setup exits 1, writes nothing and asks for the project type → `test_missing_project_manifest_fails` red before, green after; real run on an empty scratch repository left only `.git`.
- [x] New Flutter app → the Riverpod rule is in HE Plan with a working link to Building Flutter Apps → full check link/Markdown gates.
- [x] Successful install → prints the new-session line and links `building-flutter-apps` → real run on a fresh macOS Flutter app.
- [x] README matches the behavior → setup table and flowchart updated.
- [x] Full check passes.

## Baseline + execution

Result: Passed
Evidence: main at a36b6e9, CI run 35254111327 success.
Execution: Single session on `feature/greenfield-project-type`.

## Risks + recovery

The agent still chooses the exact scaffold command per stack; Hard Eng does not run it. Agents that ignore setup output keep guessing. Recovery is reverting this branch.

## ux_reference

N/A — installer message and documentation only; no product appearance.

## Verification

Result: Passed
E2E: Passed — this checkout's `setup.py` against an empty scratch Git repository printed the project-type question, exited 1 and wrote nothing; against a fresh `flutter create --platforms=macos --empty` app it installed, linked `building-flutter-apps` and printed "Start a new agent session so it loads the installed skills."
Evidence: `test_missing_project_manifest_fails` failed with `setup.py` stashed and passed after. `hard-eng.py check --base origin/main` exit 0: all 17 checks passed, 770 tests and 4 performance checks.

Delivery target: Merge
Delivery: Pending — PR #120 CI passed on 22e5009; the user authorized merging once CI passes. Merge and merged-main CI remain unverified.
