#!/usr/bin/env node
import assert from 'node:assert/strict';
import {
  hasGreenProof,
  hasImplementationProofCommand,
  hasRedProof,
  hasTestFirstProofCommand,
  hasTestQualityEvidence,
  matchesTestFirstProofGuardrail,
} from '../scripts/he-state-proof.mjs';

for (const command of [
  'npm test || true',
  'npm test; true',
  'npm test | cat',
  'npm test && true || true',
  'npm test &',
  'npm test & true',
  'npm(){ true; }; npm test',
  'function npm { true; }; npm test',
  'npm()\n{ true; }\nnpm test',
  'function npm\n{ true; }\nnpm test',
  'jest(){ true; }; jest',
  'function stryker { true; }; stryker run',
  'echo ok || npm test',
  'PATH=./fake-bin npm test',
  'env PATH=./fake-bin npm test',
  '"NODE_ENV=test" npm test',
  'export PATH=./fake-bin:$PATH; npm test',
  'export FOO=ok PATH=./fake-bin:$PATH; npm test',
  'set -e; false; npm test',
  'set -o errexit; false; npm test',
  'set -o pipefail; false | true && npm test',
  'npm --if-present test',
  'npm run test --if-present',
  'npm test -- --help',
  'jest "--passWithNoTests"',
  'jest --passWithNoTests',
  'cargo test "--no-run"',
  "jest $'--passWithNoTests'",
  'jest $"--passWithNoTests"',
  "cargo test $'--no-run'",
  'pytest --collect-only',
  'mocha --dry-run',
  'node --test --help',
  'go test -list .',
  '{ false; } && npm test',
  '{ exit 0; }; npm test',
  'alias npm=true; npm test',
  'alias jest="jest --passWithNoTests"; jest',
  'hash -p /bin/true npm; npm test',
  'hash npm=/bin/true; npm test',
  'eval "npm(){ true; }"; npm test',
  'source ./fake-runners.sh; npm test',
  '. ./fake-runners.sh; npm test',
  'builtin export PATH=./fake-bin:$PATH; npm test',
  'command export PATH=./fake-bin:$PATH; npm test',
  'builtin cd /tmp; npm test',
  'command cd /tmp; npm test',
  'builtin source ./fake-runners.sh; npm test',
  'command source ./fake-runners.sh; npm test',
  'export "PATH=./fake-bin:$PATH"; npm test',
  "export $'PATH=./fake-bin:$PATH'; npm test",
  'export $"PATH=./fake-bin:$PATH"; npm test',
  'npm --prefix /tmp/fake test',
  'npm --prefix=/tmp/fake test',
  'npm --prefix ../other test',
  'pnpm --dir ../other test',
  'pnpm --dir=../other test',
  'yarn --cwd /tmp/fake test',
  'cd /tmp/fake; npm test',
  'pushd web; npm test',
  'popd; npm test',
  'grep __missing__ /dev/null && npm test',
  '(false) && npm test',
  '(exit 0); npm test',
  "cat <<'#EOF'\nnpm test\n#EOF",
  'cat <<-EOF\nnpm test\nEOF',
  'echo <(true && npm test )',
  'echo >(true && npm test )',
  'echo =(true && npm test )',
  'typeset PATH=./fake-bin:$PATH; npm test',
  'declare -x PATH=./fake-bin:$PATH; npm test',
  'local PATH=./fake-bin:$PATH; npm test',
  'readonly PATH=./fake-bin:$PATH; npm test',
  "trap 'exit 0' ERR; npm test",
  "trap 'exit 0' EXIT; npm test",
  'cargo test --no-run',
  'mvn test --no-test',
  'gradle test --no-execute',
  'gradle test -x test',
  './gradlew test --exclude-task test',
  './gradlew test --exclude-task=test',
]) {
  assert.equal(hasImplementationProofCommand(command), false, command);
  assert.equal(hasTestFirstProofCommand(command), false, command);
}

for (const command of [
  'npm test',
  'echo setup && npm test -- owner',
  'printf setup; vitest run owner',
  'false || pytest tests',
  'NODE_ENV=test npm test',
  'env NODE_ENV=test npm test',
  'npm --prefix web test',
  'npm --prefix=packages/web test',
  'pnpm --dir packages/web test',
  'yarn --cwd ./web test',
  'npm test -- owner && npm run lint',
  'pnpm test:unit',
  'yarn test:unit',
  'gradle test',
  './gradlew test',
  'set -e; true; npm test -- owner',
  'set -e; false || pytest tests',
]) {
  assert.equal(hasImplementationProofCommand(command), true, command);
  assert.equal(hasTestFirstProofCommand(command), true, command);
}

