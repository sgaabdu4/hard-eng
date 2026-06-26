#!/usr/bin/env node
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const scriptDir = dirname(fileURLToPath(import.meta.url));

function usage() {
  console.log(`Usage:
  export-html-deck.mjs --url <url> --out <pdf> [options]

Options:
  --selector <css>        Page/slide selector. Default: .slide
  --width <px>            Browser viewport width. Default: 1280
  --height <px>           Browser viewport height. Default: 720
  --scale <n>             Device scale factor for capture. Default: 2
  --quality <1-100>       JPEG quality. Default: 94
  --work-dir <path>       Temp directory. Default: tmp/pdfs/create-pdf
  --python <path>         Python executable. Default: python3
  --pdftoppm <path>       pdftoppm executable for QA. Default: pdftoppm
  --no-links              Do not preserve HTML anchors as PDF links.
  --skip-qa               Skip render-back contact sheet QA.
  --keep-work-dir         Do not remove intermediate files.
  --require-font <family>  Fail if the computed font stack and loaded FontFace set do not include this family.
  --font-weights <csv>     Optional required weights, e.g. "400,500,600".
  --font-selector <css>    Element used for computed font checks. Default: body
  --cache-bust             Add a timestamp query param to the URL before loading.
  --browser-channel <name> Use an installed browser channel such as chrome when Playwright's bundled browser is missing.

Set NODE_PATH to a node_modules directory containing playwright when needed.`);
}

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i += 1) {
    const item = argv[i];
    if (!item.startsWith('--')) continue;
    const key = item.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith('--')) {
      args[key] = true;
    } else {
      args[key] = next;
      i += 1;
    }
  }
  return args;
}

