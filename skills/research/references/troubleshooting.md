# Failure and remedy research

- Establish expected behavior, observed failure and the exact environment: relevant command/route, input, error, version and configuration. Use available evidence before asking the user to repeat it.
- Reproduce the reported case when authorized and practical. If reproduction is unavailable, retain that limitation instead of claiming a confirmed cause.
- Form plausible competing explanations and choose the smallest observation that distinguishes them. Investigate the failing boundary and adjacent assumptions rather than repeating the same unsuccessful action.
- Search current official docs, changelogs and issues using the error and environment. Consult analogous community incidents for leads; match their versions and conditions before adopting a remedy.
- Trace the relevant caller, dependency and response/error handling through Codebase and Library and API routes as needed.
- Prefer a correction tied to the demonstrated cause. Explain unresolved hypotheses and what would distinguish them when evidence is insufficient.
- If implementation is authorized, verify the original failure and the affected behavior after the correction. Otherwise provide a concrete recommendation and the remaining proof, without implying that a proposed fix has been tested.
