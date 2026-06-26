import { mkdir, rename, stat } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";

export function ensureOutputDir(outputDir) {
  if (!existsSync(outputDir)) {
    throw new Error(
      `Output directory does not exist yet: ${outputDir}. Create it before recording.`,
    );
  }
  return outputDir;
}

export async function ensureOutputDirAsync(outputDir) {
  await mkdir(outputDir, { recursive: true });
  return outputDir;
}

const STAGE_CSS = `
  :root {
    --demo-stage-accent: #2563eb;
    --demo-stage-ink: #111111;
    --demo-stage-muted: #4b5563;
    --demo-stage-paper: #fffaf2;
    --demo-stage-panel: rgba(255, 250, 242, 0.94);
    --demo-stage-border: rgba(17, 17, 17, 0.14);
    --demo-stage-scale: 1;
    --demo-stage-pan-x: 0px;
    --demo-stage-pan-y: 0px;
  }

  body.demo-video-stage-active {
    overflow: hidden;
    background:
      linear-gradient(135deg, #f8f1e7 0%, #eef7f2 48%, #f1eefb 100%);
  }

  .demo-video-stage-root {
    transform: translate3d(var(--demo-stage-pan-x), var(--demo-stage-pan-y), 0)
      scale(var(--demo-stage-scale));
    transform-origin: 50% 50%;
    transition:
      transform 820ms cubic-bezier(0.16, 1, 0.3, 1),
      filter 820ms cubic-bezier(0.16, 1, 0.3, 1);
    will-change: transform, filter;
  }

  .demo-video-brand-mark,
  .demo-video-chapter-card {
    position: fixed;
    z-index: 2147483600;
    pointer-events: none;
    font-family: var(
      --font-family-title,
      Archivo,
      Karla,
      -apple-system,
      BlinkMacSystemFont,
      "Segoe UI",
      system-ui,
      sans-serif
    );
    letter-spacing: 0;
  }

  .demo-video-brand-mark {
    top: 24px;
    left: 32px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 34px;
    padding: 0 12px;
    border: 1px solid var(--demo-stage-border);
    border-radius: 999px;
    background: rgba(255, 250, 242, 0.9);
    color: var(--demo-stage-ink);
    font-size: 15px;
    font-weight: 800;
    box-shadow: 0 14px 44px rgba(17, 17, 17, 0.12);
    backdrop-filter: blur(18px) saturate(1.18);
  }

  .demo-video-brand-mark[data-position="right"] {
    right: 28px;
    left: auto;
  }

  .demo-video-brand-mark::before {
    content: "";
    width: 9px;
    height: 9px;
    border-radius: 999px;
    background: var(--demo-stage-accent);
  }

  .demo-video-chapter-card {
    left: 32px;
    bottom: 34px;
    width: min(430px, calc(100vw - 64px));
    padding: 24px 25px 26px;
    border: 1px solid var(--demo-stage-border);
    border-radius: 18px;
    background:
      linear-gradient(155deg, rgba(255, 255, 255, 0.92), var(--demo-stage-panel)),
      var(--demo-stage-paper);
    color: var(--demo-stage-ink);
    box-shadow:
      0 28px 90px rgba(17, 17, 17, 0.18),
      inset 0 1px 0 rgba(255, 255, 255, 0.74);
    backdrop-filter: blur(22px) saturate(1.18);
    overflow: hidden;
  }

  .demo-video-chapter-card[data-position="right"] {
    right: 28px;
    left: auto;
  }

  .demo-video-chapter-card::before {
    content: "";
    position: absolute;
    left: 0;
    top: 20px;
    bottom: 20px;
    width: 5px;
    border-radius: 0 999px 999px 0;
    background: var(--demo-stage-accent);
  }

  .demo-video-chapter-card::after {
    content: "";
    position: absolute;
    right: 18px;
    top: 18px;
    width: 72px;
    height: 72px;
    border: 1px solid color-mix(in srgb, var(--demo-stage-accent) 42%, transparent);
    border-radius: 999px;
    opacity: 0.32;
  }

  .demo-video-chapter-eyebrow {
    display: block;
    margin-bottom: 8px;
    color: var(--demo-stage-accent);
    font-size: 12px;
    font-weight: 800;
    line-height: 1.15;
    text-transform: uppercase;
  }

  .demo-video-chapter-title {
    display: block;
    max-width: 14ch;
    font-family: var(
      --font-family-display,
      "Iowan Old Style",
      "Palatino Linotype",
      Georgia,
      ui-serif,
      serif
    );
    font-size: 38px;
    font-weight: 700;
    line-height: 0.98;
    letter-spacing: 0;
  }

  .demo-video-chapter-copy {
    display: block;
    max-width: 32ch;
    margin-top: 12px;
    color: var(--demo-stage-muted);
    font-family: var(
      --font-family-ui,
      Karla,
      -apple-system,
      BlinkMacSystemFont,
      "Segoe UI",
      system-ui,
      sans-serif
    );
    font-size: 16px;
    font-weight: 600;
    line-height: 1.42;
  }

  .demo-video-chapter-card-enter {
    animation: demo-video-card-enter 720ms cubic-bezier(0.16, 1, 0.3, 1) both;
  }

  .demo-video-chapter-card-enter .demo-video-chapter-eyebrow,
  .demo-video-chapter-card-enter .demo-video-chapter-title,
  .demo-video-chapter-card-enter .demo-video-chapter-copy {
    animation: demo-video-line-in 760ms cubic-bezier(0.16, 1, 0.3, 1) both;
  }

  .demo-video-chapter-card-enter .demo-video-chapter-title {
    animation-delay: 80ms;
  }

  .demo-video-chapter-card-enter .demo-video-chapter-copy {
    animation-delay: 150ms;
  }

  @keyframes demo-video-card-enter {
    from {
      opacity: 0;
      transform: translate3d(-18px, 18px, 0) scale(0.98);
    }
    to {
      opacity: 1;
      transform: translate3d(0, 0, 0) scale(1);
    }
  }

  @keyframes demo-video-line-in {
    from {
      opacity: 0;
      transform: translate3d(0, 12px, 0);
    }
    to {
      opacity: 1;
      transform: translate3d(0, 0, 0);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .demo-video-stage-root,
    .demo-video-chapter-card-enter,
    .demo-video-chapter-card-enter .demo-video-chapter-eyebrow,
    .demo-video-chapter-card-enter .demo-video-chapter-title,
    .demo-video-chapter-card-enter .demo-video-chapter-copy {
      animation-duration: 1ms;
      transition-duration: 1ms;
    }
  }

  @media (max-width: 760px) {
    .demo-video-chapter-card,
    .demo-video-chapter-card[data-position="right"] {
      right: 18px;
      left: 18px;
      bottom: 18px;
      width: auto;
      padding: 18px 19px 20px;
    }

    .demo-video-chapter-title {
      max-width: 16ch;
      font-size: 30px;
    }
  }
`;

