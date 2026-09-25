# Enforce the comment rule in check

Status: Ready

## Outcome + scope

`check` fails when any changed source file contains a comment block longer than one line, so Stop, pre-push and CI enforce the rule for every client and every edit path. Code comments are none by default, with at most one terse line of why. The whole changed file must comply, including blocks written before the change. Only narration lines count: delimiters, blank comment lines, tooling directives (lint suppressions, type-checker pragmas, shebangs, build tags), JSDoc type tags and rustdoc section headings do not. Doc comments count like any comment; the user chose this over exempting them, so projects whose linters demand longer docs turn those lints off. Detection tracks strings, heredocs and block comments, so comment-like text inside string data passes. Generated and vendored files, installed agent skills under `.agents/` (vendored tooling copied into projects on every install), deleted files, symlinks and non-source files are skipped. Hard Eng's own `.hooks` ship into every project, so they comply too. Non-goals: judging whether a single line is necessary, docstrings and other string literals, and files the change does not touch.

## Repository context

Owners: `check` in `.hooks/hard-eng.py` runs `validate_plans` before the gates; `changed_files` and `generated_sources` in `.hooks/gate_config.py` give the changed set and generator output. Setup installs `AGENTS.md` into projects and copies `.hooks`. Stop, pre-push and CI all run `check`. Before this change, one project enforced the rule with its own Claude-only PreToolUse hook, which Codex, shell edits and CI never pass through.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked for comments to be banned by default with at most one line of why, enforced for every file a change touches, and pre-push to enforce it.

## Acceptance + steps

- [ ] A changed Python, shell, JavaScript/TypeScript, Dart or Rust file with two narration lines in one comment block fails `check` and names the file and line, including a block that opens after code; single-line comments, trailing comments, directives, JSDoc type blocks, rustdoc headings, comment-like text in strings, templates and heredocs, and Markdown files pass → `tests/test_comments.py`.
- [ ] An older block in a touched file fails; the same block in an untouched file does not; generated files are skipped → `tests/test_comments.py`.
- [ ] Pre-push rejects a commit that adds a two-line comment block → real `git push` to a local bare remote in `tests/test_comments.py`.
- [ ] AGENTS.md and gates.md state the rule.
- [ ] Full gate passes; `/codex:adversarial-review` findings resolved.

## Baseline + execution

Result: Passed
Evidence: Pre-push `check` on `1060801` (the same tree as main `475c938`) → exit 0; 17/17 gates PASS, 840 tests passed; 1m56s.
Execution: One builder; the rule module and check call, tests, then the instruction text.

## Risks + recovery

Projects whose touched files hold multi-line comments fail until those blocks are compressed or deleted; that is the requested behaviour. The rule covers Python, shell, JavaScript/TypeScript, Dart and Rust; the lexers handle strings, raw strings, templates, regex literals, heredocs and shell escapes, but they are not full parsers, so an unusual literal can still be misread. Recovery: narrow detection for the affected language.

## ux_reference

N/A — gate and instruction change with no visual surface.

## Verification

Result: Pending
Evidence: Pending
E2E: Required — real `git push` through the installed pre-push hook in a fixture repository.

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge to main, main CI green.
