const owner = (file, marker) => ({ file, marker });
const change = (status, file, marker) => ({ status, file, marker });

const retainedExact = (name, baseline_sha256) => ({
  name,
  baseline_sha256,
  baseline_type: 'tree',
  disposition: 'retained-exact',
  owners: [owner(`skills/${name}/SKILL.md`, null)],
  changes: [],
});

const retainedStrengthened = (name, baseline_sha256, changes) => ({
  name,
  baseline_sha256,
  baseline_type: 'tree',
  disposition: 'retained-strengthened',
  owners: [owner(`skills/${name}/SKILL.md`, null)],
  changes,
});

const consolidated = (name, baseline_sha256, baseline_marker, owners) => ({
  name,
  baseline_sha256,
  baseline_type: 'tree',
  baseline_marker,
  disposition: 'consolidated',
  owners,
  changes: [],
});

const retiredApproved = (name, baseline_sha256, baseline_marker, owners) => ({
  name,
  baseline_sha256,
  baseline_type: 'tree',
  baseline_marker,
  disposition: 'retired-approved',
  owners,
  changes: [],
});

const retainedSymlink = (name, baseline_sha256) => ({
  name,
  baseline_sha256,
  baseline_type: 'symlink',
  disposition: 'retained-exact',
  owners: [owner(`skills/${name}`, null)],
  changes: [],
});

const retainedAdapter = (name, baseline_sha256, baseline_marker, owners, changes) => ({
  name,
  baseline_sha256,
  baseline_type: 'symlink',
  baseline_marker,
  disposition: 'retained-strengthened',
  owners,
  changes,
});

const consolidatedSymlink = (name, baseline_sha256, baseline_marker, owners) => ({
  name,
  baseline_sha256,
  baseline_type: 'symlink',
  baseline_marker,
  disposition: 'consolidated',
  owners,
  changes: [],
});

const retiredSymlink = (name, baseline_sha256, baseline_marker, owners) => ({
  name,
  baseline_sha256,
  baseline_type: 'symlink',
  baseline_marker,
  disposition: 'retired-approved',
  owners,
  changes: [],
});

export const SKILL_PARITY_BASELINE = '59014f3';