export async function createDemoDriver(page, options = {}) {
  const cursor = {
    x: options.startX ?? 80,
    y: options.startY ?? 80,
  };
  const startedAt = Date.now();
  const emitEvent = (event) => {
    options.onEvent?.({ t: Date.now() - startedAt, ...event });
  };
  await installDemoCursor(page, cursor);

  const pause = (ms = 500) => page.waitForTimeout(ms);

  async function moveToLocator(locator, moveOptions = {}) {
    await locator.scrollIntoViewIfNeeded();
    const box = await locator.boundingBox();
    if (!box) {
      throw new Error("Target is not visible for cursor movement.");
    }
    const target = {
      x: Math.round(box.x + box.width / 2),
      y: Math.round(box.y + box.height / 2),
    };
    await animateCursor(page, cursor, target, moveOptions);
    emitEvent({ type: "move", ...target });
    return target;
  }

  async function clickLocator(locator, clickOptions = {}) {
    const target = await moveToLocator(locator, clickOptions);
    await page.mouse.click(target.x, target.y, { delay: clickOptions.delay ?? 90 });
    await page.evaluate(({ x, y }) => {
      window.__demoCursorClick?.(x, y);
    }, target);
    emitEvent({ type: "click", ...target });
    if (clickOptions.zoom) {
      const zoomOptions =
        typeof clickOptions.zoom === "object" ? clickOptions.zoom : {};
      await zoomToPoint(target, zoomOptions);
    }
    await pause(clickOptions.after ?? 550);
  }

  async function zoomToLocator(locator, zoomOptions = {}) {
    await locator.scrollIntoViewIfNeeded();
    const box = await locator.boundingBox();
    if (!box) {
      throw new Error("Target is not visible for zoom.");
    }
    return zoomToPoint(
      {
        x: Math.round(box.x + box.width / 2),
        y: Math.round(box.y + box.height / 2),
      },
      zoomOptions,
    );
  }

  async function zoomToPoint(point, zoomOptions = {}) {
    const viewport = await page.evaluate(() => ({
      width: window.innerWidth,
      height: window.innerHeight,
    }));
    const scale = zoomOptions.scale ?? 1.16;
    const panX = Math.round(
      (viewport.width / 2 - point.x) * scale + (zoomOptions.offsetX ?? 0),
    );
    const panY = Math.round(
      (viewport.height / 2 - point.y) * scale + (zoomOptions.offsetY ?? 0),
    );
    await setDemoZoom(page, { scale, panX, panY });
    emitEvent({ type: "zoom", x: point.x, y: point.y, scale, panX, panY });
    await pause(zoomOptions.after ?? 520);
    return { scale, panX, panY };
  }

  async function clickByRole(role, options, clickOptions = {}) {
    await clickLocator(page.getByRole(role, options).first(), clickOptions);
  }

  async function clickByLabel(label, clickOptions = {}) {
    await clickLocator(page.getByLabel(label).first(), clickOptions);
  }

  async function typeByLabel(label, text, typeOptions = {}) {
    const locator = page.getByLabel(label).first();
    await clickLocator(locator, { after: 180 });
    await locator.fill("");
    await locator.pressSequentially(text, { delay: typeOptions.delay ?? 22 });
    emitEvent({ type: "type", label, text });
    await pause(typeOptions.after ?? 450);
  }

  async function selectByLabel(label, value, selectOptions = {}) {
    const locator = page.getByLabel(label).first();
    await clickLocator(locator, { after: 180 });
    await locator.selectOption(value);
    emitEvent({ type: "select", label, value });
    await pause(selectOptions.after ?? 400);
  }

  return {
    clickByLabel,
    clickByRole,
    clickLocator,
    moveToLocator,
    pause,
    resetZoom: () => resetDemoZoom(page),
    selectByLabel,
    typeByLabel,
    zoomToLocator,
    zoomToPoint,
  };
}

