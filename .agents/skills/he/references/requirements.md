# Requirements

Each Hard Eng rule is defined once here, under a stable ID. Code, tests, skills and docs name the ID instead of restating the rule. `python3 .hooks/hard-eng.py check` fails on a repeated, unknown or retired ID, a `Proof: check` rule without an enforcing source and a test that name it, a `Proof: guidance` rule without a skill or `AGENTS.md` link, and a definition sentence copied into other Markdown.

A project may add its own rules as `REQ-` IDs in `docs/requirements.md`, in the same format. An ID is a prefix and parts joined by hyphens; each part holds only capital letters and digits. An `HE-` ID has one or more parts, and a `REQ-` ID has two or more. A test names an ID in its name string (JavaScript, Dart) or the first line of its docstring (Python). Never reuse an ID; a retired entry keeps its heading and holds only `Status: Retired — use <ID>`.

## HE-REQUIREMENT-REGISTRY

Every rule has one definition in a requirement registry, under an ID that is never reused. Other files name the ID instead of repeating the rule.

Proof: check

## HE-COVERAGE-MIN

A language package's tests cover at least 70% of its executable lines. The tests gate fails when its coverage report shows less.

Proof: check

## HE-FILE-LENGTH

A handwritten source or test file holds at most 1000 physical lines. A larger file needs an exact, reviewed file-size exception with a reason and evidence.

Proof: check

## HE-PERFORMANCE-SUITE

Each language package runs a performance suite with a real workload, a time budget and a native report. A package without a meaningful workload records a nonblank, reviewed `performance_exception` instead.

Proof: check

## HE-DEBT-SHRINK-ONLY

Findings that existing code fails with when Hard Eng is installed may be recorded once, by `python3 .hooks/hard-eng.py adopt`, in `hard-eng.debt.json`. A gate with recorded lines fails on any output line beyond them, and when a recorded line is gone but still listed. Only the change that installs Hard Eng can add the file; later changes only remove lines. Tests, lockfiles and secrets never carry debt.

Proof: check

## HE-COMMENT-LINES

A changed source file holds no comment block longer than one line. Generated output and scaffold paths are exempt, and so are blocks a file already held before the change that installs Hard Eng.

Proof: check

## HE-NO-SWITCH-OFF

A change fails when its added lines hold any of these: a Python, JavaScript, TypeScript, Dart or Swift suppression; a skipped or focused test; in any file, an inline ignore marker of Semgrep, Gitleaks, jscpd, Fallow, ShellCheck, zizmor or Dart coverage (`coverage:ignore`); a line that is not a comment in `.gitleaksignore`, `.gitleaks.toml` or `.semgrepignore`. A test argument that skips or focuses (Dart `skip:` or `solo:` with any value but `false`; JavaScript or TypeScript `skip:` set to `true` or a text reason, or `only: true`) is flagged only in a test file. It also fails when it removes more `assert` or `expect(` lines from test files than it adds. Paths under `.hooks/`, `.agents/` and `.claude/` are exempt, lines that existed before the change are not flagged, and there is no allow-list.

Proof: check

## HE-UNTRUSTED-JSON

In JavaScript and TypeScript, parsed JSON has the type `unknown` until code validates it. TypeScript configurations must load the Hard Eng declarations that set this type.

Proof: check

## HE-ADR-SCOPE

A changed, unsuperseded decision record names the paths it governs on an `Applies to:` line. A change that removes the last file under such a path must update or supersede the record.

Proof: check

## HE-OUTPUT-PLAIN

Agent replies and reports use plain, simplified technical English: one idea per sentence, active voice and common words. Reports state changes, proof and gaps.

Proof: guidance

## HE-NO-FOREGROUND-POLL

An agent starts a long job in the background and reads the host's exit notice when the notice comes. While the job runs, the agent does other work that is ready, and it never ends its turn only to wait when other work is ready. No hook checks those two sentences. The agent never waits in a foreground sleep loop or a long foreground sleep, and in Claude Code a hook enforces that part. The hook denies a foreground shell command of the main session that holds a `while` or `until` loop and a sleep of at least 1 second, or sleeps that add up to at least 30 seconds. The hook ignores comments. It also ignores text in quotes and heredoc bodies, with three exceptions: the text counts when `sh`, `bash`, `zsh`, `python`, `perl`, `ruby`, `node` or `ssh` runs it, when `eval` runs quoted text, or when double-quoted text holds a command substitution. A subagent may wait in the foreground, because nothing watches its background job after its turn ends. Codex has no such hook: it returns a long command early and waits on that command's session, not on a sleep loop.

Proof: check

## HE-REAL-APP-PREVIEW

A proposed change to a screen that exists is shown as before and after captures of the real app, rendered in an isolated checkout, never as a hand-made mock. In Claude Code, a hook adds this note to every Artifact publish or quickstart call; the call always proceeds, because an artifact can be the right way to show other things. Codex has no Artifact tool.

Proof: check

## HE-HOT-PATH

Code must not build a constant regex inside a function, allocate an array of booleans, read whole rows or entities (`SELECT *`, an ORM query without a column list), add an in-process cache, await inside a loop, await independent calls in sequence, parse the same URL on each loop pass or use a JSON column. Every Semgrep `security` gate runs these rules on the whole repository, so old code fails too; only the change that installs Hard Eng can record them as debt. Each rule skips the shapes that need the slow form, such as calls on one database session, async streams, worker loops and loops that stop early; generated and vendored files are not scanned. When Semgrep can parse only part of a file, the gate scans the parsed part and prints the lines it skipped; every other scan error fails. `python3 .hooks/hard-eng.py hot-paths` lists the findings.

Proof: check

## HE-YAGNI

Add a file, dependency, abstraction, configuration or stored state only for a current agreed requirement that existing code or a direct command cannot meet.

Proof: guidance