export const SKILL_PARITY = [
  retainedSymlink('appwrite-backend', '9e97e673ec616077c204111572c21768e2baf35e2e3f24ff627d22e5eb88cb44'),
  retainedExact('atomic-ui', '367449c703feb9ce62d91a96506fd0e567e13c6fc5b516eb90d025cac9829139'),
  retainedSymlink('building-flutter-apps', '931688488e2c4914f19b1cf46607d790e00754095754bb3a778797471b3059a8'),
  retainedStrengthened('code-review', 'cdbac92f4155129d1e506faf3edfc8dfde6fa78eff49bb26bc211b6e6227ee91', [
    change('M', 'references/two-axis-review.md', 'requests delegation'),
  ]),
  retainedStrengthened('codebase-design', 'eccb9e05aeb2af9a44d54dcbf7752531098b173d666a3fd48826662552294b9f', [
    change('M', 'SKILL.md', 'enter `$hard-eng` Plan first'),
    change('M', 'references/deep-modules.md', 'delegation remains explicit-user-only'),
    change('M', 'references/design-it-twice.md', 'subagents only when the user explicitly requests delegation'),
  ]),
  retainedStrengthened('codebase-memory', '803781900753ae4548624851d94bcbd8a28b368b2462b138af2c210c2598b99e', [
    change('M', 'SKILL.md', 'Never use its MCP transport.'),
    change('M', 'references/tool-catalog.md', 'Never translate these calls to `mcp__*`'),
    change('M', 'references/workflows.md', 'Never start the MCP transport.'),
  ]),
  retainedExact('create-pdf', '2debad3c04a0cfe6731a4ff8a536b239ed782c0de01725c72cd88234493b0ac5'),
  retainedExact('diagnosing-bugs', 'f42eab83b269e7d4633ca8a5d5674503975677d5541b7ff70a8b51d6e7ba7fe2'),
  retainedExact('domain-modeling', '3807cd0615eddbb3f6f8bb025143da31a7b444675eb0760510c5ab1296b61505'),
  retainedStrengthened('e2e', '8f2ad89d456f8d1fccd0f1d2424cdc57bd1222c8c7071dbbd1669f3621ddd696', [
    change('M', 'references/browser-first.md', 'available Chrome or Browser control capability'),
    change('M', 'references/runbook.md', 'current Hard Eng Build slice'),
    change('M', 'templates/automation.md', 'Do not count unit tests'),
  ]),
  retainedAdapter('fallow', '1ab970688e359155233a6c7322c602da47bdbd1368535763c9f3e257b15793da',
    '../vendor/skill-upstreams/fallow-skills/fallow/skills/fallow', [
      owner('skills/fallow/SKILL.md', 'pinned upstream owner'),
      owner('vendor/skill-upstreams/fallow-skills/fallow/skills/fallow/SKILL.md', 'Fallow'),
    ], [
      change('D', null, null),
      change('A', 'SKILL.md', 'pinned upstream owner'),
    ]),
  retainedExact('find-skills', '91b158746aeafa867dafd671652981c81c634d7d1e366e30e652aeecff4e2697'),
  consolidated('grill-me', 'da2794554d028ecae7111cf46591e084a0eb25c0757666a346a1cc34c6407ff2',
    'Interview one clear, plain-language question at a time', [
      owner('skills/hard-eng/references/plan.md', 'bounded decision at a time'),
    ]),
  retainedStrengthened('handoff', 'dc9dd4906a17ff3fe27c07014a55d1afabe14346dc57c30f094db3e1dbd316c2', [
    change('M', 'agents/openai.yaml', 'allow_implicit_invocation: true'),
  ]),
  consolidated('he-implement', 'd19203f3dd960816f6ce333a506cba7db8e877e840908b5123a7391bfca06d30',
    'owner-first implementation', [
      owner('skills/hard-eng/references/build.md', 'At `implement`, change the canonical owner'),
    ]),
  consolidated('he-learn', 'b7169d9fec1859dfe9588b36507591223f1023a173cbfc5cb0c1d066d38608d8',
    'durable guard', [
      owner('skills/hard-eng/references/learn.md', 'Learn is a conditional Build/Ship interrupt'),
    ]),
  consolidated('he-plan', '987a2eea2ad775d20ca94e64bbf1ef53e5c5fa45d14e38c7e19cd4719ce9f5bf',
    'scope, owner, blast radius, proof path', [
      owner('skills/hard-eng/references/plan.md', 'Plan turns an ambiguous or material request'),
    ]),
  consolidated('he-ship', '26c2f62770c53492e3ff309f4c5c03a4f38ce45027bd762b016e72394d0ff857',
    'final gates', [
      owner('skills/hard-eng/references/ship.md', 'Ship is the only local delivery gate'),
    ]),
  consolidated('he-verify', '0ecab17793c867d9e9bec3f0dc196df0c254d080b560a3b41f14213339c4ced3',
    'verification loop', [
      owner('skills/hard-eng/references/build.md', 'Build is one Implement ⇄ Verify loop'),
    ]),
  retiredSymlink('impeccable', '04da148f16292872149bfedad954561bd0731b6112fb837cbb782ea5aa8305e3',
    '../vendor/skill-upstreams/impeccable/.agents/skills/impeccable', [
      owner('skills/atomic-ui/SKILL.md', 'Atomic UI'),
      owner('skills/hard-eng/references/ui-decision-lab.md', 'UI Decision Lab'),
    ]),
  consolidated('implement', '1a5463f3e5a319cad566f892c1fea74837c10c463dc613b39e227e3cef37a25e',
    'Implement a piece of work', [
      owner('skills/hard-eng/references/build.md', 'At `implement`, change the canonical owner'),
    ]),
  retainedStrengthened('improve-codebase-architecture', '3e1bb9dc4a246607f6fde1c69d7ce1429ee6db530fcda105b36dd85d20503609', [
    change('M', 'agents/openai.yaml', 'allow_implicit_invocation: true'),
    change('M', 'references/workflow.md', 'explicitly requests delegation'),
  ]),
  consolidatedSymlink('no-mistakes', 'f1f4bccb3a1801ac1863176c06e11155c0bb122d7207ce25c5c616b5707b0176',
    '../vendor/skill-upstreams/no-mistakes/skills/no-mistakes', [
      owner('skills/hard-eng/references/ship.md', 'ordered preflight'),
      owner('runtime/lib/findings.mjs', 'Finding provenance is required'),
      owner('runtime/lib/check-registry.mjs', 'Package check wrapper contains a prohibited'),
    ]),
  retainedExact('performance-rescue', '32bd5b55b295fb2e7a46fc082812ca3e4238be7d8c1c78b314a8aaed96237653'),
  retainedStrengthened('product-demo-video', '94a841f335bdee0038567063452183139ac83cc06ba95f832be5cec57c6a9123', [
    change('M', 'SKILL.md', 'ordinary E2E screenshots and verification recordings do not trigger it'),
    change('A', 'agents/openai.yaml', 'allow_implicit_invocation: true'),
  ]),
  retainedExact('prototype', '06e5f8f25771cc70956e48bb5d0b7bafe91515e19e5f3c0320df10b53dabfd48'),
  retainedSymlink('react-doctor', 'e2ac3ef903793e3d30aa60ae6b34502ad924422152ef439a21c9f99944a82f13'),
  retainedExact('repeated-failure-learning', 'dbfcbd4942a0ba6123567d950511e8865d35d689434db36ade7db0fbdd955c51'),
  retainedExact('research', '12cb38547a50cc51b6b41eee64d301b16cd76f92dfae49efccecf5b450a4962a'),
  retainedExact('resolving-merge-conflicts', 'ee25693171c1fabcf27ecf441c7bbbbf991671556678991066e66cff7c260cdd'),
  retainedExact('security-review', 'aad872197e5b28a84778262d52dda20b0ddad1639b77795e5d7c6552f984e2f8'),
  consolidated('sentry-cli', '3b269f6698a57ea1b8f90d01e619d9ad49a3241e0a4f54a989214fe2a9cd38c0',
    'Sentry CLI capability', [
      owner('skills/sentry-workflow/references/upstream-routing.md', 'Sentry CLI commands'),
    ]),
  consolidated('sentry-feature-setup', '9c85e5b6984ee01ceea5a134833351b06f92a3e0b4478247bdef7481e0cb5824',
    'Sentry feature-setup capability', [
      owner('skills/sentry-workflow/references/upstream-routing.md', 'sentry-feature-setup/SKILL.md'),
    ]),
  retainedStrengthened('sentry-workflow', '2c15c08793127e24a7c535586caa3fde3f89a114b130b0971c5c7d23b449020e', [
    change('M', 'SKILL.md', 'issues/events, CLI/API, SDK setup or upgrade'),
    change('M', 'references/upstream-routing.md', 'sentry-snapshots-cocoa/SKILL.md'),
  ]),
  retainedStrengthened('setup-engineering-skills', '076093fe4859e79589e4d1ddc0da08d3e831809ce752dcdc4b58f7eb6e328d47', [
    change('M', 'agents/openai.yaml', 'allow_implicit_invocation: true'),
    change('M', 'domain.md', '`domain-modeling` and `improve-codebase-architecture` skills'),
    change('M', 'references/workflow.md', 'if it is absent, ask before creating it'),
  ]),
  retainedStrengthened('setup-pre-commit', 'd6b725eef2c3f18fe9ff7a04c0797919f4e34ea6db1752edaeb82ae10c597168', [
    change('M', 'agents/openai.yaml', 'allow_implicit_invocation: true'),
  ]),
  retainedExact('tdd', 'c6c3e47e6eb516ad21c941274b715b6d2ff2333a8e379d8f26d7c39c84f4bf26'),
  retainedStrengthened('teach', 'b310bb1e081a1f8d7e3bbac09a084e1878f9f0f05584ab64c6edd0db9b369125', [
    change('M', 'SKILL.md', 'only when the user asks for'),
    change('M', 'agents/openai.yaml', 'allow_implicit_invocation: true'),
    change('M', 'references/workflow.md', 'Reuse is the default'),
  ]),
  retainedExact('terse', 'bd91c8c720697b6c718ade140d96e3ee0c7699070e6b98e3e85771371a0080a1'),
  retainedExact('test-quality', 'ecbd23031e4c69a7fa3d46daf0ebc007078c9b878c95adbe0d4aca5e74fc113c'),
  retainedStrengthened('thermo-nuclear-code-quality-review', '51d75f36b6687303eb1695c3276f75bccd4646a5533e621eee9a9fb2a8a9ba30', [
    change('M', 'references/review-board.md', 'Use subagents only after an explicit user request'),
  ]),
  retiredApproved('treehouse', '46481d6bde88caa6ceb55422aeabbd17fc513d1035fb88764b3e8f2b04d73b62',
    'Treehouse = local CLI for reusable git worktrees', [
      owner('runtime/lib/worktree.mjs', "copy_owner: 'codex-managed-worktree'"),
    ]),
  retainedStrengthened('triage', 'fad7454a2bd9b70a51cdb560d7002d1ed42ab8b8c88a33dea5e594478d265459', [
    change('M', 'agents/openai.yaml', 'allow_implicit_invocation: true'),
    change('M', 'references/workflow.md', 'ask one targeted unresolved question at a time'),
  ]),
  retainedSymlink('vercel-react-best-practices', 'd2bb1f0652ea63fa5c8808b5834f4e5e0977a164c3c8713b3c51cc516a93af4f'),
  retainedStrengthened('website-launch-readiness', '852ab46d899e417b2d000228539a62ed224f26f81413516fb369822bf3b0d367', [
    change('M', 'SKILL.md', 'explicitly asks for website launch readiness'),
    change('M', 'agents/openai.yaml', 'allow_implicit_invocation: true'),
  ]),
  consolidated('workflow-help', '009684f0b7c92881db3c47bde4851e5b1641f2aca77ca615a15af852d3969c94',
    'canonical router', [
      owner('skills/hard-eng/references/route.md', 'Classify the request from evidence before creating state'),
    ]),
  retainedStrengthened('writing-great-skills', 'e4612f87386d9f12b924ae7309ff7f47986c9338abe525cc56cf7a76a69d8444', [
    change('M', 'GLOSSARY.md', 'In Codex, set `agents/openai.yaml`'),
    change('M', 'SKILL.md', 'model evaluations release-only'),
    change('A', 'agents/openai.yaml', 'allow_implicit_invocation: true'),
    change('M', 'references/skill-writing-method.md', '`policy.allow_implicit_invocation: true`'),
  ]),
];
