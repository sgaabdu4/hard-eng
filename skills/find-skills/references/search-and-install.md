# Search And Install

## Discovery

1. Identify the user's domain and specific task
2. Check whether an installed skill already covers the request
3. Search the public ecosystem only when local skills are insufficient
4. Verify source quality before recommending a result
5. Present the best matching option and install command

## Skills CLI

Use `npx skills` for ecosystem lookup and installation.

Key commands:

- `npx skills find [query] [--owner <owner>]`
- `npx skills add <package>`
- `npx skills check`
- `npx skills update`

Browse the public index at `https://skills.sh/`.

## Quality Checks

Verify recommendations with:

- Install count, preferably 1K+
- Source reputation such as official or well-known maintainers
- Repository health such as stars, recent activity, and clear docs
- Scope match against the user's actual task

Treat unknown authors, very low installs, and inactive repositories as risky.

## Response Shape

When a skill fits, include:

- Skill name and what it does
- Install count or source confidence when available
- Exact install command
- Link to the skills.sh page or source repository

When no skill fits:

- Say no relevant existing skill was found
- Offer to handle the task directly
- Mention `npx skills init` only when the user wants to create a reusable skill
