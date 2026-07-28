# Gate Migration

- State = `gate-migration`; trigger = existing project missing `hard-eng.gates.json` or one required family.
- Entry = worktree `write` PASS + preserve lifecycle status/intended product diff + pause product mutation.
- Evidence = existing project commands/config + impacted-owner map; repository-wide fallback/guess = forbidden.
- Unambiguous mapping → add only manifest/closest command adapter; new dependency/scanner/formatter + product cleanup = forbidden.
- Missing/ambiguous command owner → `CONCERNS` + exact wiring proposal; no mutation.
- Proof = migration diff review + manifest validation + original affected-owner gate.
- Gate finding → exit migration → normal build finding; migration scope never absorbs source cleanup.
- Exit = `gate-migration → ready`; resume preserved lifecycle stage + intended action.
