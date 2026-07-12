#!/usr/bin/env node
import {
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const skillRoot = resolve(scriptDir, "..");
const templateRoot = join(skillRoot, "assets", "remotion-product-demo");

const DEFAULT_COLORS = {
  "color-neutral-0": "oklch(99% 0.003 130)",
  "color-neutral-1": "oklch(97% 0.005 130)",
  "color-neutral-2": "oklch(93% 0.008 130)",
  "color-neutral-3": "oklch(86% 0.012 130)",
  "color-ink-1": "oklch(18% 0.017 138)",
  "color-ink-2": "oklch(35% 0.018 138)",
  "color-accent-1": "oklch(34% 0.105 158)",
  "color-accent-2": "oklch(92% 0.04 155)",
};

const DEFAULT_TYPOGRAPHY = {
  uiFontFamily: "system-ui",
  displayFontFamily: "system-ui",
  uiStack: "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",
  displayStack: "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",
};

function parseArgs(argv) {
  const args = {
    cwd: process.cwd(),
    out: "docs/demo/remotion",
    design: undefined,
    force: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--cwd") args.cwd = argv[++index];
    else if (arg === "--out") args.out = argv[++index];
    else if (arg === "--design") args.design = argv[++index];
    else if (arg === "--force") args.force = true;
    else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  return {
    ...args,
    cwd: resolve(args.cwd),
    out: resolve(args.cwd, args.out),
    design: args.design ? resolve(args.cwd, args.design) : undefined,
  };
}

function printHelp() {
  console.log(`Usage:
  node <skill>/scripts/create-remotion-demo.mjs [--out docs/demo/remotion] [--design DESIGN.md] [--force]

Creates a reusable Remotion product-demo template and generates design.generated.ts
from DESIGN.md/design.md so fonts, colors, radius, and register come from the project.`);
}

function findDesignFile(cwd, explicitPath) {
  if (explicitPath) {
    if (!existsSync(explicitPath)) {
      throw new Error(`Design file not found: ${explicitPath}`);
    }
    return explicitPath;
  }

  const candidates = [
    "DESIGN.md",
    "design.md",
    "docs/DESIGN.md",
    "docs/design.md",
    ".agents/DESIGN.md",
    ".agents/design.md",
  ];

  return candidates.map((candidate) => join(cwd, candidate)).find(existsSync);
}

function readDesign(designPath) {
  if (!designPath) {
    return {
      sourcePath: null,
      design: buildDesignObject("product", "", ""),
    };
  }

  const markdown = readFileSync(designPath, "utf8");
  return {
    sourcePath: designPath,
    design: parseDesignMarkdown(markdown),
  };
}

function parseDesignMarkdown(markdown) {
  let name = "product";
  let register = "product";
  let visualDirection = "";
  const colors = { ...DEFAULT_COLORS };
  const radii = {};
  const typography = { ...DEFAULT_TYPOGRAPHY };
  let typographyRole = null;

  const lines = markdown.split(/\r?\n/);
  for (const line of lines) {
    const topLevel = line.match(/^([A-Za-z][\w-]*):\s*["']?([^"']+)["']?\s*$/);
    if (topLevel) {
      const [, key, rawValue] = topLevel;
      const value = rawValue.trim();
      if (key === "name") name = value;
      if (key === "register") register = value;
      if (key === "visualDirection") visualDirection = value;
    }

    const yamlToken = line.match(/^\s{2,}([A-Za-z][\w-]*):\s*["']?([^"']+)["']?\s*$/);
    if (yamlToken) {
      const [, key, value] = yamlToken;
      if (key.startsWith("color-")) colors[key] = value.trim();
      if (key.startsWith("radius-")) radii[key] = value.trim();
    }

    const typographyRoleMatch = line.match(/^\s{2,}(ui|body|title|titles|display|heading):\s*$/i);
    if (typographyRoleMatch) {
      const role = typographyRoleMatch[1].toLowerCase();
      typographyRole = role === "ui" || role === "body" ? "ui" : "display";
    }

    const nestedFont = line.match(/^\s{4,}fontFamily:\s*["']?([^"']+)["']?\s*$/);
    if (nestedFont && typographyRole) {
      const font = cleanFontName(nestedFont[1]);
      if (typographyRole === "display") typography.displayFontFamily = font;
      else typography.uiFontFamily = font;
    }

    const cssToken = line.match(/--([a-z0-9-]+)\s*:\s*([^;`]+)/i);
    if (cssToken) {
      const [, key, value] = cssToken;
      if (key.startsWith("color-")) colors[key] = value.trim();
      if (key.startsWith("radius-")) radii[key] = value.trim();
    }

    const family = line.match(/^\s*-\s*(?:UI\/body|body|ui):\s*`([^`]+)`/i);
    if (family) {
      typography.uiFontFamily = cleanFontName(family[1]);
    }

    const display = line.match(/^\s*-\s*(?:Titles\/task titles|task titles|titles|display):\s*`([^`]+)`/i);
    if (display) {
      typography.displayFontFamily = cleanFontName(display[1]);
    }

    const yamlFont = line.match(/^\s{2,}(uiFontFamily|displayFontFamily|fontFamily):\s*["']?([^"']+)["']?\s*$/);
    if (yamlFont) {
      const [, key, value] = yamlFont;
      const font = cleanFontName(value);
      if (key === "displayFontFamily") typography.displayFontFamily = font;
      else typography.uiFontFamily = font;
    }
  }

  typography.uiStack = buildFontStack(typography.uiFontFamily, "ui");
  typography.displayStack = buildFontStack(
    typography.displayFontFamily === "system-ui"
      ? typography.uiFontFamily
      : typography.displayFontFamily,
    "display",
  );

  return {
    ...buildDesignObject(name, register, visualDirection),
    colors,
    radii,
    typography,
  };
}

function buildDesignObject(name, register, visualDirection) {
  return {
    name: name || "product",
    register: register || "product",
    visualDirection: visualDirection || "Design-system driven product demo",
    colors: { ...DEFAULT_COLORS },
    radii: {},
    typography: { ...DEFAULT_TYPOGRAPHY },
  };
}

function cleanFontName(value) {
  return value
    .replace(/[.;]+$/g, "")
    .replace(/^["']|["']$/g, "")
    .replace(/\s+(?:[1-9]00)$/g, "")
    .trim();
}

function buildFontStack(fontFamily, role) {
  const fallback =
    role === "display"
      ? "ui-sans-serif, system-ui, sans-serif"
      : "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif";

  if (!fontFamily || fontFamily === "system-ui") return DEFAULT_TYPOGRAPHY.uiStack;
  if (fontFamily.includes(",")) return fontFamily;
  return `"${fontFamily}", ${fallback}`;
}

function copyTemplateFiles(fromDir, toDir, { force }) {
  mkdirSync(toDir, { recursive: true });
  const written = [];

  for (const entry of readdirSync(fromDir)) {
    const source = join(fromDir, entry);
    const destination = join(toDir, entry);
    const stats = statSync(source);

    if (stats.isDirectory()) {
      written.push(...copyTemplateFiles(source, destination, { force }));
      continue;
    }

    if (existsSync(destination) && !force) {
      continue;
    }

    writeFileSync(destination, readFileSync(source));
    written.push(destination);
  }

  return written;
}

function writeGeneratedDesign(outDir, design, sourcePath) {
  const destination = join(outDir, "design.generated.ts");
  const sourceComment = sourcePath
    ? `Generated from ${relative(process.cwd(), sourcePath)}.`
    : "Generated without DESIGN.md; replace with project design tokens when available.";
  const content = `// ${sourceComment}
// Do not edit by hand. Re-run create-remotion-demo.mjs after design changes.

export const demoDesign = ${JSON.stringify(
    { ...design, sourcePath: sourcePath ? relative(process.cwd(), sourcePath) : null },
    null,
    2,
  )} as const;

export type GeneratedDemoDesign = typeof demoDesign;
`;
  writeFileSync(destination, content);
  return destination;
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  if (!existsSync(templateRoot)) {
    throw new Error(`Template directory missing: ${templateRoot}`);
  }

  const designPath = findDesignFile(options.cwd, options.design);
  const { design, sourcePath } = readDesign(designPath);
  const copied = copyTemplateFiles(templateRoot, options.out, { force: options.force });
  const generated = writeGeneratedDesign(options.out, design, sourcePath);

  console.log("Remotion product-demo template ready.");
  console.log(`out=${relative(options.cwd, options.out)}`);
  console.log(`design=${sourcePath ? relative(options.cwd, sourcePath) : "not found"}`);
  console.log(`generated=${relative(options.cwd, generated)}`);
  if (copied.length > 0) {
    console.log(`template_files=${copied.map((file) => relative(options.cwd, file)).join(",")}`);
  }
}

try {
  main();
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
