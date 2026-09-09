# Agent Rules

- Before editing, state the single change being implemented, which files it will touch, and how it will be verified. Prefer a native command or existing file. Every new file, dependency, wrapper or abstraction must be necessary for that change.
- Scope = the user's request + accepted constraints; preserve unrelated work.
- YAGNI = ultra always unless the user changes it. Understand the real flow first; reuse existing code, stdlib, native features and installed dependencies before adding code.
- Additions = before adding a file, dependency, abstraction, configuration or stored state, identify the current agreed requirement it serves and why the existing code or a direct command cannot satisfy it. Without both answers, leave it out. Keep this reasoning in normal updates; create no justification files.
- Changes = fix the cause at its existing owner. Optional improvements and extra infrastructure require an explicit user request; do not silently include them under robustness, best practices or future needs.
- Tests = each added test must prove a named required outcome or catch a specific meaningful failure. Reuse existing tests first; do not add tests that merely mirror implementation details or pad coverage.
- Verification = run applicable gates and prove affected behavior; never hide findings, weaken checks to obtain a pass or claim an unrun check succeeded.
- Acceptance = before completion, review the actual diff against the latest request, remove unsupported additions and report any remaining expansion. Passing tools does not excuse unnecessary code; automated metrics cannot prove necessity or test quality.
- Authorization = reuse settled approvals; ask only when missing information changes the result or an unapproved consequential action is necessary.
- Communication = concise plain English; report actual changes, proof and remaining gaps.
- Hard Eng = follow `.agents/skills/he/SKILL.md` when working on this repository; use `python3 .hooks/hard-eng.py --help` for commands.
