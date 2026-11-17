"""Measured screen limits for web pages: one table, one page script, one record per image."""

import hashlib
import json
import subprocess
from pathlib import Path

LIMITS = {"text_px": 14, "control_px": 44, "link_px": 24, "accent_colours": 2}
AXE_TAGS = "wcag2a,wcag2aa,wcag21a,wcag21aa,wcag22aa"
AXE_NAMES = {
    "color-contrast": "contrast",
    "target-size": "link-size",
    "button-name": "label",
    "input-button-name": "label",
    "link-name": "label",
    "label": "label",
    "select-name": "label",
    "image-alt": "label",
}
MEASURE_SCRIPT = """(() => {
const LIMITS = LIMITS_JSON;
const found = [];
const visible = (el) => {
  const s = getComputedStyle(el);
  const b = el.getBoundingClientRect();
  const clipped = (s.clip && s.clip !== "auto") || (s.clipPath && s.clipPath !== "none");
  return !clipped && s.visibility !== "hidden" && s.display !== "none" && +s.opacity > 0 && b.width > 1 && b.height > 1;
};
const rgb = (c) => (c.match(/[\\d.]+/g) || []).map(Number);
const opaque = (c) => { const v = rgb(c); return v.length >= 3 && (v.length < 4 || v[3] > 0.1); };
const hue = ([r, g, b]) => {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
  const l = (max + min) / 2, s = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
  if (s < 0.25 || l < 0.12 || l > 0.92) return null;
  const h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return Math.round(((h * 60) + 360) % 360 / 30);
};
const controls = [...document.querySelectorAll("button,a[href],input:not([type=hidden]),select,textarea,[role=button],[role=link]")].filter(visible);
const name = (el) => (el.innerText || el.getAttribute("aria-label") || el.tagName).trim().slice(0, 30);
const ownText = (el) => [...el.childNodes].some((n) => n.nodeType === 3 && n.nodeValue.trim());
const texts = [...document.body.querySelectorAll("*")].filter((el) => ownText(el) && visible(el));
for (const el of texts) {
  const px = parseFloat(getComputedStyle(el).fontSize);
  if (px < LIMITS.text_px) found.push({ rule: "text-size", at: name(el), px });
}
for (const el of controls) {
  const b = el.getBoundingClientRect();
  const link = el.tagName === "A" || el.getAttribute("role") === "link";
  if (!link && (b.width < LIMITS.control_px || b.height < LIMITS.control_px)) {
    found.push({ rule: "tap-size", at: name(el), w: Math.round(b.width), h: Math.round(b.height) });
  }
}
const groups = new Map();
for (const el of controls.filter((c) => c.tagName === "BUTTON" || c.getAttribute("role") === "button")) {
  groups.set(el.parentElement, [...(groups.get(el.parentElement) || []), el]);
}
const colourOf = (el, s) => [ownText(el) ? s.color : "", s.backgroundColor, s.borderTopWidth !== "0px" ? s.borderTopColor : ""];
for (const [parent, members] of groups) {
  if (members.length < 2) continue;
  const behind = getComputedStyle(parent).backgroundColor;
  const filled = members.filter((m) => { const c = getComputedStyle(m).backgroundColor; return opaque(c) && c !== behind && hue(rgb(c)) !== null; });
  const fills = new Set(filled.map((m) => getComputedStyle(m).backgroundColor));
  if (fills.size > 1) found.push({ rule: "competing-buttons", at: filled.map(name).join(" + "), fills: fills.size });
  const block = parent.parentElement;
  const box = block.getBoundingClientRect();
  const pad = parseFloat(getComputedStyle(block).paddingLeft);
  const left = Math.min(...members.map((m) => m.getBoundingClientRect().left));
  const row = parent.getBoundingClientRect();
  const stacked = (c) => { const r = c.getBoundingClientRect(); return r.bottom <= row.top + 1 || r.top >= row.bottom - 1; };
  const siblings = [...block.children].filter((c) => c !== parent && visible(c) && ownText(c) && stacked(c));
  const textLefts = siblings.map((c) => { const r = document.createRange(); r.selectNodeContents(c); return r.getBoundingClientRect().left; });
  const edges = new Set([left, ...textLefts].map((x) => Math.round(x - box.left - pad)));
  if (edges.size > 1) found.push({ rule: "shared-edge", at: name(block), edges: [...edges] });
  const colours = new Set();
  for (const el of [block, ...block.querySelectorAll("*")]) {
    if (!visible(el)) continue;
    for (const c of colourOf(el, getComputedStyle(el))) {
      if (c && opaque(c) && hue(rgb(c)) !== null) colours.add(rgb(c).slice(0, 3).join(","));
    }
  }
  if (colours.size > LIMITS.accent_colours) found.push({ rule: "accent-colours", at: name(block), colours: colours.size });
}
if (document.documentElement.scrollWidth > innerWidth + 1) {
  found.push({ rule: "overflow", at: "page", scrollWidth: document.documentElement.scrollWidth, width: innerWidth });
}
return JSON.stringify(found);
})()"""


def measure_script() -> str:
    return MEASURE_SCRIPT.replace("LIMITS_JSON", json.dumps(LIMITS))


def axe_findings(output: str) -> list[dict[str, object]]:
    """The violations of an axe run, one finding for each element."""
    data = json.loads(output[output.index("{") :])["data"]
    return [
        {
            "rule": AXE_NAMES.get(item["id"], item["id"]),
            "at": ", ".join(node["target"][-1:]),
        }
        for item in data["violations"]
        for node in item["nodes"]
    ]


def checkout_state(root: Path) -> dict[str, object]:
    """The commit a capture was taken from and whether the checkout had uncommitted changes."""

    def git(*args: str) -> str:
        done = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=False
        )
        return done.stdout.strip() if done.returncode == 0 else ""

    return {
        "commit": git("rev-parse", "HEAD"),
        "dirty": bool(git("status", "--porcelain")),
    }


def write_record(
    root: Path, image: Path, width: int, findings: list[dict[str, object]]
) -> Path:
    record = image.with_suffix(".json")
    record.write_text(
        json.dumps(
            {
                "image": image.name,
                "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                "width": width,
                "findings": findings,
                **checkout_state(root),
            },
            indent=2,
        )
        + "\n"
    )
    return record
