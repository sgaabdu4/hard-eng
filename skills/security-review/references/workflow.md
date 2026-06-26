# Security Review Workflow

1. Scope stack, entry points, auth/session, data stores, routes, jobs, uploads, storage, LLM/tool use, deploy, and CI.
2. Run quick scans: secrets, auth, data access, injection/RCE/SSRF/XSS, uploads, dependencies, CORS/CSRF/headers/cookies/rate limits, logs/debug routes, and AI/tool boundaries.
3. For suspicious paths, trace source -> auth/policy -> sink/data impact.
4. Check tests/fixtures to distinguish intended behavior from vulnerability.
5. Report confirmed findings first by severity. Keep speculative items separate.
