import { expect, mock, test } from "bun:test";

const cloudflare = await import("@opennextjs/cloudflare");
const initOpenNextCloudflareForDev = mock(async () => {});
mock.module("@opennextjs/cloudflare", () => ({
	...cloudflare,
	initOpenNextCloudflareForDev,
}));
const fonts = {
	Geist: () => ({ variable: "font-sans-variable" }),
	Geist_Mono: () => ({ variable: "font-mono-variable" }),
};
mock.module("next/font/google", () => fonts);

const { default: RootLayout, metadata } = await import("./layout");
const { default: Home } = await import("./page");
const { default: openNextConfig } = await import("../../open-next.config");
const { default: postcssConfig } = await import("../../postcss.config.mjs");
await import("../../next.config");

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
	return elements(RootLayout({ children: Home() }));
}

test("home page renders inside the root layout with both fonts", () => {
	const tree = renderHome();
	expect(tree[0]?.type).toBe("html");
	expect(tree[0]?.props.lang).toBe("en");
	const body = tree.find((element) => element.type === "body");
	expect(`${body?.props.className}`.split(" ")).toEqual(
		expect.arrayContaining(["font-sans-variable", "font-mono-variable"]),
	);
	expect(metadata.title).toBe("Create Next App");
	expect(tree.some((element) => element.props.alt === "Next.js logo")).toBe(
		true,
	);
	expect(text(tree.find((element) => element.type === "ol"))).toContain(
		"Save and see your changes instantly.",
	);
});

test("outside links open in a new tab without sharing the opener", () => {
	const links = renderHome().filter(
		(element) => element.type === "a" && element.props.target === "_blank",
	);
	expect(links.map(text)).toEqual([
		"Read our docs",
		"Learn",
		"Go to nextjs.org →",
	]);
	for (const link of links) {
		expect(link.props.rel).toBe("noopener noreferrer");
	}
});

test("next dev gets the Cloudflare bindings", () => {
	expect(initOpenNextCloudflareForDev).toHaveBeenCalledTimes(1);
});

test("the Worker uses the Cloudflare wrapper and needs no cache storage", () => {
	expect(openNextConfig.default.override?.wrapper).toBe("cloudflare-node");
	expect(openNextConfig.default.override?.incrementalCache).toBe("dummy");
});

test("CSS goes through the installed Tailwind PostCSS plugin", () => {
	expect(postcssConfig.plugins).toEqual(["@tailwindcss/postcss"]);
	expect(import.meta.resolve("@tailwindcss/postcss")).toContain(
		"/node_modules/@tailwindcss/postcss/",
	);
});
