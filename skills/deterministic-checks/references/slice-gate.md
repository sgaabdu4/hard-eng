# Slice Gate

- Owner = slice/full-gate check receipts bound to the exact repository artifact; `plan_state.py` rejects slice completion without a current `<S-ID>` receipt + `building → green` without a current `full` receipt.
- Derivation = changed paths vs HEAD + untracked → Route-table stack rows; no matched stack → one `targeted` proof; cross-stack = union; receipts = lifecycle bytes under `features/<slug>/receipts/`, excluded from green artifact + delivery like `PLAN.md`.
- Families = `targeted | typecheck lint tests fallow | react-doctor | dart-analyze dart-test dart-decimate`; every applicable family needs one matching command with exit `0`.
- Any later tree/HEAD mutation = receipt stale → rerun on the final tree; wrong plan/slice/repo = rejected.
- `--behavior` = one observable behavior; `+`/`;`/`→` separators = rejected → split the extra behaviors into their own slices.
- `--e2e <path>` = canonical `e2e` receipt; validator PASS required + receipt bytes sha-bound; later change = stale.
- `risk_level = critical` + overlay naming the slice (or naming none, or `--full`) → `--security not-applicable` rejected; record the protected-boundary review summary.
- PLAN `ux_reference` != n/a + changed `.tsx|.jsx|.dart` paths → `--e2e not-applicable` rejected; actual-media receipt required.

```sh
python3 "$HOME/.agents/skills/deterministic-checks/scripts/slice_gate.py" run \
  --repo <repo> --plan features/<slug>/PLAN.md (--slice <S-ID> | --full) --timeout <seconds> \
  --behavior "<one demonstrated observable behavior>" \
  --check <family>="<command>" [--check ...] \
  --e2e <media-receipt-path|not-applicable:<reason>> \
  --security <summary|not-applicable:<reason>> --review "<actual-diff review summary>"
python3 "$HOME/.agents/skills/deterministic-checks/scripts/slice_gate.py" status \
  --repo <repo> --plan features/<slug>/PLAN.md (--slice <S-ID> | --full)
```
