# Setup Pre-Commit Workflow

## Detect Package Manager

Check lockfiles:

- `package-lock.json` -> npm
- `pnpm-lock.yaml` -> pnpm
- `yarn.lock` -> yarn
- `bun.lockb` or `bun.lock` -> bun

Default to npm only when no lockfile or package-manager field resolves the choice.

## Install Dependencies

Install as dev dependencies:

```text
husky lint-staged prettier
```

Use the detected package manager.

## Initialize Husky

Prefer the repo's existing Husky version and config. For Husky v9, `npx husky init` creates `.husky/` and adds `prepare: "husky"` to `package.json`.

If `.husky/pre-commit` already exists, patch the managed block instead of replacing user-owned lines.

## Pre-Commit Contents

Create or update `.husky/pre-commit` with the detected package manager:

```sh
npx lint-staged
npm run typecheck
npm run test
```

Adapt:

- replace `npm` with the detected package manager
- omit `typecheck` when `package.json` has no script
- omit `test` when `package.json` has no script
- report omitted checks as gaps

## lint-staged

Create `.lintstagedrc` only when the repo has no lint-staged config:

```json
{
  "*": "prettier --ignore-unknown --write"
}
```

## Prettier

Create `.prettierrc` only when the repo has no Prettier config:

```json
{
  "useTabs": false,
  "tabWidth": 2,
  "printWidth": 80,
  "singleQuote": false,
  "trailingComma": "es5",
  "semi": true,
  "arrowParens": "always"
}
```

## Verify

Prove:

- `.husky/pre-commit` exists and is executable
- lint-staged config exists
- `prepare` script is present when Husky requires it
- Prettier config exists
- `npx lint-staged` or equivalent succeeds

Report changed files, omitted checks, and commands run. Do not commit unless the user explicitly asks.
