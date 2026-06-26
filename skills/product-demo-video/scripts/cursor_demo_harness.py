from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import shutil
import time
from typing import Any


CURSOR_CSS = """
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
"""


CURSOR_JS = """
({ x, y }) => {
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
}
"""


STAGE_CSS = """
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
"""


STAGE_JS = """
({ brand, accent, brandPosition, chapterPosition, ink, muted, paper }) => {
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
}
"""


@dataclass
class CursorPosition:
    x: int = 80
    y: int = 80


def ensure_output_dir(path: str | Path) -> Path:
    output_dir = Path(path)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def install_demo_stage(
    page: Any,
    *,
    brand: str = "Product",
    accent: str = "#2563eb",
    brand_position: str = "left",
    chapter_position: str = "left",
    ink: str = "#111111",
    muted: str = "#4b5563",
    paper: str = "#fffaf2",
) -> None:
    page.add_style_tag(content=STAGE_CSS)
    page.evaluate(
        STAGE_JS,
        {
            "brand": brand,
            "accent": accent,
            "brandPosition": brand_position,
            "chapterPosition": chapter_position,
            "ink": ink,
            "muted": muted,
            "paper": paper,
        },
    )


def set_demo_chapter(
    page: Any,
    *,
    eyebrow: str = "Demo",
    title: str,
    copy: str = "",
) -> None:
    page.evaluate(
        "(chapter) => window.__demoSetChapter?.(chapter)",
        {"eyebrow": eyebrow, "title": title, "copy": copy},
    )


def set_demo_zoom(
    page: Any,
    *,
    scale: float = 1,
    pan_x: int = 0,
    pan_y: int = 0,
) -> None:
    page.evaluate(
        "(zoom) => window.__demoSetZoom?.(zoom)",
        {"scale": scale, "panX": pan_x, "panY": pan_y},
    )


def reset_demo_zoom(page: Any) -> None:
    set_demo_zoom(page, scale=1, pan_x=0, pan_y=0)


def zoom_to_point(
    page: Any,
    *,
    x: int,
    y: int,
    scale: float = 1.16,
    offset_x: int = 0,
    offset_y: int = 0,
    after_ms: int = 520,
) -> dict[str, int | float]:
    viewport = page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")
    pan_x = round((viewport["width"] / 2 - x) * scale + offset_x)
    pan_y = round((viewport["height"] / 2 - y) * scale + offset_y)
    set_demo_zoom(page, scale=scale, pan_x=pan_x, pan_y=pan_y)
    page.wait_for_timeout(after_ms)
    return {"scale": scale, "pan_x": pan_x, "pan_y": pan_y}


