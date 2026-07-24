# Legacy v4 Migration

## Contract

- Trigger = exact canonical legacy v4 `features/<slug>/PLAN.md`.
- Current authority = supplied Git root + repo-contained no-symlink path + full byte token.
- Archived repository/branch/HEAD = provenance only.
- Supported mapping = planning/unapproved + build-ready/building approved.
- Preserve = plan ID + approval provenance + active/completed progress + next action + complete readable legacy content.
- Building `active_slice=final` = v1 building + `active_slice=none` + complete preserved slice prefix; approval/provenance/next action unchanged.
- Terminal v4 = ignored by active discovery + explicit migration rejected unchanged.

```sh
python3 <skill-dir>/scripts/plan_state.py migrate-v4 --repo <repo> \
  --plan features/<slug>/PLAN.md --expect-token sha256:<full-document-byte-hash>
```

## Storage

- Archive = deterministic name + byte-exact content + exact mode + no-follow descriptor-relative write.
- Replacement = archive first + final expected-preimage comparison + atomic PLAN replacement.
- Identical archive-first retry = resume; mismatched archive = fail unchanged.
- Approved mapping = archive provenance + readable legacy content in frozen Material decisions; no new approval manufactured.

## Output

- Required = result + plan + old/new hash + archive path/hash + token + lifecycle + approval + route + active/completed slices + approval provenance + next action.
- Malformed/unsupported/stale/path escape/symlink/preimage drift/second migration = exit `4` + PLAN/archive unchanged.
