#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const args = process.argv.slice(2);
const runDirIndex = args.indexOf('--run-dir');
const videoModeIndex = args.indexOf('--video');
const videoProfilesIndex = args.indexOf('--video-profiles');
const allowUnresolved = args.includes('--allow-unresolved');

if (runDirIndex === -1 || !args[runDirIndex + 1]) {
  console.error('Usage: check-e2e-run-artifacts.mjs --run-dir <docs/e2e/RUN_ID> [--video expected|optional|off] [--video-profiles desktop,mobile|any] [--allow-unresolved]');
  process.exit(2);
}

const runDir = path.resolve(args[runDirIndex + 1]);
const videoMode = videoModeIndex === -1 ? 'expected' : args[videoModeIndex + 1];
const videoProfilesRaw = videoProfilesIndex === -1 ? 'desktop,mobile' : args[videoProfilesIndex + 1];
const failures = [];
const warnings = [];
const requiredVideoProfiles = videoProfilesRaw === 'any'
  ? []
  : String(videoProfilesRaw || '')
    .split(',')
    .map((profile) => profile.trim().toLowerCase())
    .filter(Boolean);

function fail(message) {
  failures.push(message);
}

function warn(message) {
  warnings.push(message);
}

function readFile(rel) {
  const fullPath = path.join(runDir, rel);
  if (!fs.existsSync(fullPath)) return null;
  return fs.readFileSync(fullPath, 'utf8');
}

function listFiles(rel, suffixes) {
  const dir = path.join(runDir, rel);
  if (!fs.existsSync(dir)) return [];
  const acceptedSuffixes = Array.isArray(suffixes) ? suffixes : [suffixes].filter(Boolean);
  const result = [];
  const stack = [dir];
  while (stack.length) {
    const current = stack.pop();
    for (const name of fs.readdirSync(current)) {
      const fullPath = path.join(current, name);
      const stat = fs.statSync(fullPath);
      if (stat.isDirectory()) {
        stack.push(fullPath);
      } else if (!acceptedSuffixes.length || acceptedSuffixes.some((suffix) => name.endsWith(suffix))) {
        result.push(fullPath);
      }
    }
  }
  return result;
}

function filesForProfile(files, profile) {
  const profilePattern = new RegExp(`(^|[-_./])${profile}($|[-_./])`, 'i');
  return files.filter((file) => profilePattern.test(path.basename(file)));
}

function missingVideoMessage(kind, profile, fallbackMentioned) {
  const suffix = fallbackMentioned ? ' (fallback noted in report)' : '';
  return `${profile} ${kind} is expected but no ${kind} file exists${suffix}`;
}

function isExistingArtifact(candidate) {
  if (typeof candidate !== 'string' || !candidate.trim()) return false;
  if (/^\d+(\.\d+)?s?$/.test(candidate)) return true;
  if (/^\d{2}:\d{2}/.test(candidate)) return true;
  const fullPath = path.isAbsolute(candidate) ? candidate : path.join(runDir, candidate);
  return fs.existsSync(fullPath);
}

function collectEvidence(value, keyPath = '') {
  if (value === null || value === undefined) return [];
  if (typeof value === 'string') {
    return /artifact|path|screenshot|video|trace|log|frame|timestamp|ts/i.test(keyPath) ? [value] : [];
  }
  if (typeof value === 'number') {
    return /video|frame|timestamp|ts/i.test(keyPath) ? [`${value}`] : [];
  }
  if (Array.isArray(value)) {
    return value.flatMap((item, index) => collectEvidence(item, `${keyPath}.${index}`));
  }
  if (typeof value === 'object') {
    return Object.entries(value).flatMap(([key, child]) => collectEvidence(child, `${keyPath}.${key}`));
  }
  return [];
}

function actionName(row) {
  const action = row.action;
  if (typeof action === 'string') return action.toLowerCase();
  if (action && typeof action.kind === 'string') return action.kind.toLowerCase();
  if (typeof row.event === 'string') return row.event.toLowerCase();
  return '';
}

function eventKey(row) {
  return [row.flow, row.step].filter(Boolean).join('::');
}

function hasTarget(row) {
  if (row.target) return true;
  return Number.isFinite(row.x) && Number.isFinite(row.y);
}

function reportHas(text, pattern) {
  return pattern.test(text);
}

