"""Measured screen limits for web pages: one table, one page script, one record per image."""

import hashlib
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

LIMITS = {
    "text_px": 11,
    "control_px": 44,
    "link_px": 24,
    "desktop_px": 1280,
    "accent_colours": 2,
    "secondary_words": 20,
    "frame_ratio": 1.1,
    "cls": 0.1,
    "fetch_waves": 3,
    "request_hold_ms": 150,
    "action_quiet_ms": 500,
    "action_reaction_ms": 1000,
}
PROOF_KINDS = {
    "Mistake-proof": ("judgement",),
    "Least effort": ("judgement",),
    "Observe": ("judgement",),
    "Undo": ("judgement",),
    "No clutter": ("measured", "judgement"),
    "Hierarchy": ("measured", "judgement"),
    "Alignment": ("measured", "judgement"),
    "Spacing": ("judgement",),
    "Design system": ("judgement",),
    "Messages": ("judgement",),
    "States": ("test",),
    "Time": ("test",),
    "Audit": ("test",),
    "Accessibility": ("measured",),
    "Widths": ("measured",),
    "Performance": ("test",),
}
ITEM_KINDS = {
    "size": f"the rendered text size against the {LIMITS['text_px']} px floor",
    "colour": "the text colour and its fill against the DESIGN.md colour tokens",
    "gap": "the gap between two neighbours against the DESIGN.md spacing tokens",
    "radius": "the corner radius against the DESIGN.md rounded tokens",
    "tap": "the control size against its tap floor",
    "weight": "the text weight against the weight of its neighbours in the same row",
    "align": "whether the text is centred in its parent (a claim that it is not); any other alignment claim is judgement",
    "judgement": "anything else: placement, any other alignment or weight claim, line count, wording",
}
MEASURED_KINDS = frozenset(ITEM_KINDS) - {"judgement"}
FINDING_RULES = {
    "competing-buttons": "Hierarchy",
    "accent-colours": "Hierarchy",
    "heading-hierarchy": "Hierarchy",
    "duplicate-buttons": "No clutter",
    "extra-text": "No clutter",
    "field-control": "No clutter",
    "shared-edge": "Alignment",
}
DECORATION = '[aria-hidden="true"],[role=img]'
COLOUR_JS = (
    "const rgb = (() => { const cv = Object.assign(document.createElement('canvas'), { width: 1, height: 1 }).getContext('2d', { willReadFrequently: true }); "
    "const byte = (x) => Math.round(x * 255) / 255; "
    "return (c) => { const m = /^(rgba?\\(|color\\(srgb )(.*)\\)$/.exec(c); if (m) { const n = m[2].split(/[\\s,\\/]+/).filter(Boolean).map(Number); "
    "if (n.length >= 3 && n.length <= 4 && n.every(Number.isFinite)) { const k = m[1][0] === 'c' ? 255 : 1; return [...n.slice(0, 3).map((v) => Math.min(255, Math.max(0, Math.round(v * k)))), byte(n.length > 3 ? n[3] : 1)]; } } "
    "const a = /\\s*\\/\\s*(\\d*\\.?\\d+)(%?)\\s*\\)$/.exec(c); "
    "cv.clearRect(0, 0, 1, 1); cv.fillStyle = 'rgba(0, 0, 0, 0)'; cv.fillStyle = a ? c.slice(0, a.index) + ')' : c; cv.fillRect(0, 0, 1, 1); const d = cv.getImageData(0, 0, 1, 1).data; "
    "return [d[0], d[1], d[2], byte(d[3] / 255 * (a ? Math.min(1, a[2] ? a[1] / 100 : +a[1]) : 1))]; }; })(); "
    "const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); }; "
)
DECORATED_JS = (
    "((el) => { const root = el.closest(DECORATION_JSON); if (!root) return false; "
    "const fill = (c) => { const v = rgb(c); return v.length >= 3 && (v.length < 4 || v[3] > 0.1); }; "
    "const covers = (s, r) => { const q = s.getBoundingClientRect(); return q.left <= r.left + 1 && q.top <= r.top + 1 && q.right >= r.right - 1 && q.bottom >= r.bottom - 1; }; "
    "const behind = (e) => { const r = e.getBoundingClientRect(); for (let n = e; n.parentElement; n = n.parentElement) { for (let s = n.previousElementSibling; s; s = s.previousElementSibling) { const c = getComputedStyle(s).backgroundColor; if (fill(c) && covers(s, r)) return c; } const c = getComputedStyle(n.parentElement).backgroundColor; if (fill(c)) return c; } return 'rgb(255, 255, 255)'; }; "
    "const apart = (c, e) => { if (!fill(c)) return false; const a = lum(rgb(c)), b = lum(rgb(behind(e))); return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05) >= LIMITS.frame_ratio; }; "
    "const boxed = (e) => { const s = getComputedStyle(e); return e.namespaceURI === 'http://www.w3.org/2000/svg' "
    "|| apart(s.backgroundColor, e) || /\\d+px \\d+px [1-9]/.test(s.boxShadow) "
    "|| (parseFloat(s.borderTopWidth) >= 1 && s.borderTopStyle !== 'none' && apart(s.borderTopColor, e)); }; "
    "for (let n = el; n; n = n.parentElement) { if (boxed(n)) return true; if (n === root) return false; } return false; })"
)
PREFETCH_SIGNS = {
    "next-router-prefetch": "",
    "purpose": "prefetch",
    "sec-purpose": "prefetch",
}
HOLD_SCRIPT = """(() => {
if (window.__heHold) return;
const HOLD = HOLD_MS;
const SIGNS = SIGNS_JSON;
const log = [];
Object.defineProperty(window, "__heHold", { value: HOLD });
Object.defineProperty(window, "__heRequests", { value: log });
const prefetching = (headers) => [...headers].some(([name, value]) => name in SIGNS && value.toLowerCase().includes(SIGNS[name]));
const realFetch = window.fetch;
window.fetch = (input, init) => {
  const headers = new Headers(input instanceof Request ? input.headers : undefined);
  new Headers(init && init.headers).forEach((value, name) => headers.set(name, value));
  const entry = { start: performance.now(), end: 0, prefetch: prefetching(headers) };
  log.push(entry);
  return new Promise((resolve, reject) => setTimeout(() => {
    realFetch(input, init).then(
      (reply) => { entry.end = performance.now(); resolve(reply); },
      (error) => { entry.end = performance.now(); reject(error); },
    );
  }, HOLD));
};
const states = new WeakMap();
const proto = XMLHttpRequest.prototype;
const realOpen = proto.open, realSend = proto.send, realSet = proto.setRequestHeader;
proto.open = function (method, url, async = true, ...rest) {
  const state = { sync: async === false, headers: new Headers(), entry: null };
  states.set(this, state);
  this.addEventListener("readystatechange", () => { if (this.readyState === 4 && state.entry) state.entry.end = performance.now(); });
  return realOpen.call(this, method, url, async, ...rest);
};
proto.setRequestHeader = function (name, value) {
  realSet.call(this, name, value);
  const state = states.get(this);
  if (state) state.headers.set(name, value);
};
proto.send = function (body) {
  const state = states.get(this);
  if (!state || state.sync) return realSend.call(this, body);
  state.entry = { start: performance.now(), end: 0, prefetch: prefetching(state.headers) };
  log.push(state.entry);
  setTimeout(() => { try { realSend.call(this, body); } catch { state.entry.end = performance.now(); } }, HOLD);
};
})()"""
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
MEASURE_SCRIPT = """(async () => {
const LIMITS = LIMITS_JSON;
const found = [];
if (!window.__heHold) return JSON.stringify({ found: [{ rule: "request-delay-missing" }], measured: {} });
const shown = (el) => {
  const s = getComputedStyle(el);
  const b = el.getBoundingClientRect();
  const clipped = (s.clip && s.clip !== "auto") || /inset\\(\\s*(50|100)%|circle\\(\\s*0|polygon\\(\\s*0/.test(s.clipPath || "");
  const away = b.right + scrollX <= 0 || b.bottom + scrollY <= 0;
  return !clipped && !away && s.visibility !== "hidden" && s.display !== "none" && +s.opacity > 0 && b.width > 1 && b.height > 1;
};
const decorated = DECORATED_JSFN;
const visible = (el) => !decorated(el) && shown(el);
COLOUR_JSFN
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
const ownText = (el) => [...el.childNodes].some((n) => n.nodeType === 3 && n.nodeValue.trim()) || ["::before", "::after"].some((p) => /^["']./.test(getComputedStyle(el, p).content));
const texts = [...document.body.querySelectorAll("*")].filter((el) => ownText(el) && visible(el));
for (const el of texts) {
  const px = parseFloat(getComputedStyle(el).fontSize);
  if (px < LIMITS.text_px) found.push({ rule: "text-size", at: name(el), px });
}
const isLink = (el) => el.tagName === "A" || el.getAttribute("role") === "link";
const inSentence = (el) => {
  if (getComputedStyle(el).display !== "inline") return false;
  let block = el.parentElement;
  while (block && getComputedStyle(block).display === "inline") block = block.parentElement;
  if (!block) return false;
  const sameLine = (n) => { for (let p = n.parentElement; p && p !== block; p = p.parentElement) if (getComputedStyle(p).display !== "inline") return false; return true; };
  const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const host = n.parentElement;
    if (host && !host.closest("a[href],[role=link]") && sameLine(n) && visible(host) && n.nodeValue.trim().length > 1) return true;
  }
  return false;
};
const factName = (el) => (el.innerText || el.getAttribute("aria-label") || "").replace(/\\s+/g, " ").trim().slice(0, 30);
const controlFacts = new Map();
for (const el of controls) {
  const b = el.getBoundingClientRect();
  const link = isLink(el);
  const exempt = link && inSentence(el);
  const floor = link && innerWidth >= LIMITS.desktop_px ? LIMITS.link_px : LIMITS.control_px;
  const under = !exempt && (b.width < floor || b.height < floor);
  const fact = { at: factName(el), w: Math.round(b.width), h: Math.round(b.height), floor, under, exempt };
  controlFacts.set(JSON.stringify(fact), fact);
  if (under) found.push({ rule: "tap-size", at: name(el), w: fact.w, h: fact.h });
}
const pseudoText = (el) => ["::before", "::after"].map((p) => {
  const c = getComputedStyle(el, p).content;
  return c && /^["']/.test(c) ? c.slice(1, -1) : "";
}).join("");
const textOf = (el) => {
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  let out = "";
  for (let n = walker.nextNode(); n; n = walker.nextNode()) if (n.parentElement && visible(n.parentElement)) out += n.nodeValue;
  for (const e of [el, ...el.querySelectorAll("*")]) if (visible(e)) out += pseudoText(e);
  return (el.value && el.tagName === "INPUT" ? el.value : out).trim();
};
const groups = new Map();
const fields = [...document.querySelectorAll("input:not([type=hidden]),select,textarea")].filter(visible).map((f) => f.getBoundingClientRect());
const inField = (el) => { const b = el.getBoundingClientRect(); return fields.some((f) => b.left < f.right && f.left < b.right && b.top < f.bottom && f.top < b.bottom); };
for (const el of controls.filter((c) => (c.tagName === "BUTTON" || c.getAttribute("role") === "button") && !inField(c))) {
  groups.set(el.parentElement, [...(groups.get(el.parentElement) || []), el]);
}
const colourOf = (el, s) => [ownText(el) ? s.color : "", s.backgroundColor, s.borderTopWidth !== "0px" ? s.borderTopColor : ""];
const rgbKey = (c) => rgb(c).slice(0, 3).join(",");
const pageInk = new Set([document.body, document.querySelector("main")].filter(Boolean).map((el) => rgbKey(getComputedStyle(el).color)));
const pageHeading = document.querySelector("h1");
const pageLevel = (el) => ["BODY", "MAIN"].includes(el.tagName) || Boolean(pageHeading && el.contains(pageHeading));
for (const [parent, members] of groups) {
  if (members.length > 1) {
    const behind = getComputedStyle(parent).backgroundColor;
    const filled = members.filter((m) => { const c = getComputedStyle(m).backgroundColor; return opaque(c) && c !== behind && hue(rgb(c)) !== null; });
    if (filled.length > 1) found.push({ rule: "competing-buttons", at: filled.map(name).join(" + "), count: filled.length });
    const seenLabels = new Map();
    for (const m of members) {
      const label = textOf(m).replace(/\\s+/g, " ").trim().toLowerCase();
      if (label) seenLabels.set(label, (seenLabels.get(label) || 0) + 1);
    }
    for (const [label, count] of seenLabels) {
      if (count > 1) found.push({ rule: "duplicate-buttons", at: label.slice(0, 30), count });
    }
  }
  if (members.length > 1) {
  const block = pageLevel(parent.parentElement) ? parent : parent.parentElement;
  const colours = new Set();
  for (const el of [block, ...block.querySelectorAll("*")]) {
    if (!visible(el)) continue;
    const [text, ...fills] = colourOf(el, getComputedStyle(el));
    for (const c of [text && pageInk.has(rgbKey(text)) ? "" : text, ...fills]) {
      if (c && opaque(c) && hue(rgb(c)) !== null) colours.add(rgbKey(c));
    }
  }
  if (colours.size > LIMITS.accent_colours) found.push({ rule: "accent-colours", at: name(block), colours: colours.size });
  }
  if ([...parent.children].some((c) => !members.includes(c) && visible(c) && textOf(c))) continue;
  if (parent.querySelector("input:not([type=hidden]),select,textarea")) continue;
  const block = parent.parentElement;
  const box = block.getBoundingClientRect();
  const pad = parseFloat(getComputedStyle(block).paddingLeft);
  const row = parent.getBoundingClientRect();
  const ps = getComputedStyle(parent);
  const framed = (opaque(ps.backgroundColor) && ps.backgroundColor !== getComputedStyle(block).backgroundColor) || (ps.borderTopWidth !== "0px" && ps.borderTopStyle !== "none");
  const left = framed ? row.left : Math.min(...members.map((m) => m.getBoundingClientRect().left));
  const stacked = (c) => { const r = c.getBoundingClientRect(); return r.bottom <= row.top + 1 || r.top >= row.bottom - 1; };
  const siblings = [...block.children].filter((c) => c !== parent && visible(c) && ownText(c) && stacked(c));
  const textLefts = siblings.map((c) => { const r = document.createRange(); r.selectNodeContents(c); return r.getBoundingClientRect().left; });
  const edges = new Set([left, ...textLefts].map((x) => Math.round(x - box.left - pad)));
  if (edges.size > 1) found.push({ rule: "shared-edge", at: name(block), edges: [...edges] });
}
const overlaps = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
const labelled = (el) => ["aria-label", "aria-labelledby", "title"].some((a) => (el.getAttribute(a) || "").trim()) || (el.textContent || "").trim() !== "";
const selectorOf = (el) => el.tagName.toLowerCase() + (el.getAttribute("name") ? `[name="${el.getAttribute("name")}"]` : "");
const BUTTONS = "button,[role=button],input[type=button],input[type=submit]";
const submitting = (el) => el.getAttribute("type") === "submit";
const isControl = (e) => e.matches(BUTTONS + ",a[href],[tabindex],[onclick],label[for]") || getComputedStyle(e).cursor === "pointer" || textOf(e) !== "";
for (const input of document.querySelectorAll("input[type=password]")) {
  if (!visible(input)) continue;
  const r = input.getBoundingClientRect();
  const scope = input.form || input.parentElement.parentElement || input.parentElement;
  const near = (br) => {
    const gap = Math.max(br.left - r.right, r.left - br.right);
    const centre = (br.top + br.bottom) / 2;
    return gap <= 24 && centre >= r.top - 4 && centre <= r.bottom + 4;
  };
  const candidates = [...scope.querySelectorAll("*")].filter((e) => e !== input && visible(e) && !e.contains(input) && !(input.labels && [...input.labels].some((l) => l.contains(e) && l.querySelector("input") === input)) && !submitting(e) && near(e.getBoundingClientRect()) && isControl(e));
  for (const b of candidates.filter((c) => !candidates.some((o) => o !== c && c.contains(o)))) {
    const text = textOf(b);
    const why = !overlaps(b.getBoundingClientRect(), r) ? "reveal control outside the field" : text ? "reveal control with text" : !labelled(b) ? "reveal control without a label" : "";
    if (why) found.push({ rule: "field-control", at: text || name(b), selector: selectorOf(input), why });
  }
}
const fieldText = (i) => [i.placeholder, i.getAttribute("aria-label"), i.title, i.name, i.id, ...[...(i.labels || [])].map((l) => l.innerText)].join(" ");
const searches = new Set([...document.querySelectorAll("input[type=search], [role=search] input:not([type=hidden],[type=submit],[type=button],[type=checkbox],[type=radio])")]);
for (const i of document.querySelectorAll("input")) if (["text", "search"].includes(i.type) && /search/i.test(fieldText(i))) searches.add(i);
for (const input of searches) {
  if (!visible(input)) continue;
  const r = input.getBoundingClientRect();
  const scope = input.form || input.closest("[role=search]") || input.parentElement;
  const drawn = (e) => ["::before", "::after"].some((p) => { const c = getComputedStyle(e, p).content; return c && c !== "none" && c !== "normal"; });
  const icon = getComputedStyle(input).backgroundImage !== "none" || drawn(input.parentElement) || drawn(scope) || [...scope.querySelectorAll("svg,img,i")].some((i) => {
    const b = i.getBoundingClientRect();
    return shown(i) && (b.left + b.right) / 2 > r.left && (b.left + b.right) / 2 < r.right && (b.top + b.bottom) / 2 > r.top && (b.top + b.bottom) / 2 < r.bottom;
  });
  const submits = [...scope.querySelectorAll("button:not([type=button],[type=reset]),input[type=submit]")].filter(visible);
  const labelledButtons = submits.filter((b) => textOf(b));
  if (icon && labelledButtons.length) found.push({ rule: "field-control", at: name(input), selector: selectorOf(input), why: "search text button beside a field with an icon" });
  if (!icon) found.push({ rule: "field-control", at: name(input), selector: selectorOf(input), why: "search field without an icon inside" });
}
const bodyPx = parseFloat(getComputedStyle(document.body).fontSize);
const SKIP = "a,button,label,legend,th,td,dt,summary,input,select,textarea,option,time,data,output,meter,nav,pre,code,[role=alert],[aria-live],h1,h2,h3,h4,h5,h6";
const chip = (el) => {
  const s = getComputedStyle(el);
  const filled = opaque(s.backgroundColor) && s.backgroundColor !== getComputedStyle(el.parentElement).backgroundColor;
  return filled || (s.borderTopWidth !== "0px" && s.borderTopStyle !== "none");
};
const lineOf = (el) => {
  const text = textOf(el);
  const words = text.split(/\\s+/).filter(Boolean);
  if (!text || !/\\p{L}/u.test(text) || el.closest(SKIP + ",li,footer,[role=contentinfo]") || chip(el) || /error|invalid|alert/i.test(el.className + " " + el.id)) return null;
  const valueLike = (t) => t.split(/\\s+/).filter(Boolean).length <= 3 && /[0-9]/.test(t);
  if (valueLike(text) || [...el.parentElement.children].some((c) => c !== el && !c.matches(HEADINGS) && ownText(c) && valueLike(textOf(c)))) return null;
  const s = getComputedStyle(el);
  const px = parseFloat(s.fontSize);
  return px < bodyPx - 0.5 ? { el, words: words.length, px } : null;
};
const HEADINGS = "h1,h2,h3,h4,h5,h6";
for (const heading of document.querySelectorAll(HEADINGS)) {
  if (!visible(heading)) continue;
  let top = heading;
  while (top.parentElement && !["BODY", "MAIN"].includes(top.parentElement.tagName) && top.parentElement.querySelectorAll(HEADINGS).length === 1) top = top.parentElement;
  const roots = [];
  if (top !== heading) roots.push(top);
  else for (let n = heading.nextElementSibling; n && !n.matches(HEADINGS) && !n.querySelector(HEADINGS); n = n.nextElementSibling) roots.push(n);
  const lines = roots.flatMap((root) => [root, ...root.querySelectorAll("*")]).filter((el) => ownText(el) && visible(el)).map(lineOf).filter(Boolean);
  if (lines.some((l) => l.px < LIMITS.text_px)) continue;
  if (lines.length > 1) found.push({ rule: "extra-text", at: name(heading), secondary_lines: lines.length });
  for (const line of lines) if (line.words > LIMITS.secondary_words) found.push({ rule: "extra-text", at: name(heading), words: line.words });
}
if (document.documentElement.scrollWidth > innerWidth + 1) {
  found.push({ rule: "overflow", at: "page", scrollWidth: document.documentElement.scrollWidth, width: innerWidth });
}
const bodyWeight = parseFloat(getComputedStyle(document.body).fontWeight) || 400;
const visibleHeadings = [...document.querySelectorAll(HEADINGS)].filter(visible);
const h1s = visibleHeadings.filter((h) => h.tagName === "H1");
const h2s = visibleHeadings.filter((h) => h.tagName === "H2");
const maxH1Px = h1s.length ? Math.max(...h1s.map((h) => parseFloat(getComputedStyle(h).fontSize))) : 0;
const heavyBody = texts.some((el) => {
  if (el.closest(HEADINGS + ",button,a,th,strong,b")) return false;
  const s = getComputedStyle(el);
  return parseFloat(s.fontSize) <= bodyPx * 1.15 && (parseFloat(s.fontWeight) || 400) >= 500;
});
for (const h of h1s) {
  const s = getComputedStyle(h);
  const px = parseFloat(s.fontSize), wt = parseFloat(s.fontWeight) || 400;
  if (px < bodyPx - 0.5 || (px <= bodyPx * 1.5 && (wt < bodyWeight || (heavyBody && wt <= 400)))) {
    found.push({ rule: "heading-hierarchy", at: name(h), px, weight: wt });
  }
}
for (const h of h2s) {
  const s = getComputedStyle(h);
  const px = parseFloat(s.fontSize), wt = parseFloat(s.fontWeight) || 400;
  if ((maxH1Px && px > maxH1Px + 0.5) || (px <= bodyPx * 1.35 && (wt < bodyWeight || (heavyBody && wt <= 400)))) {
    found.push({ rule: "heading-hierarchy", at: name(h), px, weight: wt });
  }
}
const measureCtx = document.createElement("canvas").getContext("2d");
const stackedBlocks = (el) => {
  const rows = [...el.querySelectorAll("*")].filter((c) => ownText(c) && visible(c) && !getComputedStyle(c).display.startsWith("inline")).map((c) => c.getBoundingClientRect());
  return rows.some((a, i) => rows.slice(i + 1).some((b) => a.bottom <= b.top + 1 || b.bottom <= a.top + 1));
};
const labelLines = (el) => {
  const boxes = [];
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (!n.nodeValue.trim() || !visible(n.parentElement)) continue;
    const range = document.createRange();
    range.selectNodeContents(n);
    for (const b of range.getClientRects()) if (b.width > 1 && b.height > 1) boxes.push({ mid: (b.top + b.bottom) / 2, h: b.height });
  }
  boxes.sort((a, b) => a.mid - b.mid);
  return boxes.filter((b, i) => i === 0 || b.mid - boxes[i - 1].mid > Math.min(b.h, boxes[i - 1].h) / 2).length;
};
for (const el of controls) {
  const s = getComputedStyle(el);
  if ((el.tagName === "BUTTON" || el.getAttribute("role") === "button" || (el.tagName === "A" && chip(el))) && !stackedBlocks(el) && labelLines(el) > 1) {
    found.push({ rule: "wrapped-label", at: name(el), lines: labelLines(el) });
  }
  if (el.tagName === "SELECT") {
    const opt = el.options[el.selectedIndex];
    const label = (opt ? opt.text : "").trim();
    if (label && measureCtx) {
      measureCtx.font = s.font || `${s.fontWeight} ${s.fontSize} ${s.fontFamily}`;
      const pad = (parseFloat(s.paddingLeft) || 0) + (parseFloat(s.paddingRight) || 0);
      const arrow = (s.appearance === "none" || s.webkitAppearance === "none") ? 0 : 18;
      const avail = el.clientWidth - pad - arrow;
      if (avail <= 8 || measureCtx.measureText(label).width > avail + 4) {
        found.push({ rule: "clipped-control", at: name(el), why: "select clips selected option" });
      }
    }
  } else if (
    (el.tagName === "BUTTON" || el.getAttribute("role") === "button") &&
    (s.overflowX === "hidden" || s.overflowX === "clip") &&
    s.whiteSpace === "nowrap" &&
    s.textOverflow !== "ellipsis" &&
    el.scrollWidth > el.clientWidth + 2
  ) {
    found.push({ rule: "clipped-control", at: name(el), why: "button text clipped" });
  }
}
const inScroller = (node, stop) => {
  for (let p = node.parentElement; p && p !== stop; p = p.parentElement) {
    const oy = getComputedStyle(p).overflowY;
    if (oy === "auto" || oy === "scroll") return true;
  }
  return false;
};
const reportedChrome = new Set();
for (const el of document.body.querySelectorAll("*")) {
  if (!visible(el)) continue;
  const s = getComputedStyle(el);
  if (s.position !== "fixed" && s.position !== "sticky") continue;
  const b = el.getBoundingClientRect();
  if (b.height < innerHeight * 0.5 || s.overflowY === "auto" || s.overflowY === "scroll") continue;
  const clipsY = s.overflowY === "hidden" || s.overflowY === "clip";
  if (s.position === "sticky" && !clipsY) continue;
  const limitY = s.position === "fixed" ? (clipsY ? Math.min(b.bottom, innerHeight) : innerHeight) : b.bottom;
  for (const ctrl of el.querySelectorAll("a[href],button,input:not([type=hidden]),select,textarea,[role=button],[role=link]")) {
    if (!visible(ctrl) || reportedChrome.has(ctrl) || inScroller(ctrl, el)) continue;
    if (ctrl.getBoundingClientRect().bottom > limitY + 2) {
      reportedChrome.add(ctrl);
      found.push({ rule: "clipped-chrome", at: name(ctrl), why: "control pushed past viewport bottom inside fixed or sticky chrome" });
    }
  }
}
const fetches = window.__heRequests
  .filter((e) => !e.prefetch && e.end > 0)
  .map((e) => ({ startTime: e.start, responseEnd: e.end }))
  .sort((a, b) => a.startTime - b.startTime);
const wavesOf = (list) => {
  let waves = 0, waveEnd = -1;
  for (const entry of list) {
    if (waves === 0 || entry.startTime >= waveEnd) {
      waves += 1;
      waveEnd = entry.responseEnd;
    } else if (entry.responseEnd > waveEnd) {
      waveEnd = entry.responseEnd;
    }
  }
  return waves;
};
const quiet = (t) => !fetches.some((e) => e.startTime < t && e.responseEnd > t - LIMITS.action_quiet_ms);
const reacts = (t) => fetches.some((e) => e.startTime >= t && e.startTime < t + LIMITS.action_reaction_ms);
const taken = ACTIONS_JSON.map(([ms, verb]) => ({ t: ms - performance.timeOrigin, verb }))
  .filter((c) => c.t > 0)
  .sort((a, b) => a.t - b.t);
const cuts = taken.filter((c) => quiet(c.t) && reacts(c.t));
const parts = [{ at: "load", entries: [] }, ...cuts.map((c) => ({ at: `${c.verb} ${taken.filter((o) => o.verb === c.verb && o.t <= c.t).length}`, entries: [] }))];
for (const entry of fetches) parts[cuts.filter((c) => c.t <= entry.startTime).length].entries.push(entry);
for (const part of parts) {
  const waves = wavesOf(part.entries);
  if (waves > LIMITS.fetch_waves) found.push({ rule: "fetch-waterfall", at: part.at, waves });
}
const shifts = [];
if (typeof PerformanceObserver !== "undefined" && (PerformanceObserver.supportedEntryTypes || []).includes("layout-shift")) {
  await new Promise((resolve) => {
    try {
      const obs = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (!entry.hadRecentInput) shifts.push(entry);
        }
      });
      obs.observe({ type: "layout-shift", buffered: true });
      setTimeout(() => {
        for (const entry of obs.takeRecords()) {
          if (!entry.hadRecentInput) shifts.push(entry);
        }
        obs.disconnect();
        resolve();
      }, 0);
    } catch { resolve(); }
  });
}
shifts.sort((a, b) => a.startTime - b.startTime);
let cls = 0, winVal = 0, winStart = 0, prevShift = 0;
for (const entry of shifts) {
  if (winVal && (entry.startTime - prevShift > 1000 || entry.startTime - winStart > 5000)) winVal = 0;
  if (!winVal) winStart = entry.startTime;
  winVal += entry.value;
  prevShift = entry.startTime;
  if (winVal > cls) cls = winVal;
}
if (cls > LIMITS.cls) {
  found.push({ rule: "layout-shift", at: "page", cls: +cls.toFixed(3) });
}
const hex = (c) => "#" + c.map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");
const solid = (el) => {
  let bg = [255, 255, 255];
  const chain = [];
  for (let n = el; n; n = n.parentElement) chain.unshift(n);
  for (const n of chain) {
    const s = getComputedStyle(n);
    if (s.backgroundImage !== "none") return null;
    const c = rgb(s.backgroundColor);
    bg = bg.map((v, i) => c[i] * c[3] + v * (1 - c[3]));
  }
  return bg;
};
const raw8 = (c) => c.slice(0, 3).map((v) => Math.round(v).toString(16).padStart(2, "0")).join("") + Math.round(c[3] * 255).toString(16).padStart(2, "0");
const fillOf = (el) => {
  for (let n = el; n; n = n.parentElement) {
    const c = getComputedStyle(n).backgroundColor;
    if (opaque(c)) return raw8(rgb(c));
  }
  return "";
};
const centredIn = (el, s) => {
  const parent = el.parentElement;
  if (!parent) return false;
  const range = document.createRange();
  range.selectNodeContents(el);
  const t = range.getBoundingClientRect(), p = parent.getBoundingClientRect(), ps = getComputedStyle(parent);
  const left = p.left + parseFloat(ps.paddingLeft) + parseFloat(ps.borderLeftWidth);
  const right = p.right - parseFloat(ps.paddingRight) - parseFloat(ps.borderRightWidth);
  const middle = (left + right) / 2;
  const lines = [];
  for (const r of [...range.getClientRects()].filter((q) => q.width > 1 && q.height > 1).sort((a, z) => a.top - z.top || a.left - z.left)) {
    const line = lines[lines.length - 1];
    if (line && r.top < line.bottom - 1) { line.left = Math.min(line.left, r.left); line.right = Math.max(line.right, r.right); line.bottom = Math.max(line.bottom, r.bottom); }
    else lines.push({ left: r.left, right: r.right, bottom: r.bottom });
  }
  if (s.textAlign !== "center" && !lines.every((r) => Math.abs((r.left + r.right) / 2 - middle) <= 2)) return false;
  return Math.abs((t.left + t.right) / 2 - middle) <= 2 && (s.textAlign === "center" || t.width < right - left - 4);
};
const textFacts = new Map();
const textNames = new Map();
for (const el of texts) textNames.set(factName(el), (textNames.get(factName(el)) || 0) + 1);
for (const el of texts) {
  const s = getComputedStyle(el);
  const size = parseFloat(s.fontSize);
  const c = rgb(s.color);
  const fact = { at: factName(el), n: textNames.get(factName(el)), px: Math.round(size * 100) / 100, weight: parseFloat(s.fontWeight) || 400, align: s.textAlign, centred: centredIn(el, s), colour: raw8(c), fill: fillOf(el), under: size < LIMITS.text_px };
  const bg = solid(el);
  if (bg) {
    const fg = c.slice(0, 3).map((v, i) => v * c[3] + bg[i] * (1 - c[3]));
    fact.ratio = Math.round(((Math.max(lum(fg), lum(bg)) + 0.05) / (Math.min(lum(fg), lum(bg)) + 0.05)) * 100) / 100;
    fact.fg = hex(fg);
    fact.bg = hex(bg);
  }
  textFacts.set(JSON.stringify(fact), fact);
}
const gaps = [];
const seenGaps = new Set();
const textSet = new Set(texts);for (const parent of document.body.querySelectorAll("*")) {
  const kids = [...parent.children].filter((c) => visible(c) && !["absolute", "fixed"].includes(getComputedStyle(c).position));
  if (kids.length < 2) continue;
  const rows = [];
  for (const box of kids.map((c) => ({ c, b: c.getBoundingClientRect() })).sort((a, z) => a.b.top - z.b.top || a.b.left - z.b.left)) {
    const row = rows[rows.length - 1];
    if (row && box.b.top < row.bottom - 1) { row.items.push(box); row.bottom = Math.max(row.bottom, box.b.bottom); }
    else rows.push({ items: [box], bottom: box.b.bottom });
  }
  const boxes = rows.flatMap((row) => row.items.sort((a, z) => a.b.left - z.b.left));
  for (let i = 1; i < boxes.length; i++) {
    const below = boxes[i].b.top - boxes[i - 1].b.bottom, beside = boxes[i].b.left - boxes[i - 1].b.right;
    const axis = below >= -1 ? "y" : beside >= -1 ? "x" : "";
    if (!axis) continue;
    const gap = { at: factName(boxes[i - 1].c), to: factName(boxes[i].c), px: Math.round(axis === "y" ? below : beside), axis };
    if (!textSet.has(boxes[i - 1].c) || !textSet.has(boxes[i].c)) gap.text = false;
    const key = JSON.stringify(gap);
    if (!seenGaps.has(key)) { seenGaps.add(key); gaps.push(gap); }
  }
}
const sizes = { controls: [...controlFacts.values()] };
const radiusOf = (el) => {
  const value = getComputedStyle(el).borderTopLeftRadius;
  if (!parseFloat(value)) return null;
  const b = el.getBoundingClientRect();
  const half = Math.round(Math.min(b.width, b.height) / 2);
  const declared = value.endsWith("%") ? Math.round(Math.min(b.width, b.height) * parseFloat(value) / 100) : Math.round(parseFloat(value));
  return { px: Math.min(declared, half), clamped: declared >= half };
};
const rounded = [...controls, ...[...document.body.querySelectorAll("*")].filter(visible)];
const radii = [];
const seenRadii = new Set();
for (const el of rounded) {
  const r = radiusOf(el);
  const fact = r && r.px > 0 ? { at: factName(el), px: r.px, clamped: r.clamped } : null;
  const key = fact && JSON.stringify(fact);
  if (fact && !seenRadii.has(key)) { seenRadii.add(key); radii.push(fact); }
}
const measured = { texts: [...textFacts.values()], gaps, sizes, radii, root_px: parseFloat(getComputedStyle(document.documentElement).fontSize) };
return JSON.stringify({ found, measured });
})()"""


