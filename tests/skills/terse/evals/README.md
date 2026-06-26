# Terse Evals

This suite checks whether `terse` stays brief without losing exact terms, risk
warnings, or paste-ready writing quality. Paste-ready cases must read
`human-writing.md`; non-artifact replies must not.

## Local Check

```bash
python3 tests/skills/terse/evals/run-mini-evals.py --label baseline
```

The runner writes timestamped results to `/tmp/terse-evals`, records Codex JSONL
logs, grades deterministic expectations, and counts final reply tokens with
`tiktoken` using `o200k_base`.
