# Two-Axis Review

## Axes

**Standards** asks whether the change follows documented repo standards plus the smell baseline.

**Spec** asks whether the change implements the originating issue, plan, PRD, or spec without missing requirements or scope creep.

Keep the axes separate. A change can pass Standards and fail Spec, or pass Spec and fail Standards.

## Fixed Point

Use the user-supplied fixed point: commit SHA, branch, tag, `main`, `HEAD~5`, or equivalent.

Capture:

- `git diff <fixed-point>...HEAD`
- `git log <fixed-point>..HEAD --oneline`

Before review, prove:

- `git rev-parse <fixed-point>` succeeds
- the three-dot diff is non-empty

A bad ref or empty diff fails before spawning any reviewer.

## Spec Source

Find the originating spec in order:

- a path or spec content the user passed
- issue or PR references explicitly supplied by the user
- issue or PR references in commit messages, fetched through `docs/agents/issue-tracker.md` when that tracker contract exists
- a matching plan/spec file under `docs/`, `specs/`, or `.scratch/`
- user-provided confirmation that no spec exists

If no spec exists, skip the Spec axis and say so.

## Standards Source

Read repo standards such as `AGENTS.md`, `CODING_STANDARDS.md`, `CONTRIBUTING.md`, framework docs, or local architecture docs.

Repo standards override the smell baseline. Skip findings that tooling already enforces.

## Smell Baseline

Treat these as judgement-call heuristics, not hard violations:

- **Mysterious Name**: name hides what a value or function means
- **Duplicated Code**: same logic shape appears in multiple hunks or files
- **Feature Envy**: code reaches into another object's data more than its own
- **Data Clumps**: the same fields or params travel together repeatedly
- **Primitive Obsession**: primitive/string stands in for a domain concept
- **Repeated Switches**: repeated conditionals branch on the same type
- **Shotgun Surgery**: one logical change is scattered across many files
- **Divergent Change**: one file changes for unrelated reasons
- **Speculative Generality**: abstraction exists for unrequested future needs
- **Message Chains**: caller navigates through too many objects
- **Middle Man**: wrapper mostly delegates onward
- **Refused Bequest**: subtype ignores most inherited contract

## Parallel Review

When subagents are available, run two independent reviewers in parallel.

Standards reviewer brief:

- diff command and commit list
- standards-source files
- full smell baseline
- report documented-standard breaches and baseline smells with file/hunk evidence
- distinguish hard violations from judgement calls
- stay under 400 words

Spec reviewer brief:

- diff command and commit list
- spec path or fetched spec content
- report missing/partial requirements, scope creep, and wrong implementation with quoted spec evidence
- stay under 400 words

If subagents are unavailable, run the same two passes directly and keep the reports separate.

## Report

Use:

```markdown
## Standards
...

## Spec
...
```

End with one line: finding count per axis and the worst issue within each axis.
