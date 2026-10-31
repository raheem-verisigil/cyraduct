'use strict';
const assert=require('node:assert/strict');const fs=require('node:fs');const os=require('node:os');const path=require('node:path');const crypto=require('node:crypto');const cp=require('node:child_process');
const root=path.resolve(__dirname,'..');const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'ncs-'));
try{
 const evidence=Buffer.from('NCS evidence fixture v0.1');fs.writeFileSync(path.join(tmp,'evidence.txt'),evidence);
 const hash=crypto.createHash('sha256').update(evidence).digest('hex');
 const manifest={schema_version:'ncs-evidence-manifest/0.1',assessment_id:'NCS-SMOKE-001',artifact:{artifact_id:'fixture-model',artifact_digest:'sha256:'+'a'.repeat(64)},source:{repository:'fixture/repo',commit:'abcdef1234567',workflow_run:null},evidence:[{evidence_id:'E-001',path:'evidence.txt',sha256:hash,classification:'REQUIRED'}],limitations:[]};
 const mp=path.join(tmp,'manifest.json');fs.writeFileSync(mp,JSON.stringify(manifest));
 let v=cp.spawnSync(process.execPath,[path.join(root,'verifier/verify-manifest.js'),mp],{encoding:'utf8'});assert.equal(v.status,0,v.stderr);assert.equal(JSON.parse(v.stdout).integrity_status,'PASS');
 manifest.evidence[0].sha256='0'.repeat(64);fs.writeFileSync(mp,JSON.stringify(manifest));v=cp.spawnSync(process.execPath,[path.join(root,'verifier/verify-manifest.js'),mp],{encoding:'utf8'});assert.equal(v.status,1);assert.equal(JSON.parse(v.stdout).integrity_status,'FAIL');
 const record={assessment_id:'NCS-SMOKE-001',decision_status:'IN_PROGRESS',stages:[]};v=cp.spawnSync(process.execPath,[path.join(root,'compiler/compile-assessment.js')],{input:JSON.stringify(record),encoding:'utf8'});assert.equal(v.status,0);const c=JSON.parse(v.stdout);assert.equal(c.status,'BLOCKED_INCOMPLETE_EVIDENCE');assert.equal(c.grade,null);assert.equal(c.certificate,null);
 console.log('NCS authority smoke tests: 3 passed, 0 failed');
}finally{fs.rmSync(tmp,{recursive:true,force:true});}
