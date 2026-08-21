# Slice Gate

- Owner = slice/full-gate check receipts bound to the exact repository artifact; `plan_state.py` rejects slice completion without a current `<S-ID>` receipt + `building → green` without a current `full` receipt.
- Derivation = changed paths vs HEAD + untracked → Route-table stack rows; no matched stack → one `targeted` proof; cross-stack = union; receipts = lifecycle bytes under `features/<slug>/receipts/`, excluded from green artifact + delivery like `PLAN.md`.
- Families = `targeted | typecheck format lint tests fallow | react-doctor | dart-analyze dart-test dart-decimate | python-format python-lint python-tests python-types | boundary-contracts`; every applicable family needs one project-manifest command with exit `0`; Python families derive only when declared in the manifest; security families (`secrets` `sast` `deps-audit`) = push/ci phases only, never slice-derived.
- Boundary contracts = a `families.boundary-contracts` entry plus `boundary_contracts.application_roots` in `hard-eng.gates.json` marks the main application; `boundary_contracts.local_package_roots` opts in first-party local packages. Relevant JS/TS/React and contract/config changes under those roots must include that family, and missing coverage fails closed. Each scoped TypeScript/React root must declare direct `zod@4`, have a nearest recognized lockfile resolving Zod 4, and run the project-owned Zod boundary command. Unlisted packages and `node_modules` are excluded.
- Command owner = repository-root `hard-eng.gates.json`; schema `1` + direct argv arrays + exact `npx --package` pins; caller-supplied shell text/no-op commands = rejected.
- Any later tree/HEAD mutation = receipt stale → rerun on the final tree; wrong plan/slice/repo = rejected.
- Checks = tree read-only; artifact drift during `run` = rejected, no receipt; capture media/codegen before the gate, never inside it.
- `--behavior` = one observable behavior; `+`/`;`/`→` separators = rejected → split the extra behaviors into their own slices.
- `--e2e <path>` = canonical `e2e` receipt; validator PASS required + receipt bytes sha-bound; later change = stale.
- `risk_level = critical` + overlay naming the slice (or naming none, or `--full`) → `--security not-applicable` rejected; record the protected-boundary review summary.
- PLAN `ux_reference` != n/a + changed `.tsx|.jsx|.dart` paths → `--e2e not-applicable` rejected; actual-media receipt required.

```sh
python3 "$HOME/.agents/skills/deterministic-checks/scripts/slice_gate.py" run \
  --repo <repo> --plan features/<slug>/PLAN.md (--slice <S-ID> | --full) --timeout <seconds> \
  --behavior "<one demonstrated observable behavior>" \
  --check <family> [--check ...] \
  --e2e <media-receipt-path|not-applicable:<reason>> \
  --security <summary|not-applicable:<reason>> --review "<actual-diff review summary>"
python3 "$HOME/.agents/skills/deterministic-checks/scripts/slice_gate.py" status \
  --repo <repo> --plan features/<slug>/PLAN.md (--slice <S-ID> | --full)
```
