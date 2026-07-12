import fs from 'node:fs';
import path from 'node:path';

export function resolveContainedPath(root, relative, { label = 'Path' } = {}) {
  if (
    typeof relative !== 'string'
    || !relative
    || relative.includes('\\')
    || relative.includes('\0')
    || path.posix.isAbsolute(relative)
    || path.posix.normalize(relative) !== relative
    || relative.split('/').some((part) => !part || part === '..')
  ) throw new Error(`${label} is not a safe repository-relative path.`);

  const base = fs.realpathSync(root);
  let target = base;
  for (const part of relative.split('/')) {
    target = path.join(target, part);
    const stat = fs.lstatSync(target);
    if (stat.isSymbolicLink()) throw new Error(`${label} contains a symlink.`);
  }
  if (!target.startsWith(`${base}${path.sep}`)) throw new Error(`${label} escapes the repository.`);
  return { target, stat: fs.lstatSync(target) };
}