def measure_script(actions: Sequence[tuple[int, str]] = ()) -> str:
    script = MEASURE_SCRIPT.replace("LIMITS_JSON", json.dumps(LIMITS))
    script = script.replace("ACTIONS_JSON", json.dumps(list(actions)))
    script = script.replace("COLOUR_JSFN", COLOUR_JS)
    script = script.replace("DECORATED_JSFN", DECORATED_JS)
    return script.replace("DECORATION_JSON", json.dumps(DECORATION))


def hold_script() -> str:
    """The script that every page of a session runs first: each fetch and XHR waits the same time before it is sent, and its own start and end are logged."""
    script = HOLD_SCRIPT.replace("HOLD_MS", str(LIMITS["request_hold_ms"]))
    return script.replace("SIGNS_JSON", json.dumps(PREFETCH_SIGNS))


def decoration_script(selectors: list[str]) -> str:
    decorated = DECORATED_JS.replace("DECORATION_JSON", json.dumps(DECORATION))
    return (
        f"(() => {{ const LIMITS = {json.dumps(LIMITS)}; {COLOUR_JS}const decorated = {decorated}; "
        f"return JSON.stringify({json.dumps(selectors)}.map((s) => {{ try {{ "
        "const el = document.querySelector(s); return Boolean(el && decorated(el)); "
        "} catch { return false; } })); })()"
    )


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
    root: Path,
    image: Path,
    width: int,
    findings: list[dict[str, object]],
    route: str = "",
    ring_boxes: list[dict[str, int]] | None = None,
    measured: dict[str, object] | None = None,
) -> Path:
    payload: dict[str, object] = {
        "image": image.name,
        "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "width": width,
        "findings": findings,
        "route": route,
        **checkout_state(root),
    }
    if ring_boxes:
        payload["ring_boxes"] = list(ring_boxes)
    if measured:
        payload["measured"] = measured
    record = image.with_suffix(".json")
    record.write_text(json.dumps(payload, indent=2) + "\n")
    return record
