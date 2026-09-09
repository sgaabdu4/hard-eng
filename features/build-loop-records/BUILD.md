# Build record: build-loop-records

Generated from the build receipts; edit the receipts, not this file.

## Outcome
- The build stage is machine-checked end to end: every slice must leave records for its edge cases mapped to success and failure tests, its green test run, a fresh-eyes review loop with a findings ledger, and an end-to-end verification run by a separate agent with fake outside services and before/after evidence; the slice gate refuses a slice without them; new push-time checks catch copy-paste clones (baseline, new clones only) and complex under-tested TypeScript functions; mutation testing scores only functions with no current ledger row, nightly in GitHub Actions on public repositories with a pull request for survivors, and on the developer machine before push on private ones, recorded in a committed ledger that the push gate and CI only read; ticket mode has a machine-checked board; build closes with one question (walkthrough video?) and prints a ship handoff block with worktree, branch, plan, and prompt.

## S-1
- behavior = slice gate refuses a slice whose build records are missing or stale
- edge cases = 9
  - edge case without failure test id
  - green record with nonzero exit
  - open review finding
  - real outside call in verify
  - verify names unknown edge case
  - tree change after records
  - missing records at gate
  - full gate without verify record
  - repository without enforcement
- green = `python3 scripts/check-skill-contracts.py`
- review =
  - round 1: R-1 fixed
- verify = logic mode; before `features/build-loop-records/receipts/s1-verify-before.json`; after `features/build-loop-records/receipts/s1-verify-after.json`
- outside calls = none (all faked)
- gate families = targeted, python-types, python-format, python-lint

## S-2
- behavior = review rounds bind to a machine-built packet and an open finding blocks the slice
- edge cases = 6
  - review round without a packet
  - review round with wrong packet hash
  - fourth review round
  - packet carries only the reviewer contract sections
  - packet before edges record or with no tree change
  - open finding shown by inspect
- green = `python3 scripts/check-skill-contracts.py`
- review =
  - round 1: R-1 rejected
- verify = logic mode; before `features/build-loop-records/receipts/s2-verify-before.json`; after `features/build-loop-records/receipts/s2-verify-after.json`
- outside calls = none (all faked)
- gate families = targeted, python-types, python-format, python-lint

## S-3
- behavior = verify records bind to a verifier packet and mode-checked before and after evidence
- edge cases = 8
  - verify without a packet or with wrong hash
  - fake log missing
  - logic mode given a screenshot
  - ui mode given JSON
  - ui screenshot that does not decode
  - real outside host
  - verifier packet content
  - full-feature verify packet
- green = `python3 scripts/check-skill-contracts.py`
- review =
  - round 1: no findings
- verify = logic mode; before `features/build-loop-records/receipts/s3-verify-before.json`; after `features/build-loop-records/receipts/s3-verify-after.json`
- outside calls = none (all faked)
- gate families = targeted, python-types, python-format, python-lint

## S-4
- behavior = the gate judges fallow audit verdicts and refuses new Python or Dart clones against a baseline
- edge cases = 6
  - fallow command not in audit mode
  - fallow audit verdict fail
  - fallow report not an audit report
  - clones command that writes files or lacks baseline
  - clones derived only for Python and Dart when declared
  - families run in parallel
- green = `python3 scripts/check-skill-contracts.py`
- review =
  - round 1: R-1 fixed, R-2 fixed, R-3 fixed
- verify = logic mode; before `features/build-loop-records/receipts/s4-verify-before.json`; after `features/build-loop-records/receipts/s4-verify-after.json`
- outside calls = none (all faked)
- gate families = targeted, python-types, python-format, python-lint, clones

## S-5
- behavior = ship entry refuses a green tree without a current mutation receipt covering every changed source file
- edge cases = 7
  - ship entry without a mutation receipt
  - scope omits a file changed since the approval base
  - survivor total differs from ledger rows
  - deferred survivor without consequence
  - runner cannot mutate the scoped language
  - runner none with runnable files
  - receipt for an older tree
- green = `python3 scripts/check-skill-contracts.py`
- review =
  - round 1: R-1 fixed, R-2 fixed
- verify = logic mode; before `features/build-loop-records/receipts/s5-verify-before.json`; after `features/build-loop-records/receipts/s5-verify-after.json`
- outside calls = none (all faked)
- gate families = targeted, python-types, python-format, python-lint, clones

