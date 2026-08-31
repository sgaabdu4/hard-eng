import assert from "node:assert/strict";
import test from "node:test";
import {
  ReleaseWorkflowContractError,
  validateManagedSkillsWorkflow,
  validateReleaseWorkflow,
} from "./release-workflow-contracts.mjs";

const EXPRESSION_START = "$" + "{{";
const SOURCE_REF = `${EXPRESSION_START} env.SOURCE_SHA }}`;
const SOURCE_EXPRESSION = `${EXPRESSION_START} github.event_name == 'repository_dispatch' && github.event.client_payload.sha || github.sha }}`;
const RELEASE_EVENT = "hard-eng-release";
const RELEASE_IF = `${EXPRESSION_START} (github.event_name == 'push' && github.ref == 'refs/heads/main') || (github.event_name == 'repository_dispatch' && github.event.action == '${RELEASE_EVENT}' && github.actor == 'github-actions[bot]' && github.ref == 'refs/heads/main' && github.event.client_payload.sha != '') }}`;
const PINNED_CHECKOUT = `actions/checkout@${"a".repeat(40)}`;
const PINNED_NODE = `actions/setup-node@${"b".repeat(40)}`;

function sourceValidation(name) {
  return {
    name,
    shell: "bash",
    run: `set -euo pipefail\nchecked_out_sha="$(git rev-parse HEAD)"\ntest "$checked_out_sha" = "$SOURCE_SHA"\nnode scripts/release-builder.mjs validate-event --event "$EVENT_NAME" --ref "$EVENT_REF" --sha "$EVENT_SHA" --action "$EVENT_ACTION" --actor "$EVENT_ACTOR" --payload-sha "$PAYLOAD_SHA" --main-sha "$EVENT_SHA" --payload-is-ancestor false --checked-out-sha "$checked_out_sha"`,
  };
}

function sourceCheckout(name) {
  return [
    {
      name: "Check out repository",
      uses: PINNED_CHECKOUT,
      with: { ref: SOURCE_REF, "fetch-depth": 0 },
    },
    sourceValidation(name),
  ];
}

function requiredJobs() {
  return {
    "hard-eng": {
      strategy: {
        "fail-fast": false,
        matrix: {
          include: [
            { os: "ubuntu-24.04" },
            { os: "ubuntu-24.04-arm" },
            { os: "macos-15-intel" },
            { os: "macos-15" },
          ],
        },
      },
      steps: [
        ...sourceCheckout("Validate source checkout"),
        {
          name: "Run Hard Eng gates",
          run: "python3 skills/deterministic-checks/scripts/project_gate.py phase --repo . --timeout 360 --phase ci",
        },
      ],
    },
    "windows-assets": {
      steps: [
        ...sourceCheckout("Validate source checkout"),
        {
          name: "Parse managed PowerShell assets natively",
          run: "./scripts/parse-windows-installer-powershell.ps1",
        },
      ],
    },
  };
}

