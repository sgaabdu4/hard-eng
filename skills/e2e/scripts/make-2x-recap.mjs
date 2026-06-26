#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const args = process.argv.slice(2);
const inputIndex = args.indexOf('--input');
const outputIndex = args.indexOf('--output');

if (inputIndex === -1 || outputIndex === -1 || !args[inputIndex + 1] || !args[outputIndex + 1]) {
  console.error('Usage: make-2x-recap.mjs --input <cursor-video.mp4> --output <recap.mp4>');
  process.exit(2);
}

const input = path.resolve(args[inputIndex + 1]);
const output = path.resolve(args[outputIndex + 1]);

if (!fs.existsSync(input)) {
  console.error(`Missing input video: ${input}`);
  process.exit(1);
}
if (fs.existsSync(output)) {
  console.error(`Refusing to overwrite existing output: ${output}`);
  process.exit(1);
}

fs.mkdirSync(path.dirname(output), { recursive: true });

const result = spawnSync('ffmpeg', [
  '-hide_banner',
  '-loglevel',
  'error',
  '-i',
  input,
  '-map',
  '0:v:0',
  '-filter:v',
  'setpts=0.5*PTS',
  '-an',
  '-movflags',
  '+faststart',
  output,
], { encoding: 'utf8' });

if (result.status !== 0) {
  console.error(result.stderr || result.stdout || 'ffmpeg failed');
  process.exit(result.status || 1);
}

console.log(JSON.stringify({
  status: 'created',
  input,
  output,
  speed: '2x',
  audio: 'omitted',
}, null, 2));
