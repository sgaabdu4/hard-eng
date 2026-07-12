import { ensureStore, withLock } from '../../runtime/lib/store.mjs';

const [repo, lockId, holdMsText = '0'] = process.argv.slice(2);
try {
  const store = ensureStore(repo);
  withLock(store, lockId, { owner: `worker-${process.pid}`, action: 'concurrency-test', time: new Date().toISOString() }, () => {
    process.stdout.write('locked\n');
    const wait = new Int32Array(new SharedArrayBuffer(4));
    Atomics.wait(wait, 0, 0, Number.parseInt(holdMsText, 10));
  });
} catch (error) {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 2;
}
