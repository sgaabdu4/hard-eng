#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { parseNoMistakesPipelineStatus } from './no-mistakes-pipeline-status.mjs';
export { parseNoMistakesPipelineStatus };
const managedStart = '<!-- nm-pr-evidence:start -->';
const managedEnd = '<!-- nm-pr-evidence:end -->';
const localRefPattern = /\/Users\/|\/var\/folders\/|\/tmp\/|no-mistakes-evidence|127\.0\.0\.1|localhost|local file|file:/i;
const imagePathPattern = /(?:\/Users\/|\/var\/folders\/|\/tmp\/|\/private\/var\/folders\/)[^<>"'`)\s]+?\.(?:png|jpe?g|gif|webp)/gi;
const videoPathPattern = /(?:\/Users\/|\/var\/folders\/|\/tmp\/|\/private\/var\/folders\/)[^<>"'`)\s]+?\.(?:mp4|mov|m4v|webm)/gi;

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    encoding: 'utf8',
    cwd: options.cwd || process.cwd(),
    input: options.input,
  });
  return {
    ok: result.status === 0,
    status: result.status,
    stdout: result.stdout || '',
    stderr: [result.stderr || '', result.error?.message || ''].filter(Boolean).join('\n'),
    error: result.error?.code || '',
  };
}

export function parseArgs(argv) {
  const options = {
    pr: null,
    repo: null,
    dryRun: false,
    checkReviewThreads: false,
    e2eVideoRequired: false,
    screenshots: [],
    videos: [],
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--pr') options.pr = argv[++index];
    else if (arg === '--repo') options.repo = argv[++index];
    else if (arg === '--screenshots') options.screenshots.push(argv[++index]);
    else if (arg === '--videos') options.videos.push(argv[++index]);
    else if (arg === '--video') options.videos.push(argv[++index]);
    else if (arg === '--e2e-video-required') options.e2eVideoRequired = true;
    else if (arg === '--dry-run') options.dryRun = true;
    else if (arg === '--check-review-threads') options.checkReviewThreads = true;
    else throw new Error(`Unknown argument: ${arg}`);
  }

  return options;
}

export function extractLocalImagePaths(body) {
  return [...new Set(body.match(imagePathPattern) || [])];
}

export function extractHostedImageMarkdown(body) {
  return [...new Set(body.match(/^!\[[^\]]*\]\(https:\/\/github\.com\/user-attachments\/assets\/[a-z0-9-]+\)$/gim) || [])];
}

export function extractLocalVideoPaths(body) {
  return [...new Set(body.match(videoPathPattern) || [])];
}

export function extractHostedVideoMarkdown(body) {
  const lines = body.split('\n').filter((line) => {
    return /(?:2x|e2e|video|recap)/i.test(line)
      && /https:\/\/github\.com\/user-attachments\/assets\/[a-z0-9-]+/i.test(line);
  });
  const markdown = [];
  for (const line of lines) {
    const linked = line.match(/(?<!!)\[[^\]]+\]\(https:\/\/github\.com\/user-attachments\/assets\/[a-z0-9-]+\)/gi) || [];
    markdown.push(...linked);
    if (linked.length === 0) {
      const urls = line.match(/https:\/\/github\.com\/user-attachments\/assets\/[a-z0-9-]+/gi) || [];
      markdown.push(...urls.map((url) => `[2x E2E video](${url})`));
    }
  }
  return [...new Set(markdown)];
}

function expandScreenshotInputs(inputs) {
  const files = [];
  for (const input of inputs) {
    if (!input) continue;
    if (!fs.existsSync(input)) continue;
    const stat = fs.statSync(input);
    if (stat.isDirectory()) {
      for (const name of fs.readdirSync(input)) {
        const fullPath = path.join(input, name);
        if (/\.(?:png|jpe?g|gif|webp)$/i.test(name) && fs.statSync(fullPath).isFile()) {
          files.push(fullPath);
        }
      }
    } else if (stat.isFile() && /\.(?:png|jpe?g|gif|webp)$/i.test(input)) {
      files.push(input);
    }
  }
  return [...new Set(files)];
}