function releaseSteps() {
  return [
    {
      name: "Check out repository",
      uses: PINNED_CHECKOUT,
      with: { ref: SOURCE_REF, "fetch-depth": 0 },
    },
    { name: "Set up Node", uses: PINNED_NODE },
    sourceValidation("Validate source event"),
    {
      name: "Build deterministic release",
      run: 'set -euo pipefail\nnode scripts/release-builder.mjs build --root "$GITHUB_WORKSPACE" --commit "$SOURCE_SHA" --output "$RELEASE_DIR"',
    },
    {
      name: "Check existing release",
      run: 'set -euo pipefail\nif gh api "repos/$GITHUB_REPOSITORY/releases/tags/$RELEASE_TAG"; then node scripts/release-builder.mjs classify --release release.json --expected expected.json; fi',
    },
    {
      name: "Check source against current main",
      if: "steps.existing-release.outputs.action != 'reuse'",
      run: 'set -euo pipefail\nremote_main_sha="$(gh api "repos/$GITHUB_REPOSITORY/git/ref/heads/main" --jq ".object.sha")"\ngit fetch --no-tags origin refs/heads/main:refs/remotes/origin/main\ntest "$(git rev-parse refs/remotes/origin/main)" = "$remote_main_sha"\ngit merge-base --is-ancestor "$SOURCE_SHA" "$remote_main_sha"\ngit diff --quiet "$SOURCE_SHA" "$remote_main_sha" -- .github/workflows',
    },
    {
      name: "Check release verification support",
      run: "set -euo pipefail\ngh release verify --help >/dev/null",
    },
    {
      name: "Claim exact tag commit",
      run: 'set -euo pipefail\nif gh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$RELEASE_TAG" > claimed-tag.json; then tag_state=existing; else if gh api --method POST "repos/$GITHUB_REPOSITORY/git/refs" -f "ref=refs/tags/$RELEASE_TAG" -f "sha=$SOURCE_SHA"; then tag_state=created; else create_status=$?; if ! gh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$RELEASE_TAG" > claimed-tag.json; then cat create-tag.error; cat tag.error; exit "$create_status"; fi; tag_state=existing-after-race; fi; fi\ntest -n "$tag_state"\ngh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$RELEASE_TAG" > claimed-tag.json\nnode scripts/release-builder.mjs validate-tag --tag claimed-tag.json --expected expected.json',
    },
    {
      name: "Create draft release",
      if: "steps.existing-release.outputs.action == 'create'",
      run: 'set -euo pipefail\ngh release create "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --target "$SOURCE_SHA" --draft --prerelease',
    },
    {
      name: "Upload missing release assets",
      if: "steps.existing-release.outputs.action != 'reuse'",
      run: 'set -euo pipefail\nmissing_assets=()\ngh release upload "$RELEASE_TAG" "$asset_path" --repo "$GITHUB_REPOSITORY"',
    },
    {
      name: "Verify draft and publish immutable release",
      if: "steps.existing-release.outputs.action != 'reuse'",
      run: 'set -euo pipefail\ngh api "repos/$GITHUB_REPOSITORY/releases/tags/$RELEASE_TAG" > draft.json\ngh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$RELEASE_TAG" > prepublish-tag.json\nnode scripts/release-builder.mjs validate-tag --tag prepublish-tag.json --expected expected.json\nnode scripts/release-builder.mjs verify-draft --release draft.json --expected expected.json\ngh release edit "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --draft=false',
    },
    {
      name: "Verify immutable release",
      run: 'set -euo pipefail\ngh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$RELEASE_TAG" > final-tag.json\nnode scripts/release-builder.mjs validate-tag --tag final-tag.json --expected expected.json\ngh api "repos/$GITHUB_REPOSITORY/releases/tags/$RELEASE_TAG" > final.json\ngh release verify "$RELEASE_TAG" --format json > attestation.json\nnode scripts/release-builder.mjs verify --release final.json --expected expected.json --attestation attestation.json',
    },
  ];
}

function releaseWorkflow() {
  return {
    on: {
      pull_request: null,
      push: { branches: ["main"] },
      repository_dispatch: { types: [RELEASE_EVENT] },
      workflow_dispatch: null,
    },
    permissions: { contents: "read" },
    concurrency: { group: `hard-eng-release-${SOURCE_EXPRESSION}`, "cancel-in-progress": false },
    jobs: {
      ...requiredJobs(),
      release: {
        "runs-on": "ubuntu-24.04",
        if: RELEASE_IF,
        needs: ["hard-eng", "windows-assets"],
        permissions: { contents: "write", attestations: "read" },
        steps: releaseSteps(),
      },
    },
  };
}

function updaterWorkflow() {
  return {
    on: { schedule: [{ cron: "30 3 * * *" }], workflow_dispatch: null },
    permissions: { contents: "write" },
    jobs: {
      update: {
        steps: [
          { name: "Check out default branch", uses: PINNED_CHECKOUT },
          { name: "Set up Node.js", uses: PINNED_NODE },
          {
            name: "Check mutation readiness",
            run: "python3 skills/deterministic-checks/scripts/worktree.py --repo . --intent write",
          },
          { name: "Install pinned repository checks", run: "npm ci --ignore-scripts" },
          {
            name: "Map checkout to the global agents home",
            run: "mkdir -p $RUNNER_TEMP/managed-skills-home",
          },
          { name: "Update every locked skill", run: "./scripts/update-managed-skills.sh --ci" },
          {
            name: "Validate and commit updates",
            id: "commit-updates",
            run: 'set -euo pipefail\nif git diff --cached --quiet; then printf "changed=false\\n" >> "$GITHUB_OUTPUT"; exit 0; fi\ngit commit -m update\ngit push origin HEAD:main\nprintf "changed=true\\nsha=%s\\n" "$(git rev-parse HEAD)" >> "$GITHUB_OUTPUT"',
          },
          {
            name: "Read back remote main after push",
            id: "remote-main",
            if: "steps.commit-updates.outputs.changed == 'true'",
            run: 'set -euo pipefail\nremote_sha="$(gh api "repos/$GITHUB_REPOSITORY/git/ref/heads/$DEFAULT_BRANCH" --jq ".object.sha")"\ntest "$remote_sha" = "$EXPECTED_SHA"\nprintf "sha=%s\\n" "$remote_sha" >> "$GITHUB_OUTPUT"',
          },
          {
            name: "Dispatch canonical release for exact SHA",
            if: "steps.commit-updates.outputs.changed == 'true'",
            run: 'set -euo pipefail\ngh api --method POST "repos/$GITHUB_REPOSITORY/dispatches" -f event_type=hard-eng-release -f "client_payload[sha]=$RELEASE_SHA"',
          },
        ],
      },
    },
  };
}

