---
name: security-review
description: Use for defensive appsec review: auth, secrets, deps, APIs, LLMs, data exposure, OWASP.
---

# Security Review

Run practical defensive triage. Findings need evidence and realistic fix direction. Do not test external targets unless the user owns them or authorization is clear.

## Rules

- Review provided/owned code, configs, artifacts, or URLs only
- Read before claiming; cite file/line, hunk, command output, or URL
- Mask secrets. Report type/prefix/location, not full value
- Do not provide weaponized exploit steps. Explain enough to fix
- Treat CVE/dependency status as current; use audit/SCA output or current sources
- Start long dependency scans early, collect/stop them before final

## Fast Flow

1. Scope stack, entry points, auth/session, data stores, routes, jobs, uploads, storage, LLM/tool use, deploy/CI.
2. Run quick scans: secrets, auth, data access, injection/RCE/SSRF/XSS, uploads, dependencies, CORS/CSRF/headers/cookies/rate limits, logs/debug routes, AI/tool boundaries.
3. For suspicious paths, trace source -> auth/policy -> sink/data impact.
4. Check tests/fixtures to distinguish intended behavior from vulnerability.
5. Report confirmed findings first by severity. Keep speculative items separate.

## Dependency Review

Use `references/dependency-vulnerability-checks.md` when dependency risk matters. Prefer OSV-Scanner plus ecosystem-native audits. Confirm installed version, affected range, fixed version, advisory source, and direct/transitive/prod/dev status before calling a dependency vulnerable.

## Checklist

Read `references/checklist.md` for detailed checks covering secrets, auth/session, tenant isolation, debug/prod boundary, uploads, supply chain, hygiene, injection, SSRF, XSS, RCE, and LLM/agentic features.

## Output

```md
## Findings
- [Severity] <title> - `<path>:<line>` - issue, impact, evidence, fix, verification

## Checked
- Secrets/Auth/Data/Uploads/Deps/Hygiene/Injection/LLM: <checked/finding/not checked + evidence>

## Not checked
- <area> - <reason + residual risk>
```

Severity: Critical for prod secret/auth bypass/cross-tenant data/RCE/payment/health/admin impact; High for exploitable sensitive BOLA/BOPLA, injection, stored XSS, dangerous upload, SSRF, CI secret exposure, high-impact tool abuse; Medium for plausible hardening gaps; Low for defense-in-depth.
