---
name: find-skills
description: Discover and install existing agent skills for user-requested capabilities.
---

# Find Skills

Use this when the user wants a capability that may already exist as an agent skill.

## Triggers

- "find a skill for X"
- "is there a skill for X"
- "how do I do X" when X may have a reusable skill
- "can you do X" for a specialized capability
- Requests to extend agent capabilities with tools, templates, or workflows

## Workflow

Read `references/search-and-install.md` before searching or recommending skills.

## Rules

- Prefer existing installed skills when they already satisfy the request
- Use the Skills CLI for discovery and install commands
- Verify quality before recommending a skill
- Give install commands only after confirming the package identifier
- If no skill fits, say so and help directly
