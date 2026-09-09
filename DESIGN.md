# Hard Eng Design

## Overview

Hard Eng has a command-line interface and no visual application.

## Components

Visual Atomic Design does not apply. The interface consists of the installer, check runner and Git hook entry point.

- `python3 /path/to/hard-eng/setup.py` installs into the current target Git repository. Replace the path with the scaffold checkout's location.
- `python3 .hooks/hard-eng.py check` runs the installed project's configured checks.
- `hard-eng.gates.json` holds native check commands and report locations.
- `.hooks/hard-eng.py` is the shared hook entry point; client files only register calls.
- Output identifies passing checks, failures and incomplete verification in plain text. Failures retain a nonzero exit status.

## Do's and Don'ts

Preserve existing instructions and configuration. Use pnpm for JavaScript/TypeScript, native Python/Dart package managers and tool reports; add no dashboard, result cache or alternative workflow.
