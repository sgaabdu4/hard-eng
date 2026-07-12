export function transitionError(run, event) {
  throw new Error(`Unsupported transition ${event.type} from ${run.phase}:${run.cursor.step}.`);
}

export function assertDigest(value, label) {
  if (!/^[a-f0-9]{64}$/i.test(value ?? '')) throw new Error(`${label} must be a SHA-256 digest.`);
}

export function requireSupportPlane(run, boundary) {
  for (const tool of ['codebase-memory', 'context-mode']) {
    const receipt = [...run.support_tools].reverse().find((item) => item.tool === tool);
    if (!receipt) throw new Error(`${boundary} requires a bounded ${tool} support receipt.`);
    if (
      tool === 'codebase-memory'
      && !['get_architecture', 'search_graph', 'trace_path', 'detect_changes'].includes(receipt.operation)
    ) throw new Error(`${boundary} requires an actual Codebase Memory structural graph or impact operation.`);
  }
}
