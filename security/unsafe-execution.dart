import 'dart:io';

Future<ProcessResult> unsafe(String input) {
  // ruleid: hard-eng.dart.shell-execution
  return Process.run('sh', ['-c', input]);
}

Future<ProcessResult> safe(String input) {
  // ok: hard-eng.dart.shell-execution
  return Process.run('printf', ['%s', input]);
}
