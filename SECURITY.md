# Security Policy

## Supported code

Security fixes target the current `main` branch. Older commits, local forks, and unpinned copies are not maintained release lines.

## Report a vulnerability

Use GitHub private vulnerability reporting from this repository's Security tab when it is available. Include the affected revision, reachable path, impact, and a minimal reproduction. Do not include credentials, tokens, signed URLs, customer data, or exploit details in a public issue.

If private reporting is not available, contact the repository owner through the GitHub profile and arrange a private channel before sharing sensitive details. This file does not claim that private reporting or any repository rule is currently enabled.

## Response

The maintainer will confirm receipt, reproduce the issue, identify affected revisions, and coordinate a fix and disclosure. Do not test against live customer data or accounts without separate written authorization.

## Security-sensitive areas

Setup and update scripts, hooks, enforcement, approval receipts, workflows, managed skills, release assets, and evidence validators require code-owner review. See [the release and update threat model](docs/security/release-update-threat-model.md) and [branch-protection requirements](.github/BRANCH_PROTECTION.md).
