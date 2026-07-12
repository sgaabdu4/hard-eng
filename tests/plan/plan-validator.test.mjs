import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { makeRepo } from '../fixtures/repo-fixture.mjs';
import { makePlan, withAcceptedDigest } from '../fixtures/plan-fixture.mjs';
import {
  computePlanDigest,
  inspectPlanOwnership,
  renderPlanExcerpt,
  validatePlanFile,
  validatePlanText,
} from '../../runtime/lib/plan.mjs';
import { sha256 } from '../../runtime/lib/canonical.mjs';
import { runCommand } from '../../runtime/he.mjs';

test('ready and accepted plans validate all canonical sections and stable digest', () => {
  const pending = makePlan();
  const ready = validatePlanText(pending, { runId: 'he-plan-fixture', requireAccepted: false });
  assert.equal(ready.status, 'PASS');
  assert.equal(Object.keys(ready.sections).length, 11);
  assert.equal(ready.open_domains.length, 0);
  assert.equal(ready.adversarial_categories.length, 8);

  const digest = computePlanDigest(pending);
  const accepted = withAcceptedDigest(pending, digest);
  assert.equal(validatePlanText(accepted, { runId: 'he-plan-fixture', requireAccepted: true }).digest, digest);
  assert.equal(computePlanDigest(accepted), digest);
});

test('validator rejects open domains, incomplete adversarial coverage, and foreign plan owners', () => {
  assert.throws(() => validatePlanText(makePlan({ openDomain: 'D4' }), { runId: 'he-plan-fixture' }), /open readiness/i);
  assert.throws(() => validatePlanText(makePlan({ omitAdversarial: 'A6' }), { runId: 'he-plan-fixture' }), /A6/i);
  assert.equal(inspectPlanOwnership('# Existing user plan\n').status, 'foreign');
  assert.equal(inspectPlanOwnership(`Prelude\n${makePlan()}`).status, 'foreign');
  assert.throws(() => validatePlanText(makePlan().replace('\n# Plan:', '\n\n# Plan:'), {
    runId: 'he-plan-fixture',
  }), /immediately after its owner header/i);
  assert.throws(() => validatePlanText(makePlan(), { runId: 'another-run' }), /run ID/i);
  assert.throws(() => validatePlanText(makePlan().replace('D2 actors/permissions/trust/accessibility', 'D2 wrong-domain'), {
    runId: 'he-plan-fixture',
  }), /D2.*label/i);
  assert.throws(() => validatePlanText(makePlan().replace('A3 journey failure', 'A3 wrong-category'), {
    runId: 'he-plan-fixture',
  }), /A3.*label/i);
  assert.throws(() => validatePlanText(makePlan().replace('| S1 | Establish the owner | runtime | none | P1 |', '| S1 | Establish the owner | runtime | S2 | P1 |'), {
    runId: 'he-plan-fixture',
  }), /dependency/i);
});

test('Plan slice IDs are contiguous so the state cursor cannot skip planned work', () => {
  const skipped = makePlan().replace('| S2 | Complete the behavior |', '| S3 | Complete the behavior |');
  assert.throws(() => validatePlanText(skipped, { runId: 'he-plan-fixture' }), /contiguous|S2/i);
  const skippedProof = makePlan()
    .replace('| S2 | Complete the behavior | runtime | S1 | P2 |', '| S2 | Complete the behavior | runtime | S1 | P3 |')
    .replace('| P2 | Journey passes end to end |', '| P3 | Journey passes end to end |');
  assert.throws(() => validatePlanText(skippedProof, { runId: 'he-plan-fixture' }), /contiguous|P2/i);
});

test('post-approval edits invalidate the accepted digest', () => {
  const pending = makePlan();
  const accepted = withAcceptedDigest(pending, computePlanDigest(pending));
  assert.throws(() => validatePlanText(`${accepted}\nChanged after approval.\n`, {
    runId: 'he-plan-fixture', requireAccepted: true,
  }), /digest/i);
});

