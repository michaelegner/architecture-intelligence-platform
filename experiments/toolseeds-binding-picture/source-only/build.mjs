import fs from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";
import {investigate,compare} from "./core.mjs";
const here=path.dirname(fileURLToPath(import.meta.url));
const base=path.resolve(here,"../../..");
const input=JSON.parse(fs.readFileSync(path.join(here,"inputs.json"),"utf8"));
const source=investigate(input);
const outDir=path.join(here,"results");fs.mkdirSync(outDir,{recursive:true});
fs.writeFileSync(path.join(outDir,"source-only.json"),JSON.stringify(source,null,2)+"\n");
function escape(s){return String(s??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;")}
function page(rows,title,compareRows=false,extra=""){
const table=rows.map((r,i)=>{
 const refs=compareRows?r.source_evidence:r.configuration_evidence;
 return '<tr><td>'+escape(r.consumer_service_id)+'</td><td>'+escape(r.topic_name)+'</td><td>'+escape(compareRows?r.source_crossing:r.crossing)+'</td><td>'+escape(compareRows?r.aip_status:r.status)+'</td><td>'+escape(compareRows?r.aip_reason:r.reason)+'</td><td>'+refs.map(x=>'<a href="'+escape(x.url)+'" target="_blank" rel="noopener">source L'+x.line+'</a>').join(' ')+'</td></tr>';
}).join("");
return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title><style>body{font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#17233d;background:#f7f9fc}section{padding:1rem;border:1px solid #dae2ec;border-radius:12px;background:white;margin:1rem 0}td,th{border-bottom:1px solid #dae2ec;padding:.6rem;text-align:left}table{width:100%;border-collapse:collapse}th{background:#eef2fa}button{cursor:pointer;padding:.4rem}tr[hidden]{display:none}a{color:#1263b1}</style></head><body><h1>'+escape(title)+'</h1><section><p>'+escape(source.question)+'</p><p>Frozen source revisions · local environment · source-only configuration is NOT an observed runtime attachment.</p></section><section><label>Direction <select id="dir"><option value="">All</option><option>INBOUND</option><option>OUTBOUND</option><option>INSIDE</option><option>NONE</option></select></label><p id="count"></p><div style="overflow-x:auto"><table><thead><tr><th>Consumer</th><th>Topic</th><th>Source crossing</th><th>'+(compareRows?"AIP status":"Source status")+'</th><th>Reason</th><th>Evidence</th></tr></thead><tbody>'+table+'</tbody></table></div></section><section>'+extra+'</section><script>const sel=document.querySelector("#dir"),tr=[...document.querySelectorAll("tbody tr")];function update(){let n=0;for(const r of tr){r.hidden=!!sel.value&&r.cells[2].textContent!==sel.value;if(!r.hidden)n++}document.querySelector("#count").textContent=n+" / "+tr.length+" pairs"}sel.addEventListener("change",update);update();</script></body></html>';
}
const sourceHtml=page(source.rows,"Sokol111 — source-only binding investigation",false,
"<h2>Source-only limitations</h2><ul>"+source.limitations.map(x=>"<li>"+escape(x)+"</li>").join("")+"</ul>");
fs.writeFileSync(path.join(outDir,"source-only.html"),sourceHtml);
const rec=JSON.parse(fs.readFileSync(path.join(base,"docs/specifications/0.8.0/i4-evidence/answers-before.json"),"utf8"));
const cmp=compare(source,rec.agent_requests[0].answer);
fs.writeFileSync(path.join(outDir,"comparison.json"),JSON.stringify(cmp,null,2)+"\n");
const comparisonHtml=page(cmp.pairs,"Sokol111 — source-only vs AIP",true,
"<h2>Comparison</h2><pre>"+escape(JSON.stringify(cmp.stats,null,2))+"</pre><p>"+escape(cmp.conclusion.pair_discovery)+"</p><p>"+escape(cmp.conclusion.status)+"</p><p>"+escape(cmp.conclusion.evaluation)+"</p><h3>AIP limitations</h3><ul>"+cmp.provider_limitations.map(x=>"<li>"+escape(x.code)+": "+escape(x.message)+"</li>").join("")+"</ul>");
fs.writeFileSync(path.join(outDir,"comparison.html"),comparisonHtml);
console.log(JSON.stringify(cmp.stats,null,2));
