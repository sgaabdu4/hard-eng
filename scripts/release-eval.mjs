#!/usr/bin/env node
import { parseReleaseEvalArgs, runReleaseEval } from '../runtime/lib/release-eval.mjs';

function human(report) {
  return [
    report.status,
    `purpose\t${report.purpose}`,
    ...report.models.map((entry) => `model\t${entry.role}\t${entry.model}`),
    `cases\t${report.cases.join(',')}`,
    `calls\t${report.predicted_calls}/${report.max_calls}`,
    `concurrency\t${report.concurrency}`,
    `automatic-retries\t${report.automatic_retries}`,
    ...(report.status === 'APPROVAL_REQUIRED' ? [
      'approval\trerun with --confirm-model-evals and the same --max-calls cap',
    ] : report.results.map((entry) => `${entry.status}\t${entry.role}\t${entry.case_id}\t${entry.output_digest}`)),
  ].join('\n');
}

try {
  const options = parseReleaseEvalArgs(process.argv.slice(2));
  const report = runReleaseEval(options);
  process.stdout.write(`${options.json ? JSON.stringify(report) : human(report)}\n`);
  if (report.status === 'FAIL') process.exitCode = 1;
} catch (error) {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
}
