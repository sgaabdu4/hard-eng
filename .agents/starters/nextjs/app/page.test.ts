import { expect, mock, test } from "bun:test";
import nextConfig from "../next.config";

mock.module("next/font/google", () => ({
  Geist: () => ({ variable: "font-sans-variable" }),
  Geist_Mono: () => ({ variable: "font-mono-variable" }),
}));

const { default: RootLayout } = await import("./layout");
const { default: Home } = await import("./page");

type Element = { type: unknown; props: Record<string, unknown> };

function isElement(node: unknown): node is Element {
  return (
    typeof node === "object" &&
    node !== null &&
    "type" in node &&
    "props" in node &&
    typeof node.props === "object" &&
    node.props !== null
  );
}

function elements(node: unknown): Element[] {
  if (Array.isArray(node)) return node.flatMap(elements);
  if (!isElement(node)) return [];
  return [node, ...elements(node.props.children)];
}

function text(node: unknown): string {
  if (typeof node === "string" || typeof node === "number") return `${node}`;
  if (Array.isArray(node)) return node.map(text).join("");
  return isElement(node) ? text(node.props.children) : "";
}

function renderHome() {
  return elements(
    RootLayout({ children: Home(), params: Promise.resolve({}) }),
  );
}

test("home page renders inside the root layout with both fonts", () => {
  const tree = renderHome();
  const html = tree[0];
  expect(html?.type).toBe("html");
  expect(html?.props.lang).toBe("en");
  expect(`${html?.props.className}`.split(" ")).toEqual(
    expect.arrayContaining(["font-sans-variable", "font-mono-variable"]),
  );
  expect(text(tree.find((element) => element.type === "h1"))).toBe(
    "To get started, edit the page.tsx file.",
  );
  expect(tree.some((element) => element.props.alt === "Next.js logo")).toBe(
    true,
  );
});

test("outside links open in a new tab without sharing the opener", () => {
  const links = renderHome().filter(
    (element) => element.type === "a" && element.props.target === "_blank",
  );
  expect(links.map(text)).toEqual(["Deploy Now", "Documentation"]);
  for (const link of links) {
    expect(link.props.rel).toBe("noopener noreferrer");
  }
});

test("CSS goes through the installed Tailwind loader", () => {
  expect(nextConfig.turbopack?.rules?.["*.css"]).toEqual({
    loaders: ["@tailwindcss/turbopack"],
    as: "*.css",
  });
  expect(import.meta.resolve("@tailwindcss/turbopack")).toContain(
    "/node_modules/@tailwindcss/turbopack/",
  );
});
