# Clones

1. Family = `clones`; tool = repository-pinned `jscpd` (`node_modules/.bin/jscpd`); pattern `jscpd|cpd`; derives for Python + Dart changes when declared; push + ci phases.
2. Command contract = `--fail-on-new-clones` + `--baseline <tracked file>` (or `--baseline-from-ref`) + `--reporters console|console-full`; `--update-baseline`, `--output`, `-o`, or file reporters = rejected (they write into the tree during a read-only gate).
3. Baseline creation = one explicit `jscpd --baseline <file> --update-baseline . ...` run outside the gate; commit the baseline; old clones stay baselined, only new clone pairs fail.
4. Console reporter prints each `[NEW]` pair with both files + line ranges; fix = dedupe into one owner or, for an accepted exact duplicate, refresh the baseline in the same commit with the reason in the message.
5. First wiring per repository = `research` PASS on the current jscpd CLI contract; this file never pins flag syntax beyond the validated set.
