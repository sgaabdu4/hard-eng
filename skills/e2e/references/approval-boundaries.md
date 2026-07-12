# E2E Approval Boundaries

Read this before any E2E step that uses real credentials, generated users/passwords, native permission prompts, prod/backend writes, backend permission/schema/index/migration/webhook changes, production payment/email/SMS/sharing side effects, or production cleanup.

## Required State

Record each risky boundary in `approvalBoundaries[]` with:

- `id`
- `category`
- `status`
- `reason`
- non-empty `evidence[]`
- exact `sideEffectKey` when production side effects differ
- `redactedCredentialRef` and `dataScope` for credential use
- positive `cleanupProof[]` for generated credentials

Allowed categories:

- `prod-backend-write`
- `prod-cleanup`
- `native-permission`
- `real-credentials`
- `generated-credentials`

Matching required boundaries must be `status: approved` with affirmative human approval proof. Request, pending, denied, unclear, or not-approved wording does not approve the side effect.

## Side-Effect Keys

Use a distinct key when one approval should not cover another action:

- `prod-sms`
- `prod-email`
- `prod-payment`
- `prod-appwrite-schema`
- `prod-db-permission`
- `prod-user-account`
- `prod-data-sharing`
- `prod-webhook`
- `prod-user-invite`
- `prod-notification`

Negated, read-only, and prevention-only evidence does not infer approval unless the same evidence records an affirmative risky action.
