# Hard Eng

## Overview

Hard Eng currently exposes a text CLI and Markdown instructions. There is no visual application or brand-token system in this repository. The interface should make required actions, failures and implementation status easy to understand.

This document follows the applicable prose sections of [Google's DESIGN.md specification](https://github.com/google-labs-code/design.md/blob/main/docs/spec.md). Visual token sections are omitted because the current product does not define them.

## Components

- Command help comes from Python's argument parser in [hard_eng/cli.py](hard_eng/cli.py).
- Check output in [hard_eng/runner.py](hard_eng/runner.py) uses `PASS` or `FAIL`, the check name and a short result or failure reason.
- CLI errors identify the failure and return a nonzero exit status.
- Decision checkboxes put implemented items first and pending or partial items below.

### Atomic Design

Atoms, molecules, organisms, templates and pages describe visual UI composition. They do not currently apply to this CLI; no UI components or hierarchy are invented here.

When Hard Eng studies a repository with a UI, its DESIGN.md should map the actual reusable components and screens to those five levels, preserving the existing code organization.

## Do's and Don'ts

- Use readable text and explicit status words; do not rely on color alone.
- Keep diagnostics useful and secret values redacted.
- Show actual results and unresolved failures.
- Use existing commands and conventions; add no decorative output or speculative interface layers.