function expandVideoInputs(inputs) {
  const files = [];
  for (const input of inputs) {
    if (!input || /^https:\/\//i.test(input) || /^\[[^\]]+\]\(https:\/\//i.test(input)) continue;
    if (!fs.existsSync(input)) continue;
    const stat = fs.statSync(input);
    if (stat.isDirectory()) {
      for (const name of fs.readdirSync(input)) {
        const fullPath = path.join(input, name);
        if (/\.(?:mp4|mov|m4v|webm)$/i.test(name) && fs.statSync(fullPath).isFile()) {
          files.push(fullPath);
        }
      }
    } else if (stat.isFile() && /\.(?:mp4|mov|m4v|webm)$/i.test(input)) {
      files.push(input);
    }
  }
  return [...new Set(files)];
}

function hostedVideosFromInputs(inputs) {
  const links = [];
  for (const input of inputs) {
    if (!input) continue;
    const markdown = input.match(/^\[[^\]]+\]\(https:\/\/[^)]+\)$/i);
    if (markdown) links.push(input);
    else if (/^https:\/\//i.test(input)) links.push(`[2x E2E video](${input})`);
  }
  return [...new Set(links)];
}

function removeManagedSection(body) {
  const escapedStart = managedStart.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const escapedEnd = managedEnd.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return body.replace(new RegExp(`${escapedStart}[\\s\\S]*?${escapedEnd}\\n?`, 'g'), '');
}

function removeHeadingSection(body, heading) {
  const pattern = new RegExp(`\\n?## ${heading}\\n[\\s\\S]*?(?=\\n## |$)`, 'i');
  const match = body.match(pattern);
  if (!match) return body;
  if (!/github\.com\/user-attachments|local file|no-mistakes-evidence|\/Users\/|\/var\/folders\//i.test(match[0])) {
    return body;
  }
  return body.replace(pattern, '\n');
}

function removeHeadingSectionAlways(body, heading) {
  const pattern = new RegExp(`\\n?## ${heading}\\n[\\s\\S]*?(?=\\n## |$)`, 'i');
  return body.replace(pattern, '\n');
}

function removeContaminatedDetails(body) {
  return body.replace(/<details\b[\s\S]*?<\/details>\n?/gi, (block) => {
    return localRefPattern.test(block) ? '' : block;
  });
}

export function sanitizeBody(body) {
  let clean = body.replace(/\r\n/g, '\n');
  clean = removeManagedSection(clean);
  clean = removeHeadingSection(clean, 'Screenshots');
  clean = removeHeadingSection(clean, 'E2E videos');
  clean = removeHeadingSection(clean, '2x E2E video');
  clean = removeHeadingSectionAlways(clean, 'No-mistakes Warnings Fixed');
  clean = clean.replace(/^Uploading Screen Recording.*$/gim, '');
  clean = removeContaminatedDetails(clean);
  clean = clean
    .split('\n')
    .filter((line) => !localRefPattern.test(line))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  return `${clean}\n`;
}

export function hasLocalRefs(body) {
  return localRefPattern.test(body);
}

function markdownTable(rows) {
  const escapeCell = (value) => String(value).replace(/\|/g, '\\|').replace(/\n/g, '<br>');
  const lines = ['| Status | Issue | Evidence |', '| --- | --- | --- |'];
  for (const row of rows) {
    lines.push(`| ${escapeCell(row.status)} | ${escapeCell(row.issue)} | ${escapeCell(row.evidence)} |`);
  }
  return lines.join('\n');
}

export function parseNoMistakesFixCommits(logOutput, repoSlug) {
  return logOutput
    .trim()
    .split('\n')
    .filter(Boolean)
    .map((line) => {
      const [sha, subject] = line.split('\t');
      const issue = (subject || '')
        .replace(/^no-mistakes(?:\([^)]+\))?:\s*/i, '')
        .trim();
      const shortSha = (sha || '').slice(0, 7);
      const evidence = repoSlug && sha
        ? `[${shortSha}](https://github.com/${repoSlug}/commit/${sha})`
        : `\`${shortSha}\``;
      return { status: 'Resolved', issue: issue || subject || shortSha, evidence };
    });
}