for (const evidence of [
  'test-quality not used; 1 failed test',
  'without test-quality; 1 failed test',
  'skipped test-quality; 1 failed test',
  'no test-quality; 1 failed test',
  'test-quality evidence missing; 1 failed test',
  'test-quality skill was skipped; 1 failed test',
  'test-quality scenario was not used; 1 failed test',
  'test-quality review missing; 1 failed test',
  'test-quality review is missing; 1 failed test',
  'test-quality scenarios are missing; 1 failed test',
  'test-quality review is disabled; 1 failed test',
  'test-quality scenarios are unavailable; 1 failed test',
  'test-quality skill was not loaded; 1 failed test',
  'test-quality skill; 1 failed test',
  'not recorded test-quality evidence; 1 failed test',
  'never used test-quality review; 1 failed test',
  'failed to use test-quality evidence; 1 failed test',
]) {
  const guardrail = {
    id: 'test-first-proof',
    stage: 'he-implement',
    kind: 'test',
    command: 'npm test -- owner',
    evidence: [evidence],
  };
  assert.equal(hasTestQualityEvidence(guardrail), false, evidence);
  assert.equal(matchesTestFirstProofGuardrail(guardrail), false, evidence);
}

for (const evidence of ['test-quality scenarios recorded; 1 failed test', 'test-quality review was used; 1 failed test', 'used test-quality review; 1 failed test']) {
  const guardrail = {
    id: 'test-first-proof',
    stage: 'he-implement',
    kind: 'test',
    command: 'npm test -- owner',
    evidence: [evidence],
  };
  assert.equal(hasTestQualityEvidence(guardrail), true, evidence);
  assert.equal(matchesTestFirstProofGuardrail(guardrail), true, evidence);
}

for (const evidence of ['1 failed, 5 passed; expected green button', '2 failed, 10 passed; expected clean label', 'red-first failed as expected for green button', 'red-first failed as expected for clean label', 'expected 1 failed test, got 1 failed, 5 passed', 'expected 1 failed test; recorded red output: 1 failed test', 'test-quality scenarios recorded; actual red output recorded: 1 failed test', 'mutation proof killed: 1 expected mutant before implementation', 'mutation proof failed as expected before implementation']) {
  assert.equal(hasRedProof(evidence), true, evidence);
}

for (const evidence of [
  'all tests passed green',
  'clean test run',
  '0 failed, 5 passed; expected green button',
  'test-quality scenarios recorded; expected 1 failed test but it did not fail',
  'test-quality scenarios recorded; expected 1 failed test but it did not run',
  'test-quality scenarios recorded; mutation score 0%; 0 killed, 1 survived',
  'test-quality scenarios recorded; mutation run: none killed',
  'test-quality scenarios recorded; mutation run failed as expected; 0 killed, 1 survived',
  'test-quality scenarios recorded; expected 1 failed test, got 5 passed',
  'test-quality scenarios recorded; expected 2 failing tests, actual 7 tests passed',
  'test-quality scenarios recorded; expected failures: 1 but passed',
  'test-quality scenarios recorded; expected 1 failed test',
  'test-quality scenarios recorded; expected 1 failed test recorded',
  'test-quality scenarios recorded; recorded failure expectation: expected 1 failed test',
  'test-quality scenarios recorded: expected 1 failed test',
  'test-quality scenarios recorded; should report 1 failed test',
  'test-quality scenarios recorded; would show 1 failing test',
]) {
  assert.equal(hasRedProof(evidence), false, evidence);
}

for (const evidence of ['expected tests passed', 'should be green', 'would be clean']) {
  assert.equal(hasGreenProof(evidence), false, evidence);
}

for (const evidence of ['actual tests passed', 'green test run recorded', '5 passed, 1 skipped']) {
  assert.equal(hasGreenProof(evidence), true, evidence);
}

for (const evidence of [
  'test-quality scenarios recorded; mutation score 0%; 0 killed, 1 survived',
  'test-quality scenarios recorded; mutation run: none killed',
  'test-quality scenarios recorded; mutation run failed as expected; 0 killed, 1 survived',
]) {
  assert.equal(matchesTestFirstProofGuardrail({
    id: 'test-first-proof',
    stage: 'he-implement',
    kind: 'test',
    command: 'stryker run owner-mutants',
    evidence: [evidence],
  }), false, evidence);
}

console.log('he-state-proof-test: pass');
