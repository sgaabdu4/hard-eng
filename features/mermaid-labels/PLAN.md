# PR diagrams: short label lines that GitHub does not cut

Status: Complete

## Outcome + scope

A PR body passes `ready` and CI's `pr text` only when every node and edge label line in its flowcharts has at most 13 characters. The rule has one owner, the `Before and after` line in `.agents/skills/he-ship/references/checks.md`; `.hooks/pr_text.py` checks it. Non-goals: skill flowcharts and the README diagrams, which are not PR bodies; other diagram types; the `LR` node count.

## Sources + coverage

Sources: N/A — the request is the only source: the user report of 2026-11-21 that node labels in PR diagrams are cut off, with the cause measured by the coordinator.

## Repository context

Owners: `.hooks/pr_text.py` (`body_problem`) owns the PR body rules; `checks.md` owns the label style text.
Same cause: N/A — no earlier label rule; searched `Mermaid`, `quoted labels` and `Before and after` in the repository.
Single source: the limit lives in `MAX_LABEL_CHARACTERS` and in the one `checks.md` line. Every other mention points to that line.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the coordinator named the rule, the owner line and the check.

## Acceptance + steps

- [x] A label line over 13 characters is refused by name in every label form: square, quoted, round, stadium, diamond, hexagon, cylinder, circle, subroutine, `-->|text|`, `-- text -->`, a label on an edge to a node → `tests/test_pr_text.py::test_a_mermaid_label_line_over_13_characters_is_refused_by_name`
- [x] Labels of 13 or fewer characters pass in each form → `tests/test_pr_text.py::test_mermaid_labels_of_13_characters_or_fewer_pass_in_every_form`
- [x] A label of 14 characters is refused → `tests/test_pr_text.py::test_a_label_of_14_characters_is_refused`
- [x] Each line of a label split by `<br>`, `<br/>`, `<br />` or `<BR>` counts alone → `tests/test_pr_text.py::test_each_line_of_a_label_split_by_a_break_counts_alone`
- [x] An entity code such as `#quot;` counts as one character → `tests/test_pr_text.py::test_an_entity_code_counts_as_one_character`
- [x] A later block and a `graph` block are checked → `tests/test_pr_text.py::test_a_long_label_in_a_later_block_is_refused`, `tests/test_pr_text.py::test_a_graph_block_is_counted_like_a_flowchart`
- [x] `subgraph`, `style`, `classDef`, `%%` comments, `linkStyle`, `direction` and front matter are not counted → `tests/test_pr_text.py::test_lines_that_are_not_labels_are_not_counted`, `tests/test_pr_text.py::test_front_matter_is_not_counted`
- [x] The `checks.md` line states the limit, the reason and the `TD` or `LR` choice → N/A — prose; the check above enforces the limit
- [x] No PR body template or example in the repository holds a refused label: every refused block is a skill flowchart or a README diagram, which stay as they are → N/A — a scan of the repository, no behavior changes

## Baseline + execution

Result: Passed
Evidence: Measured in GitHub's viewer by the coordinator, 2026-11-21 (viewscreen.githubusercontent.com, script `mermaidMarkdown-295c87097d1a6081bcc4.js`). GitHub's flowchart config has `wrappingWidth` 120 and `minNodeWidth` 120. Each label is a div with `white-space: nowrap` and `max-width: 120px`. Mermaid wraps the label only when its measured width equals 120 exactly. At browser zoom 0.9, 1.1, 1.25 and 1.333 the measured width is a fraction off, so the label never wraps and the box edge cuts it. Plain labels of 19 and 36 characters were cut at those zooms and whole at 1.0. Front matter `wrappingWidth: 400` was still cut at 0.9. `%%{init}%%` and front matter `htmlLabels: false` did not change node labels. Labels split with `<br>` into lines under 100px stayed whole at 0.9, 1.0, 1.1, 1.25 and 1.333. Font: 16px "trebuchet ms". Widths: 13 characters 99.9px; 14 characters 107.3px and 14 characters 116.4px; 19 characters 160px. Edge labels use the same code path. Six `LR` nodes drew 1112px wide in an 880px space, so the diagram shrank. On this branch before the change, the new refused-label tests fail: 22 failed, 21 passed.
Execution: One new check in `.hooks/pr_text.py`, one line in `checks.md`, the test rows.

## Risks + recovery

A PR body with a long label is now refused until its labels are split. The check reads flowchart and graph blocks only. Recovery: revert the commit.
Not checked: Safari and Firefox; renderers other than GitHub.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Passed
Evidence: Focused tests: `tests/test_pr_text.py` 151 passed. Full suite on the first head: 7324 passed and 1 failed, `tests/test_dart_coverage.py::test_native_dart_lcov_omits_declaration_only_libraries`, whose `dart test` hit its 90 s limit on a Mac at load 600; it does not read the PR text code. Ruff (format, lint, complexity, annotations), Pyrefly and Vulture report no finding. Hook timing, compiled modules, two runs each: import 228 ms and 75 ms before, 228 ms and 188 ms after, within the noise of a loaded Mac; 200 body checks took 1.9 ms to 55.9 ms before and 4.4 ms after. Seven reviews ran; fixes made for the reachable findings, declines listed below. Full check: CI.
Review declined: a Mermaid fence inside a blockquote, and the inline code text `<!--` hiding later diagrams :: both need a PR body that quotes or explains Markdown syntax; the size rule already reads comments and fences the same way, and one shared Markdown parser would add a dependency for no reported case.
Review declined: a node named `title` in an edge, `accDescr` after a semicolon, and links with no spaces before a reused long ID :: each needs a hand-written diagram form that PR bodies do not use, and a fix needs a full Mermaid grammar; a miss only lets a long label through to the viewer, as before this change.
Review declined: an apostrophe inside a double-quoted attribute label, pipes inside two adjacent quoted node labels, a long source ID joined to an attribute node with no spaces, and a top-level four-space-indented example :: each needs a form PR bodies do not use; the indented-fence rule flipped between two reviews, and a diagram nested in a list is the common case, so it stays counted.
Review declined: a single-line `accTitle` that follows an `accDescr` line holding a brace and itself holds a semicolon :: needs two accessibility lines with those exact characters, which PR diagrams do not carry; the text is metadata and a miss only refuses a PR that can be edited.
Review declined: a literal line of mixed fence characters, and a four-space-indented closer, inside a fenced Markdown example that sits between two real diagrams :: each needs an example of Markdown syntax inside a PR body, and the miss is bounded the same as the other declined forms; a stricter fence parser would copy a Markdown parser into a hook.
E2E: N/A — the change is a pure check of PR text, proved by the tests above.
Real service: N/A — no service is called; the GitHub viewer facts come from the coordinator's measurement.
Retro: (1) User correction: "diagram labels cut off" → `tests/test_pr_text.py::test_a_mermaid_label_line_over_13_characters_is_refused_by_name`.

Delivery target: PR
Delivery: Pending — draft PR against develop; develop is frozen.
