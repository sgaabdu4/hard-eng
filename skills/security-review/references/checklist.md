# Security Checklist

## Secrets

Look for provider keys, JWT/session/encryption secrets, OAuth/webhook secrets, DB URLs, private keys, service-account JSON, kubeconfig, SSH keys, `.env` files, frontend bundles, logs, source maps, CI output, and debug pages. Move to env/secret manager, rotate exposed values, remove from history when needed, add scanning.

## Auth / Accounts

Check login/signup/session/JWT/OAuth/reset/invite/MFA/admin paths. Flag client-provided identity/role/tenant, frontend-only admin checks, unsigned or wrong-audience JWTs, non-expiring tokens, weak cookie flags, missing auth middleware, or account recovery without ownership/re-auth.

## Data Authorization

Check routes/resolvers/actions accepting IDs, filters, tenant/org/account/order/payment/profile IDs. Flag object/property access bugs, mass assignment, list/export endpoints missing tenant filters, webhooks/jobs processing IDs without signature or ownership checks. Fix through policy-aware queries, same-query subject/tenant filters, explicit DTOs, and input allowlists.

## Debug / Prod Boundary

Search for debug mode, stack traces, SQL logs, test users, demo bypass headers, seed credentials, env defaults that fail open, flags disabling auth/billing/MFA/rate limits, and logs containing PII/secrets/prompts/payment/health data. Fail closed and isolate environments.

## Uploads / Files

Check type allowlists, magic bytes, filenames, public serving, executable paths, size/count/time limits, archive expansion, image/video/PDF processors, SVG/HTML/markdown handling, bucket ACLs, and shell calls. Use random server names, locked storage, safe MIME/download headers, limits, and sandbox/scanning.

## Supply Chain

Review manifests, lockfiles, containers, CI, postinstall scripts, Git/path deps, registries, private scopes, dependency confusion, floating image tags, build args, provenance, and release tokens. Use version-aware SCA; old alone is not vulnerable.

## Hygiene

Check CORS with credentials, CSRF for cookie-auth writes, login/reset/invite/OTP rate limits, CSP/frame-ancestors/X-Content-Type-Options/HSTS/referrer policy, cookie flags, HTTPS/TLS validation, user-facing verbose errors, and missing audit logs for auth/admin/export actions.

## Injection / SSRF / XSS / RCE

Trace user input into SQL/NoSQL/raw queries, dynamic filters, markdown/rich text, `innerHTML`, raw templates, redirects, URL fetchers, metadata/private IPs, `eval`, `Function`, deserialization, template-from-string, and shell/process calls. Prefer parameterized APIs, text rendering, proven sanitizers, URL/IP allowlists after DNS resolution, argv arrays, and safe parsers.

## LLM / Agentic Features

Check prompt boundaries, tenant-scoped retrieval, secrets in prompts/logs/traces/test artifacts, model-selected IDs/URLs/file paths/SQL/shell/payment/email/admin actions, output validation, quotas, audit logs, human approval, and token/file/audio cost DoS. Authz lives outside the model.

## False Positives

Avoid flagging placeholders in `.env.example`, isolated test credentials, public client IDs by themselves, dependency advisories that do not affect installed versions/reachable code, app headers injected by verified platform layers, or debug code provably unreachable in production.
