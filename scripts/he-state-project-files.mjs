import fs from 'node:fs';
import path from 'node:path';

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function nearestProjectRoot(start) {
  let current = path.resolve(start || process.cwd());
  while (true) {
    if (fs.existsSync(path.join(current, '.git'))) return current;
    const parent = path.dirname(current);
    if (parent === current) return '';
    current = parent;
  }
}

export function projectRoot(options = {}) {
  const configured = options.projectRoot || options.liveRepo;
  const candidate = configured ? path.resolve(configured) : nearestProjectRoot(options.root);
  if (!candidate || !fs.existsSync(path.join(candidate, '.git'))) return '';
  try {
    return fs.realpathSync(candidate);
  } catch {
    return candidate;
  }
}

function isWithin(root, candidate) {
  const relative = path.relative(root, candidate);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
}

export function resolveProjectFile(value, options = {}) {
  if (!hasText(value)) return { ok: false, error: 'must be a non-empty project-relative path' };
  if (path.isAbsolute(value)) return { ok: false, error: 'must use a project-relative path' };
  const root = projectRoot(options);
  if (!root) return { ok: false, error: 'requires a real Git project root' };
  const candidate = path.resolve(root, value);
  if (!isWithin(root, candidate)) return { ok: false, error: 'must stay within the project root' };
  let real;
  let stat;
  try {
    real = fs.realpathSync(candidate);
    stat = fs.statSync(real);
  } catch {
    return { ok: false, error: 'does not exist' };
  }
  if (!isWithin(root, real)) return { ok: false, error: 'must not resolve outside the project root' };
  if (!stat.isFile()) return { ok: false, error: 'must reference a file' };
  return { ok: true, root, absolute: real, relative: path.relative(root, real).split(path.sep).join('/') };
}

export function splitProjectReference(value) {
  if (!hasText(value)) return null;
  const hashIndex = value.indexOf('#');
  if (hashIndex > 0) {
    return { file: value.slice(0, hashIndex), locator: value.slice(hashIndex) };
  }
  const lineMatch = value.match(/^(.*):L(\d+)(?:-L?(\d+))?$/i);
  if (!lineMatch?.[1]) return null;
  return { file: lineMatch[1], locator: `#L${lineMatch[2]}${lineMatch[3] ? `-L${lineMatch[3]}` : ''}` };
}

function markdownHeadingSlugs(text) {
  const seen = new Map();
  const slugs = new Set();
  for (const line of text.split(/\r\n|\n|\r/)) {
    const match = line.match(/^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$/);
    if (!match) continue;
    const base = match[1]
      .toLowerCase()
      .replace(/<[^>]*>/g, '')
      .replace(/[^\p{L}\p{N}\s_-]/gu, '')
      .trim()
      .replace(/\s+/g, '-');
    const count = seen.get(base) || 0;
    seen.set(base, count + 1);
    slugs.add(count ? `${base}-${count}` : base);
  }
  return slugs;
}

export function resolveProjectReference(value, options = {}) {
  const reference = splitProjectReference(value);
  if (!reference || !hasText(reference.locator.slice(1))) {
    return { ok: false, error: 'must contain a file and concrete locator' };
  }
  const file = resolveProjectFile(reference.file, options);
  if (!file.ok) return file;
  const text = fs.readFileSync(file.absolute, 'utf8');
  const lineMatch = reference.locator.match(/^#L(\d+)(?:-L?(\d+))?$/i);
  if (lineMatch) {
    const start = Number(lineMatch[1]);
    const end = Number(lineMatch[2] || lineMatch[1]);
    const lineCount = text.split(/\r\n|\n|\r/).length;
    if (start < 1 || end < start || end > lineCount) return { ok: false, error: 'has a line locator outside the referenced file' };
  } else if (path.extname(file.absolute).toLowerCase() === '.md') {
    let slug;
    try {
      slug = decodeURIComponent(reference.locator.slice(1)).toLowerCase();
    } catch {
      return { ok: false, error: 'has an invalid encoded heading locator' };
    }
    if (!markdownHeadingSlugs(text).has(slug) && !new RegExp(`\\bid=["']${slug.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}["']`, 'i').test(text)) {
      return { ok: false, error: `references missing heading #${slug}` };
    }
  } else {
    return { ok: false, error: 'non-Markdown references require a line locator' };
  }
  return { ...file, locator: reference.locator };
}