test('UI plan verifies a run-owned coded prototype and realistic edge states', () => {
  const repo = makeRepo();
  const runId = 'he-ui-fixture';
  const relative = `.hard-eng/prototypes/${runId}/flow.html`;
  const target = path.join(repo, relative);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  const html = '<!doctype html><html><body data-hard-eng-prototype="interactive" data-mock="realistic-sanitized"><button>Continue</button><section data-state="happy loading empty validation permission error">Mock flow</section></body></html>';
  fs.writeFileSync(target, html);
  const pending = makePlan({ runId, ui: { prototypePath: relative, prototypeDigest: sha256(html) } });
  fs.writeFileSync(path.join(repo, 'plan.md'), pending);
  assert.equal(validatePlanFile(repo, { runId, requireAccepted: false }).ui.applicable, true);

  fs.writeFileSync(target, `${html}\nchanged`);
  assert.throws(() => validatePlanFile(repo, { runId, requireAccepted: false }), /prototype digest/i);
});

test('UI prototype cannot escape through a symlinked parent', () => {
  const repo = makeRepo('hard-eng-ui-symlink-');
  const runId = 'he-ui-symlink';
  const outside = fs.mkdtempSync(path.join(path.dirname(repo), 'hard-eng-ui-outside-'));
  const html = '<!doctype html><html><body data-hard-eng-prototype="interactive" data-mock="realistic-sanitized"><button>Continue</button><p>happy loading empty validation permission error</p></body></html>';
  fs.writeFileSync(path.join(outside, 'flow.html'), html);
  fs.mkdirSync(path.join(repo, '.hard-eng', 'prototypes'), { recursive: true });
  fs.symlinkSync(outside, path.join(repo, '.hard-eng', 'prototypes', runId));
  const relative = `.hard-eng/prototypes/${runId}/flow.html`;
  fs.writeFileSync(path.join(repo, 'plan.md'), makePlan({
    runId,
    ui: { prototypePath: relative, prototypeDigest: sha256(html) },
  }));
  assert.throws(() => validatePlanFile(repo, { runId }), /symlink|escape/i);
});

test('existing UI baseline proves reproducible scenario metadata and screenshot digest', () => {
  const repo = makeRepo();
  const runId = 'he-baseline-fixture';
  const prefix = `.hard-eng/baselines/${runId}`;
  const screenshotRelative = `${prefix}/before.png`;
  const screenshot = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nfsAAAAASUVORK5CYII=', 'base64');
  fs.mkdirSync(path.join(repo, prefix), { recursive: true });
  fs.writeFileSync(path.join(repo, screenshotRelative), screenshot);
  const metadata = {
    commit_or_tree: 'a'.repeat(40),
    route: '/fixture',
    role: 'member',
    seed_state: 'sanitized-seed-v1',
    viewport_or_device: '1440x900',
    environment: 'local deterministic fixture',
    screenshots: [{ path: screenshotRelative, digest: sha256(screenshot) }],
  };
  const metadataRelative = `${prefix}/baseline.json`;
  const metadataText = JSON.stringify(metadata);
  fs.writeFileSync(path.join(repo, metadataRelative), metadataText);

  const prototypeRelative = `.hard-eng/prototypes/${runId}/flow.html`;
  const prototype = '<html><body data-hard-eng-prototype="interactive" data-mock="realistic-sanitized"><button>Go</button><div>happy loading empty validation permission error</div></body></html>';
  fs.mkdirSync(path.dirname(path.join(repo, prototypeRelative)), { recursive: true });
  fs.writeFileSync(path.join(repo, prototypeRelative), prototype);
  const plan = makePlan({
    runId,
    ui: {
      baseline: `${metadataRelative} @ ${sha256(metadataText)}`,
      designOwner: 'src/theme/tokens.css',
      exploration: 'existing-system',
      prototypePath: prototypeRelative,
      prototypeDigest: sha256(prototype),
    },
  });
  fs.writeFileSync(path.join(repo, 'plan.md'), plan);
  assert.equal(validatePlanFile(repo, { runId }).ui.baseline.applicable, true);
  fs.writeFileSync(path.join(repo, metadataRelative), JSON.stringify({ ...metadata, role: null }));
  assert.throws(() => validatePlanFile(repo, { runId }), /baseline metadata|digest/i);
});