export async function installDemoCursor(page, cursor) {
  await page.addStyleTag({
    content: `
      .demo-video-cursor {
        position: fixed;
        left: 0;
        top: 0;
        z-index: 2147483647;
        width: 23px;
        height: 27px;
        margin-left: -21px;
        margin-top: -13px;
        filter: drop-shadow(0 5px 8px rgba(17, 17, 17, 0.32));
        pointer-events: none;
        transform: translate3d(var(--demo-cursor-x, 80px), var(--demo-cursor-y, 80px), 0);
      }

      .demo-video-cursor::after {
        content: "";
        position: absolute;
        left: 0;
        top: 0;
        width: 23px;
        height: 27px;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 28'%3E%3Cpath fill='%23050505' d='M4.1 3.2C2.6 2.1 .8 3.2 .8 5.1v17.8c0 1.9 2.1 3 3.7 1.8l17.2-9.9c1.6-.9 1.6-3.2 0-4.1L4.1 3.2Z'/%3E%3C/svg%3E");
        background-repeat: no-repeat;
        background-size: 100% 100%;
        transform: rotate(-7deg);
        transform-origin: 92% 50%;
      }

      .demo-video-cursor::after {
        opacity: 1;
      }

      .demo-video-click-ripple {
        position: fixed;
        left: 0;
        top: 0;
        z-index: 2147483646;
        width: 16px;
        height: 16px;
        margin-left: -8px;
        margin-top: -8px;
        border: 1.5px solid color-mix(in srgb, var(--demo-stage-accent, #2563eb) 82%, white);
        border-radius: 999px;
        box-shadow:
          0 0 0 8px color-mix(in srgb, var(--demo-stage-accent, #2563eb) 16%, transparent),
          0 0 36px color-mix(in srgb, var(--demo-stage-accent, #2563eb) 34%, transparent);
        pointer-events: none;
        transform: translate3d(var(--demo-click-x), var(--demo-click-y), 0) scale(0.8);
        animation: demo-video-ripple 680ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
      }

      @keyframes demo-video-ripple {
        to {
          opacity: 0;
          transform: translate3d(var(--demo-click-x), var(--demo-click-y), 0) scale(3.8);
        }
      }
    `,
  });

  await page.evaluate(({ x, y }) => {
    const existing = document.querySelector(".demo-video-cursor");
    const cursorEl = existing ?? document.createElement("div");
    cursorEl.className = "demo-video-cursor";
    document.body.append(cursorEl);
    document.documentElement.style.setProperty("--demo-cursor-x", `${x}px`);
    document.documentElement.style.setProperty("--demo-cursor-y", `${y}px`);
    window.__demoCursorMove = (nextX, nextY) => {
      document.documentElement.style.setProperty("--demo-cursor-x", `${nextX}px`);
      document.documentElement.style.setProperty("--demo-cursor-y", `${nextY}px`);
    };
    window.__demoCursorClick = (nextX, nextY) => {
      const ripple = document.createElement("div");
      ripple.className = "demo-video-click-ripple";
      ripple.style.setProperty("--demo-click-x", `${nextX}px`);
      ripple.style.setProperty("--demo-click-y", `${nextY}px`);
      document.body.append(ripple);
      window.setTimeout(() => ripple.remove(), 620);
    };
  }, cursor);
}