export function parseNoMistakesStatus(statusOutput) {
  if (!statusOutput.trim()) {
    return [{ status: 'Unknown', issue: 'no-mistakes status unavailable', evidence: 'status command returned no output' }];
  }
  if (/findings:\s*none/i.test(statusOutput)) {
    return [{ status: 'Resolved', issue: 'No open no-mistakes findings', evidence: '`no-mistakes axi status` -> `findings: none`' }];
  }
  const findingLines = statusOutput
    .split('\n')
    .filter((line) => /\b(open|running|failed|finding|warning|error)\b/i.test(line))
    .slice(0, 5);
  return [{
    status: 'Open',
    issue: 'no-mistakes still reports active findings or incomplete checks',
    evidence: findingLines.join('<br>') || 'run `no-mistakes axi status`',
  }];
}

function compactText(value, maxLength = 140) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1)}...`;
}

export function screenshotStatusRows({ screenshots, uploadError }) {
  if (screenshots.length > 0) {
    return [{
      status: 'Resolved',
      issue: 'PR screenshots attached',
      evidence: `${screenshots.length} screenshot(s) in PR evidence`,
    }];
  }

  if (uploadError) {
    return [{
      status: 'Open',
      issue: 'Screenshot upload failed',
      evidence: compactText(uploadError),
    }];
  }

  return [{
    status: 'Open',
    issue: 'No PR screenshots attached',
    evidence: 'No screenshot artifacts or hosted screenshot links found',
  }];
}

export function videoStatusRows({ videos, localVideos, required, uploadError = '' }) {
  if (videos.length > 0) {
    return [{
      status: 'Resolved',
      issue: '2x E2E video attached',
      evidence: `${videos.length} video link(s) in PR evidence`,
    }];
  }

  if (uploadError) {
    return [{
      status: 'Open',
      issue: '2x E2E video upload failed',
      evidence: compactText(uploadError),
    }];
  }

  if (required && localVideos.length > 0) {
    return [{
      status: 'Open',
      issue: '2x E2E video not hosted',
      evidence: `${localVideos.length} local video artifact(s) found; attach a reviewer-openable 2x video link`,
    }];
  }

  if (required) {
    return [{
      status: 'Open',
      issue: 'No 2x E2E video attached',
      evidence: 'UI or phone E2E requires a reviewer-openable 2x video link in PR evidence',
    }];
  }

  return [];
}

export function selectVideoUploadPaths(paths, required) {
  const unique = [...new Set(paths)];
  if (!required) return unique;

  return unique.filter((file) => {
    const name = path.basename(file).toLowerCase();
    return /(^|[-_.\s])2x([-_.\s]|$)|2x-|recap/.test(name);
  });
}

function reviewThreadRowsFromNodes(nodes) {
  if (!Array.isArray(nodes)) {
    return [{
      status: 'Open',
      issue: 'GitHub review thread check could not read reviewThreads',
      evidence: 'gh api graphql returned an unexpected shape',
    }];
  }

  const unresolved = nodes.filter((thread) => !thread.isResolved);
  if (unresolved.length === 0) {
    return [{
      status: 'Resolved',
      issue: 'No open GitHub review threads',
      evidence: `${nodes.length} thread(s) checked`,
    }];
  }

  return unresolved.map((thread) => {
    const comment = thread.comments?.nodes?.[0] || {};
    const author = comment.author?.login || 'reviewer';
    const location = [thread.path, thread.line].filter(Boolean).join(':') || 'review thread';
    const summary = compactText(comment.body || thread.id || 'Unresolved review thread');
    const evidence = comment.url
      ? `[${location}](${comment.url})`
      : location;
    return {
      status: 'Open',
      issue: `${author}: ${summary}`,
      evidence,
    };
  });
}

export function reviewThreadRowsFromGraphql(payload) {
  return reviewThreadRowsFromNodes(payload?.data?.repository?.pullRequest?.reviewThreads?.nodes);
}

export function buildEvidenceSection({ screenshots, videos = [], statusRows, uploadError, e2eVideoRequired = false, currentHeadSha = '' }) {
  const lines = [managedStart, '## No-mistakes Evidence', ''];

  if (currentHeadSha) {
    lines.push(`Current head: \`${currentHeadSha}\``, '');
  }

  lines.push('### Screenshots', '');
  if (screenshots.length > 0) {
    lines.push(...screenshots, '');
  } else if (uploadError) {
    lines.push(`Screenshots were captured, but upload failed: ${uploadError}`, '');
  } else {
    lines.push('No screenshot artifacts were found for this run.', '');
  }

  if (videos.length > 0 || e2eVideoRequired) {
    lines.push('### 2x E2E video', '');
    if (videos.length > 0) {
      lines.push(...videos, '');
    } else {
      lines.push('No reviewer-openable 2x E2E video link was found for this run.', '');
    }
  }

  lines.push('### Issue status', '');
  lines.push(markdownTable(statusRows), '');
  lines.push(managedEnd);
  return lines.join('\n');
}

