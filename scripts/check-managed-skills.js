const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const fail = (message) => {
  console.error(`managed-skills: ${message}`);
  process.exit(1);
};

const objectHash = (type, body) => crypto
  .createHash('sha1')
  .update(`${type} ${body.length}\0`)
  .update(body)
  .digest();

const treeHash = (directory) => {
  const entries = fs.readdirSync(directory, { withFileTypes: true }).map((entry) => {
    const target = path.join(directory, entry.name);
    if (entry.isSymbolicLink()) fail(`${target} must not be a symlink`);
    if (entry.isDirectory()) {
      return { name: entry.name, mode: '40000', hash: treeHash(target), directory: true };
    }
    if (!entry.isFile()) fail(`${target} has an unsupported file type`);

    const body = fs.readFileSync(target);
    const mode = (fs.statSync(target).mode & 0o111) ? '100755' : '100644';
    return { name: entry.name, mode, hash: objectHash('blob', body), directory: false };
  });

  entries.sort((left, right) => {
    const leftName = Buffer.from(left.name + (left.directory ? '/' : ''));
    const rightName = Buffer.from(right.name + (right.directory ? '/' : ''));
    return leftName.compare(rightName);
  });

  const body = Buffer.concat(entries.flatMap((entry) => [
    Buffer.from(`${entry.mode} ${entry.name}\0`),
    entry.hash,
  ]));
  return objectHash('tree', body);
};

process.chdir(root);

let lock;
try {
  lock = JSON.parse(fs.readFileSync('.skill-lock.json', 'utf8'));
} catch (error) {
  fail(`invalid .skill-lock.json: ${error.message}`);
}

if (!lock.skills || typeof lock.skills !== 'object' || Array.isArray(lock.skills)) {
  fail('.skill-lock.json.skills must be an object');
}

const names = Object.keys(lock.skills).sort();
const folders = fs.readdirSync('skills', { withFileTypes: true })
  .map((entry) => entry.name)
  .sort();

if (names.length === 0) fail('the lock contains no skills');
if (JSON.stringify(folders) !== JSON.stringify(names)) {
  fail(`skills/ must equal lock keys; lock=[${names.join(', ')}] folders=[${folders.join(', ')}]`);
}

for (const name of names) {
  if (!/^[a-z0-9][a-z0-9-]*$/.test(name)) fail(`unsafe lock key: ${name}`);

  const directory = path.join('skills', name);
  const stat = fs.lstatSync(directory);
  if (!stat.isDirectory() || stat.isSymbolicLink()) fail(`${directory} must be a plain directory`);
  if (!fs.existsSync(path.join(directory, 'SKILL.md'))) fail(`${directory}/SKILL.md is missing`);

  const item = lock.skills[name];
  for (const field of ['source', 'sourceType', 'sourceUrl', 'skillPath', 'skillFolderHash']) {
    if (!item || typeof item[field] !== 'string' || item[field].length === 0) {
      fail(`${name}.${field} is missing`);
    }
  }
  for (const field of ['installedAt', 'updatedAt']) {
    if (typeof item[field] !== 'string' || !item[field].endsWith('Z') || Number.isNaN(Date.parse(item[field]))) {
      fail(`${name}.${field} must be a UTC timestamp`);
    }
  }

  const actual = treeHash(directory).toString('hex');
  if (actual !== item.skillFolderHash) {
    fail(`${directory} differs from its locked upstream hash`);
  }
}

console.log(`managed-skills: PASS (${names.length} locked skills match upstream hashes)`);
