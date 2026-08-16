import { parseDocument } from "yaml";

export function parseWorkflowYaml(source, fail) {
  const document = parseDocument(source, {
    merge: false,
    schema: "core",
    strict: true,
    uniqueKeys: true,
  });
  if (document.errors.length) fail(`workflow YAML is invalid: ${document.errors[0].message}`);
  return workflowMapping(document.toJS({ maxAliasCount: 0 }), fail);
}

function workflowMapping(value, fail) {
  if (value == null || Array.isArray(value) || typeof value !== "object") {
    fail("workflow must be a mapping");
  }
  return value;
}