export async function installDemoStage(page, options = {}) {
  await page.addStyleTag({ content: STAGE_CSS });
  await page.evaluate(({ brand, accent, brandPosition, chapterPosition, ink, muted, paper }) => {
    document.body.classList.add("demo-video-stage-active");
    document.documentElement.style.setProperty(
      "--demo-stage-accent",
      accent ?? "#2563eb",
    );
    document.documentElement.style.setProperty("--demo-stage-ink", ink ?? "#111111");
    document.documentElement.style.setProperty("--demo-stage-muted", muted ?? "#4b5563");
    document.documentElement.style.setProperty("--demo-stage-paper", paper ?? "#fffaf2");

    const appRoot = document.querySelector("#root") ?? document.body.firstElementChild;
    if (appRoot && appRoot !== document.body) {
      appRoot.classList.add("demo-video-stage-root");
    }

    const brandLabel = brand ?? "Product";
    let brandMark = document.querySelector(".demo-video-brand-mark");
    if (brandLabel) {
      if (!brandMark) {
        brandMark = document.createElement("div");
        brandMark.className = "demo-video-brand-mark";
        brandMark.setAttribute("aria-hidden", "true");
        document.body.append(brandMark);
      }
      brandMark.textContent = brandLabel;
      brandMark.dataset.position = brandPosition ?? "left";
    } else if (brandMark) {
      brandMark.remove();
    }

    window.__demoSetChapter = ({ eyebrow, title, copy }) => {
      let card = document.querySelector(".demo-video-chapter-card");
      if (!card) {
        card = document.createElement("aside");
        card.className = "demo-video-chapter-card";
        card.setAttribute("aria-hidden", "true");
        card.innerHTML = `
          <span class="demo-video-chapter-eyebrow"></span>
          <span class="demo-video-chapter-title"></span>
          <span class="demo-video-chapter-copy"></span>
        `;
        document.body.append(card);
      }
      card.dataset.position = chapterPosition ?? "left";
      card.querySelector(".demo-video-chapter-eyebrow").textContent =
        eyebrow ?? "Demo";
      card.querySelector(".demo-video-chapter-title").textContent = title ?? "";
      card.querySelector(".demo-video-chapter-copy").textContent = copy ?? "";
      card.classList.remove("demo-video-chapter-card-enter");
      void card.offsetWidth;
      card.classList.add("demo-video-chapter-card-enter");
    };

    window.__demoSetZoom = ({ scale, panX, panY }) => {
      document.documentElement.style.setProperty(
        "--demo-stage-scale",
        String(scale ?? 1),
      );
      document.documentElement.style.setProperty(
        "--demo-stage-pan-x",
        `${panX ?? 0}px`,
      );
      document.documentElement.style.setProperty(
        "--demo-stage-pan-y",
        `${panY ?? 0}px`,
      );
    };
  }, options);
}

export async function setDemoChapter(page, chapter) {
  await page.evaluate((nextChapter) => {
    window.__demoSetChapter?.(nextChapter);
  }, chapter);
}

export async function setDemoZoom(page, options = {}) {
  await page.evaluate((nextZoom) => {
    window.__demoSetZoom?.({
      scale: nextZoom.scale ?? 1,
      panX: nextZoom.panX ?? 0,
      panY: nextZoom.panY ?? 0,
    });
  }, options);
}

export async function resetDemoZoom(page) {
  await setDemoZoom(page, { scale: 1, panX: 0, panY: 0 });
}

export async function animateCursor(page, cursor, target, options = {}) {
  const steps = options.steps ?? 18;
  const durationMs = options.durationMs ?? 420;
  for (let index = 1; index <= steps; index += 1) {
    const progress = easeInOutCubic(index / steps);
    const x = Math.round(cursor.x + (target.x - cursor.x) * progress);
    const y = Math.round(cursor.y + (target.y - cursor.y) * progress);
    await page.mouse.move(x, y);
    await page.evaluate(({ nextX, nextY }) => {
      window.__demoCursorMove?.(nextX, nextY);
    }, { nextX: x, nextY: y });
    await page.waitForTimeout(Math.max(1, Math.round(durationMs / steps)));
  }
  cursor.x = target.x;
  cursor.y = target.y;
}

export async function moveRecordedVideo(page, destinationPath) {
  const video = page.video();
  if (!video) {
    throw new Error("No Playwright video is attached to this page.");
  }
  const sourcePath = await video.path();
  await mkdir(path.dirname(destinationPath), { recursive: true });
  await rename(sourcePath, destinationPath);
  const info = await stat(destinationPath);
  return {
    path: destinationPath,
    sizeBytes: info.size,
  };
}

function easeInOutCubic(value) {
  return value < 0.5
    ? 4 * value * value * value
    : 1 - Math.pow(-2 * value + 2, 3) / 2;
}