function expectFailure(call, message) {
  assert.throws(
    call,
    (error) =>
      error instanceof ReleaseWorkflowContractError && new RegExp(message).test(error.message),
  );
}

test("accepts trusted source, full gate needs, exact assets, and updater dispatch", () => {
  assert.equal(validateReleaseWorkflow(releaseWorkflow()), true);
  assert.equal(validateManagedSkillsWorkflow(updaterWorkflow()), true);
});

test("rejects manual, untrusted, or wrong-ref release conditions", () => {
  const wrongEvent = releaseWorkflow();
  wrongEvent.jobs.release.if = `${EXPRESSION_START} github.event_name == 'workflow_dispatch' }}`;
  expectFailure(() => validateReleaseWorkflow(wrongEvent), "trusted main");
  const wrongActor = releaseWorkflow();
  wrongActor.jobs.release.if = RELEASE_IF.replace("github-actions[bot]", "octocat");
  expectFailure(() => validateReleaseWorkflow(wrongActor), "trusted main");
  const missingPayload = releaseWorkflow();
  missingPayload.jobs.release.if = RELEASE_IF.replace(
    " && github.event.client_payload.sha != ''",
    "",
  );
  expectFailure(() => validateReleaseWorkflow(missingPayload), "trusted main");
});

test("requires all required jobs, source checkout, and non-bypass behavior", () => {
  const missing = releaseWorkflow();
  missing.jobs.release.needs = ["hard-eng"];
  expectFailure(() => validateReleaseWorkflow(missing), "every required");
  const noRef = releaseWorkflow();
  delete noRef.jobs["windows-assets"].steps[0].with.ref;
  expectFailure(() => validateReleaseWorkflow(noRef), "checkout");
  const bypass = releaseWorkflow();
  bypass.jobs["hard-eng"]["continue-on-error"] = true;
  expectFailure(() => validateReleaseWorkflow(bypass), "fail closed");
  const noOp = releaseWorkflow();
  noOp.jobs.release.steps.find(
    (step) => step.name === "Verify draft and publish immutable release",
  ).run = "# gh release edit --draft=false\necho gh release edit --draft=false";
  expectFailure(() => validateReleaseWorkflow(noOp), "publish");
});

test("requires source-SHA concurrency and safe exact rerun conditions", () => {
  const cancelled = releaseWorkflow();
  cancelled.concurrency["cancel-in-progress"] = true;
  expectFailure(() => validateReleaseWorkflow(cancelled), "must not cancel");
  const wrongGroup = releaseWorkflow();
  wrongGroup.concurrency.group = `hard-eng-release-${EXPRESSION_START} github.run_id }}`;
  expectFailure(() => validateReleaseWorkflow(wrongGroup), "source SHA");
  const unguarded = releaseWorkflow();
  delete unguarded.jobs.release.steps.find(
    (step) => step.name === "Verify draft and publish immutable release",
  ).if;
  expectFailure(() => validateReleaseWorkflow(unguarded), "rerun");
  const staleTag = releaseWorkflow();
  staleTag.jobs.release.steps.find(
    (step) => step.name === "Verify draft and publish immutable release",
  ).run =
    "set -euo pipefail\nnode scripts/release-builder.mjs verify-draft --release draft.json --expected expected.json";
  expectFailure(() => validateReleaseWorkflow(staleTag), "prove exact tag");
});

test("requires the current-main eligibility preflight before mutation", () => {
  const missingPreflight = releaseWorkflow();
  missingPreflight.jobs.release.steps.find(
    (step) => step.name === "Check source against current main",
  ).run = "set -euo pipefail\necho source checked";
  expectFailure(() => validateReleaseWorkflow(missingPreflight), "prove SOURCE_SHA is an ancestor");
  const mismatchedWorkflowCheck = releaseWorkflow();
  mismatchedWorkflowCheck.jobs.release.steps.find(
    (step) => step.name === "Check source against current main",
  ).run =
    'set -euo pipefail\nremote_main_sha="$(gh api refs/heads/main --jq ".object.sha")"\ngit merge-base --is-ancestor "$SOURCE_SHA" "$remote_main_sha"';
  expectFailure(
    () => validateReleaseWorkflow(mismatchedWorkflowCheck),
    "prove SOURCE_SHA is an ancestor",
  );
  const wrongCondition = releaseWorkflow();
  wrongCondition.jobs.release.steps.find(
    (step) => step.name === "Check source against current main",
  ).if = "true";
  expectFailure(() => validateReleaseWorkflow(wrongCondition), "exact rerun conditions");
});

