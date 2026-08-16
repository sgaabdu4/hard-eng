# Release and Update Threat Model

## Assets

The protected assets are setup pins, npm locks, managed-skill trees, workflow files, hook and enforcement code, approval receipts, generated release assets, and the exact revision delivered to users.

## Threats

- A mutable or substituted upstream supplies different bytes under a familiar name.
- A pull request changes a workflow, hook, updater, or release asset without the right reviewer.
- Untrusted dispatch input reaches a shell command.
- A stale, mismatched, or reused approval authorizes a different action.
- A timeout leaves descendant processes running.
- A symlink or concurrent edit redirects an immutable state write.
- A scheduled updater changes files outside its locked scope.
- A release is reported green without exact repository, workflow, revision, job, and step identity.

## Controls

- Versions, action revisions, binary checksums, managed-skill sources, and managed trees are pinned.
- Setup state uses no-follow, preimage-bound, durable replacement with rollback.
- The bounded runner applies whole-run deadlines and process-group cleanup.
- Dispatch input is validated before it reaches Windows release commands.
- Approval challenges bind the task, session, repository state, action, expiry, and one-time consumption.
- CODEOWNERS names reviewers for setup, hooks, enforcement, workflows, managed skills, release assets, and security files.
- Pull requests run the full platform matrix and native Windows asset checks.
- Managed-skill updates are limited to locked paths and run the publish gates before the scheduled commit.
- Delivery verification checks exact workflow and run identity, revision, jobs, and steps.

## Residual limits

Repository files cannot prove that GitHub branch rules, private vulnerability reporting, or a narrow updater bypass are enabled. Those settings require administrator readback. Native Windows behavior is proven only by the Windows CI job for a pushed revision. Compromise of GitHub, an upstream maintainer, or a maintainer account remains outside local gate control.