if (!fs.existsSync(runDir)) {
  fail(`run dir missing: ${runDir}`);
} else {
  const rawEvents = readFile('events.jsonl');
  const report = readFile('report.md');
  const issues = readFile('issues.md') || '';

  if (!rawEvents) {
    fail('events.jsonl is missing');
  }

  if (!report) {
    fail('report.md is missing');
  }

  const events = [];
  if (rawEvents) {
    rawEvents.split('\n').filter((line) => line.trim()).forEach((line, index) => {
      try {
        events.push(JSON.parse(line));
      } catch (error) {
        fail(`events.jsonl line ${index + 1} is not valid JSON: ${error.message}`);
      }
    });
  }

  if (events.length === 0) {
    fail('events.jsonl has no events');
  }

  const uiEvents = events.filter((row) => /click|tap|type|input|select|submit|navigate|navigation|hover|scroll|drag/.test(actionName(row)));
  const assertionSteps = new Set(events
    .filter((row) => actionName(row).includes('assert') || row.assertion)
    .map(eventKey));

  if (uiEvents.length === 0) {
    fail('no UI action events were recorded');
  }

  events.forEach((row, index) => {
    const label = row.eventId || `line ${index + 1}`;
    for (const key of ['runId', 'flow', 'step', 'eventId', 'ts', 'driver', 'status']) {
      if (!row[key]) fail(`${label} missing ${key}`);
    }
  });

  uiEvents.forEach((row) => {
    const label = row.eventId || `${row.flow}/${row.step}`;
    const evidence = collectEvidence(row).filter(isExistingArtifact);
    if (!hasTarget(row)) fail(`${label} missing target or x/y coordinates`);
    if (!row.assertion && !assertionSteps.has(eventKey(row))) fail(`${label} missing settled assertion for its step`);
    if (evidence.length === 0) fail(`${label} missing existing screenshot/video/log/trace evidence`);
  });

  events
    .filter((row) => /fail|error/i.test(String(row.status)))
    .forEach((row) => {
      const evidence = collectEvidence(row).filter((item) => /screenshot|\.png$/i.test(item)).filter(isExistingArtifact);
      if (evidence.length === 0) fail(`${row.eventId || eventKey(row)} failed without screenshot evidence`);
    });

  if (report) {
    if (!reportHas(report, /driver|fallback/i)) fail('report.md omits driver or fallback summary');
    if (!reportHas(report, /issue|unresolved/i)) fail('report.md omits issue summary');
    if (!reportHas(report, /regression/i)) fail('report.md omits regression commands/results');
    if (!reportHas(report, /2x|recap|cursor/i)) fail('report.md omits 2x cursor recap path or fallback reason');
  }

  if (!allowUnresolved && /-\s*\[\s*\]\s*resolved/i.test(issues)) {
    fail('issues.md contains unresolved issue checkboxes');
  }

  const videos = listFiles('videos', ['.mp4', '.webm', '.mov']);
  const recaps = listFiles('recaps', ['.mp4', '.webm', '.mov']);
  const reportMentionsVideoFallback = report ? /video.*(unavailable|unsupported|blocked|fallback|not supported)|no video/i.test(report) : false;
  const reportMentionsRecapFallback = report ? /recap.*(unavailable|unsupported|blocked|fallback|not supported)|no 2x|no recap/i.test(report) : false;

  if (!['expected', 'optional', 'off'].includes(videoMode)) {
    fail(`invalid --video value: ${videoMode}`);
  }
  if (videoProfilesIndex !== -1 && !args[videoProfilesIndex + 1]) {
    fail('--video-profiles requires a value');
  }
  if (videoProfilesRaw !== 'any' && requiredVideoProfiles.length === 0) {
    fail('no video profiles requested');
  }

  if (videoMode === 'expected') {
    if (requiredVideoProfiles.length) {
      for (const profile of requiredVideoProfiles) {
        if (!filesForProfile(videos, profile).length) fail(missingVideoMessage('video', profile, reportMentionsVideoFallback));
        if (!filesForProfile(recaps, profile).length) fail(missingVideoMessage('2x recap', profile, reportMentionsRecapFallback));
      }
    } else {
      if (!videos.length) fail(`video is expected but no video file exists${reportMentionsVideoFallback ? ' (fallback noted in report)' : ''}`);
      if (!recaps.length) fail(`2x recap is expected but no recap file exists${reportMentionsRecapFallback ? ' (fallback noted in report)' : ''}`);
    }
  } else if (videoMode === 'optional') {
    const profiles = requiredVideoProfiles.length ? requiredVideoProfiles : ['any'];
    for (const profile of profiles) {
      const profileVideos = profile === 'any' ? videos : filesForProfile(videos, profile);
      const profileRecaps = profile === 'any' ? recaps : filesForProfile(recaps, profile);
      if (!profileVideos.length && !reportMentionsVideoFallback) warn(`${profile} video missing without fallback reason`);
      if (!profileRecaps.length && !reportMentionsRecapFallback) warn(`${profile} 2x recap missing without fallback reason`);
    }
  }
}

const result = {
  status: failures.length ? 'fail' : 'pass',
  runDir,
  failures,
  warnings,
  requiredVideoProfiles,
};

console.log(JSON.stringify(result, null, 2));
process.exit(failures.length ? 1 : 0);
