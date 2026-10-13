import { expect, test } from "bun:test";
import { gzipSync } from "node:zlib";
import { build } from "vite";
import config from "../vite.config.ts";

const budgetBytes = 100 * 1024;

async function productionBuild() {
	const previous = process.env.NODE_ENV;
	process.env.NODE_ENV = "production";
	try {
		return await build({
			...config,
			root: `${import.meta.dir}/..`,
			configFile: false,
			logLevel: "silent",
			build: { write: false },
		});
	} finally {
		process.env.NODE_ENV = previous;
	}
}

test("the production JavaScript stays under 100 KiB gzipped", async () => {
	const result = await productionBuild();
	let bytes = 0;
	for (const output of Array.isArray(result) ? result : [result]) {
		if (!("output" in output)) {
			throw new Error("Vite started a watcher instead of a build");
		}
		for (const chunk of output.output) {
			if (chunk.type === "chunk") {
				bytes += gzipSync(chunk.code).byteLength;
			}
		}
	}
	console.log(`Production JavaScript: ${bytes} bytes gzipped`);
	expect(bytes).toBeGreaterThan(0);
	expect(bytes).toBeLessThanOrEqual(budgetBytes);
});