class DemoDriver:
    def __init__(self, page: Any, start_x: int = 80, start_y: int = 80) -> None:
        self.page = page
        self.cursor = CursorPosition(start_x, start_y)
        self.install_cursor()

    def install_cursor(self) -> None:
        self.page.add_style_tag(content=CURSOR_CSS)
        self.page.evaluate(CURSOR_JS, {"x": self.cursor.x, "y": self.cursor.y})

    def pause(self, ms: int = 500) -> None:
        self.page.wait_for_timeout(ms)

    def move_to_locator(self, locator: Any, *, steps: int = 18, duration_ms: int = 420) -> dict[str, int]:
        locator.scroll_into_view_if_needed()
        box = locator.bounding_box()
        if not box:
            raise RuntimeError("Target is not visible for cursor movement.")
        target = {
            "x": round(box["x"] + box["width"] / 2),
            "y": round(box["y"] + box["height"] / 2),
        }
        self.animate_cursor(target, steps=steps, duration_ms=duration_ms)
        return target

    def animate_cursor(self, target: dict[str, int], *, steps: int = 18, duration_ms: int = 420) -> None:
        start_x = self.cursor.x
        start_y = self.cursor.y
        for index in range(1, steps + 1):
            progress = ease_in_out_cubic(index / steps)
            x = round(start_x + (target["x"] - start_x) * progress)
            y = round(start_y + (target["y"] - start_y) * progress)
            self.page.mouse.move(x, y)
            self.page.evaluate(
                "(point) => window.__demoCursorMove?.(point.x, point.y)",
                {"x": x, "y": y},
            )
            time.sleep(max(0.001, (duration_ms / steps) / 1000))
        self.cursor.x = target["x"]
        self.cursor.y = target["y"]

    def zoom_to_locator(
        self,
        locator: Any,
        *,
        scale: float = 1.16,
        offset_x: int = 0,
        offset_y: int = 0,
        after_ms: int = 520,
    ) -> dict[str, int | float]:
        locator.scroll_into_view_if_needed()
        box = locator.bounding_box()
        if not box:
            raise RuntimeError("Target is not visible for zoom.")
        return zoom_to_point(
            self.page,
            x=round(box["x"] + box["width"] / 2),
            y=round(box["y"] + box["height"] / 2),
            scale=scale,
            offset_x=offset_x,
            offset_y=offset_y,
            after_ms=after_ms,
        )

    def zoom_to_point(
        self,
        *,
        x: int,
        y: int,
        scale: float = 1.16,
        offset_x: int = 0,
        offset_y: int = 0,
        after_ms: int = 520,
    ) -> dict[str, int | float]:
        return zoom_to_point(
            self.page,
            x=x,
            y=y,
            scale=scale,
            offset_x=offset_x,
            offset_y=offset_y,
            after_ms=after_ms,
        )

    def reset_zoom(self) -> None:
        reset_demo_zoom(self.page)

    def click_locator(
        self,
        locator: Any,
        *,
        after_ms: int = 550,
        delay_ms: int = 90,
        zoom: bool | dict[str, Any] = False,
    ) -> None:
        target = self.move_to_locator(locator)
        self.page.mouse.click(target["x"], target["y"], delay=delay_ms)
        self.page.evaluate(
            "(point) => window.__demoCursorClick?.(point.x, point.y)",
            target,
        )
        if zoom:
            zoom_options = zoom if isinstance(zoom, dict) else {}
            zoom_to_point(self.page, x=target["x"], y=target["y"], **zoom_options)
        self.pause(after_ms)

    def click_role(
        self,
        role: str,
        name: str | None = None,
        *,
        after_ms: int = 550,
        zoom: bool | dict[str, Any] = False,
    ) -> None:
        options = {"name": name} if name is not None else {}
        self.click_locator(self.page.get_by_role(role, **options).first, after_ms=after_ms, zoom=zoom)

    def click_label(
        self,
        label: str,
        *,
        after_ms: int = 550,
        zoom: bool | dict[str, Any] = False,
    ) -> None:
        self.click_locator(self.page.get_by_label(label).first, after_ms=after_ms, zoom=zoom)

    def type_label(self, label: str, text: str, *, delay_ms: int = 22, after_ms: int = 450) -> None:
        locator = self.page.get_by_label(label).first
        self.click_locator(locator, after_ms=180)
        locator.fill("")
        locator.press_sequentially(text, delay=delay_ms)
        self.pause(after_ms)

    def select_label(self, label: str, value: str, *, after_ms: int = 400) -> None:
        locator = self.page.get_by_label(label).first
        self.click_locator(locator, after_ms=180)
        locator.select_option(value)
        self.pause(after_ms)


def move_recorded_video(page: Any, destination: str | Path) -> dict[str, Any]:
    video = page.video
    if video is None:
        raise RuntimeError("No Playwright video is attached to this page.")
    source = Path(video.path())
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if destination_path.exists():
        destination_path.unlink()
    shutil.move(str(source), str(destination_path))
    return {"path": str(destination_path), "size_bytes": destination_path.stat().st_size}


def ease_in_out_cubic(value: float) -> float:
    if value < 0.5:
        return 4 * value * value * value
    return 1 - math.pow(-2 * value + 2, 3) / 2
