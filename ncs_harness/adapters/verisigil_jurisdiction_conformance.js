'use strict';
// NCS adapter: execute VeriSigil jurisdiction vectors against a LOCAL or approved staging API.
// This script does not change VeriSigil source and does not call production by default.
// Required: VERISIGIL_API_ROOT, VERISIGIL_API_KEY, VERISIGIL_VECTORS_PATH.
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const apiRoot = process.env.VERISIGIL_API_ROOT;
const apiKey = process.env.VERISIGIL_API_KEY;
const vectorsPath = process.env.VERISIGIL_VECTORS_PATH;
if (!apiRoot || !apiKey || !vectorsPath) {
  console.error('Set VERISIGIL_API_ROOT, VERISIGIL_API_KEY and VERISIGIL_VECTORS_PATH.');
  process.exit(2);
}
const { VeriSigilClient } = require(path.join(apiRoot, 'verisigil_sdk.js'));
const suite = JSON.parse(fs.readFileSync(vectorsPath, 'utf8'));
const vectors = (suite.vectors || []).filter(v => /^VEC-0(4[3-9]|5[0-8])$/.test(v.id));
if (vectors.length !== 16) {
  console.error(`Expected 16 jurisdiction vectors; found ${vectors.length}. Refusing partial run.`);
  process.exit(2);
}
function payloadOf(response) {
  if (!response || typeof response !== 'object') throw new Error('API response is not an object');
  for (const key of ['result', 'data']) {
    if (response[key] && typeof response[key] === 'object') return response[key];
  }
  return response;
}
(async () => {
  const client = new VeriSigilClient(apiKey, apiRoot);
  let passed = 0, failed = 0;
  for (const v of vectors) {
    try {
      const i = v.input;
      const response = await client.resolveJurisdiction(
        i.action_type, i.data_subject_region, i.infrastructure_region, i.agent_owner_jurisdiction
      );
      const actual = payloadOf(response);
      for (const field of ['primary_regime', 'decision', 'conflicts']) {
        assert(Object.prototype.hasOwnProperty.call(actual, field), `${v.id}: response missing required field ${field}`);
      }
      assert.strictEqual(actual.primary_regime, v.expected_primary_regime, `${v.id}: primary_regime mismatch`);
      assert.strictEqual(actual.decision, v.expected_decision, `${v.id}: decision mismatch`);
      assert.strictEqual(actual.conflicts, v.expected_conflicts, `${v.id}: conflicts mismatch`);
      passed++;
      console.log(`PASS ${v.id}`);
    } catch (e) {
      failed++;
      console.error(`FAIL ${v.id}: ${e.message}`);
    }
  }
  console.log(JSON.stringify({suite:'NCS-VSA jurisdiction vectors', total:vectors.length, passed, failed, status:failed===0?'PASS':'FAIL'}, null, 2));
  process.exit(failed === 0 ? 0 : 1);
})().catch(e => { console.error(e); process.exit(1); });
