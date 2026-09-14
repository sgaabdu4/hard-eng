# Hard Eng Design

## Overview

Hard Eng has a command-line interface and no visual application.

## Components

Visual Atomic Design does not apply. The interface consists of the installer, skills, check runner and native agent/Git/CI integrations.

- `python3 /path/to/hard-eng/setup.py` installs into the current target Git repository. Replace the path with the scaffold checkout's location.
- `python3 .hooks/hard-eng.py check` runs the installed project's configured checks.
- `hard-eng.gates.json` holds native check commands and report locations.
- `.agents/skills` owns conditional guidance; Code Review reuses Hard Eng's test-quality reference.
- `.hooks/hard-eng.py` is the shared hook entry point; client files only register calls.
- `python3 .hooks/hard-eng.py ship --plan PLAN.md --pr <actual-PR-URL>` verifies delivery readiness using the project's `shipping` settings in the existing gate file. Merge/cleanup are explicit guarded stages; local plan Complete remains build completion, not publication.
- Session hooks request updates and give conditional tool-readiness guidance; completion hooks invoke checks. Integration detection runs during setup, not every session. Git pre-push verifies the pushed commits; CI runs independently. Native host limitations are tracked in [DECISION](DECISION.md#current-status).
- Session and supported failure checkpoints request HE Learn; ordinary prompts and successful tools have no Hard Eng callback. Claude/Copilot retain separate failure events. Failed completion checks retain a learning prompt and the existing loop guard. No recurrence database or test-result cache.
- `docs/adr/` holds terse project decisions; Accepted records preserve authority and rationale, while their evidence distinguishes implemented behavior from pending proof. Source ADRs are not copied into consuming projects.
- Output identifies passing checks, failures and incomplete verification in plain text. Failures retain a nonzero exit status.

## Do's and Don'ts

Preserve existing instructions and configuration. Use pnpm for JavaScript/TypeScript, native Python/Dart package managers and tool reports; add no dashboard, result cache or alternative workflow.
