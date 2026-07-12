const quotedAbsolutePath = /(["'`])(?:file:\/\/\/|\/|[A-Za-z]:[\\/]|\\\\)[^"'`\r\n]*\1/g;
const fileUrl = /\bfile:\/\/\/[^\s"'`<>]+/gi;
const posixPath = /(^|[\s([{=:;,])\/(?:[^\s"'`<>|()[\]{};,]+\/?)+/g;
const windowsPath = /(^|[\s([{=:;,])(?:[A-Za-z]:[\\/]|\\\\)[^\s"'`<>|]+/g;
const homePath = /(^|[\s([{=:;,])~\/[^\s"'`<>|]+/g;
const secretLike = [
  /-----BEGIN [A-Z ]*PRIVATE KEY-----/gi,
  /\b(?:sk|rk|pk)-[A-Za-z0-9_-]{20,}\b/g,
  /\bgh[pousr]_[A-Za-z0-9]{20,}\b/g,
  /\bxox[baprs]-[A-Za-z0-9-]{20,}\b/g,
  /\bAKIA[A-Z0-9]{16}\b/g,
  /\bBearer\s+[A-Za-z0-9._-]{20,}\b/gi,
  /\b(?:password|passwd|secret|token|api[_-]?key|authorization)\s*[:=]\s*(?:"[^"]*"|'[^']*'|[^\s,;]+)/gi,
];

function replacePrefixed(pattern, value) {
  return value.replace(pattern, (_, prefix) => `${prefix}<path>`);
}

export function redactErrorMessage(error) {
  let value = String(error?.message ?? error ?? 'Unknown error.');
  value = value.replace(/[\u0000-\u001f\u007f]+/g, ' ');
  value = value.replace(/\b(https?:\/\/)[^/\s:@]+:[^@\s/]+@/gi, '$1<redacted>@');
  for (const pattern of secretLike) value = value.replace(pattern, '<redacted>');
  value = value.replace(quotedAbsolutePath, '<path>');
  value = value.replace(fileUrl, '<path>');
  value = replacePrefixed(windowsPath, value);
  value = replacePrefixed(homePath, value);
  value = replacePrefixed(posixPath, value);
  value = value.replace(/\s+/g, ' ').trim() || 'Unknown error.';
  return value.length <= 512 ? value : `${value.slice(0, 509)}...`;
}
