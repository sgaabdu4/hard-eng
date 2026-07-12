#!/usr/bin/env node
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);

function usage() {
  console.log(`Usage:
  audit-fixed-html.mjs --url <url> [--selector .slide] [--width 1280] [--height 720] [--stale <regex>]

Checks fixed HTML pages/slides for:
  - exact element dimensions
  - content crossing element boundaries
  - hidden/clipped overflow
  - broken images
  - stale text regex matches
  - required custom font activation when --require-font is set

Font options:
  --require-font <family>  Fail if the computed font stack and loaded FontFace set do not include this family.
  --font-weights <csv>     Optional required weights, e.g. "400,500,600".
  --font-selector <css>    Element used for computed font checks. Default: body
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

const args = parseArgs(process.argv);
if (args.help || !args.url) {
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
const expectedWidth = Number(args.width || 1280);
const expectedHeight = Number(args.height || 720);
const staleRegex = args.stale ? new RegExp(args.stale, 'gi') : null;
const requiredFont = args['require-font'] || '';
const fontWeights = String(args['font-weights'] || '')
  .split(',')
  .map((weight) => weight.trim())
  .filter(Boolean);
const fontSelector = args['font-selector'] || 'body';

const launchOptions = { headless: true };
if (args['browser-channel'] || process.env.PLAYWRIGHT_CHANNEL) {
  launchOptions.channel = args['browser-channel'] || process.env.PLAYWRIGHT_CHANNEL;
}

const browser = await chromium.launch(launchOptions);
const page = await browser.newPage({
  viewport: { width: expectedWidth, height: expectedHeight },
  deviceScaleFactor: Number(args.scale || 1),
});

try {
  await page.goto(args.url, { waitUntil: args.wait || 'networkidle' });
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

  const report = await page.evaluate(({ selector, expectedWidth, expectedHeight, staleSource, requiredFont, fontWeights, fontSelector }) => {
    const staleRegex = staleSource ? new RegExp(staleSource, 'gi') : null;
    const pages = [...document.querySelectorAll(selector)];
    const normalizeFont = (value) => String(value || '').replace(/^["']|["']$/g, '').toLowerCase();
    const visible = (el) => {
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      return cs.display !== 'none'
        && cs.visibility !== 'hidden'
        && Number(cs.opacity) > 0.01
        && r.width > 0.5
        && r.height > 0.5;
    };

    const results = pages.map((pageEl, index) => {
      const pr = pageEl.getBoundingClientRect();
      const elements = [...pageEl.querySelectorAll('*')].filter(visible);
      const boundaryViolations = elements
        .filter((el) => !el.closest('.media'))
        .map((el) => ({ el, r: el.getBoundingClientRect() }))
        .filter(({ r }) => r.left < pr.left - 1 || r.top < pr.top - 1 || r.right > pr.right + 1 || r.bottom > pr.bottom + 1)
        .map(({ el, r }) => ({
          selector: `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ''}${el.className ? `.${String(el.className).replace(/\s+/g, '.')}` : ''}`,
          text: (el.innerText || el.alt || '').trim().slice(0, 100),
          rect: {
            left: Math.round(r.left - pr.left),
            top: Math.round(r.top - pr.top),
            right: Math.round(r.right - pr.left),
            bottom: Math.round(r.bottom - pr.top),
          },
        }));

      const hiddenOverflow = elements
        .filter((el) => {
          const cs = getComputedStyle(el);
          const clipsX = ['hidden', 'clip', 'auto', 'scroll'].includes(cs.overflowX);
          const clipsY = ['hidden', 'clip', 'auto', 'scroll'].includes(cs.overflowY);
          return (clipsX && el.scrollWidth > el.clientWidth + 1) || (clipsY && el.scrollHeight > el.clientHeight + 1);
        })
        .map((el) => ({
          selector: `${el.tagName.toLowerCase()}${el.className ? `.${String(el.className).replace(/\s+/g, '.')}` : ''}`,
          text: (el.innerText || el.alt || '').trim().slice(0, 100),
          scrollWidth: el.scrollWidth,
          clientWidth: el.clientWidth,
          scrollHeight: el.scrollHeight,
          clientHeight: el.clientHeight,
        }));

      const brokenImages = [...pageEl.querySelectorAll('img')]
        .filter((img) => !img.complete || img.naturalWidth === 0 || img.naturalHeight === 0)
        .map((img) => img.getAttribute('src'));

      return {
        page: pageEl.id || `${selector}-${index + 1}`,
        exactSize: Math.round(pr.width) === expectedWidth && Math.round(pr.height) === expectedHeight,
        size: { width: Math.round(pr.width), height: Math.round(pr.height) },
        boundaryViolations,
        hiddenOverflow,
        brokenImages,
      };
    });

    let fontCheck = null;
    if (requiredFont) {
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

      fontCheck = {
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
    }

    return {
      pageCount: pages.length,
      allExactSize: results.every((r) => r.exactSize),
      staleCopyMatches: staleRegex ? (document.body.innerText.match(staleRegex) || []) : [],
      fontCheck,
      failures: results.filter((r) => !r.exactSize || r.boundaryViolations.length || r.hiddenOverflow.length || r.brokenImages.length),
      results,
    };
  }, { selector, expectedWidth, expectedHeight, staleSource: staleRegex?.source || null, requiredFont, fontWeights, fontSelector });

  console.log(JSON.stringify(report, null, 2));
  const failed = report.pageCount === 0 || report.failures.length > 0 || report.staleCopyMatches.length > 0 || report.fontCheck?.ok === false;
  process.exitCode = failed ? 1 : 0;
} finally {
  await browser.close();
}
