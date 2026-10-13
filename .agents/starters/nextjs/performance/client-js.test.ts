import { expect, test } from "bun:test";

const budget = 170_000;

test(`home page loads under ${budget} gzipped bytes of JavaScript`, async () => {
  const build = Bun.spawn(["bun", "run", "build"], {
    stdout: "ignore",
    stderr: "inherit",
  });
  expect(await build.exited).toBe(0);
  const html = await Bun.file(".next/server/app/index.html").text();
  const scripts = [
    ...html.matchAll(
      /<script src="\/_next(\/static\/chunks\/[^"]+\.js)" async="">/g,
    ),
  ].map((match) => `.next${match[1]}`);
  let bytes = 0;
  for (const path of scripts) {
    bytes += Bun.gzipSync(await Bun.file(path).bytes()).length;
  }
  console.log(
    `home page JavaScript: ${scripts.length} files, ${bytes} gzipped bytes`,
  );
  expect(scripts.length).toBeGreaterThan(0);
  expect(bytes).toBeLessThan(budget);
}, 120_000);