function run(command, commandArgs, label) {
  const result = spawnSync(command, commandArgs, { stdio: 'inherit' });
  if (result.error) {
    throw new Error(`${label} failed: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`${label} exited with status ${result.status}`);
  }
}

function withCacheBust(url) {
  if (!args['cache-bust']) return url;
  try {
    const parsed = new URL(url);
    parsed.searchParams.set('_pdf_cache', String(Date.now()));
    return parsed.href;
  } catch {
    const separator = url.includes('?') ? '&' : '?';
    return `${url}${separator}_pdf_cache=${Date.now()}`;
  }
}

async function assertRequiredFont(page, requiredFont, fontWeights, fontSelector) {
  if (!requiredFont) return;
  const fontCheck = await page.evaluate(({ requiredFont, fontWeights, fontSelector }) => {
    const normalizeFont = (value) => String(value || '').replace(/^["']|["']$/g, '').toLowerCase();
    const target = document.querySelector(fontSelector) || document.body;
    const computed = getComputedStyle(target);
    const expected = normalizeFont(requiredFont);
    const loadedFaces = document.fonts
      ? [...document.fonts].map((font) => ({
        family: font.family,
        weight: font.weight,
        status: font.status,
      })).filter((font) => normalizeFont(font.family) === expected)
      : [];
    const loadedWeights = new Set(loadedFaces.filter((font) => font.status === 'loaded').map((font) => String(font.weight)));
    const missingWeights = fontWeights.filter((weight) => !loadedWeights.has(String(weight)));
    const familyInComputedStack = computed.fontFamily
      .split(',')
      .map((part) => normalizeFont(part.trim()))
      .includes(expected);

    return {
      expectedFamily: requiredFont,
      selector: fontSelector,
      computedFont: computed.font,
      computedFontFamily: computed.fontFamily,
      familyInComputedStack,
      loadedFaces,
      loadedWeights: [...loadedWeights].sort(),
      requiredWeights: fontWeights,
      missingWeights,
      ok: familyInComputedStack && loadedFaces.some((font) => font.status === 'loaded') && missingWeights.length === 0,
    };
  }, { requiredFont, fontWeights, fontSelector });

  if (!fontCheck.ok) {
    throw new Error(`Required font is not active before export: ${JSON.stringify(fontCheck)}`);
  }
  console.log(`Required font active: ${requiredFont} ${fontCheck.loadedWeights.join(',')}`);
}

const args = parseArgs(process.argv);
if (args.help || !args.url || !args.out) {
  usage();
  process.exit(args.help ? 0 : 2);
}

let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (error) {
  console.error('Could not load playwright. Set NODE_PATH to a node_modules directory containing playwright.');
  console.error(error.message);
  process.exit(2);
}

const selector = args.selector || '.slide';
const width = Number(args.width || 1280);
const height = Number(args.height || 720);
const scale = Number(args.scale || 2);
const quality = Number(args.quality || 94);
const out = resolve(args.out);
const workDir = resolve(args['work-dir'] || 'tmp/pdfs/create-pdf');
const captureDir = join(workDir, 'slides');
const python = args.python || process.env.PYTHON || 'python3';
const pdftoppm = args.pdftoppm || process.env.PDFTOPPM || 'pdftoppm';
const linksJson = join(workDir, 'links.json');
const requiredFont = args['require-font'] || '';
const fontWeights = String(args['font-weights'] || '')
  .split(',')
  .map((weight) => weight.trim())
  .filter(Boolean);
const fontSelector = args['font-selector'] || 'body';

mkdirSync(dirname(out), { recursive: true });
if (existsSync(captureDir)) rmSync(captureDir, { recursive: true, force: true });
mkdirSync(captureDir, { recursive: true });

const launchOptions = { headless: true };
if (args['browser-channel'] || process.env.PLAYWRIGHT_CHANNEL) {
  launchOptions.channel = args['browser-channel'] || process.env.PLAYWRIGHT_CHANNEL;
}

const browser = await chromium.launch(launchOptions);
try {
  const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: scale });
  await page.goto(withCacheBust(args.url), { waitUntil: args.wait || 'networkidle' });
  await page.evaluate(async () => {
    document.documentElement.style.scrollBehavior = 'auto';
    await document.fonts?.ready;
    const images = [...document.images];
    await Promise.all(images.map((img) => (
      img.complete && img.naturalWidth > 0
        ? null
        : new Promise((resolve, reject) => {
          img.addEventListener('load', resolve, { once: true });
          img.addEventListener('error', reject, { once: true });
      })
    )));
  });
  await assertRequiredFont(page, requiredFont, fontWeights, fontSelector);

  const count = await page.locator(selector).count();
  if (count < 1) throw new Error(`No elements matched selector: ${selector}`);

  if (!args['no-links']) {
    const links = await page.$$eval(selector, (slides) => slides.map((slide) => {
      const slideRect = slide.getBoundingClientRect();
      return [...slide.querySelectorAll('a[href]')]
        .map((anchor) => {
          const rect = anchor.getBoundingClientRect();
          const left = Math.max(rect.left, slideRect.left) - slideRect.left;
          const top = Math.max(rect.top, slideRect.top) - slideRect.top;
          const right = Math.min(rect.right, slideRect.right) - slideRect.left;
          const bottom = Math.min(rect.bottom, slideRect.bottom) - slideRect.top;
          const width = right - left;
          const height = bottom - top;
          if (width < 4 || height < 4) return null;
          return {
            href: anchor.href,
            label: (anchor.getAttribute('aria-label') || anchor.textContent || '').trim().replace(/\s+/g, ' '),
            rect: { x: left, y: top, width, height },
          };
        })
        .filter(Boolean);
    }));
    writeFileSync(linksJson, JSON.stringify({ sourceWidth: width, sourceHeight: height, pages: links }, null, 2));
  }

  for (let i = 0; i < count; i += 1) {
    const locator = page.locator(selector).nth(i);
    const file = join(captureDir, `slide-${String(i + 1).padStart(2, '0')}.jpg`);
    await locator.screenshot({ path: file, type: 'jpeg', quality, animations: 'disabled' });
  }
  console.log(`Captured ${count} pages to ${captureDir}`);
} finally {
  await browser.close();
}

run(python, [
  join(scriptDir, 'images-to-pdf.py'),
  '--input-dir', captureDir,
  '--out', out,
  ...(existsSync(linksJson) ? ['--links-json', linksJson] : []),
], 'images-to-pdf');

if (!args['skip-qa']) {
  run(python, [
    join(scriptDir, 'render-pdf-contact-sheet.py'),
    '--pdf', out,
    '--out-dir', join(workDir, 'rendered'),
    '--contact-sheet', join(workDir, 'contact-sheet.jpg'),
    '--pdftoppm', pdftoppm,
  ], 'render-pdf-contact-sheet');
  console.log(`QA contact sheet: ${join(workDir, 'contact-sheet.jpg')}`);
}

if (!args['keep-work-dir'] && args['skip-qa']) {
  rmSync(workDir, { recursive: true, force: true });
}

console.log(`PDF written: ${out}`);
