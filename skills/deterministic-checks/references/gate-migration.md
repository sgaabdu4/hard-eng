# Gate Migration

- State = `gate-migration`; trigger = existing project missing `hard-eng.gates.json` or one required family, surfaced at `he` feature setup or before direct product mutation.
- Entry = worktree `write` PASS + preserve lifecycle status/intended product diff + pause product mutation.
- Evidence = existing project commands/config + impacted-owner map; repository-wide fallback/guess = forbidden.
- Greenfield/no existing commands = bootstrap from the chosen stack's own toolchain; evidence = the stack files this work introduces; the no-guess rule governs existing owners only.
- Unambiguous mapping → add only manifest/closest command adapter; new dependency/scanner/formatter + product cleanup = forbidden.
- Missing/ambiguous command owner → `CONCERNS` + exact wiring proposal; no mutation.
- Required whole-tree normalization → exit migration → dedicated baseline commit on target base → actual check PASS → resume wiring; baseline + wiring + feature diff mixing = forbidden.
- Proof = migration diff review + manifest validation + original affected-owner gate.
- Gate finding → exit migration → normal build finding; migration scope never absorbs source cleanup.
- Wiring complete = manifest validation PASS + commit/push hook enforcement wired per `hooks.md`; manifest without hooks = not wired (`setup_state.py` fails it).
- Exit = `gate-migration → ready`; resume preserved lifecycle stage + intended action.