export function insertEvidenceSection(body, section) {
  return `${body.trim()}\n\n${section}\n`;
}

function currentRepoSlug() {
  const ghRepo = run('gh', ['repo', 'view', '--json', 'nameWithOwner', '--jq', '.nameWithOwner']);
  if (ghRepo.ok && ghRepo.stdout.trim()) return ghRepo.stdout.trim();

  const remote = run('git', ['remote', 'get-url', 'origin']);
  const match = remote.stdout.trim().match(/github\.com[:/](.+?)(?:\.git)?$/);
  return match ? match[1] : '';
}

function repoParts(repoSlug) {
  const [owner, name] = String(repoSlug || '').split('/');
  return owner && name ? { owner, name } : null;
}

function currentPrNumber() {
  const result = run('gh', ['pr', 'view', '--json', 'number', '--jq', '.number']);
  if (!result.ok || !result.stdout.trim()) {
    throw new Error('Could not infer PR number. Pass --pr <number>.');
  }
  return result.stdout.trim();
}

export function currentHeadSha(pr = '', runner = run) {
  const local = runner('git', ['rev-parse', 'HEAD']);
  const localSha = local.ok ? local.stdout.trim() : '';
  if (pr) {
    const prHead = runner('gh', ['pr', 'view', String(pr), '--json', 'headRefOid', '--jq', '.headRefOid']);
    const headSha = prHead.ok ? prHead.stdout.trim() : '';
    if (/^[0-9a-f]{40}$/i.test(headSha)) {
      if (/^[0-9a-f]{40}$/i.test(localSha) && localSha !== headSha) {
        throw new Error(`Local HEAD ${localSha} does not match PR ${pr} head ${headSha}. Push or fetch before repairing current-head evidence.`);
      }
      return headSha;
    }
  }

  return localSha;
}

function branchRange() {
  for (const base of ['origin/main', 'origin/master', 'origin/HEAD']) {
    const mergeBase = run('git', ['merge-base', base, 'HEAD']);
    if (mergeBase.ok && mergeBase.stdout.trim()) {
      return `${mergeBase.stdout.trim()}..HEAD`;
    }
  }
  return '-20';
}

function noMistakesFixRows(repoSlug) {
  const result = run('git', [
    'log',
    '--format=%H%x09%s',
    '--regexp-ignore-case',
    '--grep=^no-mistakes',
    branchRange(),
  ]);
  if (!result.ok || !result.stdout.trim()) return [];
  return parseNoMistakesFixCommits(result.stdout, repoSlug);
}

