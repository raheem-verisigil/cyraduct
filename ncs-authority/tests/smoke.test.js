'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto'),cp=require('node:child_process');
const root=path.resolve(__dirname,'..'),tmp=fs.mkdtempSync(path.join(os.tmpdir(),'ncs-'));
try{
 const data=Buffer.from('NCS evidence fixture v0.2');fs.writeFileSync(path.join(tmp,'evidence.txt'),data);
 const hash=crypto.createHash('sha256').update(data).digest('hex'),mp=path.join(tmp,'manifest.json');
 const base=()=>({schema_version:'ncs-evidence-manifest/0.1',assessment_id:'NCS-SMOKE-001',artifact:{artifact_id:'fixture-model',artifact_digest:'sha256:'+'a'.repeat(64)},source:{repository:'fixture/repo',commit:'abcdef1234567',workflow_run:null},evidence:[{evidence_id:'E-001',path:'evidence.txt',sha256:hash,classification:'REQUIRED'}],limitations:[]});
 const verify=m=>{fs.writeFileSync(mp,JSON.stringify(m));return cp.spawnSync(process.execPath,[path.join(root,'verifier/verify-manifest.js'),mp],{encoding:'utf8'});};
 let v=verify(base());assert.equal(v.status,0,v.stderr);assert.equal(JSON.parse(v.stdout).integrity_status,'PASS');
 let m=base();m.evidence[0].sha256='0'.repeat(64);v=verify(m);assert.equal(v.status,1);assert.equal(JSON.parse(v.stdout).integrity_status,'FAIL');
 m=base();m.evidence=[];v=verify(m);assert.equal(v.status,1);assert.match(v.stdout,/non-empty array/);
 m=base();m.evidence.push({...m.evidence[0]});v=verify(m);assert.equal(v.status,1);assert.match(v.stdout,/duplicate evidence_id/);
 m=base();m.evidence[0].path='../outside.txt';v=verify(m);assert.equal(v.status,1);assert.match(v.stdout,/escapes/);
 m=base();m.evidence[0].path='/etc/passwd';v=verify(m);assert.equal(v.status,1);assert.match(v.stdout,/relative/);
 const record={assessment_id:'NCS-SMOKE-001',decision_status:'IN_PROGRESS',stages:[]};v=cp.spawnSync(process.execPath,[path.join(root,'compiler/compile-assessment.js')],{input:JSON.stringify(record),encoding:'utf8'});assert.equal(v.status,0);const c=JSON.parse(v.stdout);assert.equal(c.status,'BLOCKED_INCOMPLETE_EVIDENCE');assert.equal(c.grade,null);assert.equal(c.certificate,null);
 console.log('NCS authority smoke tests: 7 passed, 0 failed');
}finally{fs.rmSync(tmp,{recursive:true,force:true});}
