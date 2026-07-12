import fs from 'node:fs';
import path from 'node:path';

function mirrorModes(source, destination) {
  const stat = fs.lstatSync(source);
  if (stat.isSymbolicLink()) return;
  if (stat.isDirectory()) {
    for (const entry of fs.readdirSync(source)) {
      mirrorModes(path.join(source, entry), path.join(destination, entry));
    }
  }
  fs.chmodSync(destination, stat.mode & 0o777);
}

export function copyDirectoryExact(source, destination) {
  const stat = fs.lstatSync(source);
  if (!stat.isDirectory() || stat.isSymbolicLink()) {
    throw new Error('Exact directory copy requires a real directory source.');
  }
  fs.cpSync(source, destination, {
    recursive: true,
    dereference: false,
    preserveTimestamps: true,
    verbatimSymlinks: true,
  });
  mirrorModes(source, destination);
}
