'use strict';
// Offline SHA-256 manifest verifier. Integrity is not truth or completeness.
const fs = require('fs'); const path = require('path'); const crypto = require('crypto');
const manifestPath = process.argv[2];
if (!manifestPath) { console.error('Usage: node verify-manifest.js <manifest.json>'); process.exit(2); }
const base = path.dirname(path.resolve(manifestPath));
const m = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const errors = [];
if (m.schema_version !== 'ncs-evidence-manifest/0.1') errors.push('Unsupported schema_version');
if (!m.assessment_id) errors.push('Missing assessment_id');
if (!m.artifact?.artifact_digest?.match(/^sha256:[a-f0-9]{64}$/)) errors.push('Invalid artifact_digest');
for (const e of (m.evidence || [])) {
  const target = path.resolve(base, e.path);
  if (!target.startsWith(base + path.sep)) { errors.push(e.evidence_id + ': path escapes manifest directory'); continue; }
  if (!fs.existsSync(target) || !fs.statSync(target).isFile()) { errors.push(e.evidence_id + ': file missing'); continue; }
  const actual = crypto.createHash('sha256').update(fs.readFileSync(target)).digest('hex');
  if (actual !== e.sha256) errors.push(e.evidence_id + ': SHA-256 mismatch');
}
const result = {schema_version:'ncs-verifier-result/0.1',assessment_id:m.assessment_id||null,integrity_status:errors.length?'FAIL':'PASS',evidence_items:(m.evidence||[]).length,errors,limitations:['Digest verification proves byte integrity only; it does not prove source authenticity, truth, completeness, signer identity, or model behaviour.','Signature and transparency-log verification are not implemented in v0.1.']};
console.log(JSON.stringify(result,null,2)); if(errors.length) process.exit(1);