export function noMistakesStatusRows(body = '', expectedHeadSha = '', runner = run) {
  const result = runner('no-mistakes', ['axi', 'status']);
  const output = result.ok ? (result.stdout || '') : `${result.stdout || ''}\n${result.stderr || ''}`;
  if (!result.ok && (
    result.status === null
    || /repo not initialized|command not found|status unavailable|ENOENT/i.test(output)
  )) {
    const pipelineRows = parseNoMistakesPipelineStatus(body, expectedHeadSha);
    if (pipelineRows.length > 0) return pipelineRows;
  }
  return parseNoMistakesStatus(output);
}

function githubReviewThreadRows(pr, repoSlug) {
  const parts = repoParts(repoSlug);
  if (!parts) {
    return [{
      status: 'Open',
      issue: 'GitHub review thread check could not infer repository',
      evidence: 'pass --repo owner/name',
    }];
  }

  const query = `
    query($owner: String!, $name: String!, $number: Int!, $after: String) {
      repository(owner: $owner, name: $name) {
        pullRequest(number: $number) {
          reviewThreads(first: 100, after: $after) {
            pageInfo {
              hasNextPage
              endCursor
            }
            nodes {
              id
              isResolved
              isOutdated
              path
              line
              comments(first: 1) {
                nodes {
                  url
                  body
                  author {
                    login
                  }
                }
              }
            }
          }
        }
      }
    }
  `;
  const nodes = [];
  let after = '';

  for (let page = 0; page < 20; page += 1) {
    const args = [
      'api',
      'graphql',
      '-f',
      `query=${query}`,
      '-F',
      `owner=${parts.owner}`,
      '-F',
      `name=${parts.name}`,
      '-F',
      `number=${Number.parseInt(pr, 10)}`,
    ];
    if (after) {
      args.push('-F', `after=${after}`);
    }

    const result = run('gh', args);
    if (!result.ok) {
      return [{
        status: 'Open',
        issue: 'GitHub review thread check failed',
        evidence: compactText(result.stderr || result.stdout || 'gh api graphql failed'),
      }];
    }

    let payload;
    try {
      payload = JSON.parse(result.stdout);
    } catch (error) {
      return [{
        status: 'Open',
        issue: 'GitHub review thread check returned invalid JSON',
        evidence: compactText(error.message),
      }];
    }

    const reviewThreads = payload?.data?.repository?.pullRequest?.reviewThreads;
    if (!reviewThreads || !Array.isArray(reviewThreads.nodes)) {
      return reviewThreadRowsFromNodes(null);
    }
    nodes.push(...reviewThreads.nodes);

    if (!reviewThreads.pageInfo?.hasNextPage) {
      return reviewThreadRowsFromNodes(nodes);
    }
    after = reviewThreads.pageInfo.endCursor;
    if (!after) {
      break;
    }
  }

  return [{
    status: 'Open',
    issue: 'GitHub review thread check hit pagination safety limit',
    evidence: `${nodes.length} thread(s) checked before stopping`,
  }];
}

function ensureGhImage() {
  const help = run('gh', ['image', '--help']);
  if (help.ok) return;
  const install = run('gh', ['extension', 'install', 'drogers0/gh-image']);
  if (!install.ok) {
    throw new Error((install.stderr || install.stdout || 'failed to install gh image').trim());
  }
}

