const approvalStatuses = new Set(['approved', 'blocked', 'not_required']);
const approvalCategories = new Set([
  'prod-backend-write',
  'native-permission',
  'real-credentials',
  'generated-credentials',
  'prod-cleanup',
]);

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function stringArray(value) {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

function textOf(value) {
  if (Array.isArray(value)) return value.filter((item) => typeof item === 'string').join(' ');
  if (typeof value === 'string') return value;
  return '';
}

function collectText(value) {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(collectText).filter(Boolean).join(' ');
  if (isObject(value)) return Object.values(value).map(collectText).filter(Boolean).join(' ');
  return '';
}

function collectStrings(value) {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(collectStrings);
  if (isObject(value)) return Object.values(value).flatMap(collectStrings);
  return [];
}

function e2ePolicyEvidenceStrings(e2ePolicy) {
  if (!isObject(e2ePolicy)) return collectStrings(e2ePolicy);
  const { requiredApprovalBoundaries, ...evidencePolicy } = e2ePolicy;
  return collectStrings(evidencePolicy);
}

function hasExplicitPerformedRiskMarker(text) {
  return /\b(?:performed[-\s]?risk|risk[-\s]?performed|performed[-\s]?(?:prod(?:uction)?\s+)?side[-\s]?effect|side[-\s]?effect[-\s]?performed|actual[-\s]?risk|actual[-\s]?side[-\s]?effect)\b/i.test(text);
}

function isReceiptArtifactPath(text) {
  return /\b(?:[\w.-]+[\\/])+[\w.-]+\b/i.test(text) || /\b\S+\.(?:spec|test|mjs|cjs|js|jsx|ts|tsx|json|md|ya?ml|png|jpe?g|webm|mp4|txt|log|html)\b/i.test(text);
}

function receiptProofStrings(value) {
  return collectStrings(value).filter((text) => !isReceiptArtifactPath(text) || hasExplicitPerformedRiskMarker(text));
}

function stepApprovalEvidenceStrings(step) {
  if (!isObject(step)) return [];
  const receipt = isObject(step.receipt) ? step.receipt : {};
  return [
    ...collectStrings(step.evidence),
    ...collectStrings(step.reason),
    ...receiptProofStrings(receipt.ownerProof),
    ...receiptProofStrings(receipt.artifacts),
    ...collectStrings(receipt.evidence),
  ];
}

function normalizeEvidenceText(text) {
  return text
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[^a-z0-9]+/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

function matchesAny(text, patterns) {
  return patterns.some((pattern) => pattern.test(text));
}

const approvalBoundaryEvidencePatterns = new Map([
  ['prod-backend-write', [
    /\b(?:applied|apply|applying|ran|run|running|executed|execute|executing)\b.*\b(?:prod|production)\b.*\b(?:backend|appwrite|database|db)\b.*\bmigrations?\b/,
    /\b(?:applied|apply|applying|ran|run|running|executed|execute|executing)\b.*\b(?:backend|appwrite|database|db)\b.*\bmigrations?\b.*\b(?:prod|production)\b/,
    /\b(?:prod|production)\b.*\b(?:backend|appwrite|database|db)\b.*\bmigrations?\b.*\b(?:applied|apply|applying|ran|run|running|executed|execute|executing)\b/,
    /\b(?:backend|appwrite|database|db)\b.*\bmigrations?\b.*\b(?:prod|production)\b.*\b(?:applied|apply|applying|ran|run|running|executed|execute|executing)\b/,
    /\b(?:inserted|insert|inserting|upserted|upsert|upserting|patched|patch|patching|uploaded|upload|uploading)\b.*\b(?:prod|production)\b.*\b(?:backend|appwrite|database|db|data|record|records|file|files|user|users|account|accounts)\b/,
    /\b(?:inserted|insert|inserting|upserted|upsert|upserting|patched|patch|patching|uploaded|upload|uploading)\b.*\b(?:backend|appwrite|database|db|data|record|records|file|files|user|users|account|accounts)\b.*\b(?:prod|production)\b/,
    /\b(?:prod|production)\b.*\b(?:backend|appwrite|database|db|data|record|records|file|files|user|users|account|accounts)\b.*\b(?:inserted|insert|inserting|upserted|upsert|upserting|patched|patch|patching|uploaded|upload|uploading)\b/,
    /\b(?:updated|update|updating|modified|modify|modifying|granted|grant|granting|revoked|revoke|revoking)\b.*\b(?:prod|production)\b.*\b(?:backend|appwrite|database|db|permission|permissions|schema|index|email|emails|sms|text|texts|message|messages|payment|payments|charge|charges|refund|refunds|receipt|receipts|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|data|record|records|file|files|link|links|notification|notifications|invite|invites|invitation|invitations|webhook|webhooks|user|users|account|accounts|access)\b/,
    /\b(?:updated|update|updating|modified|modify|modifying|granted|grant|granting|revoked|revoke|revoking)\b.*\b(?:backend|appwrite|database|db|permission|permissions|schema|index|email|emails|sms|text|texts|message|messages|payment|payments|charge|charges|refund|refunds|receipt|receipts|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|data|record|records|file|files|link|links|notification|notifications|invite|invites|invitation|invitations|webhook|webhooks|user|users|account|accounts|access)\b.*\b(?:prod|production)\b/,
    /\b(?:prod|production)\b.*\b(?:backend|appwrite|database|db|permission|permissions|schema|index|email|emails|sms|text|texts|message|messages|payment|payments|charge|charges|refund|refunds|receipt|receipts|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|data|record|records|file|files|link|links|notification|notifications|invite|invites|invitation|invitations|webhook|webhooks|user|users|account|accounts|access)\b.*\b(?:updated|update|updating|modified|modify|modifying|granted|grant|granting|revoked|revoke|revoking)\b/,
    /\b(?:changed|change|changing|wrote|write|writing|mutated|mutation|mutate|deleted|delete|deleting|created|create|creating|disabled|disable|disabling|enabled|enable|enabling|suspended|suspend|suspending|deactivated|deactivate|deactivating|removed|remove|removing|reset|resetting)\b.*\b(?:prod|production)\b.*\b(?:backend|appwrite|database|db|permission|permissions|schema|index|email|emails|sms|text|texts|message|messages|payment|payments|charge|charges|refund|refunds|receipt|receipts|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|data|record|records|file|files|link|links|notification|notifications|invite|invites|invitation|invitations|webhook|webhooks|user|users|account|accounts)\b/,
    /\b(?:changed|change|changing|wrote|write|writing|mutated|mutation|mutate|deleted|delete|deleting|created|create|creating|disabled|disable|disabling|enabled|enable|enabling|suspended|suspend|suspending|deactivated|deactivate|deactivating|removed|remove|removing|reset|resetting)\b.*\b(?:backend|appwrite|database|db|permission|permissions|schema|index|email|emails|sms|text|texts|message|messages|payment|payments|charge|charges|refund|refunds|receipt|receipts|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|data|record|records|file|files|link|links|notification|notifications|invite|invites|invitation|invitations|webhook|webhooks|user|users|account|accounts)\b.*\b(?:prod|production)\b/,
    /\b(?:prod|production)\b.*\b(?:backend|appwrite|database|db|permission|permissions|schema|index|email|emails|sms|text|texts|message|messages|payment|payments|charge|charges|refund|refunds|receipt|receipts|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|data|record|records|file|files|link|links|notification|notifications|invite|invites|invitation|invitations|webhook|webhooks|user|users|account|accounts)\b.*\b(?:changed|change|changing|wrote|write|writing|mutated|mutation|mutate|deleted|delete|deleting|created|create|creating|disabled|disable|disabling|enabled|enable|enabling|suspended|suspend|suspending|deactivated|deactivate|deactivating|removed|remove|removing|reset|resetting)\b/,
    /\b(?:sent|send|sending|emailed|emailing|texted|texting|messaged|messaging|charged|charge|charging|refunded|refund|refunding|shared|share|sharing|published|publish|publishing|notified|notify|notifying|invited|invite|inviting)\b.*\b(?:prod|production)\b.*\b(?:email|emails|sms|text|texts|message|messages|payment|payments|charge|charges|refund|refunds|receipt|receipts|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|data|file|files|link|links|notification|notifications|invite|invites|invitation|invitations|webhook|webhooks|user|users|account|accounts|access)\b/,
    /\b(?:sent|send|sending|emailed|emailing|texted|texting|messaged|messaging|charged|charge|charging|refunded|refund|refunding|shared|share|sharing|published|publish|publishing|notified|notify|notifying|invited|invite|inviting)\b.*\b(?:email|emails|sms|text|texts|message|messages|payment|payments|charge|charges|refund|refunds|receipt|receipts|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|data|file|files|link|links|notification|notifications|invite|invites|invitation|invitations|webhook|webhooks|user|users|account|accounts|access)\b.*\b(?:prod|production)\b/,
    /\b(?:prod|production)\b.*\b(?:email|emails|sms|text|texts|message|messages|payment|payments|charge|charges|refund|refunds|receipt|receipts|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|data|file|files|link|links|notification|notifications|invite|invites|invitation|invitations|webhook|webhooks|user|users|account|accounts|access)\b.*\b(?:sent|send|sending|emailed|emailing|texted|texting|messaged|messaging|charged|charge|charging|refunded|refund|refunding|shared|share|sharing|published|publish|publishing|notified|notify|notifying|invited|invite|inviting)\b/,
    /\b(?:email|emails|sms|text|texts|message|messages|receipt|receipts)\b.*\b(?:sent|send|sending|emailed|emailing|texted|texting|messaged|messaging|notified|notify|notifying|invited|invite|inviting)\b.*\b(?:prod|production)\b/,
    /\b(?:email|emails|sms|text|texts|message|messages|receipt|receipts)\b.*\b(?:prod|production)\b.*\b(?:sent|send|sending|emailed|emailing|texted|texting|messaged|messaging|notified|notify|notifying|invited|invite|inviting)\b/,
    /\b(?:changed|change|changing|wrote|write|writing|mutated|mutation|mutate|deleted|delete|deleting)\b.*\b(?:backend|appwrite|database|db|permission|permissions|schema|index)\b.*\b(?:prod|production)\b/,
    /\b(?:changed|change|changing|wrote|write|writing|mutated|mutation|mutate|deleted|delete|deleting)\b.*\b(?:prod|production)\b.*\b(?:backend|appwrite|database|db|permission|permissions|schema|index)\b/,
    /\b(?:prod|production)\b.*\b(?:backend|appwrite|database|db|permission|permissions|schema|index)\b.*\b(?:changed|change|changing|wrote|write|writing|mutated|mutation|mutate|deleted|delete|deleting|gap|fix|fixed)\b/,
    /\b(?:backend|appwrite|database|db)\b.*\b(?:permission|permissions|schema|index)\b.*\b(?:prod|production)\b/,
    /\b(?:backend|appwrite|database|db)\b.*\b(?:schema|index|permission|permissions)\b.*\b(?:must|need|needs|required|requires)\b.*\b(?:change|write|mutation|fix)\b/,
  ]],
  ['native-permission', [
    /\bnative\b.*\b(?:permission|prompt|dialog)\b/,
    /\bpermission\b.*\bprompt\b/,
    /\b(?:native|permission|prompt|dialog)\b.*\b(?:clicked|click|accepted|accept|allowed|allow|granted|grant)\b/,
    /\b(?:clicked|click|accepted|accept|allowed|allow|granted|grant)\b.*\b(?:native|permission|prompt|dialog)\b/,
  ]],
  ['real-credentials', [
    /\breal\b.*\b(?:credential|credentials|account|user)\b/,
    /\b(?:used|use|using|logged(?:\s+in)?|log\s+in|logging\s+in|login|signed(?:\s+in)?|sign\s+in|signing\s+in|authenticated|authenticate|authenticating)\b.*\b(?:saved auth|personal account|real credential|real credentials|real account|real user|saved account|saved session)\b/,
  ]],
  ['generated-credentials', [
    /\bgenerated\b.*\b(?:credential|credentials|user|test user|account|password)\b/,
    /\b(?:created|create|generated|used|use|using)\b.*\bgenerated\b.*\b(?:user|credential|credentials|password|account)\b/,
    /\b(?:created|create|creating|used|use|using)\b.*\b(?:e2e|test)\b.*\b(?:user|users|account|accounts|credential|credentials|password|passwords)\b/,
    /\b(?:created|create|creating|used|use|using)\b.*\b(?:user|users|account|accounts|credential|credentials|password|passwords)\b.*\b(?:e2e|test)\b/,
  ]],
  ['prod-cleanup', [
    /\b(?:prod|production)\b.*\bcleanup\b/,
    /\bcleanup\b.*\b(?:prod|production)\b/,
  ]],
]);

const approvalBoundarySideEffectPatterns = new Map([
  ['prod-backend-write', [
    ['prod-appwrite-permission', [
      /\bappwrite\b.*\b(?:permission|permissions|access)\b/,
      /\b(?:permission|permissions|access)\b.*\bappwrite\b/,
    ]],
    ['prod-appwrite-schema', [
      /\bappwrite\b.*\b(?:schema|index|indexes|indices)\b/,
      /\b(?:schema|index|indexes|indices)\b.*\bappwrite\b/,
      /\bappwrite\b.*\bmigrations?\b/,
      /\bmigrations?\b.*\bappwrite\b/,
    ]],
    ['prod-db-schema', [
      /\b(?:database|db)\b.*\b(?:schema|index|indexes|indices)\b/,
      /\b(?:schema|index|indexes|indices)\b.*\b(?:database|db)\b/,
      /\b(?:database|db)\b.*\bmigrations?\b/,
      /\bmigrations?\b.*\b(?:database|db)\b/,
    ]],
    ['prod-db-permission', [
      /\b(?:database|db)\b.*\b(?:permission|permissions|access)\b/,
      /\b(?:permission|permissions|access)\b.*\b(?:database|db)\b/,
    ]],
    ['prod-backend-permission', [
      /\bbackend\b.*\b(?:permission|permissions|access)\b/,
      /\b(?:permission|permissions|access)\b.*\bbackend\b/,
    ]],
    ['prod-backend-schema', [
      /\bbackend\b.*\b(?:schema|index|indexes|indices)\b/,
      /\b(?:schema|index|indexes|indices)\b.*\bbackend\b/,
      /\bbackend\b.*\bmigrations?\b/,
      /\bmigrations?\b.*\bbackend\b/,
    ]],
    ['prod-sms', [
      /\b(?:sent|send|sending|texted|texting|messaged|messaging|notified|notify|notifying|invited|invite|inviting)\b.*\b(?:prod|production)\b.*\b(?:sms|text|texts|message|messages)\b/,
      /\b(?:sent|send|sending|texted|texting|messaged|messaging|notified|notify|notifying|invited|invite|inviting)\b.*\b(?:sms|text|texts|message|messages)\b.*\b(?:prod|production)\b/,
      /\b(?:prod|production)\b.*\b(?:sms|text|texts|message|messages)\b.*\b(?:sent|send|sending|texted|texting|messaged|messaging|notified|notify|notifying|invited|invite|inviting)\b/,
      /\b(?:sms|text|texts|message|messages)\b.*\b(?:sent|send|sending|texted|texting|messaged|messaging|notified|notify|notifying|invited|invite|inviting)\b.*\b(?:prod|production)\b/,
      /\b(?:sms|text|texts|message|messages)\b.*\b(?:prod|production)\b.*\b(?:sent|send|sending|texted|texting|messaged|messaging|notified|notify|notifying|invited|invite|inviting)\b/,
      /\b(?:texted|texting|messaged|messaging)\b.*\b(?:prod|production)\b.*\b(?:user|users|account|accounts|customer|customers)\b/,
      /\b(?:prod|production)\b.*\b(?:user|users|account|accounts|customer|customers)\b.*\b(?:texted|texting|messaged|messaging)\b/,
    ]],
    ['prod-email', [
      /\b(?:sent|send|sending|emailed|emailing|messaged|messaging|notified|notify|notifying|invited|invite|inviting)\b.*\b(?:prod|production)\b.*\b(?:email|emails|receipt|receipts)\b/,
      /\b(?:sent|send|sending|emailed|emailing|messaged|messaging|notified|notify|notifying|invited|invite|inviting)\b.*\b(?:email|emails|receipt|receipts)\b.*\b(?:prod|production)\b/,
      /\b(?:prod|production)\b.*\b(?:email|emails|receipt|receipts)\b.*\b(?:sent|send|sending|emailed|emailing|messaged|messaging|notified|notify|notifying|invited|invite|inviting)\b/,
      /\b(?:email|emails|receipt|receipts)\b.*\b(?:sent|send|sending|emailed|emailing|messaged|messaging|notified|notify|notifying|invited|invite|inviting)\b.*\b(?:prod|production)\b/,
      /\b(?:email|emails|receipt|receipts)\b.*\b(?:prod|production)\b.*\b(?:sent|send|sending|emailed|emailing|messaged|messaging|notified|notify|notifying|invited|invite|inviting)\b/,
      /\b(?:emailed|emailing)\b.*\b(?:prod|production)\b.*\b(?:user|users|account|accounts|customer|customers)\b/,
      /\b(?:prod|production)\b.*\b(?:user|users|account|accounts|customer|customers)\b.*\b(?:emailed|emailing)\b/,
    ]],
    ['prod-payment', [
      /\b(?:payment|payments|charge|charges|charged|charging|refund|refunds|refunded|refunding|billing|bill|billed|invoice|invoices|invoiced)\b/,
      /\b(?:charged|charge|charging|refunded|refund|refunding|payment|payments|billing|bill|billed|invoiced|invoice|subscribed|subscribe|subscription)\b.*\b(?:card|cards|customer|customers|subscription|subscriptions|invoice|invoices)\b/,
      /\b(?:card|cards|customer|customers|subscription|subscriptions|invoice|invoices)\b.*\b(?:charged|charge|charging|refunded|refund|refunding|payment|payments|billing|bill|billed|invoiced|invoice|subscribed|subscribe|subscription)\b/,
      /\b(?:changed|change|changing|updated|update|updating|modified|modify|modifying|created|create|creating|deleted|delete|deleting|removed|remove|removing|reset|resetting)\b.*\b(?:subscription|subscriptions|invoice|invoices|billing)\b/,
      /\b(?:subscription|subscriptions|invoice|invoices|billing)\b.*\b(?:changed|change|changing|updated|update|updating|modified|modify|modifying|created|create|creating|deleted|delete|deleting|removed|remove|removing|reset|resetting)\b/,
    ]],
    ['prod-user-account', [
      /\b(?:changed|change|changing|updated|update|updating|modified|modify|modifying|inserted|insert|inserting|upserted|upsert|upserting|patched|patch|patching|wrote|write|writing|mutated|mutate|mutating|deleted|delete|deleting|created|create|creating|granted|grant|granting|revoked|revoke|revoking|disabled|disable|disabling|enabled|enable|enabling|suspended|suspend|suspending|deactivated|deactivate|deactivating|removed|remove|removing|reset|resetting)\b.*\b(?:user|users|account|accounts|access)\b/,
      /\b(?:user|users|account|accounts|access)\b.*\b(?:changed|change|changing|updated|update|updating|modified|modify|modifying|inserted|insert|inserting|upserted|upsert|upserting|patched|patch|patching|wrote|write|writing|mutated|mutate|mutating|deleted|delete|deleting|created|create|creating|granted|grant|granting|revoked|revoke|revoking|disabled|disable|disabling|enabled|enable|enabling|suspended|suspend|suspending|deactivated|deactivate|deactivating|removed|remove|removing|reset|resetting)\b/,
    ]],
    ['prod-data-sharing', [
      /\b(?:shared|share|sharing|published|publish|publishing)\b.*\b(?:data|file|files|link|links)\b/,
      /\b(?:data|file|files|link|links)\b.*\b(?:shared|share|sharing|published|publish|publishing)\b/,
    ]],
    ['prod-notification', [/\b(?:notification|notifications|notify|notified|invite|invites|invited|invitation|invitations|webhook|webhooks)\b/]],
  ]],
]);

const approvalBoundaryFallbackSideEffectPatterns = new Map([
  ['prod-backend-write', [
    ['prod-data-record', [/\b(?:data|record|records|file|files|link|links)\b/]],
  ]],
]);

const approvalBoundaryCategoryProofPatterns = new Map([
  ['prod-backend-write', [
    /\b(?:prod|production)\b.*\b(?:backend|appwrite|database|db|permission|permissions|schema|index|indexes|indices|write|writes|mutation|mutations|side\s*effects?|payment|payments|charge|charges|refund|refunds|receipt|receipts|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|email|emails|sms|text|texts|message|messages|data|record|records|file|files|link|links|notification|notifications|invite|invites|invitation|invitations|webhook|webhooks|user|users|account|accounts|access)\b/,
    /\b(?:backend|appwrite|database|db|permission|permissions|schema|index|indexes|indices|write|writes|mutation|mutations|side\s*effects?|payment|payments|charge|charges|refund|refunds|receipt|receipts|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|email|emails|sms|text|texts|message|messages|data|record|records|file|files|link|links|notification|notifications|invite|invites|invitation|invitations|webhook|webhooks|user|users|account|accounts|access)\b.*\b(?:prod|production)\b/,
  ]],
  ['native-permission', [
    /\b(?:native|permission|prompt|dialog)\b/,
    /\b(?:click|clicked|clicking|accepted|accept|allowed|allow|granted|granting|grant)\b.*\b(?:allow|permission|prompt|dialog|native)\b/,
    /\b(?:allow|permission|prompt|dialog|native)\b.*\b(?:click|clicked|clicking|accepted|accept|allowed|allow|granted|granting|grant)\b/,
  ]],
  ['real-credentials', [
    /\b(?:real|personal|saved\s+auth|saved\s+account|saved\s+session|credentials?)\b/,
  ]],
  ['generated-credentials', [
    /\b(?:generated|test\s+user|test\s+account|credentials?|password)\b/,
  ]],
  ['prod-cleanup', [
    /\b(?:prod|production)\b.*\bcleanup\b/,
    /\bcleanup\b.*\b(?:prod|production)\b/,
  ]],
]);

const nonRiskApprovalEvidencePatterns = [
  /\b(?:no|not|never|without)(?:\s+\w+){0,3}\s+(?:real\s+credentials?|real\s+accounts?|real\s+users?|generated\s+credentials?|generated\s+users?|generated\s+accounts?|native\s+permission|permission\s+prompt)\b/,
  /\b(?:no|not|never|without)(?:\s+\w+){0,3}\s+(?:prod|production)\s+(?:cleanup|write|writes|mutation|delete|backend|appwrite|database|db)\b/,
  /\b(?:no|not|never|without)(?:\s+\w+){0,4}\s+(?:prod|production|backend|appwrite|database|db|native|real|generated|credential|credentials|cleanup|email|emails|sms|payment|payments|sharing|shared|data|side effects?)(?:\s+\w+){0,6}\s+(?:write|writes|wrote|writing|mutation|mutate|mutated|mutating|change|changed|changing|update|updated|updating|modify|modified|modifying|grant|granted|granting|revoke|revoked|revoking|delete|deleted|deleting|created|create|creating|used|use|using|clicked|click|allow|cleanup|sent|send|sending|emailed|emailing|texted|texting|messaged|messaging|charged|charge|charging|refunded|refund|refunding|shared|share|sharing|published|publish|publishing|notified|notify|notifying|invited|invite|inviting)\b/,
  /\b(?:no|not|never|without)(?:\s+\w+){0,4}\s+(?:write|writes|wrote|writing|mutation|mutate|mutated|mutating|change|changed|changing|update|updated|updating|modify|modified|modifying|grant|granted|granting|revoke|revoked|revoking|delete|deleted|deleting|created|create|creating|used|use|using|clicked|click|allow|cleanup|sent|send|sending|emailed|emailing|texted|texting|messaged|messaging|charged|charge|charging|refunded|refund|refunding|shared|share|sharing|published|publish|publishing|notified|notify|notifying|invited|invite|inviting)(?:\s+\w+){0,6}\s+(?:prod|production|backend|appwrite|database|db|native|real|generated|credential|credentials|cleanup|email|emails|sms|payment|payments|sharing|shared|data|side effects?)\b/,
];

const postposedNonRiskApprovalEvidencePatterns = [
  /\b(?:prod|production)\s+cleanup(?:\s+\w+){0,4}\s+(?:not|never)\s+(?:needed|required|necessary|applicable)\b/,
  /\bcleanup(?:\s+\w+){0,4}\s+(?:prod|production)(?:\s+\w+){0,4}\s+(?:not|never)\s+(?:needed|required|necessary|applicable)\b/,
  /\b(?:prod|production)\b(?:\s+\w+){0,6}\s+(?:backend|appwrite|database|db|permission|permissions|schema|index|email|emails|sms|text|texts|message|messages|payment|payments|charge|charges|refund|refunds|receipt|receipts|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|data|record|records|file|files|link|links|notification|notifications|invite|invites|invitation|invitations|webhook|webhooks|user|users|account|accounts|access|cleanup|side effects?)\b(?:\s+\w+){0,4}\s+(?:not|never)\s+(?:changed|updated|modified|wrote|written|mutated|deleted|created|granted|revoked|used|clicked|accepted|allowed|sent|emailed|texted|messaged|charged|refunded|shared|published|notified|invited|shown|displayed|performed|run)\b/,
  /\b(?:email|emails|sms|text|texts|message|messages|receipt|receipts)\b(?:\s+\w+){0,4}\s+(?:prod|production)\b(?:\s+\w+){0,4}\s+(?:not|never)\s+(?:sent|emailed|texted|messaged|notified|invited)\b/,
  /\b(?:native|permission|prompt|dialog)\b(?:\s+\w+){0,5}\s+(?:not|never)\s+(?:shown|displayed|clicked|accepted|allowed|granted|used)\b/,
  /\b(?:real|generated)\b(?:\s+\w+){0,4}\s+(?:credentials?|users?|accounts?|passwords?)\b(?:\s+\w+){0,4}\s+(?:not|never)\s+(?:used|created|generated|logged)\b/,
];

const actionObjectNegatedApprovalEvidencePatterns = [
  /\b(?:sent|send|sending|emailed|emailing|texted|texting|messaged|messaging|charged|charge|charging|refunded|refund|refunding|shared|share|sharing|published|publish|publishing|notified|notify|notifying|invited|invite|inviting)\b(?:\s+\w+){0,3}\s+(?:no|zero|0|none)\s+(?:prod|production)\b(?:\s+\w+){0,4}\s+(?:email|emails|sms|text|texts|message|messages|payment|payments|charge|charges|refund|refunds|receipt|receipts|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|data|file|files|link|links|notification|notifications|invite|invites|invitation|invitations|webhook|webhooks|user|users|account|accounts|access)\b/,
  /\b(?:sent|send|sending|emailed|emailing|texted|texting|messaged|messaging|charged|charge|charging|refunded|refund|refunding|shared|share|sharing|published|publish|publishing|notified|notify|notifying|invited|invite|inviting)\b(?:\s+\w+){0,3}\s+(?:no|zero|0|none)\s+(?:email|emails|sms|text|texts|message|messages|payment|payments|charge|charges|refund|refunds|receipt|receipts|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|data|file|files|link|links|notification|notifications|invite|invites|invitation|invitations|webhook|webhooks|user|users|account|accounts|access)\b(?:\s+\w+){0,4}\s+(?:prod|production)\b/,
  /\b(?:no|zero|0|none)\s+(?:prod|production)\b(?:\s+\w+){0,4}\s+(?:email|emails|sms|text|texts|message|messages|payment|payments|charge|charges|refund|refunds|receipt|receipts|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|data|file|files|link|links|notification|notifications|invite|invites|invitation|invitations|webhook|webhooks|user|users|account|accounts|access)\b(?:\s+\w+){0,4}\s+(?:sent|send|sending|emailed|emailing|texted|texting|messaged|messaging|charged|charge|charging|refunded|refund|refunding|shared|share|sharing|published|publish|publishing|notified|notify|notifying|invited|invite|inviting)\b/,
  /\b(?:no|zero|0|none)\s+(?:email|emails|sms|text|texts|message|messages|payment|payments|charge|charges|refund|refunds|receipt|receipts|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|data|file|files|link|links|notification|notifications|invite|invites|invitation|invitations|webhook|webhooks|user|users|account|accounts|access)\b(?:\s+\w+){0,4}\s+(?:prod|production)\b(?:\s+\w+){0,4}\s+(?:sent|send|sending|emailed|emailing|texted|texting|messaged|messaging|charged|charge|charging|refunded|refund|refunding|shared|share|sharing|published|publish|publishing|notified|notify|notifying|invited|invite|inviting)\b/,
];

const nonGeneratedCredentialApprovalEvidencePatterns = [
  /\b(?:non generated|not generated|local only)\b.*\b(?:e2e|test)\b.*\b(?:user|users|account|accounts|credential|credentials|password|passwords)\b/,
  /\b(?:e2e|test)\b.*\b(?:user|users|account|accounts|credential|credentials|password|passwords)\b.*\b(?:non generated|not generated|local only)\b/,
];

const codePreventionOnlyApprovalEvidencePatterns = [
  /\b(?:changed|change|changing|updated|update|updating|added|add|adding|implemented|implementing|tightened|tighten|tightening|fixed|fixing)\b.*\b(?:scanner|validator|validation|guardrail|check|test|regex|pattern|lint|script|hook|gate)\b.*\b(?:prevent|prevents|prevented|prevention|block|blocks|blocked|blocking|guard|guards|guarded|detect|detects|detected|reject|rejects|rejected)\b/,
];

const codeOnlyBackendSchemaRepairApprovalEvidencePatterns = [
  /\b(?:backend|appwrite|database|db)\b.*\b(?:schema|index|indexes|indices|permission|permissions)\b.*\b(?:validator|validation|scanner|test|tests|spec|script|regex|pattern|check|guardrail|gate|code)\b.*\b(?:must|needs?|requires?|required|fix|fixed|repair|repaired|update|updated)\b/,
  /\b(?:validator|validation|scanner|test|tests|spec|script|regex|pattern|check|guardrail|gate|code)\b.*\b(?:backend|appwrite|database|db)\b.*\b(?:schema|index|indexes|indices|permission|permissions)\b.*\b(?:must|needs?|requires?|required|fix|fixed|repair|repaired|update|updated)\b/,
];

const preventionOnlyApprovalEvidencePatterns = [
  /\b(?:prevent|prevents|prevented|prevention|blocked|blocking|guarded|guardrail|check|scanner|validation|verify|verified)(?:\s+\w+){0,8}\s+(?:no|without|blocked|denied|read only|readonly|clean)\b/,
  /\b(?:read only|readonly)(?:\s+\w+){0,6}\s+(?:check|probe|review|inspection|verification|prevention|passed|clean)\b/,
  /\b(?:check|probe|review|inspection|verification|prevention)(?:\s+\w+){0,6}\s+(?:read only|readonly)\b/,
];

const hypotheticalApprovalEvidencePatterns = [
  /\b(?:skipped|skip|not run|preflight|dry run|hypothetical|simulated|simulation)\b(?:\s+\w+){0,10}\s+(?:would|could|might|may|avoid|avoids|avoided|avoiding)\b(?:\s+\w+){0,10}\s+(?:changed|change|changing|updated|update|updating|modified|modify|modifying|wrote|write|writing|mutated|mutation|mutate|deleted|delete|deleting|created|create|creating|disabled|disable|disabling|enabled|enable|enabling|suspended|suspend|suspending|deactivated|deactivate|deactivating|removed|remove|removing|reset|resetting|used|use|using|clicked|click|accepted|accept|allowed|allow|granted|grant|granting|revoked|revoke|revoking|sent|send|sending|emailed|emailing|texted|texting|messaged|messaging|charged|charge|charging|refunded|refund|refunding|shared|share|sharing|published|publish|publishing|notified|notify|notifying|invited|invite|inviting)\b(?:\s+\w+){0,8}\s+(?:prod|production|backend|appwrite|database|db|native|real|generated|credential|credentials|cleanup|email|emails|sms|text|texts|message|messages|payment|payments|card|cards|customer|customers|data|user|users|account|accounts|permission|permissions|schema|index|access)\b/,
  /\b(?:skipped|skip|not run|preflight|dry run|hypothetical|simulated|simulation)\b(?:\s+\w+){0,10}\s+(?:would|could|might|may|avoid|avoids|avoided|avoiding)\b(?:\s+\w+){0,10}\s+(?:prod|production|backend|appwrite|database|db|native|real|generated|credential|credentials|cleanup|email|emails|sms|text|texts|message|messages|payment|payments|card|cards|customer|customers|data|user|users|account|accounts|permission|permissions|schema|index|access)\b(?:\s+\w+){0,8}\s+(?:changed|change|changing|updated|update|updating|modified|modify|modifying|wrote|write|writing|mutated|mutation|mutate|deleted|delete|deleting|created|create|creating|disabled|disable|disabling|enabled|enable|enabling|suspended|suspend|suspending|deactivated|deactivate|deactivating|removed|remove|removing|reset|resetting|used|use|using|clicked|click|accepted|accept|allowed|allow|granted|grant|granting|revoked|revoke|revoking|sent|send|sending|emailed|emailing|texted|texting|messaged|messaging|charged|charge|charging|refunded|refund|refunding|shared|share|sharing|published|publish|publishing|notified|notify|notifying|invited|invite|inviting)\b/,
  /\b(?:would|could|might|may)\s+(?:be\s+)?(?:changed|change|changing|updated|update|updating|modified|modify|modifying|wrote|write|writing|mutated|mutation|mutate|deleted|delete|deleting|created|create|creating|disabled|disable|disabling|enabled|enable|enabling|suspended|suspend|suspending|deactivated|deactivate|deactivating|removed|remove|removing|reset|resetting|used|use|using|clicked|click|accepted|accept|allowed|allow|granted|grant|granting|revoked|revoke|revoking|sent|send|sending|emailed|emailing|texted|texting|messaged|messaging|charged|charge|charging|refunded|refund|refunding|shared|share|sharing|published|publish|publishing|notified|notify|notifying|invited|invite|inviting)\b(?:\s+\w+){0,8}\s+(?:prod|production|backend|appwrite|database|db|native|real|generated|credential|credentials|cleanup|email|emails|sms|text|texts|message|messages|payment|payments|card|cards|customer|customers|data|user|users|account|accounts|permission|permissions|schema|index|access)\b/,
  /\b(?:changing|updating|modifying|writing|mutating|deleting|creating|disabling|enabling|suspending|deactivating|removing|resetting|using|clicking|granting|revoking|sending|emailing|texting|messaging|charging|refunding|sharing|publishing|notifying|inviting)\b(?:\s+\w+){0,8}\s+(?:prod|production|backend|appwrite|database|db|native|real|generated|credential|credentials|cleanup|email|emails|sms|text|texts|message|messages|payment|payments|card|cards|customer|customers|data|user|users|account|accounts|permission|permissions|schema|index|access)\b(?:\s+\w+){0,6}\s+(?:would|could|might|may)\b/,
  /\b(?:avoid|avoids|avoided|avoiding)\b(?:\s+\w+){0,8}\s+(?:changed|change|changing|updated|update|updating|modified|modify|modifying|wrote|write|writing|mutated|mutation|mutate|deleted|delete|deleting|created|create|creating|disabled|disable|disabling|enabled|enable|enabling|suspended|suspend|suspending|deactivated|deactivate|deactivating|removed|remove|removing|reset|resetting|used|use|using|clicked|click|accepted|accept|allowed|allow|granted|grant|granting|revoked|revoke|revoking|sent|send|sending|emailed|emailing|texted|texting|messaged|messaging|charged|charge|charging|refunded|refund|refunding|shared|share|sharing|published|publish|publishing|notified|notify|notifying|invited|invite|inviting)\b(?:\s+\w+){0,8}\s+(?:prod|production|backend|appwrite|database|db|native|real|generated|credential|credentials|cleanup|email|emails|sms|text|texts|message|messages|payment|payments|card|cards|customer|customers|data|user|users|account|accounts|permission|permissions|schema|index|access)\b/,
  /\b(?:prod|production)\b(?:\s+\w+){0,8}\s+(?:backend|appwrite|database|db|permission|permissions|schema|index|email|emails|sms|text|texts|message|messages|payment|payments|card|cards|customer|customers|data|user|users|account|accounts|access|cleanup)\b(?:\s+\w+){0,5}\s+(?:would|could|might|may)\s+(?:be\s+)?(?:changed|updated|modified|written|mutated|deleted|created|disabled|enabled|suspended|deactivated|removed|reset|used|clicked|accepted|allowed|granted|revoked|sent|emailed|texted|messaged|charged|refunded|shared|published|notified|invited)\b/,
  /\b(?:would|could|might|may)\s+(?:be\s+)?(?:changed|change|updated|update|modified|modify|written|write|mutated|mutate|deleted|delete|created|create|disabled|disable|enabled|enable|suspended|suspend|deactivated|deactivate|removed|remove|reset|used|use|clicked|click|accepted|accept|allowed|allow|granted|grant|revoked|revoke|sent|send|emailed|email|texted|text|messaged|message|charged|charge|refunded|refund|shared|share|published|publish|notified|notify|invited|invite)\b(?:\s+\w+){0,8}\s+(?:prod|production|backend|appwrite|database|db|native|real|generated|credential|credentials|cleanup|email|emails|sms|text|texts|message|messages|payment|payments|card|cards|customer|customers|data|user|users|account|accounts|permission|permissions|schema|index|access)\b/,
];

const performedApprovalRiskActionPatternSource = '\\b(?:changed|changing|updated|updating|modified|modifying|inserted|inserting|upserted|upserting|patched|patching|uploaded|uploading|applied|applying|ran|running|executed|executing|wrote|writing|mutated|mutating|deleted|deleting|created|creating|disabled|disabling|enabled|enabling|suspended|suspending|deactivated|deactivating|removed|removing|reset|resetting|used|using|clicked|accepted|allowed|granted|granting|revoked|revoking|logged|sent|sending|emailed|emailing|texted|texting|messaged|messaging|charged|charging|refunded|refunding|shared|sharing|published|publishing|notified|notifying|invited|inviting)\\b|\\b(?:logged|log|logging|signed|sign|signing)\\s+in\\b';
const performedApprovalRiskActionPatterns = [new RegExp(performedApprovalRiskActionPatternSource, 'i')];
const approvalObjectBeforeVerbRiskPatternSource = '\\b(?:prod|production)\\b(?:\\s+\\w+){0,8}\\s+(?:backend|appwrite|database|db|permission|permissions|schema|index|indexes|indices|migration|migrations|email|emails|sms|text|texts|message|messages|payment|payments|charge|charges|refund|refunds|receipt|receipts|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|data|record|records|file|files|link|links|notification|notifications|invite|invites|invitation|invitations|webhook|webhooks|user|users|account|accounts|access|cleanup|side\\s*effects?)\\b(?:\\s+\\w+){0,6}\\s+(?:changed|changing|updated|updating|modified|modifying|inserted|inserting|upserted|upserting|patched|patching|uploaded|uploading|applied|applying|ran|running|executed|executing|wrote|writing|mutated|mutating|deleted|deleting|created|creating|disabled|disabling|enabled|enabling|suspended|suspending|deactivated|deactivating|removed|removing|reset|resetting|sent|sending|emailed|emailing|texted|texting|messaged|messaging|charged|charging|refunded|refunding|shared|sharing|published|publishing|notified|notifying|invited|inviting)\\b';
const approvalRiskLeadPattern = '(?:changed|changing|updated|updating|modified|modifying|inserted|inserting|upserted|upserting|patched|patching|uploaded|uploading|applied|applying|ran|running|executed|executing|wrote|writing|mutated|mutating|deleted|deleting|created|creating|disabled|disabling|enabled|enabling|suspended|suspending|deactivated|deactivating|removed|removing|reset|resetting|used|using|clicked|accepted|allowed|granted|granting|revoked|revoking|logged|log|logging|signed|sign|signing|sent|sending|emailed|emailing|texted|texting|messaged|messaging|charged|charging|refunded|refunding|shared|sharing|published|publishing|notified|notifying|invited|inviting|production|prod|backend|appwrite|database|db|native|real|generated)';
const approvalClauseBoundaryPattern = new RegExp(`\\b(?:but|however|yet|except|though|although|whereas|then|because|since)\\b|\\b(?:before|after|while|when|during|since)\\b(?:\\s+(?!(?:${approvalRiskLeadPattern})\\b)\\w+){0,3}\\s+(?=(?:${approvalRiskLeadPattern})\\b)|\\band\\s+(?=(?:${approvalRiskLeadPattern})\\b)`, 'i');
const approvalContextConnectorPattern = /\b(?:but|however|yet|except|though|although|whereas|then|because|since|before|after|while|when|during|following|as)\b/i;
const nearNegationBeforeApprovalActionPattern = /\b(?:no|not|never|without|zero|0|none)(?:\s+\w+){0,2}$/i;
const nonAffirmativeApprovalPattern = /\b(?:not|never|no|without|denied|missing|blocked|rejected)\b(?:\s+\w+){0,3}\s+(?:approved|approval|authorized|authorised|authorization|authorisation|allowed|permission|consent|confirmed)\b|\b(?:approved|approval|authorized|authorised|authorization|authorisation|allowed|permission|consent|confirmed)\b(?:\s+\w+){0,3}\s+(?:not|never|denied|missing|blocked|rejected)\b|\b(?:approved|approval|authorized|authorised|authorization|authorisation|allowed|permission|consent|confirmed)\b(?:\s+\w+){0,3}\s+not\s+(?:required|needed|necessary|applicable)\b/i;
const explicitApprovalGrantPattern = /\b(?:approved|authorized|authorised|confirmed|okayed|signed off|allowed)\b|\b(?:approval|authorization|authorisation|permission|consent)\b(?:\s+\w+){0,3}\s+granted\b|\bgranted(?:\s+\w+){0,3}\s+(?:approval|authorization|authorisation|permission|consent)\b/i;
const nonProofApprovalPattern = /\b(?:approval|authorization|authorisation|permission|consent)\b(?:\s+\w+){0,3}\s+(?:required|requested|pending|awaiting|needed|necessary)\b|\b(?:requires?|requested|requesting|pending|awaiting|waiting|needs?|needed)\b(?:\s+\w+){0,3}\s+(?:approval|authorization|authorisation|permission|consent)\b/i;
const deniedApprovalProofPattern = /\b(?:approval|approved|authorization|authorisation|authorized|authorised|permission|consent|confirmation|confirmed)\b.*\b(?:denied|rejected|blocked|pending|awaiting|requested)\b|\b(?:denied|rejected|blocked|pending|awaiting|requested)\b.*\b(?:approval|approved|authorization|authorisation|authorized|authorised|permission|consent|confirmation|confirmed)\b/i;
const generatedCredentialCleanupNegativePattern = /\b(?:pending|requested|requesting|awaiting|required|needed|failed|failure|failing|not|never|without|unable|cannot|can t|could not|missing|incomplete)\b(?:\s+\w+){0,5}\s+(?:cleanup|cleaned|delete|deleted|deletion|remove|removed|removal|purge|purged)\b|\b(?:cleanup|cleaned|delete|deleted|deletion|remove|removed|removal|purge|purged)\b(?:\s+\w+){0,5}\s+(?:pending|requested|requesting|awaiting|required|needed|failed|failure|failing|not|never|unable|cannot|can t|could not|missing|incomplete)\b/i;
const generatedCredentialCleanupPositivePattern = /\b(?:cleaned up|cleaned-up|deleted|deletion|removed|removal|purged|revoked)\b|\bcleanup\b(?:\s+\w+){0,5}\s+(?:pass|passed|passing|clean|succeeded|success|ok|complete|completed|done|confirmed|verified)\b|\b(?:confirmed|verified|passed|complete|completed|done|success|succeeded|clean)\b(?:\s+\w+){0,5}\s+(?:cleanup|delete|deleted|deletion|remove|removed|removal|purge|purged)\b/i;

function firstPatternIndex(text, patterns) {
  return patterns.reduce((earliest, pattern) => {
    const match = text.match(pattern);
    if (!match || match.index === undefined) return earliest;
    return earliest === -1 ? match.index : Math.min(earliest, match.index);
  }, -1);
}

function hasPerformedApprovalRiskAction(text) {
  return matchesAny(text, performedApprovalRiskActionPatterns);
}

function isNonRiskApprovalEvidence(text) {
  if (/\b(?:no|without)(?:\s+\w+){0,2}\s+approval\b/.test(text)) return false;
  if (matchesAny(text, hypotheticalApprovalEvidencePatterns)) return true;
  if (matchesAny(text, nonGeneratedCredentialApprovalEvidencePatterns)) return true;
  if (matchesAny(text, actionObjectNegatedApprovalEvidencePatterns)) return true;
  if (matchesAny(text, postposedNonRiskApprovalEvidencePatterns)) return true;
  if (!/\b(?:prod|production)\b/.test(text) && matchesAny(text, codeOnlyBackendSchemaRepairApprovalEvidencePatterns)) return true;
  const negationIndex = firstPatternIndex(text, [/\b(?:no|not|never|without|read only|readonly)\b/]);
  const actionIndex = firstPatternIndex(text, performedApprovalRiskActionPatterns);
  if (matchesAny(text, nonRiskApprovalEvidencePatterns)) {
    return actionIndex === -1 || (negationIndex !== -1 && negationIndex <= actionIndex);
  }
  if (matchesAny(text, codePreventionOnlyApprovalEvidencePatterns)) return true;
  if (matchesAny(text, preventionOnlyApprovalEvidencePatterns)) {
    return !hasPerformedApprovalRiskAction(text);
  }
  return false;
}

function approvalEvidenceSegments(text) {
  return String(text)
    .split(/[;,\n|]+|\.(?=\s|$)/)
    .flatMap((segment) => normalizeEvidenceText(segment).split(approvalClauseBoundaryPattern))
    .map((segment) => segment.trim())
    .filter(Boolean);
}

function approvalRiskActionSubsegments(text) {
  const segments = [];
  const actionPattern = new RegExp(performedApprovalRiskActionPatternSource, 'gi');
  for (const match of text.matchAll(actionPattern)) {
    if (match.index === undefined || match.index === 0) continue;
    const prefix = text.slice(0, match.index).trim();
    if (nearNegationBeforeApprovalActionPattern.test(prefix)) continue;
    const contextPrefix = prefix.split(/\s+/).slice(-8).join(' ');
    const actionSegment = text.slice(match.index).trim();
    segments.push(actionSegment);
    if (hasText(contextPrefix)) {
      segments.push(`${contextPrefix} ${actionSegment}`);
      const connectorClauses = contextPrefix.split(approvalContextConnectorPattern).map((part) => part.trim()).filter(Boolean);
      const lastClause = connectorClauses.at(-1);
      if (hasText(lastClause) && lastClause !== contextPrefix) segments.push(`${lastClause} ${actionSegment}`);
    }
  }
  return segments;
}

function approvalObjectBeforeVerbSubsegments(text) {
  const segments = [];
  const prodPattern = /\b(?:prod|production)\b/gi;
  const objectBeforeVerbPattern = new RegExp(`^${approvalObjectBeforeVerbRiskPatternSource}`, 'i');
  for (const prodMatch of text.matchAll(prodPattern)) {
    if (prodMatch.index === undefined) continue;
    const match = text.slice(prodMatch.index).match(objectBeforeVerbPattern);
    if (!match) continue;
    const prefix = text.slice(0, prodMatch.index).trim().split(/\s+/).slice(-3).join(' ');
    if (nearNegationBeforeApprovalActionPattern.test(prefix)) continue;
    segments.push(match[0].trim());
  }
  return segments;
}

function approvalRiskCandidateSubsegments(text) {
  return [
    ...approvalObjectBeforeVerbSubsegments(text),
    ...approvalRiskActionSubsegments(text),
  ];
}

function hasAffirmativeApprovalText(text) {
  if (!explicitApprovalGrantPattern.test(text)) return false;
  if (deniedApprovalProofPattern.test(text)) return false;
  if (nonAffirmativeApprovalPattern.test(text)) return false;
  if (nonProofApprovalPattern.test(text) && !explicitApprovalGrantPattern.test(text)) return false;
  return true;
}

function hasPositiveGeneratedCredentialCleanupProof(cleanupProof) {
  const proofText = normalizeEvidenceText(textOf(cleanupProof));
  if (!hasText(proofText)) return false;
  if (generatedCredentialCleanupNegativePattern.test(proofText)) return false;
  return generatedCredentialCleanupPositivePattern.test(proofText);
}

function sideEffectKeysForCategoryText(category, text) {
  const sideEffects = approvalBoundarySideEffectPatterns.get(category);
  if (!sideEffects) return [category];
  const keys = sideEffects
    .filter(([, patterns]) => matchesAny(text, patterns))
    .map(([key]) => key);
  if (keys.length > 0) return keys;
  const fallbackSideEffects = approvalBoundaryFallbackSideEffectPatterns.get(category) || [];
  for (const [key, patterns] of fallbackSideEffects) {
    if (matchesAny(text, patterns)) return [key];
  }
  return [category];
}

function normalizeSideEffectKey(value) {
  return hasText(value) ? normalizeEvidenceText(value).replace(/\s+/g, '-') : '';
}

function allowedSideEffectKeysForCategory(category) {
  return new Set([
    category,
    ...(approvalBoundarySideEffectPatterns.get(category) || []).map(([key]) => key),
    ...(approvalBoundaryFallbackSideEffectPatterns.get(category) || []).map(([key]) => key),
  ]);
}

function categoryApprovalProofMatches(category, text) {
  return matchesAny(text, approvalBoundaryCategoryProofPatterns.get(category) || []);
}

function approvalBoundaryProofTexts(boundary) {
  return [
    boundary?.reason,
    ...(Array.isArray(boundary?.evidence) ? boundary.evidence : []),
  ].filter(hasText);
}

function sideEffectMentionMatches(category, sideEffectKey, text) {
  const expectedKey = sideEffectKey || category;
  if (expectedKey === category) return categoryApprovalProofMatches(category, text);
  const mentionPatterns = new Map([
    ['prod-sms', [/\b(?:prod|production)\b.*\b(?:sms|text|texts|message|messages)\b/, /\b(?:sms|text|texts|message|messages)\b.*\b(?:prod|production)\b/]],
    ['prod-email', [/\b(?:prod|production)\b.*\b(?:email|emails|receipt|receipts)\b/, /\b(?:email|emails|receipt|receipts)\b.*\b(?:prod|production)\b/]],
    ['prod-payment', [/\b(?:prod|production)\b.*\b(?:payment|payments|charge|charges|refund|refunds|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|billing)\b/, /\b(?:payment|payments|charge|charges|refund|refunds|card|cards|customer|customers|subscription|subscriptions|invoice|invoices|billing)\b.*\b(?:prod|production)\b/]],
    ['prod-appwrite-permission', [/\b(?:prod|production)\b.*\bappwrite\b.*\b(?:permission|permissions|access)\b/, /\bappwrite\b.*\b(?:permission|permissions|access)\b.*\b(?:prod|production)\b/]],
    ['prod-appwrite-schema', [/\b(?:prod|production)\b.*\bappwrite\b.*\b(?:schema|index|indexes|indices|migration|migrations)\b/, /\bappwrite\b.*\b(?:schema|index|indexes|indices|migration|migrations)\b.*\b(?:prod|production)\b/]],
    ['prod-db-schema', [/\b(?:prod|production)\b.*\b(?:database|db)\b.*\b(?:schema|index|indexes|indices|migration|migrations)\b/, /\b(?:database|db)\b.*\b(?:schema|index|indexes|indices|migration|migrations)\b.*\b(?:prod|production)\b/]],
    ['prod-db-permission', [/\b(?:prod|production)\b.*\b(?:database|db)\b.*\b(?:permission|permissions|access)\b/, /\b(?:database|db)\b.*\b(?:permission|permissions|access)\b.*\b(?:prod|production)\b/]],
    ['prod-backend-schema', [/\b(?:prod|production)\b.*\bbackend\b.*\b(?:schema|index|indexes|indices|migration|migrations)\b/, /\bbackend\b.*\b(?:schema|index|indexes|indices|migration|migrations)\b.*\b(?:prod|production)\b/]],
    ['prod-user-account', [/\b(?:prod|production)\b.*\b(?:user|users|account|accounts|access)\b/, /\b(?:user|users|account|accounts|access)\b.*\b(?:prod|production)\b/]],
    ['prod-data-sharing', [/\b(?:prod|production)\b.*\b(?:data|file|files|link|links)\b/, /\b(?:data|file|files|link|links)\b.*\b(?:prod|production)\b/]],
  ]);
  return matchesAny(text, mentionPatterns.get(expectedKey) || []);
}

function hasContradictorySideEffectApprovalProof(category, sideEffectKey, proofTexts) {
  const expectedKey = sideEffectKey || category;
  for (const text of proofTexts) {
    for (const segment of approvalEvidenceSegments(text)) {
      if (!isNonRiskApprovalEvidence(segment) && !deniedApprovalProofPattern.test(segment)) continue;
      const segmentKeys = sideEffectKeysForCategoryText(category, segment);
      if (expectedKey === category) {
        if (categoryApprovalProofMatches(category, segment) || segmentKeys.some((key) => key !== category)) return true;
      } else if (segmentKeys.includes(expectedKey) || sideEffectMentionMatches(category, expectedKey, segment)) {
        return true;
      }
    }
  }
  return false;
}

function approvalBoundaryRequirementsForText(text) {
  const requirements = new Map();
  const segments = approvalEvidenceSegments(text);
  for (const normalized of segments) {
    for (const subsegment of approvalRiskCandidateSubsegments(normalized)) {
      if (isNonRiskApprovalEvidence(subsegment)) continue;
      for (const [category, patterns] of approvalBoundaryEvidencePatterns.entries()) {
        if (!matchesAny(subsegment, patterns)) continue;
        for (const sideEffectKey of sideEffectKeysForCategoryText(category, subsegment)) {
          requirements.set(`${category}:${sideEffectKey}`, { category, sideEffectKey });
        }
      }
    }
    if (isNonRiskApprovalEvidence(normalized)) continue;
    for (const [category, patterns] of approvalBoundaryEvidencePatterns.entries()) {
      if (!matchesAny(normalized, patterns)) continue;
      for (const sideEffectKey of sideEffectKeysForCategoryText(category, normalized)) {
        requirements.set(`${category}:${sideEffectKey}`, { category, sideEffectKey });
      }
    }
  }
  return Array.from(requirements.values());
}

function inferredApprovalBoundaryRequirements(state) {
  const requirements = new Map();
  const texts = e2ePolicyEvidenceStrings(state.e2ePolicy);
  if (Array.isArray(state.guardrails)) {
    for (const guardrail of state.guardrails) {
      if (!isObject(guardrail) || guardrail.kind === 'eval') continue;
      texts.push(...collectStrings(guardrail.evidence), ...collectStrings(guardrail.reason));
    }
  }
  if (Array.isArray(state.agentWork)) {
    for (const work of state.agentWork) {
      if (!isObject(work)) continue;
      texts.push(...collectStrings(work.evidence), ...collectStrings(work.reason));
    }
  }
  if (Array.isArray(state.steps)) {
    for (const step of state.steps) texts.push(...stepApprovalEvidenceStrings(step));
  }
  for (const text of texts) {
    for (const requirement of approvalBoundaryRequirementsForText(text)) {
      requirements.set(`${requirement.category}:${requirement.sideEffectKey}`, requirement);
    }
  }
  return Array.from(requirements.values());
}

function approvedSideEffectKeysForBoundary(boundary, category) {
  const keys = new Set();
  const structuredKey = normalizeSideEffectKey(boundary?.sideEffectKey);
  const proofTexts = approvalBoundaryProofTexts(boundary);
  if (proofTexts.some((text) => deniedApprovalProofPattern.test(normalizeEvidenceText(text)))) return [];
  const approvalProofText = normalizeEvidenceText(proofTexts.join(' '));
  if (
    structuredKey
    && allowedSideEffectKeysForCategory(category).has(structuredKey)
    && hasAffirmativeApprovalText(approvalProofText)
    && !hasContradictorySideEffectApprovalProof(category, structuredKey, proofTexts)
    && (structuredKey !== category || categoryApprovalProofMatches(category, approvalProofText))
  ) {
    keys.add(structuredKey);
  }
  const segments = [
    ...approvalEvidenceSegments(boundary?.reason || ''),
    ...approvalEvidenceSegments(textOf(boundary?.evidence)),
  ];
  for (const segment of segments) {
    if (isNonRiskApprovalEvidence(segment)) continue;
    if (!hasAffirmativeApprovalText(segment)) continue;
    for (const key of sideEffectKeysForCategoryText(category, segment)) {
      if (
        !hasContradictorySideEffectApprovalProof(category, key, proofTexts)
        && (key !== category || categoryApprovalProofMatches(category, segment))
      ) {
        keys.add(key);
      }
    }
  }
  return Array.from(keys);
}

function approvalBoundaryMatchesRequirement(boundary, requirement) {
  if (boundary?.category !== requirement.category) return false;
  const approvedKeys = approvedSideEffectKeysForBoundary(boundary, requirement.category);
  if (!requirement.sideEffectKey) return approvedKeys.length > 0;
  return approvedKeys.includes(requirement.sideEffectKey);
}

function normalizeIssueClass(issueClass) {
  return issueClass.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
}

function escapedRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function openLearningFindings(state) {
  return Array.isArray(state.findings)
    ? state.findings.filter((finding) => finding?.ownerStage === 'he-learn' && finding?.repairType === 'learning' && ['open', 'owned', 'blocked'].includes(finding.status))
    : [];
}

function learningFindingMatchesIssueClass(finding, issueClass) {
  const structuredIssueClass = hasText(finding?.issueClass) ? normalizeIssueClass(finding.issueClass) : '';
  if (structuredIssueClass && structuredIssueClass === issueClass) return true;
  const findingText = normalizeIssueClass([
    finding.summary,
    finding.owner,
    textOf(finding.ownerProof),
    textOf(finding.artifacts),
  ].filter(Boolean).join(' '));
  return new RegExp(`(?:^|-)${escapedRegExp(issueClass)}(?:-|$)`).test(findingText);
}

function validateApprovalBoundaries(state, errors) {
  const boundaries = state.approvalBoundaries;
  if (boundaries !== undefined && !Array.isArray(boundaries)) {
    errors.push('approvalBoundaries must be an array');
    return;
  }
  if (Array.isArray(boundaries)) {
    for (const [index, boundary] of boundaries.entries()) {
      if (!isObject(boundary)) {
        errors.push(`approvalBoundaries[${index}] must be an object`);
        continue;
      }
      for (const key of ['id', 'category', 'status', 'reason']) {
        if (!hasText(boundary[key])) errors.push(`approvalBoundaries[${index}].${key} is required`);
      }
      if (boundary.category && !approvalCategories.has(boundary.category)) errors.push(`approvalBoundaries[${index}].category is invalid`);
      if (boundary.status && !approvalStatuses.has(boundary.status)) errors.push(`approvalBoundaries[${index}].status must be approved, blocked, or not_required`);
      if (!stringArray(boundary.evidence) || boundary.evidence.length === 0 || !boundary.evidence.every(hasText)) errors.push(`approvalBoundaries[${index}].evidence must be non-empty string[]`);
      if (['real-credentials', 'generated-credentials'].includes(boundary.category)) {
        if (!hasText(boundary.redactedCredentialRef)) errors.push(`approvalBoundaries[${index}].redactedCredentialRef is required for ${boundary.category}`);
        if (!hasText(boundary.dataScope)) errors.push(`approvalBoundaries[${index}].dataScope is required for ${boundary.category}`);
      }
      if (boundary.category === 'generated-credentials') {
        if (!stringArray(boundary.cleanupProof) || boundary.cleanupProof.length === 0 || !boundary.cleanupProof.every(hasText)) {
          errors.push(`approvalBoundaries[${index}].cleanupProof must be non-empty string[] for generated credentials`);
        } else if (!hasPositiveGeneratedCredentialCleanupProof(boundary.cleanupProof)) {
          errors.push(`approvalBoundaries[${index}].cleanupProof must include positive cleanup result for generated credentials`);
        }
      }
    }
  }

  const configuredRequired = state.e2ePolicy?.requiredApprovalBoundaries;
  if (configuredRequired !== undefined && !stringArray(configuredRequired)) {
    errors.push('e2ePolicy.requiredApprovalBoundaries must be string[]');
    return;
  }
  const inferredRequired = inferredApprovalBoundaryRequirements(state);
  const required = [
    ...(Array.isArray(configuredRequired) ? configuredRequired.map((category) => ({ category, sideEffectKey: '' })) : []),
    ...inferredRequired,
  ].filter((requirement, index, requirements) => (
    requirements.findIndex((item) => item.category === requirement.category && item.sideEffectKey === requirement.sideEffectKey) === index
  ));
  if (required.length === 0) return;
  if (state.next?.ready !== true) return;
  if (!Array.isArray(boundaries)) {
    errors.push(`approvalBoundaries are required when ${Array.isArray(configuredRequired) && configuredRequired.length > 0 ? 'e2ePolicy.requiredApprovalBoundaries is non-empty' : 'guardrail evidence records risky actions'}`);
    return;
  }
  for (const requirement of required) {
    const { category, sideEffectKey } = requirement;
    if (!approvalCategories.has(category)) {
      errors.push(`e2ePolicy.requiredApprovalBoundaries includes invalid ${category}`);
      continue;
    }
    const matchingBoundaries = boundaries.filter((item) => approvalBoundaryMatchesRequirement(item, requirement));
    if (matchingBoundaries.some((item) => item.status === 'approved')) continue;
    if (matchingBoundaries.length === 0) {
      errors.push(sideEffectKey
        ? `approvalBoundaries requires ${category} side effect ${sideEffectKey}`
        : `approvalBoundaries requires ${category}`);
      continue;
    }
    errors.push(sideEffectKey
      ? `approvalBoundaries ${category} side effect ${sideEffectKey} must be approved before ready handoff`
      : `approvalBoundaries ${category} must be approved before ready handoff`);
  }
}

function validateRepeatMisses(state, errors) {
  const repeatMisses = state.repeatMisses;
  if (repeatMisses !== undefined && !Array.isArray(repeatMisses)) {
    errors.push('repeatMisses must be an array');
    return;
  }
  if (!Array.isArray(repeatMisses) || repeatMisses.length === 0) return;
  for (const [index, miss] of repeatMisses.entries()) {
    if (!isObject(miss)) {
      errors.push(`repeatMisses[${index}] must be an object`);
      continue;
    }
    if (!hasText(miss.issueClass)) {
      errors.push(`repeatMisses[${index}].issueClass is required`);
    } else if (!normalizeIssueClass(miss.issueClass)) {
      errors.push(`repeatMisses[${index}].issueClass must include an alphanumeric slug`);
    }
    if (!stringArray(miss.evidence) || miss.evidence.length === 0 || !miss.evidence.every(hasText)) errors.push(`repeatMisses[${index}].evidence must be non-empty string[]`);
  }
  const grouped = new Map();
  for (const miss of repeatMisses) {
    if (!hasText(miss?.issueClass)) continue;
    const issueClass = normalizeIssueClass(miss.issueClass);
    if (!issueClass) continue;
    grouped.set(issueClass, (grouped.get(issueClass) || 0) + 1);
  }
  const repeatedClasses = Array.from(grouped.entries()).filter(([, count]) => count >= 2).map(([issueClass]) => issueClass);
  if (!repeatedClasses.length) return;
  const learningFindings = openLearningFindings(state);
  for (const issueClass of repeatedClasses) {
    if (!learningFindings.some((finding) => learningFindingMatchesIssueClass(finding, issueClass))) {
      errors.push(`repeatMisses ${issueClass} requires a he-learn learning finding`);
    }
  }
}

export function validateComplianceState(state, errors) {
  validateApprovalBoundaries(state, errors);
  validateRepeatMisses(state, errors);
}
