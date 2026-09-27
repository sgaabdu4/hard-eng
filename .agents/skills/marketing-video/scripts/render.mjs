import { spawn } from 'node:child_process';
import { createReadStream, existsSync, mkdirSync, statSync } from 'node:fs';
import { createServer } from 'node:http';
import { dirname, extname, join, normalize, resolve } from 'node:path';
import { chromium } from 'playwright';

const [workArg, ...rest] = process.argv.slice(2);
const work = resolve(workArg);
const stills = rest[0] === '--stills';
const types = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.ttf': 'font/ttf',
  '.otf': 'font/otf',
  '.woff2': 'font/woff2',
  '.woff': 'font/woff',
};
const server = createServer((req, res) => {
  const path = normalize(join(work, decodeURIComponent(new URL(req.url, 'http://x').pathname)));
  if (!path.startsWith(work) || !existsSync(path) || statSync(path).isDirectory()) return res.writeHead(404).end();
  res.writeHead(200, {
    'content-type': types[extname(path)] ?? 'application/octet-stream',
  });
  createReadStream(path).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const browser = await chromium.launch();
try {
  const page = await (await browser.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('requestfailed', (r) => errors.push(`failed ${r.url()}`));
  page.on('response', (r) => r.status() >= 400 && errors.push(`${r.status()} ${r.url()}`));
  await page.goto(`http://127.0.0.1:${server.address().port}/render/index.html`);
  const total = await page.evaluate(() => window.ready);
  if (errors.length) throw new Error(errors.join('\n'));
  if (stills) {
    mkdirSync(join(work, 'stills'), { recursive: true });
    for (const t of rest.slice(1).map(Number)) {
      await page.evaluate((x) => window.seek(x), t);
      await page.screenshot({
        path: join(work, 'stills', `t${t.toFixed(2)}.png`),
      });
      console.log('still', t);
    }
  } else {
    const out = resolve(rest[0] ?? join(work, 'out/silent.mp4'));
    mkdirSync(dirname(out), { recursive: true });
    const args = [
      '-v',
      'error',
      '-y',
      '-f',
      'image2pipe',
      '-framerate',
      '30',
      '-i',
      '-',
      '-c:v',
      'libx264',
      '-preset',
      'slow',
      '-crf',
      '15',
      '-pix_fmt',
      'yuv420p',
      '-movflags',
      '+faststart',
      out,
    ];
    const ff = spawn('ffmpeg', args, { stdio: ['pipe', 'inherit', 'inherit'] });
    const frames = Math.ceil(total * 30);
    for (let f = 0; f < frames; f++) {
      await page.evaluate((x) => window.seek(x), f / 30);
      if (!ff.stdin.write(await page.screenshot({ type: 'png' }))) await new Promise((r) => ff.stdin.once('drain', r));
      if (f % 300 === 0) console.log('frame', f, '/', frames);
    }
    ff.stdin.end();
    await new Promise((r) => ff.on('close', r));
    if (errors.length) throw new Error(errors.join('\n'));
    console.log('video', out, total.toFixed(2), 's');
  }
} finally {
  await browser.close();
  server.close();
}