function uploadScreenshots(paths, repoSlug) {
  if (paths.length === 0) return [];
  ensureGhImage();
  const args = ['image'];
  if (repoSlug) args.push('--repo', repoSlug);
  args.push(...paths);
  const result = run('gh', args);
  if (!result.ok) {
    throw new Error((result.stderr || result.stdout || 'gh image upload failed').trim());
  }
  return result.stdout
    .trim()
    .split('\n')
    .filter((line) => /^!\[.*\]\(https:\/\/github\.com\/user-attachments\/assets\//.test(line));
}

function uploadVideos(paths, repoSlug) {
  if (paths.length === 0) return [];
  ensureGhImage();
  const args = ['image'];
  if (repoSlug) args.push('--repo', repoSlug);
  args.push(...paths);
  const result = run('gh', args);
  if (!result.ok) {
    throw new Error((result.stderr || result.stdout || 'gh image upload failed').trim());
  }
  return result.stdout
    .trim()
    .split('\n')
    .map((line) => {
      const match = line.match(/^!\[[^\]]*\]\((https:\/\/github\.com\/user-attachments\/assets\/[a-z0-9-]+)\)$/i);
      return match ? `[2x E2E video](${match[1]})` : '';
    })
    .filter(Boolean);
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const pr = options.pr || currentPrNumber();
  const repoSlug = options.repo || currentRepoSlug();
  const view = run('gh', ['pr', 'view', pr, '--json', 'body', '--jq', '.body']);
  if (!view.ok) throw new Error((view.stderr || view.stdout).trim());

  const originalBody = view.stdout;
  const localScreenshots = [
    ...extractLocalImagePaths(originalBody),
    ...expandScreenshotInputs(options.screenshots),
  ].filter((file) => fs.existsSync(file));
  const localVideos = [
    ...extractLocalVideoPaths(originalBody),
    ...expandVideoInputs(options.videos),
  ].filter((file) => fs.existsSync(file));

  const hostedScreenshots = extractHostedImageMarkdown(originalBody);
  const hostedVideos = [
    ...extractHostedVideoMarkdown(originalBody),
    ...hostedVideosFromInputs(options.videos),
  ];
  const videoUploadPaths = selectVideoUploadPaths(localVideos, options.e2eVideoRequired);
  let screenshotMarkdown = [];
  let uploadError = '';
  let videoMarkdown = [...new Set(hostedVideos)];
  let videoUploadError = '';
  if (options.dryRun && localScreenshots.length > 0) {
    screenshotMarkdown = hostedScreenshots.length > 0
      ? hostedScreenshots
      : [`Would upload ${localScreenshots.length} screenshot artifact(s).`];
  } else {
    try {
      screenshotMarkdown = localScreenshots.length > 0
        ? uploadScreenshots([...new Set(localScreenshots)], repoSlug)
        : hostedScreenshots;
    } catch (error) {
      uploadError = error.message;
      screenshotMarkdown = hostedScreenshots;
    }
  }

  if (options.dryRun && videoUploadPaths.length > 0) {
    videoMarkdown = videoMarkdown.length > 0
      ? videoMarkdown
      : [`Would upload ${videoUploadPaths.length} video artifact(s).`];
  } else if (videoUploadPaths.length > 0) {
    try {
      videoMarkdown = [...new Set([
        ...videoMarkdown,
        ...uploadVideos(videoUploadPaths, repoSlug),
      ])];
    } catch (error) {
      videoUploadError = error.message;
    }
  }

  const headSha = currentHeadSha(pr);
  const statusRows = [
    ...screenshotStatusRows({ screenshots: screenshotMarkdown, uploadError }),
    ...videoStatusRows({
      videos: videoMarkdown,
      localVideos,
      required: options.e2eVideoRequired,
      uploadError: videoUploadError,
    }),
    ...noMistakesStatusRows(originalBody, headSha),
    ...(options.checkReviewThreads ? githubReviewThreadRows(pr, repoSlug) : []),
    ...noMistakesFixRows(repoSlug),
  ];
  const section = buildEvidenceSection({
    screenshots: screenshotMarkdown,
    videos: videoMarkdown,
    statusRows,
    uploadError,
    e2eVideoRequired: options.e2eVideoRequired,
    currentHeadSha: headSha,
  });
  const newBody = insertEvidenceSection(sanitizeBody(originalBody), section);

  if (hasLocalRefs(newBody)) {
    throw new Error('Refusing to update PR body because local-only references remain after sanitizing.');
  }

  if (options.dryRun) {
    process.stdout.write(newBody);
    return;
  }

  const edit = run('gh', ['pr', 'edit', pr, '--body', newBody]);
  if (!edit.ok) throw new Error((edit.stderr || edit.stdout).trim());
  process.stdout.write(`Updated PR ${pr} evidence.\n`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
