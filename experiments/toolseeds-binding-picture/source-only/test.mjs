import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";
import {investigate,compare} from "./core.mjs";
const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,"../../..");
const input=JSON.parse(fs.readFileSync(path.join(here,"inputs.json"),"utf8"));
const provider=JSON.parse(fs.readFileSync(path.join(root,"docs/specifications/0.8.0/i4-evidence/answers-before.json"),"utf8")).agent_requests[0].answer;
test("source-only never consumes AIP response",()=>{
  const source=investigate(input);assert.equal(source.rows.length,9);
  assert.equal(source.observation_status,"NOT_AVAILABLE");
  assert.equal(source.promise_assessment,"NOT_AVAILABLE");
  assert.ok(source.rows.every(r=>r.capture_time===null&&r.provider_assessment===null));
});
test("nine source configured pairs match independent AIP rows, without status conflation",()=>{
 const c=compare(investigate(input),provider);
 assert.equal(c.stats.matching_pairs,9);assert.equal(c.stats.same_crossing,9);
 assert.equal(c.stats.aip_only_rows,0);assert.equal(c.stats.source_only_pairs,0);
 assert.equal(c.stats.source_observed_attachment_claims,0);
 assert.equal(c.stats.aip_observed_attachments_at_capture,9);
 assert.equal(c.stats.aip_promised_and_observed,2);
});
test("source evidence references are pinned to original GitHub revisions/lines",()=>{
 const source=investigate(input);
 for(const row of source.rows){
  assert.ok(row.configuration_evidence.length>=3);
  for(const ref of [...row.configuration_evidence,...row.producers.flatMap(p=>p.evidence),...row.documentation_evidence]){
    const s=input.sources.find(x=>x.repo===ref.repository&&x.revision===ref.revision&&x.path===ref.path);
    assert.ok(s,ref.url);
    assert.ok(s.lines.some(x=>x.line===ref.line),ref.url);
  }
 }
});
test("source-only no configured runtime attestation or manufactured owner promises",()=>{
 const source=investigate(input);
 assert.ok(source.rows.every(x=>x.status==="CONFIGURED_CONSUMPTION_ONLY"));
 assert.ok(source.rows.every(x=>x.reason==="RUNTIME_ATTACHMENT_NOT_TESTED"));
 assert.equal(source.rows.reduce((n,r)=>n+r.documentation_evidence.length,0),2);
});
test("delete one configuration consumer -> one source-only pair disappears",()=>{
 const copy=structuredClone(input);
 const s=copy.sources.find(x=>x.kind==="consumer_config"&&x.owner_service==="ecommerce-image-service");
 s.lines=s.lines.filter(x=>!x.text.includes('topic: "tenant.tenant.events"'));
 const subset=investigate(copy);
 assert.equal(subset.rows.length,8);
 assert.equal(compare(subset,provider).stats.aip_only_rows,1);
});
test("inconsistent producer documentation yields unresolved crossing, not guessed identity",()=>{
 const copy=structuredClone(input);copy.sources=copy.sources.filter(x=>x.kind!=="event_topic_map"||!x.repo.includes("tenant-service-api"));
 const subset=investigate(copy);
 assert.equal(subset.rows.filter(x=>x.topic_name==="tenant.tenant.events").length,4);
 assert.ok(subset.rows.filter(x=>x.topic_name==="tenant.tenant.events").every(x=>x.crossing==="UNRESOLVED"));
});
test("source and comparison reproducible with same frozen inputs",()=>{
 assert.equal(JSON.stringify(investigate(input)),JSON.stringify(investigate(input)));
 const cmp=()=>JSON.stringify(compare(investigate(input),provider));
 assert.equal(cmp(),cmp());
});
