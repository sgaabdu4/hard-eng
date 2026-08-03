// fallow-ignore-file unused-file -- imported by project-owned capture actors outside this repository.
const CURSOR_ID = "product-walkthrough-cursor";
const CAPTION_ID = "product-walkthrough-caption";

export async function installWalkthroughOverlays(page) {
  await page.evaluate(
    ({ cursorId, captionId }) => {
      const existingCursor = document.getElementById(cursorId);
      if (!existingCursor) {
        const cursor = document.createElement("div");
        cursor.id = cursorId;
        Object.assign(cursor.style, {
          position: "fixed",
          left: "28px",
          top: "28px",
          width: "22px",
          height: "22px",
          borderRadius: "999px",
          border: "3px solid white",
          background: "#12372a",
          boxShadow: "0 2px 10px rgba(0,0,0,.45)",
          pointerEvents: "none",
          transform: "translate(-50%, -50%)",
          transition:
            "left 520ms cubic-bezier(.22,.61,.36,1), top 520ms cubic-bezier(.22,.61,.36,1), transform 160ms ease",
          zIndex: "2147483647",
        });
        document.body.append(cursor);
      }

      const existingCaption = document.getElementById(captionId);
      if (!existingCaption) {
        const caption = document.createElement("div");
        caption.id = captionId;
        Object.assign(caption.style, {
          position: "fixed",
          left: "50%",
          bottom: "28px",
          maxWidth: "min(900px, calc(100vw - 80px))",
          padding: "13px 20px",
          borderRadius: "14px",
          background: "rgba(22, 33, 28, .92)",
          color: "white",
          font: "600 18px/1.35 system-ui, sans-serif",
          letterSpacing: ".01em",
          textAlign: "center",
          boxShadow: "0 8px 28px rgba(0,0,0,.3)",
          opacity: "0",
          transform: "translate(-50%, 12px)",
          transition: "opacity 180ms ease, transform 180ms ease",
          pointerEvents: "none",
          zIndex: "2147483646",
        });
        document.body.append(caption);
      }
    },
    { cursorId: CURSOR_ID, captionId: CAPTION_ID },
  );
}

export async function setWalkthroughCaption(page, text) {
  await page.evaluate(
    ({ captionId, value }) => {
      const caption = document.getElementById(captionId);
      if (!caption) throw new Error("walkthrough caption overlay is missing");
      caption.textContent = value;
      caption.style.opacity = value ? "1" : "0";
      caption.style.transform = value ? "translate(-50%, 0)" : "translate(-50%, 12px)";
    },
    { captionId: CAPTION_ID, value: text },
  );
}

export async function moveWalkthroughCursor(page, locator, options = {}) {
  const { durationMs = 650, offsetX = 0, offsetY = 0 } = options;
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  if (!box) throw new Error("walkthrough cursor target has no bounding box");
  const x = box.x + box.width / 2 + offsetX;
  const y = box.y + box.height / 2 + offsetY;
  await page.evaluate(
    ({ cursorId, targetX, targetY, duration }) => {
      const cursor = document.getElementById(cursorId);
      if (!cursor) throw new Error("walkthrough cursor overlay is missing");
      cursor.style.transitionDuration = `${duration}ms, ${duration}ms, 160ms`;
      cursor.style.left = `${targetX}px`;
      cursor.style.top = `${targetY}px`;
    },
    { cursorId: CURSOR_ID, targetX: x, targetY: y, duration: durationMs },
  );
  await page.mouse.move(x, y, { steps: 24 });
  await page.waitForTimeout(durationMs + 80);
}

export async function clickWalkthroughTarget(page, locator, options = {}) {
  await moveWalkthroughCursor(page, locator, options);
  await page.evaluate((cursorId) => {
    const cursor = document.getElementById(cursorId);
    if (!cursor) throw new Error("walkthrough cursor overlay is missing");
    cursor.style.transform = "translate(-50%, -50%) scale(.72)";
    cursor.style.boxShadow = "0 0 0 12px rgba(18,55,42,.18), 0 2px 10px rgba(0,0,0,.45)";
  }, CURSOR_ID);
  await locator.click();
  await page.waitForTimeout(150);
  await page.evaluate((cursorId) => {
    const cursor = document.getElementById(cursorId);
    if (!cursor) throw new Error("walkthrough cursor overlay is missing");
    cursor.style.transform = "translate(-50%, -50%) scale(1)";
    cursor.style.boxShadow = "0 2px 10px rgba(0,0,0,.45)";
  }, CURSOR_ID);
}

export function requestIsAllowed(url, allowedOrigins) {
  const parsed = new URL(url);
  if (parsed.protocol === "data:" || parsed.protocol === "blob:") return true;
  return allowedOrigins.includes(parsed.origin);
}
