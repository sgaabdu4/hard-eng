export function unsafe(expression: string) {
  // ruleid: hard-eng.javascript.dynamic-eval
  return eval(expression);
}

export function safeJson(input: string): unknown {
  // ok: hard-eng.javascript.dynamic-eval
  return JSON.parse(input);
}
