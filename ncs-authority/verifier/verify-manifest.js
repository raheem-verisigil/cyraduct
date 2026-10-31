'use strict';
// Offline manifest digest verifier. A PASS is byte-integrity evidence only.
const fs=require('node:fs');const path=require('node:path');const crypto=require('node:crypto');
const manifestPath=process.argv[2];
if(!manifestPath){console.error('Usage: node verify-manifest.js <manifest.json>');process.exit(2);}
const base=path.dirname(path.resolve(manifestPath));let m;
try{m=JSON.parse(fs.readFileSync(manifestPath,'utf8'));}catch(e){console.error(JSON.stringify({integrity_status:'FAIL',errors:['Manifest unreadable or invalid JSON: '+e.message]}));process.exit(1);}
const errors=[];const idSet=new Set();const pathSet=new Set();
if(!m||typeof m!=='object'||Array.isArray(m))errors.push('Manifest root must be an object');
if(m.schema_version!=='ncs-evidence-manifest/0.1')errors.push('Unsupported schema_version');
if(typeof m.assessment_id!=='string'||!m.assessment_id.trim())errors.push('Missing assessment_id');
if(!m.artifact||typeof m.artifact!=='object')errors.push('Missing artifact object');
if(!/^sha256:[a-f0-9]{64}$/.test(m.artifact?.artifact_digest||''))errors.push('Invalid artifact_digest');
if(!Array.isArray(m.evidence)||m.evidence.length===0)errors.push('Evidence must be a non-empty array');
for(const [i,e] of (Array.isArray(m.evidence)?m.evidence:[]).entries()){
 const label=typeof e?.evidence_id==='string'&&e.evidence_id?e.evidence_id:'evidence['+i+']';
 if(!e||typeof e!=='object'||Array.isArray(e)){errors.push(label+': entry must be an object');continue;}
 if(typeof e.evidence_id!=='string'||!e.evidence_id.trim())errors.push(label+': missing evidence_id');
 else if(idSet.has(e.evidence_id))errors.push(label+': duplicate evidence_id');else idSet.add(e.evidence_id);
 if(typeof e.path!=='string'||!e.path.trim()){errors.push(label+': missing path');continue;}
 if(path.isAbsolute(e.path)||e.path.includes('\\')){errors.push(label+': path must be relative and use forward slashes');continue;}
 const normalized=path.posix.normalize(e.path);
 if(normalized==='.'||normalized==='..'||normalized.startsWith('../')){errors.push(label+': path escapes evidence directory');continue;}
 if(pathSet.has(normalized))errors.push(label+': duplicate evidence path');else pathSet.add(normalized);
 if(!/^[a-f0-9]{64}$/.test(e.sha256||'')){errors.push(label+': invalid SHA-256 digest');continue;}
 if(!['REQUIRED','SUPPORTING','CHALLENGE','EXCEPTION'].includes(e.classification))errors.push(label+': invalid classification');
 const target=path.resolve(base,...normalized.split('/'));
 if(!target.startsWith(base+path.sep)){errors.push(label+': resolved path escapes manifest directory');continue;}
 try{const stat=fs.lstatSync(target);if(!stat.isFile()||stat.isSymbolicLink()){errors.push(label+': evidence must be a regular non-symlink file');continue;}
 const actual=crypto.createHash('sha256').update(fs.readFileSync(target)).digest('hex');if(actual!==e.sha256)errors.push(label+': SHA-256 mismatch');
 }catch(err){errors.push(label+': file missing or unreadable');}
}
const result={schema_version:'ncs-verifier-result/0.2',assessment_id:m?.assessment_id||null,integrity_status:errors.length?'FAIL':'PASS',evidence_items:Array.isArray(m?.evidence)?m.evidence.length:0,errors,limitations:['Digest verification proves byte integrity only; it does not prove source authenticity, truth, completeness, signer identity, or model behaviour.','This verifier does not validate the JSON Schema, cryptographic signatures, trusted timestamps, or transparency-log inclusion.','Manifest evidence lists are self-declared; this tool cannot prove that omitted evidence exists or that all required evidence was supplied.']};
console.log(JSON.stringify(result,null,2));if(errors.length)process.exit(1);
