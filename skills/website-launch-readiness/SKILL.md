---
name: website-launch-readiness
description: Use only when the user explicitly asks for website launch readiness, SEO, analytics, hosting/CDN or Cloudflare, performance, security.txt, or AI-agent discovery checks.
---

# Website Launch Readiness

Use this skill to make a web surface launch-ready without mixing marketing, portal, and infrastructure scopes.

## Use

1. Identify the canonical surface owner, then read `references/checklist.md`.
2. Implement only owner-level launch fixes, deploy, verify live, and report stale third-party scans separately from current evidence.

## Scope Rules

- Keep public marketing content and authenticated portal content separate
- For portals, expose only product/operational public documentation to agents. Do not expose private workspace data, task text, user records, tokens, or authenticated API schemas
- For Cloudflare findings, do not mutate unrelated `workers.dev`, staging, or sibling-zone findings unless the user explicitly scopes them
- MFA and account-user findings are owner actions. Report them instead of attempting account takeover-style setup

## Validation

Use `references/checklist.md` for live URL, text endpoint, build/test, and repo-gate verification.
