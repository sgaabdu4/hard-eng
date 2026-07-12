# Website Launch Readiness Checklist

## Surface Ownership

- Confirm the target domain and exact repo/package. Do not infer that `www`, apex, portal, app, and `workers.dev` have the same owner
- Identify canonical host redirects before SEO/indexing work
- For a portal, decide what is public metadata versus authenticated product state

## SEO And Sharing

- Set unique page titles, descriptions, canonical URLs, favicon/apple icons, Open Graph, Twitter card metadata, and structured data
- Add or update `sitemap.xml` and `robots.txt`
- Submit Google Search Console property, sitemap, and URL Inspection requests when the user is logged in and explicitly asks
- Verify how Google displays stale titles/descriptions by checking actual indexed output; explain that Google may rewrite snippets

## Analytics

- Install GA4 and Microsoft Clarity only through stable config owners or environment variables
- Keep third-party scripts privacy-aware and avoid exposing private portal data in page titles, event names, or URLs

## AI-Agent Readiness

- Add public `llms.txt` and, when useful, `llms-full.txt`
- Add public machine-readable docs such as `.well-known/api-catalog`, `.well-known/openapi.json`, `.well-known/mcp.json`, `.well-known/mcp/server-card.json`, and `.well-known/agent-skills/...` when they describe public capabilities
- Include `Link` headers to advertise machine-readable docs on public routes when the framework makes this practical
- Keep `Content-Signal` or equivalent training-use signals explicit when the site has an AI policy
- For authenticated portals, make the agent docs describe product capabilities and safe public entry points only. Do not expose private tenant data or privileged endpoints

## Security And Cloudflare

- Safe transport fixes: `Always Use HTTPS`, SSL/TLS mode `Full (strict)`, minimum TLS `1.2+`, HSTS with a normal max-age, `security.txt`, and `X-Content-Type-Options: nosniff`
- Avoid HSTS preload unless explicitly approved and every current/future subdomain policy is understood
- Do not enable Bot Fight Mode, AI Labyrinth, AI bot blocking, or similar crawler blockers by default on SEO/agent-ready sites. These can reduce legitimate indexing, automation, or agent access
- Turnstile requires app/form integration. Do not enable it globally just to clear an account-level suggestion
- Cloudflare Security Center rows can lag after fixes. Rescan, but trust current Cloudflare settings plus live `curl`, header, redirect, and TLS probes when old row timestamps contradict live evidence

## Live Verification

- Check apex, `www`, and portal hosts separately
- Verify live URLs with `curl -I` and fetch text endpoints directly
- Verify:
  - `http://...` redirects to `https://...`
  - `https://...` returns expected status
  - HSTS and no-sniff headers exist where intended
  - `/.well-known/security.txt` and `/security.txt` return valid text
  - forced TLS 1.0/1.1 fail and TLS 1.2+ succeeds when changing TLS policy
  - deployed release endpoint or asset proves the intended app version is live
- Run available typecheck, build, and tests
- Run the repo push or dry-run gate when repo policy requires it
- Run PageSpeed or Lighthouse-style checks when performance was part of the request; fix major regressions before final
