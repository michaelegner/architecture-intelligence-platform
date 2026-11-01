import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
function generate(r,k,without=false){
 const missing={question:"What bindings matter when Catalog Management moves to Kafka?",boundary:"catalog-management",provider:null,outcome:"NOT_AVAILABLE",snapshot:null,context:null,rows:[],limitations:[],capture_sources:[],catalog_source:null,missing:["No architecture-knowledge provider input","No independent source-analysis input"],source_url:null};
 if(without)return {view:missing,checks:{provider_removed:true,rows:0}};
 const reqs=r.agent_requests??[];
 if(reqs.length!==1)throw Error("Exactly one recorded AIP request required");
 const a=reqs[0].answer;
 if(a?.tool!=="get_binding_picture"||a.mode!=="query"||!["PARTIAL","COMPLETE"].includes(a.outcome))throw Error("Unsupported answer");
 if(!a.snapshot?.snapshot_id||!Array.isArray(a.data?.rows))throw Error("Snapshot or row array missing");
 const ctx=a.data.request_context, kc=k.request;
 if(ctx.bounded_context_id!==kc.bounded_context_id||ctx.environment!==kc.environment||
 JSON.stringify([...(ctx.broker_ids??[])].sort())!==JSON.stringify([...(kc.broker_ids??[])].sort()))throw Error("Request context mismatch");
 const fields=["broker_id","topic_name","consumer_service_id","crossing","status","reason","cross_broker_producers"];
 const signature=x=>JSON.stringify(fields.map(f=>x[f]??null));
 if(JSON.stringify(a.data.rows.map(signature).sort())!==JSON.stringify(k.rows.map(signature).sort()))throw Error("Reference mismatch: status, direction or identity");
 const lim=a.limitations.map(x=>x.code).sort();
 if(JSON.stringify(lim)!==JSON.stringify([...k.limitations].sort()))throw Error("Reference limitation mismatch");
 if(a.data.page?.returned!==a.data.rows.length||a.data.rows.length>a.data.page?.limit)throw Error("Rows truncated");
 const times=[...new Set(a.data.rows.map(x=>x.captured_at))];
 if(times.length!==1||!times[0])throw Error("No consistent capture time");
 for(const row of a.data.rows){
  for(const f of ["attachment_evidence_refs","mapping_evidence_refs","promise_evidence_refs"])if(!Array.isArray(row[f]))throw Error("Missing evidence references");
  if(!row.attachment_evidence_refs.length||!row.mapping_evidence_refs.length)throw Error("Missing observation evidence refs");
  if(row.status==="PROMISED_AND_OBSERVED"&&!row.promise_evidence_refs.length)throw Error("Missing promise evidence refs");
  if(row.reason==="PROMISE_COVERAGE_MISSING"&&row.promise_evidence_refs.length)throw Error("Contradictory promise refs");
 }
 const view={question:missing.question,boundary:ctx.bounded_context_id,provider:"AIP get_binding_picture, recorded v0.8 query",outcome:a.outcome,snapshot:a.snapshot,context:ctx,
 rows:a.data.rows,limitations:a.limitations,capture_sources:a.data.capture_sources,catalog_source:a.data.catalog_source,
 missing:["Evidence-mode resolution was not included in this frozen query; opaque refs are preserved but unresolved here",
 "No source-level handler investigation was performed",
 "Single capture does not establish exhaustive bindings, event handling or cross-broker delivery",
 "No post-migration state or independent functional validation is shown"],
 source_url:"https://github.com/michaelegner/architecture-intelligence-platform/blob/main/docs/specifications/0.8.0/i4-evidence/answers-before.json"};
 const c=(name)=>a.data.rows.filter(x=>x.status===name).length;
 const refs=a.data.rows.reduce((n,x)=>n+x.attachment_evidence_refs.length+x.mapping_evidence_refs.length+x.promise_evidence_refs.length,0);
 return {view,checks:{reference_check:"PASS",rows:a.data.rows.length,promised_and_observed:c("PROMISED_AND_OBSERVED"),unresolved:c("UNRESOLVED"),
 crossing_counts:Object.fromEntries(["INBOUND","OUTBOUND","INSIDE","NONE"].map(c=>[c,a.data.rows.filter(x=>x.crossing===c).length])),
 evidence_refs_retained:refs,limitations_retained:lim,snapshot_id:a.snapshot.snapshot_id,capture_at:times[0]}};
}
function htmlPage(view){
 const source=JSON.stringify(view).replace(/</g,"\\u003c").replace(/>/g,"\\u003e").replace(/&/g,"\\u0026");
 return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sokol111 binding picture</title>
<style>body{font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#17233d;background:#f7f9fc}section{background:#fff;padding:1rem;margin:1rem 0;border:1px solid #dae2ec;border-radius:12px}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:.55rem;border-bottom:1px solid #dee4ed}th{background:#edf2fa}tr[tabindex]:hover,tr[aria-selected=true]{background:#dcecff;cursor:pointer}tr:focus{outline:2px solid #2061ba}label{margin:0 1rem 0 0}select{padding:.4rem}pre{background:#f1f5f9;padding:1rem;white-space:pre-wrap;overflow-wrap:anywhere;max-height:500px;overflow:auto}p,li{overflow-wrap:anywhere}</style></head>
<body><h1>Sokol111 — binding picture</h1><p id="question"></p><section id="context"></section>
<section><h2>Recorded AIP bindings</h2><label>Direction <select id="direction"><option value="">All</option><option>INBOUND</option><option>OUTBOUND</option><option>INSIDE</option><option>NONE</option></select></label>
<label>Status <select id="status"><option value="">All</option><option>UNRESOLVED</option><option>PROMISED_AND_OBSERVED</option></select></label><p id="count"></p>
<div style="overflow-x:auto"><table><thead><tr><th>Consumer</th><th>Topic</th><th>Direction</th><th>Assessment</th><th>Reason</th></tr></thead><tbody id="rows"></tbody></table></div></section>
<section><h2>Selected binding: raw provider fields</h2><div id="detail">Select a row to inspect all provider fields and opaque evidence references.</div></section>
<section><h2>Provider limitations</h2><ul id="limits"></ul><h2>Inputs and claims not established</h2><ul id="missing"></ul></section>
<script type="application/json" id="binding-data">${source}</script><script>
const m=JSON.parse(document.getElementById('binding-data').textContent),el=id=>document.getElementById(id);
el('question').textContent=m.question;
el('context').textContent='Boundary: '+m.boundary+' | Outcome: '+m.outcome+' | Snapshot: '+(m.snapshot?.snapshot_id||'none')+' | Provider: '+(m.provider||'none');
function inspect(r){const d=el('detail');d.replaceChildren();const pre=document.createElement('pre');pre.textContent=JSON.stringify(r,null,2);d.append(pre);
const p=document.createElement('p');p.textContent='These are unmodified provider fields. Evidence refs have not been independently resolved by this prototype.';d.append(p);
if(m.source_url){const a=document.createElement('a');a.href=m.source_url;a.textContent='Original recorded provider response';a.rel='noopener';a.target='_blank';d.append(a);}}
function render(){const dir=el('direction').value,s=el('status').value,tbody=el('rows');tbody.replaceChildren();
const list=m.rows.filter(r=>(!dir||r.crossing===dir)&&(!s||r.status===s));el('count').textContent=list.length+' of '+m.rows.length+' bindings';
for(const r of list){const tr=document.createElement('tr');tr.tabIndex=0;
for(const f of ['consumer_service_id','topic_name','crossing','status','reason']){const td=document.createElement('td');td.textContent=r[f]??'—';tr.append(td);}
const pick=()=>{for(const x of tbody.children)x.setAttribute('aria-selected','false');tr.setAttribute('aria-selected','true');inspect(r)};
tr.addEventListener('click',pick);tr.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pick()}});tbody.append(tr);}}
for(const id of ['direction','status'])el(id).addEventListener('change',render);
for(const x of m.limitations){const li=document.createElement('li');li.textContent=x.code+': '+x.message;el('limits').append(li);}
for(const x of m.missing){const li=document.createElement('li');li.textContent=x;el('missing').append(li);}
render();</script></body></html>`;
}
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const rec=JSON.parse(fs.readFileSync(path.join(root,'docs/specifications/0.8.0/i4-evidence/answers-before.json'),'utf8'));
const ref=JSON.parse(fs.readFileSync(path.join(root,'docs/specifications/0.8.0/i2-vectors/c1-expected.json'),'utf8'));
const copy=()=>JSON.parse(JSON.stringify(rec));
test('C1 9 rows 4 limitations, 2 promised and observed',()=>{const o=generate(rec,ref);assert.equal(o.checks.rows,9);assert.equal(o.checks.promised_and_observed,2);assert.equal(o.checks.unresolved,7);assert.equal(o.checks.limitations_retained.length,4)});
test('provider rows, refs, and snapshot copied verbatim',()=>{const v=generate(rec,ref).view;const a=rec.agent_requests[0].answer;assert.deepEqual(v.rows,a.data.rows);assert.deepEqual(v.limitations,a.limitations);assert.deepEqual(v.snapshot,a.snapshot)});
test('without provider does not generate provider-backed claims',()=>assert.equal(generate(rec,ref,true).view.rows.length,0));
test('mutated status rejected',()=>{const c=copy();c.agent_requests[0].answer.data.rows[0].status='PROMISED_AND_OBSERVED';assert.throws(()=>generate(c,ref))});
test('missing refs rejected',()=>{const c=copy();delete c.agent_requests[0].answer.data.rows[0].attachment_evidence_refs;assert.throws(()=>generate(c,ref))});
test('missing limitation rejected',()=>{const c=copy();c.agent_requests[0].answer.limitations.pop();assert.throws(()=>generate(c,ref))});
test('HTML stable for identical input',()=>assert.equal(htmlPage(generate(rec,ref).view),htmlPage(generate(rec,ref).view)));
