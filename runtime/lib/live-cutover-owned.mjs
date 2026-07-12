import fs from 'node:fs';
import path from 'node:path';

export const BOOTSTRAP_PATH = '.zshenv';
export const E2E_CACHE_PATH = '.cache/hard-eng/e2e-playwright';

const oldBegin = '# BEGIN hard-eng bootstrap path';
const oldEnd = '# END hard-eng bootstrap path';
const newBegin = '# BEGIN personal toolchain path';
const newEnd = '# END personal toolchain path';

function count(text, token) {
  return text.split(token).length - 1;
}

export function neutralizeBootstrap(bytes) {
  if (!Buffer.isBuffer(bytes) || bytes.length > 1024 * 1024 || bytes.includes(0)) {
    throw new Error('Hard Eng bootstrap owner is unsafe or oversized.');
  }
  const text = bytes.toString('utf8');
  const oldCounts = [count(text, oldBegin), count(text, oldEnd)];
  const newCounts = [count(text, newBegin), count(text, newEnd)];
  if (oldCounts[0] === 0 && oldCounts[1] === 0) {
    if (newCounts[0] === newCounts[1] && newCounts[0] <= 1) return null;
    throw new Error('Personal toolchain bootstrap markers are malformed.');
  }
  if (
    oldCounts[0] !== 1
    || oldCounts[1] !== 1
    || newCounts[0] !== 0
    || newCounts[1] !== 0
    || text.indexOf(oldBegin) >= text.indexOf(oldEnd)
  ) throw new Error('Hard Eng bootstrap markers are malformed.');
  return Buffer.from(text.replace(oldBegin, newBegin).replace(oldEnd, newEnd));
}

function exactType(target, type) {
  const stat = fs.lstatSync(target);
  if (stat.isSymbolicLink()) return false;
  return type === 'file' ? stat.isFile() : stat.isDirectory();
}

export function validateE2eCache(directory) {
  const top = fs.readdirSync(directory).sort();
  if (JSON.stringify(top) !== JSON.stringify(['node_modules', 'package-lock.json', 'package.json'])) {
    throw new Error('Hard Eng E2E cache contains an unexpected top-level entry.');
  }
  if (
    !exactType(path.join(directory, 'package.json'), 'file')
    || !exactType(path.join(directory, 'package-lock.json'), 'file')
    || !exactType(path.join(directory, 'node_modules'), 'directory')
  ) throw new Error('Hard Eng E2E cache ownership shape is invalid.');

  const modules = fs.readdirSync(path.join(directory, 'node_modules')).sort();
  const allowed = new Set(['.bin', '.package-lock.json', 'fsevents', 'playwright', 'playwright-core']);
  if (
    modules.some((name) => !allowed.has(name))
    || !modules.includes('playwright')
    || !modules.includes('playwright-core')
    || !exactType(path.join(directory, 'node_modules', 'playwright'), 'directory')
    || !exactType(path.join(directory, 'node_modules', 'playwright-core'), 'directory')
  ) throw new Error('Hard Eng E2E cache contains an unknown package or invalid owner.');
}

export function validateCanonicalTeach(sourceRoot) {
  const root = path.join(sourceRoot, 'skills', 'teach');
  for (const relative of [
    'SKILL.md', 'MISSION-FORMAT.md', 'RESOURCES-FORMAT.md',
    'LEARNING-RECORD-FORMAT.md', 'GLOSSARY-FORMAT.md',
    'references/workflow.md', 'agents/openai.yaml',
  ]) {
    const target = path.join(root, relative);
    if (!fs.existsSync(target) || !exactType(target, 'file')) {
      throw new Error(`Canonical Teach parity owner is missing: ${relative}.`);
    }
  }
  const skill = fs.readFileSync(path.join(root, 'SKILL.md'), 'utf8');
  const workflow = fs.readFileSync(path.join(root, 'references', 'workflow.md'), 'utf8');
  if (!/references\/workflow\.md/.test(skill)) throw new Error('Canonical Teach skill does not load its workflow owner.');
  for (const requirement of [
    /MISSION\.md/, /trusted resources/i, /parametric memory/i,
    /retrieval practice/i, /spacing/i, /interleaving/i,
    /accessible, clean, readable, and print-friendly/i,
    /primary source/i, /follow-up questions/i, /Reuse is the default/i,
    /Zone Of Proximal Development/i, /community/i, /NOTES\.md/,
  ]) {
    if (!requirement.test(workflow)) throw new Error(`Canonical Teach parity is incomplete: ${requirement}.`);
  }
  return true;
}
