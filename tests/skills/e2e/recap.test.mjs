import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';

const repoRoot = path.resolve(new URL('../../..', import.meta.url).pathname);
const recap = path.join(repoRoot, 'skills/e2e/scripts/make-2x-recap.mjs');
const hasFfmpeg = spawnSync('ffmpeg', ['-version'], { encoding: 'utf8' }).status === 0;
const hasFfprobe = spawnSync('ffprobe', ['-version'], { encoding: 'utf8' }).status === 0;

function makeDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'e2e-recap-'));
}

function secondsFor(file) {
  const result = spawnSync('ffprobe', [
    '-v',
    'error',
    '-show_entries',
    'format=duration',
    '-of',
    'default=noprint_wrappers=1:nokey=1',
    file,
  ], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  return Number(result.stdout.trim());
}

test('2x recap helper creates a shorter MP4 when ffmpeg is available', { skip: !hasFfmpeg && 'ffmpeg unavailable' }, () => {
  const dir = makeDir();
  const input = path.join(dir, 'input.mp4');
  const output = path.join(dir, 'recap.mp4');

  const create = spawnSync('ffmpeg', [
    '-hide_banner',
    '-loglevel',
    'error',
    '-f',
    'lavfi',
    '-i',
    'color=c=black:s=320x180:d=2:r=10',
    '-pix_fmt',
    'yuv420p',
    input,
  ], { encoding: 'utf8' });
  assert.equal(create.status, 0, create.stderr);

  const result = spawnSync('node', [recap, '--input', input, '--output', output], {
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.equal(fs.existsSync(output), true);
  assert.ok(fs.statSync(output).size > 0);

  if (hasFfprobe) {
    assert.ok(secondsFor(output) < secondsFor(input));
  }
});

test('2x recap helper refuses to overwrite existing output', () => {
  const dir = makeDir();
  const input = path.join(dir, 'input.mp4');
  const output = path.join(dir, 'recap.mp4');
  fs.writeFileSync(input, 'input');
  fs.writeFileSync(output, 'existing');

  const result = spawnSync('node', [recap, '--input', input, '--output', output], {
    encoding: 'utf8',
  });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Refusing to overwrite/);
  assert.equal(fs.readFileSync(output, 'utf8'), 'existing');
});

test('2x recap helper rejects missing input', () => {
  const dir = makeDir();
  const result = spawnSync('node', [
    recap,
    '--input',
    path.join(dir, 'missing.mp4'),
    '--output',
    path.join(dir, 'recap.mp4'),
  ], { encoding: 'utf8' });

  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Missing input video/);
});
