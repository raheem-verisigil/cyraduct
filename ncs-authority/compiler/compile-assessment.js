'use strict';
// Deterministic fail-closed readiness compiler. Never assigns grades or certificates.
const fs=require('node:fs');
let r;
try{r=JSON.parse(fs.readFileSync(0,'utf8'));}catch(e){process.stderr.write('Invalid assessment JSON: '+e.message+'\n');process.exit(2);}
const errors=[];
if(!r||typeof r!=='object'||Array.isArray(r))errors.push('Assessment root must be an object');
if(typeof r.assessment_id!=='string'||!r.assessment_id.trim())errors.push('assessment_id is required');
const allowedDecision=['INTAKE','IN_PROGRESS','BLOCKED','PROVISIONAL','REVIEW_REQUIRED','DECIDED','REVOKED'];
if(!allowedDecision.includes(r.decision_status))errors.push('Invalid decision_status');
if(!Array.isArray(r.stages))errors.push('stages must be an array');
const allowedStatus=['NOT_STARTED','BLOCKED','RUNNING','COMPLETED','FAILED','NOT_APPLICABLE'];
const stages=new Map();
for(const [i,s] of (Array.isArray(r.stages)?r.stages:[]).entries()){
 if(!s||typeof s!=='object'||Array.isArray(s)){errors.push('stages['+i+'] must be an object');continue;}
 if(typeof s.name!=='string'||!s.name.trim()){errors.push('stages['+i+'] missing name');continue;}
 if(!allowedStatus.includes(s.status)){errors.push('Stage '+s.name+' has invalid status');continue;}
 if(stages.has(s.name))errors.push('Duplicate stage: '+s.name);
 else stages.set(s.name,s.status);
}
const mandatory=['artifact_identity','build_record','native_baseline','policy_delta','independent_review'];
const missing=mandatory.filter(n=>stages.get(n)!=='COMPLETED');
const hardBlocked=errors.length>0||missing.length>0||r.decision_status==='BLOCKED'||r.decision_status==='REVOKED';
const output={
 schema_version:'ncs-compiler-output/0.2',
 assessment_id:typeof r.assessment_id==='string'?r.assessment_id:null,
 status:errors.length?'INVALID_ASSESSMENT':hardBlocked?'BLOCKED_INCOMPLETE_EVIDENCE':'READY_FOR_AUTHORIZED_REVIEW',
 validation_errors:errors,
 missing_or_incomplete_stages:missing,
 grade:null,
 certificate:null,
 rule:'This compiler only validates structural readiness. It never assigns a grade or issues a certificate. READY_FOR_AUTHORIZED_REVIEW is not a decision or certification.'
};
process.stdout.write(JSON.stringify(output,null,2)+'\n');