## S-6
- behavior = a fifth worker cannot claim and the orchestrator cannot edit a claimed ticket path
- edge cases = 6
  - fifth worker claims a ticket
  - orchestrator edits a claimed ticket path in the primary checkout
  - worker edits its own claimed path inside its worktree
  - unclaimed ticket path edited by the orchestrator
  - checkpoint hook wiring
  - dependency-aware claim and board in inspect
- green = `python3 scripts/check-skill-contracts.py`
- review =
  - round 1: R-1 fixed
- verify = logic mode; before `features/build-loop-records/receipts/s6-verify-before.json`; after `features/build-loop-records/receipts/s6-verify-after.json`
- outside calls = none (all faked)
- gate families = targeted, python-types, python-format, python-lint, clones

## S-7
- behavior = the green checkpoint refuses until the walkthrough question is answered, then writes BUILD.md and inspect prints the ship handoff
- edge cases = 6
  - green checkpoint without the closing answer
  - walkthrough yes without a video in the full verify record
  - walkthrough value outside pending|yes|no
  - BUILD.md generated only at green and tolerated by the extra-Markdown guards
  - inspect at green prints the ship handoff
  - terminal cleanup excludes BUILD.md like PLAN.md
- green = `python3 scripts/check-skill-contracts.py`
- review =
  - round 1: R-1 fixed
- verify = logic mode; before `features/build-loop-records/receipts/s7-verify-before.json`; after `features/build-loop-records/receipts/s7-verify-after.json`
- outside calls = none (all faked)
- gate families = targeted, python-types, python-format, python-lint, clones

## S-8
- behavior = the build, ship, reference, and product docs describe the record loop exactly as the scripts enforce it
- edge cases = 5
  - he-build docs name every new record command and payload shape
  - he-ship docs require the mutation receipt and BUILD.md
  - reference docs match validated gate contracts
  - PRODUCT.md tells the new build truth in one row each
  - every skill reference is linked from its SKILL.md
- green = `python3 scripts/check-skill-contracts.py`
- review =
  - round 1: R-1 fixed, R-2 fixed, R-3 fixed
- verify = logic mode; before `features/build-loop-records/receipts/s8-verify-before.json`; after `features/build-loop-records/receipts/s8-verify-after.json`
- outside calls = none (all faked)
- gate families = targeted, python-types, python-format, python-lint, clones

## S-9
- behavior = validate and approve refuse a planning brief whose vendor tool has no cited research source
- edge cases = 6
  - brief names a vendor tool with only local research
  - memory note instead of a source row
  - code-study external_contract names a tool the brief does not
  - manifest introduces a new gate tool
  - research receipt expired
  - in-flight plan past planning
- green = `python3 scripts/check-skill-contracts.py`
- review =
  - round 1: R-1 fixed
- verify = logic mode; before `features/build-loop-records/receipts/s9-verify-before.json`; after `features/build-loop-records/receipts/s9-verify-after.json`
- outside calls = none (all faked)
- gate families = targeted, python-types, python-format, python-lint, clones

## S-10
- behavior = the push gate refuses a private-repository changed function that has no current mutation-ledger row
- edge cases = 12
  - private repository changed function without a current row
  - public repository with unscored functions
  - function whose mutants did not all finish
  - mutant no test reaches
  - needs-verdict row older than seven days
  - formatting-only edit versus a real change
  - no usable comparison base
  - repository visibility unknown
  - nightly run over unscored functions
  - repository without a mutation runner or with a broken ledger
  - invalid verdict input
  - nightly job on a private repository
- green = `python3 skills/deterministic-checks/scripts/project_gate.py phase --repo . --timeout 900 --phase push`
- review =
  - round 1: R-1 rejected, R-2 rejected, R-3 rejected, R-4 fixed
  - round 2: no findings
  - round 3: no findings
- verify = logic mode; before `features/build-loop-records/receipts/s10-verify-before.json`; after `features/build-loop-records/receipts/s10-verify-after.json`
- outside calls = none (all faked)
- gate families = clones, python-format, python-lint, python-types

## Whole feature
- verify = logic mode; before `features/build-loop-records/receipts/full-verify-2-before.json`; after `features/build-loop-records/receipts/full-verify-2-after.json`
- full gate = clones, python-format, python-lint, python-types, fallow, format, lint, tests, typecheck