test("requires tag claim before draft creation and ignores heredoc text as commands", () => {
  const wrongOrder = releaseWorkflow();
  const steps = wrongOrder.jobs.release.steps;
  const claimIndex = steps.findIndex((step) => step.name === "Claim exact tag commit");
  const draftIndex = steps.findIndex((step) => step.name === "Create draft release");
  [steps[claimIndex], steps[draftIndex]] = [steps[draftIndex], steps[claimIndex]];
  expectFailure(() => validateReleaseWorkflow(wrongOrder), "exact reviewed step set");

  const heredoc = releaseWorkflow();
  heredoc.jobs.release.steps.find((step) => step.name === "Claim exact tag commit").run =
    "set -euo pipefail\ncat <<'SH'\ngh api --method POST refs/tags/$RELEASE_TAG\nnode scripts/release-builder.mjs validate-tag --tag tag.json --expected expected.json\nSH";
  expectFailure(
    () => validateReleaseWorkflow(heredoc),
    "create or read and validate the exact tag",
  );

  const negatedPost = releaseWorkflow();
  negatedPost.jobs.release.steps.find((step) => step.name === "Claim exact tag commit").run =
    'set -euo pipefail\nif ! gh api --method POST "repos/$GITHUB_REPOSITORY/git/refs" -f "ref=refs/tags/$RELEASE_TAG" -f "sha=$SOURCE_SHA"; then exit 1; fi\ngh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$RELEASE_TAG" > claimed-tag.json\nnode scripts/release-builder.mjs validate-tag --tag claimed-tag.json --expected expected.json';
  expectFailure(
    () => validateReleaseWorkflow(negatedPost),
    "create or read and validate the exact tag",
  );

  const wrongPublishOrder = releaseWorkflow();
  wrongPublishOrder.jobs.release.steps.find(
    (step) => step.name === "Verify draft and publish immutable release",
  ).run =
    'set -euo pipefail\ngh release edit "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --draft=false\nnode scripts/release-builder.mjs verify-draft --release draft.json --expected expected.json';
  expectFailure(() => validateReleaseWorkflow(wrongPublishOrder), "immediately before publishing");

  const separatePublish = releaseWorkflow();
  const combined = separatePublish.jobs.release.steps.find(
    (step) => step.name === "Verify draft and publish immutable release",
  );
  combined.name = "Check draft release before publish";
  separatePublish.jobs.release.steps.push({
    name: "Publish immutable release",
    if: "steps.existing-release.outputs.action != 'reuse'",
    run: 'set -euo pipefail\ngh release edit "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --draft=false',
  });
  expectFailure(() => validateReleaseWorkflow(separatePublish), "exact reviewed step set");
});

test("requires immutable capability, exact draft resume, and post-publish attestation", () => {
  const noCapability = releaseWorkflow();
  noCapability.jobs.release.steps.find(
    (step) => step.name === "Check release verification support",
  ).run = "echo gh release verify --help";
  expectFailure(() => validateReleaseWorkflow(noCapability), "capability");
  const noAttestation = releaseWorkflow();
  noAttestation.jobs.release.steps.find((step) => step.name === "Verify immutable release").run =
    "set -euo pipefail\ngh api final\ngh release verify tag\nnode scripts/release-builder.mjs verify --release final --expected expected";
  expectFailure(() => validateReleaseWorkflow(noAttestation), "attestation");
  const noDispatchReadback = updaterWorkflow();
  noDispatchReadback.jobs.update.steps[7].run =
    'set -euo pipefail\nprintf \'sha=%s\\n\' "$remote_sha" >> "$GITHUB_OUTPUT"';
  expectFailure(() => validateManagedSkillsWorkflow(noDispatchReadback), "read back remote");
});

test("rejects updater dispatch before remote readback or mismatched pushed SHA", () => {
  const missingReadback = updaterWorkflow();
  missingReadback.jobs.update.steps.splice(7, 1);
  expectFailure(() => validateManagedSkillsWorkflow(missingReadback), "step set");
  const wrongCompare = updaterWorkflow();
  wrongCompare.jobs.update.steps[7].run =
    'set -euo pipefail\ngh api refs/heads/$DEFAULT_BRANCH\ntest "$remote_sha" = "$OTHER_SHA"';
  expectFailure(() => validateManagedSkillsWorkflow(wrongCompare), "read back remote");
  const continueOnError = updaterWorkflow();
  continueOnError.jobs.update.steps[8]["continue-on-error"] = true;
  expectFailure(() => validateManagedSkillsWorkflow(continueOnError), "fail closed");
});
