# PRD Template

Before writing, verify the current repo context if the PRD names code modules,
routes, schemas, storage keys, or tests.
Use project glossary terms and respect nearby ADRs when they exist.

## Output Shape

```md
# <Feature or Change Name>

## Problem
- <who is affected>
- <current gap>
- <why it matters>

## Goals
- <observable outcome>
- <observable outcome>

## Non-Goals
- <explicitly out of scope>

## User Stories
- As a <actor>, I want <capability>, so that <benefit>

## Requirements
- <functional requirement with acceptance signal>
- <edge case or failure behavior>

## Implementation Decisions
- Owner modules/files:
- Interfaces/contracts:
- Data or schema changes:
- Routes/endpoints:
- Storage/cache keys:
- Migration or compatibility:
- Open decisions:

## Testing Decisions
- Highest useful test seam:
- Behavior assertions:
- Fixtures or prior-art tests:
- E2E or manual checks:

## Risks
- <risk and mitigation>

## Acceptance Criteria
- [ ] <criterion>
- [ ] <criterion>
```

## Quality Bar

- Separate confirmed decisions from assumptions
- Keep requirements behavior-facing
- Name data contracts, routes, schemas, and storage keys when known
- Prefer existing test seams and existing module owners
- Mark unknowns plainly instead of inventing scope