test('Imagegen exploration requires explicit budget, sanitized brief, and two or three comparable board digests', () => {
  const repo = makeRepo();
  const runId = 'he-imagegen-fixture';
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nfsAAAAASUVORK5CYII=', 'base64');
  const boardBytes = [png, Buffer.concat([png, Buffer.from([0])])];
  const boardDir = `.hard-eng/directions/${runId}`;
  fs.mkdirSync(path.join(repo, boardDir), { recursive: true });
  const boardPaths = [`${boardDir}/one.png`, `${boardDir}/two.png`];
  boardPaths.forEach((relative, index) => fs.writeFileSync(path.join(repo, relative), boardBytes[index]));
  const prototypeRelative = `.hard-eng/prototypes/${runId}/flow.html`;
  const prototype = '<html><body data-hard-eng-prototype="interactive" data-mock="realistic-sanitized"><button>Go</button><div>happy loading empty validation permission error</div></body></html>';
  fs.mkdirSync(path.dirname(path.join(repo, prototypeRelative)), { recursive: true });
  fs.writeFileSync(path.join(repo, prototypeRelative), prototype);
  const plan = makePlan({
    runId,
    ui: {
      exploration: 'imagegen',
      directionBoards: boardPaths.map((relative, index) => `${relative} @ ${sha256(boardBytes[index])}`).join('; '),
      prototypePath: prototypeRelative,
      prototypeDigest: sha256(prototype),
    },
  });
  fs.writeFileSync(path.join(repo, 'plan.md'), plan);
  assert.equal(validatePlanFile(repo, { runId }).ui.direction_boards.length, 2);
  const duplicateBoard = plan.replace(
    `${boardPaths[1]} @ ${sha256(boardBytes[1])}`,
    `${boardPaths[0]} @ ${sha256(boardBytes[0])}`,
  );
  fs.writeFileSync(path.join(repo, 'plan.md'), duplicateBoard);
  assert.throws(() => validatePlanFile(repo, { runId }), /distinct artifacts/i);
  fs.writeFileSync(path.join(repo, 'plan.md'), plan.replace('approved: 2 calls', 'pending'));
  assert.throws(() => validatePlanFile(repo, { runId }), /approved two- or three-call budget/i);
});

test('Build excerpt contains global constraints and only the current slice proof', () => {
  const text = makePlan();
  const excerpt = renderPlanExcerpt(text, { runId: 'he-plan-fixture', sliceId: 'S1' });
  assert.match(excerpt, /S1/);
  assert.match(excerpt, /P1/);
  assert.match(excerpt, /Readiness ledger/);
  assert.match(excerpt, /Validate inputs, preserve privacy/);
  assert.doesNotMatch(excerpt, /S2 \| Complete|P2 \| Journey/);
  assert.ok(excerpt.length < 4_800, `excerpt too large: ${excerpt.length}`);
});

test('read-only he Plan commands validate, digest, and render one slice', () => {
  const repo = makeRepo();
  const text = makePlan();
  fs.writeFileSync(path.join(repo, 'plan.md'), text);
  assert.equal(runCommand(['plan-validate', '--repo', repo, '--run', 'he-plan-fixture']).status, 'PASS');
  assert.equal(runCommand(['plan-digest', '--repo', repo, '--run', 'he-plan-fixture']), computePlanDigest(text));
  const excerpt = runCommand(['plan-excerpt', '--repo', repo, '--run', 'he-plan-fixture', '--slice', 'S2']);
  assert.match(excerpt, /S2/);
  assert.match(excerpt, /P2/);
  assert.doesNotMatch(excerpt, /S1 \| Establish/);
});
