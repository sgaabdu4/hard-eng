import { afterAll, beforeAll, expect, test } from "bun:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { act } from "react";

beforeAll(() => {
	GlobalRegistrator.register();
	Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
	document.body.innerHTML = '<div id="root"></div>';
});

afterAll(async () => {
	await GlobalRegistrator.unregister();
});

test("the starter screen boots into #root and its counter counts clicks", async () => {
	await act(async () => {
		await import("../src/main.tsx");
	});
	expect(document.querySelector("h1")?.textContent).toBe("Get started");
	const counter = document.querySelector("button.counter");
	expect(counter?.textContent).toBe("Count is 0");
	await act(async () => {
		counter?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
	});
	await act(async () => {
		counter?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
	});
	expect(counter?.textContent).toBe("Count is 2");
});
