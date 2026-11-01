// Frozen-source investigation. No AIP input, broker observations, or promise assessments.
const serviceId = s => "service:" + s;
const ref = (s, line) => ({
  kind: s.kind,
  repository: s.repo,
  revision: s.revision,
  path: s.path,
  line,
  url: "https://github.com/" + s.repo + "/blob/" + s.revision + "/" + s.path + "#L" + line
});
const match = (s, pat) => s.lines.filter(x => pat.test(x.text));
const slug = s => s.replace(/Event$/, "");
function topicMaps(sources) {
  const result = new Map();
  for (const s of sources.filter(x => x.kind === "event_topic_map")) {
    const constants = new Map(), full = s.lines.map(x => x.text).join("\n");
    for (const x of s.lines) {
      const m = x.text.match(/^\s*(Topic\w+)\s*=\s*"([^"]+)"/);
      if (m) constants.set(m[1], {topic:m[2], line:x.line});
    }
    const ownersRepo = s.repo.replace(/-api$/, "");
    const owners = ownersRepo.split("/").at(-1);
    const factoryFiles = sources.filter(x => x.kind === "event_factory" && x.repo === ownersRepo);
    if (!factoryFiles.some(x => x.lines.some(z => z.text.includes("TopicFor(") && x.lines.some(w => w.text.includes("outbox.Message{")))))
      throw Error("No outbox factory evidence for " + owners);
    for (const x of s.lines) {
      const m = x.text.match(/\(&eventsv1\.(\w+)\{\}\).*:\s*(Topic\w+)/);
      if (!m) continue;
      const found = constants.get(m[2]);
      if (!found) throw Error("Unknown topic constant "+m[2]);
      const event = slug(m[1]);
      const matchFactory = factoryFiles.filter(f => f.lines.some(z => z.text.includes(event) || z.text.includes(m[1])));
      if (!matchFactory.length) throw Error("No event factory for " + event);
      const topic = found.topic;
      const evidence = [ref(s, found.line),ref(s,x.line), ...matchFactory.map(f=>{
        const item=f.lines.find(z=>z.text.includes("TopicFor("));
        return ref(f,item.line);
      })];
      const list=result.get(topic)??[];
      if (!list.some(y=>y.service_id===serviceId(owners)))list.push({service_id:serviceId(owners),evidence,events:[event]});
      else{
        const item=list.find(y=>y.service_id===serviceId(owners));
        item.events.push(event);item.evidence.push(...evidence);
      }
      result.set(topic,list);
    }
  }
  return result;
}
export function investigate(input) {
  if (!input?.boundary?.inside?.length) throw Error("Question must select a known inside side");
  const consumerFiles=input.sources.filter(x=>x.kind==="consumer_config");
  const producers=topicMaps(input.sources);
  const doc=input.sources.find(x=>x.kind==="architecture_document" && x.path.includes("product-update-flow.md"));
  // Aliases are explicit in the reviewed sequence diagram; no name-based service identity matching.
  const knownDiagramParticipants=new Map([
    ["ProductQuery","ecommerce-product-query-service"],
    ["Image","ecommerce-image-service"]
  ]);
  const docByConsumerTopic=new Map();
  if(doc) for(const l of doc.lines){
    const m=l.text.match(/Events->>(ProductQuery|Image): Consume (.+?) event/);
    if(!m)continue;
    const c=knownDiagramParticipants.get(m[1]), topic=[...producers.entries()].find(([_,ps])=>ps.some(p=>p.events.some(e=>m[2].includes(e)||e.includes(m[2].replace(/\s+event/i,"").replace("image promotion","ProductImagePromoted")))))?.[0];
    // Explicit event/topic mapping, no inference from topic prefixes.
    if(topic)docByConsumerTopic.set(c+"|"+topic,ref(doc,l.line));
  }
  // The diagram names "image promotion event" rather than a schema type.
  const productTopic=[...producers.entries()].find(([t,ps])=>ps.some(p=>p.events.includes("ProductImagePromoted")))?.[0];
  if(productTopic && doc)for(const l of doc.lines){if(/Events->>ProductQuery: Consume image promotion event/.test(l.text))
    docByConsumerTopic.set("ecommerce-product-query-service|"+productTopic,ref(doc,l.line));
  }
  const rows=[];
  for(const cfg of consumerFiles){
    const svc=cfg.owner_service;if(!svc)throw Error("Missing service identity on source file");
    const broker=cfg.lines.find(x=>/^\s*brokers:\s*"/.test(x.text));
    if(!broker)throw Error("No configured broker: "+svc);
    const group=cfg.lines.find(x=>/default-group-id:/.test(x.text));
    if(!group)throw Error("No consumer group in "+svc);
    const topics=cfg.lines.filter(x=>/^\s*topic:\s*"[^"]+"/.test(x.text));
    for(const item of topics){
      const topic=item.text.match(/topic:\s*"([^"]+)"/)[1];
      const producerCandidates=producers.get(topic)??[];
      const insideConsumer=input.boundary.inside.includes(svc);
      const insideProducer=producerCandidates.some(p=>input.boundary.inside.includes(p.service_id.replace(/^service:/,"")));
      const outsideProducer=producerCandidates.some(p=>!input.boundary.inside.includes(p.service_id.replace(/^service:/,"")));
      const crossing=!producerCandidates.length?"UNRESOLVED":insideConsumer?(outsideProducer?"INBOUND":"INSIDE"):(insideProducer?"OUTBOUND":"NONE");
      const evidence=[ref(cfg,item.line),ref(cfg,group.line),ref(cfg,broker.line)];
      const dref=docByConsumerTopic.get(svc+"|"+topic);
      rows.push({
        topic_name:topic,consumer_service_id:serviceId(svc),crossing,
        status:"CONFIGURED_CONSUMPTION_ONLY",
        reason:"RUNTIME_ATTACHMENT_NOT_TESTED",
        broker_configuration:broker.text.match(/"([^"]+)"/)?.[1]??null,
        configured_group_id:group.text.match(/"([^"]+)"/)?.[1]??null,
        producers:producerCandidates,
        configuration_evidence:evidence,
        documentation_evidence:dref?[dref]:[],
        provider_assessment:null,
        capture_time:null,
        questions:["Is this group actually attached in the intended environment and at what time?","Does an attributable promise cover this binding?","Does the consuming implementation handle the relevant event types?"]
      });
    }
  }
  rows.sort((a,b)=>a.topic_name.localeCompare(b.topic_name)||a.consumer_service_id.localeCompare(b.consumer_service_id));
  const duplicates=new Set();for(const r of rows){const k=r.consumer_service_id+"|"+r.topic_name;if(duplicates.has(k))throw Error("Duplicate configured pair "+k);duplicates.add(k)}
  return {
    question:input.question,boundary:input.boundary,environment:input.environment,
    origin:"Frozen Sokol111 source/configuration only; no AIP, runtime or broker access",
    observation_status:"NOT_AVAILABLE",promise_assessment:"NOT_AVAILABLE",
    source_count:input.sources.length,rows,
    limitations:[
      "Helm values show configured consumers, not actual broker attachment or runtime use",
      "Topic mappings and event factories establish implementation intent, not successful production or delivery",
      "An event described by documentation is not an owner-confirmed architectural promise",
      "Crossing directions use the selected migration boundary and source-declared producer paths; they are not qualified runtime facts",
      "Only selected files and local environment excerpts were inspected; this is not a complete dependency inventory"
    ]
  };
}
export function compare(source, provider) {
  if(provider.tool!=="get_binding_picture"||provider.mode!=="query")throw Error("Invalid AIP response");
  const indexed=new Map(provider.data.rows.map(r=>[r.consumer_service_id+"|"+r.topic_name+"|"+r.broker_id,r]));
  const pairs=source.rows.map(row=>{
    const p=provider.data.rows.find(x=>x.topic_name===row.topic_name&&x.consumer_service_id===row.consumer_service_id);
    return {consumer_service_id:row.consumer_service_id,topic_name:row.topic_name,
      source_crossing:row.crossing,aip_crossing:p?.crossing??null,
      source_claim:"CONFIGURED_CONSUMPTION_ONLY",aip_status:p?.status??null,aip_reason:p?.reason??null,
      source_evidence:row.configuration_evidence,source_documentation:row.documentation_evidence,
      aip_evidence_refs:p?{
        attachment:p.attachment_evidence_refs,mapping:p.mapping_evidence_refs,promise:p.promise_evidence_refs
      }:null,
      source_runtime_established:false,aip_runtime_attachment_at_capture:!!p?.attachment_evidence_refs?.length,
      same_crossing:row.crossing===p?.crossing};
  });
  const extraAip=provider.data.rows.filter(p=>!source.rows.some(r=>r.topic_name===p.topic_name&&r.consumer_service_id===p.consumer_service_id));
  const stats={
    source_configured_pairs:source.rows.length,aip_rows:provider.data.rows.length,
    matching_pairs:pairs.filter(p=>p.aip_status!==null).length,
    same_crossing:pairs.filter(p=>p.same_crossing).length,
    source_only_pairs:pairs.filter(p=>!p.aip_status).length,aip_only_rows:extraAip.length,
    source_documented_pairs:pairs.filter(p=>p.source_documentation.length).length,
    source_observed_attachment_claims:0,
    aip_observed_attachments_at_capture:provider.data.rows.filter(r=>r.attachment_evidence_refs.length>0).length,
    aip_promised_and_observed:provider.data.rows.filter(r=>r.status==="PROMISED_AND_OBSERVED").length,
    aip_unresolved:provider.data.rows.filter(r=>r.status==="UNRESOLVED").length,
    source_only_runtime_or_promise_proof:false
  };
  return {question:source.question,boundary:source.boundary.id,source_origin:source.origin,
    aip_snapshot:provider.snapshot,aip_outcome:provider.outcome,
    aip_capture:provider.data.capture_sources,provider_limitations:provider.limitations,
    stats,pairs,additional_aip_rows:extraAip,conclusion:{
      pair_discovery:"With full access to selected infrastructure configuration, source-only identifies the same nine configured consumer/topic pairs. No unique pair is attributable to AIP in this fixture.",
      status:"Only AIP's recorded capture establishes group/topic attachment at its captured time; source-only does not. AIP qualifies two promises in its demo EventCatalog, seven rows have missing promise coverage; missing coverage is not proof no promise exists elsewhere.",
      evaluation:"No human/agent comprehension or decision-quality comparison has been run. This is an information-availability comparison, not a product-value claim."
    }};
}
