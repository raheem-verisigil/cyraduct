'use strict';

// Deterministic provisional compiler. It does not certify or grade a model.
// Input: assessment record JSON on stdin. Output: machine-readable status JSON.
const fs = require('fs');
const raw = fs.readFileSync(0, 'utf8');
const r = JSON.parse(raw);
const mandatory = ['artifact_identity','build_record','native_baseline','policy_delta','independent_review'];
const stages = new Map((r.stages || []).map(s => [s.name, s.status]));
const missing = mandatory.filter(name => stages.get(name) !== 'COMPLETED');
const blocked = missing.length > 0 || r.decision_status === 'BLOCKED';
const output = {
  schema_version: 'ncs-compiler-output/0.1',
  assessment_id: r.assessment_id || null,
  status: blocked ? 'BLOCKED_INCOMPLETE_EVIDENCE' : 'REVIEW_REQUIRED',
  missing_or_incomplete_stages: missing,
  grade: null,
  certificate: null,
  rule: 'No grade or certificate is emitted by this prototype. Mandatory evidence and independent review must be complete before authorized adjudication.'
};
process.stdout.write(JSON.stringify(output, null, 2) + '\n');
