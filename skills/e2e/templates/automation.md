# E2E Automation

Every persisted E2E flow needs a runnable automation command.
Manual exploration can discover a flow, but the final project pack should leave an executable command for the next AI or engineer.

## Commands

- `unknown`

## Rules

- Prefer existing project runners when they exist
- Add the smallest durable automated smoke when no runner exists
- Do not commit cookies, tokens, passwords, private session dumps, or real customer data
- Do not count unit tests, typechecks, static scans, or curl-only checks as E2E

