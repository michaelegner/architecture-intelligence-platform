# AIP v0.6.2 — Realistic Messaging Demo: Pitstop

**Status:** Draft (2026-10-07), amended 2026-10-07 after the I1 gate spike ([`i1-spike-finding.md`](i1-spike-finding.md), #460)  
**Target:** `v0.6.2`  
**Baseline:** Published and post-release-verified `v0.6.1`  
**Scope authority:** [ROADMAP.md — v0.6.2](../../../ROADMAP.md) (this release is a demo release like v0.5.1, not a capability release)

## 1. Promise and task

> **Which services receive from the messaging destination this service publishes to, how far can the evidence resolve that topology, and what must I still inspect before changing the event?**

v0.6.2 establishes the **hosted, persistent Live AIP Demo** that later releases extend (v0.7 API-aware, v0.8 Intent): a canonical AIP instance, hosted by the owner, continuously ingests a running Pitstop garage-management sample (a private fork pinned to one upstream commit, driven by controlled traffic) and answers from evidence accumulated in its observation windows. "Live" means the system and evidence ingestion run continuously; answers use the last completed supported observation window and may therefore lag wall-clock activity by that window's duration. A one-command local version (`run.sh`) exists for reproducibility and offline use. It demonstrates the v0.6.0/v0.6.1 messaging knowledge on a second, independent system.

The concrete developer task is:
> **"In `MaintenanceJobFinished`, replace `StartTime` and `EndTime` with a single `Duration` field. The workshop only needs to report how long a job took. Plan the change."**

The demo lets a coding agent, with a scoped checkout (`WorkshopManagementAPI` plus the repository's `docs/`), obtain the messaging context for that task without reconstructing it: which Broker, which Topic, which Subscriptions and Services AIP can resolve as receiving from it, what was observed, and where the evidence stops. Receipt is established per messaging destination (the exchange), never per event type.

The release does **not** add a new architecture-question class, semantic, source family or tool. It shows existing semantics on a system where the decisive consumer is not named in any document the agent can read.

## 2. Constraints

- Reuse the released v0.6.1 product: no new entity kind, relation, claim type, source family, schema or MCP tool. Exactly the existing four tools. The one permitted product change is the small hardening prerequisite I0 (§3.3), which corrects two evidence-correctness defects found by the gate spike and adds no new semantics, surface or schema.
- No payload or field-level knowledge. AIP does not model which consumer reads which field of a message; no answer, fixture, overlay, skill or client text may claim it. Field usage stays **outside AIP** and is what the agent must still inspect.
- No Intent or Assessment. `docs/` (ADRs and arc42) stays in the agent's checkout, unmodified, as the agent's own reading material. AIP does not ingest it and does not claim that documents are stale. If the agent notices that the documented consumer list differs from the evidenced one, that is the agent's observation, not an AIP drift claim.
- **The canonical demo is hosted and live, not a replay.** Live runtime messaging evidence is a **requirement** of this release (see the stop rule in §3.2), not a degradable feature. Pitstop runs continuously with a controlled traffic generator (§4.2). Runtime evidence is OTLP telemetry from the running fork, and answers are produced for explicit environment and observation-window contexts that AIP already supports. A timestamp-frozen OTLP fixture remains **only** for deterministic tests, the smoke test, release qualification and the local `--replay` mode; it does not define the product demo.
- No live broker discovery and no broker adapter: AIP never reads RabbitMQ. Declared evidence is a disclosed, operator-authored AsyncAPI 2.6.0 overlay (§4.1), maintained with the fork.
- Telemetry instrumentation of the fork is allowed because telemetry is the evidence source, but it is a disclosed fork change and must not alter Pitstop's behaviour (§4.2).
- Reproducibility is **semantic, not byte-identical**: with the same environment, window, overlay and identity configuration, the same claims, qualifications, limitations and evidence resolution must result. Live answers change as windows roll; the demo always prints the window it asks about.
- Runtime evidence only qualifies declared Topic and Subscription topology; it never creates an observed-only Topic or Subscription (existing rule). The demo must not depend on it doing so.
- The fork keeps the shared package, the silent-failure worker pattern and the undocumented consumer as they are; no change to Pitstop for the sake of the demo beyond the fork specification.
- The Claude Code client assets (§6) are **example agent-client material**, not product semantics. They add no AIP behaviour and may be removed without changing any AIP answer.
- Implement each increment against its section in this document, with the reviewed implementation plan retained in the PR description, as in v0.5.1 and v0.6.1.

## 3. Why Pitstop, and what must be confirmed first

### 3.1 Evidence basis

| Aspect | Pitstop (fork) |
|---|---|
| Broker | One RabbitMQ broker, one fanout exchange `Pitstop` |
| Consumers | One durable queue per consumer: `Invoicing`, `Notifications`, `WorkshopManagement`, `Auditlog`, and the fork's `Reporting` |
| Publishers | WorkshopManagementAPI, CustomerManagementAPI, VehicleManagementAPI, TimeService |
| Contract | No shared schema; each consumer has its own event class; the message type travels in a header |
| Declared messaging | None upstream. An operator-authored AsyncAPI overlay is required, as for Quarkus |
| Documents | ADRs and arc42 in `docs/`; the consumer table in arc42 8.1 lists four consumers of `MaintenanceJobFinished` |
| Added by the fork | ReportingService, a fifth consumer, in no README, doc or picture. It appears in AIP evidence through its own declared overlay, qualified by runtime telemetry; telemetry alone does not discover it. Also: OTLP instrumentation, a Collector and a traffic generator for the persistent demo (fork specification) |

Why this adds to the Quarkus demo: Quarkus shows an unresolved Subscription. Pitstop shows a fanout topology whose consumer set is richer than the documents the agent reads, on a different broker and stack, with the same four tools.

### 3.2 Modelling decision and open items

Intended mapping: exchange `Pitstop` → Topic; each per-consumer queue → one named Subscription of that Topic; the RabbitMQ instance → one Broker with a stable id (`rabbitmq:pitstop-rabbitmq`).

The gates G1–G5 were executed as a spike against v0.6.1 on real Neo4j (`i1-spike-finding.md`, #460; characterization tests in `tests/integration/test_v062_i1_gate_spike.py`). Results and their consequences for this specification:

| # | Gate | Verdict | Consequence |
|---|---|---|---|
| G1 | The existing AsyncAPI rules declare a fanout exchange as a Topic and five named queues as Subscriptions | Pass | The nine overlays (§4.1) import into one Topic, one Broker and five named Subscriptions. An invalid document rejects the whole import atomically; this is accepted and desirable for a controlled overlay set (§4.3) |
| G2 | The five Subscriptions and their Services appear in the existing answer | Pass, **publisher-side only** | Receivers are `RESOLVED_SERVICE` claims in the answer for a **declared publisher**; there is no receiver-side or Topic-centric question and no fallback through the other services' answers. The question ladder is publisher-centric (§5) |
| G3 | One Topic carrying several event types is answerable per Topic without a per-event claim | Pass | No claim has an event dimension. "Consumers are per Topic, not per event type" must be stated by the demo text (§1, §5); the answer does not say it |
| G4 | Live OTLP messaging spans qualify the declared topology | Pass with limits; **blocked on I0** | A publisher `send` span qualifies **all** claims of that publisher alike; a consumer span adds `OBSERVED` evidence to that receiver's route. v0.6.1 has **no per-Subscription qualification**. A consumer span naming *another* declared Subscription of the Topic is accepted and adds an undeclared competing route with no limitation: this is the I0 defect H1 |
| G5 | Windows apply to messaging qualification and a completed window is stable | Pass with limits; **blocked on I0** | Windows are caller-chosen (explicit UTC offset, at most 31 days), not whole-UTC-day-only. Later receiver traffic adds out-of-window evidence refs to a completed window's claim: the I0 defect H2. `snapshot_id` changes with every ingested span and a stale snapshot is refused; this is intended snapshot design and is **not** an I0 requirement (see §4.4) |

**Stop rule (remains active):** v0.6.2 is the Live AIP Demo. Because G4 and G5 ended with limits that affect the Live promise, the owner decided (2026-10-07) on a separate product fix first: neither accept-and-disclose nor a replay-only re-scope. No Pitstop `run.sh`, hosted mode, fixture or §4.4 freeze before I0 is merged and the G4/G5 spike tests have been rerun against it with acceptable results. If G4 or G5 still fails after I0, do not ship a declared-topology-only demo under this name: record the finding and re-scope explicitly. G3 fails only into stated limits, never into silence.

### 3.3 I0 — Product hardening prerequisite

A small, separately specified and separately reviewed product change, outside the demo code. It is the only product change in this release and is complete only when both defects are fixed and the spike tests are rerun.

| # | Defect found by the spike | Required outcome |
|---|---|---|
| H1 | Receiver-route safety: a consumer span for Service A naming a different declared Subscription B of the same Topic creates an observed `RECEIVES_FROM` A → B that no declaration supports, and the publisher's answer gains a sixth, separately identified claim for A via B with no limitation | Runtime evidence must not silently create or strengthen a Service → Subscription route that is not supported by declared evidence. The guard establishing when an observed `RECEIVES_FROM` may support or create such a relation is defined in the I0 specification, not here |
| H2 | Observation-window correctness: `resolution_evidence_refs` use the accepted relation evidence without applying the requested observation window, so receiver traffic from a later window changes the claim of a completed one | The answer for an explicit observation context must not cite or be changed by evidence observed outside that context. "Completed window" is then meaningful as: an explicit window the caller has chosen that lies wholly in the past |

Not part of I0: snapshot-id stability (the snapshot fingerprints live evidence by design; after H2 the G5 tests are rerun and differing snapshot ids are re-judged as an expected provenance property, returning to the owner only if a residual question remains); per-Subscription qualification (the demo words Q4 accordingly, §5); the `service.name` mismatch behaviour (documented in §4.2 and guarded by the demo instrumentation, widened into I0 only if it causes a false answer in the Pitstop scenario). Acceptance: the I0 spec's own criteria, plus the G4/G5 spike tests rerun against the change, with the two cross-queue and later-window characterizations replaced by tests of the new behaviour.

## 4. I1 — Hosted live demo and local one-command version

Entry point: `examples/pitstop-demo/run.sh`

### 4.1 Declared overlay (operator-authored, disclosed)

AsyncAPI 2.6.0 files in the style of the v0.5.1 Quarkus overlay, one per service, each with an explicit `x-aip-service-id`, `x-aip-destination-kind: topic` and the shared `x-aip-broker-id`:

- publishes to `Pitstop`: WorkshopManagementAPI, CustomerManagementAPI, VehicleManagementAPI, TimeService;
- subscribes via a named queue: InvoiceService (`Invoicing`), NotificationService (`Notifications`), WorkshopManagementEventHandler (`WorkshopManagement`), AuditlogService (`Auditlog`), ReportingService (`Reporting`).

Overlay rules established by the spike: every document uses the same channel name `Pitstop` and the same `x-aip-broker-id`, sets no AMQP `virtualHost` (it would split the exchange into two Topics), carries `info.title` equal to the service's OTel `service.name` (§4.2), and gives each subscriber exactly one `subscribe` with `x-aip-subscription-name`. A subscriber without a name gets no Subscription.

Overlay files live under `examples/pitstop-demo/overlay/<service>/asyncapi.yaml`, outside the agent's checkout. A `PROVENANCE.md` records the pinned upstream SHA, the fork commit, and which file/line each declaration was read from. The overlay declares **no message payload or field**.

### 4.2 Live runtime evidence

- Pitstop runs continuously in the demo stack (Compose) with an OpenTelemetry Collector forwarding OTLP/HTTP to AIP.
- A **controlled traffic generator** registers customers and vehicles, plans and finishes jobs at a steady, documented rate, so every window contains traffic on the Topic. It publishes only through the application's own API.
- Each service resource carries `service.name` equal to its overlay `info.title` (AIP matches the declared Service **name**, not `x-aip-service-id`; a different `service.name` mints a second, observed-only Service and leaves the declared claims unqualified) and `deployment.environment.name` set to the demo environment (the legacy `deployment.environment` is not read). Messaging spans carry `messaging.operation.type` (`send`, `receive` or `process`; the legacy `messaging.operation` is ignored), `messaging.destination.name` equal to the exchange name `Pitstop` (exact), `messaging.system=rabbitmq` and, on consumer spans, `messaging.destination.subscription.name` equal to that service's declared queue name (G4).
- Instrumentation is a disclosed fork change (see the fork specification). It adds spans and attributes only.
- A timestamp-frozen OTLP fixture, authored from the same flows and documented as such, is kept under `examples/pitstop-demo/fixtures/` for tests and release qualification.

### 4.3 Deployment modes

**Hosted (canonical).** A long-running AIP + Neo4j instance, the Pitstop fork, the Collector and the traffic generator run on the owner's host. It is the product demo: always warm, queried through its MCP URL. Questions refer to the **last completed observation window**: an explicit, caller-chosen window (explicit UTC offset, at most 31 days) lying wholly in the past, which the demo prompt names explicitly. For the demo this is a documented UTC day. "Completed" is the demo's convention, not an AIP concept, and is meaningful only after I0 (H2). Operation: restarts must not change the claims for a completed window; a new window is usable after it completes; traffic gaps are visible as coverage, not hidden.

**Local (reproducible).** `examples/pitstop-demo/run.sh` starts AIP and Neo4j (existing Compose pattern), imports the overlay and identity/mapping configuration, and by default **replays the frozen fixture** with its fixed window, so the demo is usable immediately. `run.sh --live` additionally starts the Pitstop fork, Collector and traffic generator; its answers are available only after the first completed window, which may be the next day. The local version is for development, qualification and offline use, not the canonical demo.

The import is atomic: one invalid overlay document rejects the whole set and commits nothing, so both modes treat a rejected import as a hard failure, never a partial demo.

Both modes verify the semantic answers (§4.4), print the MCP URL, the environment and window to ask about, and the ready-to-use agent prompt.

Hosting concerns (access control for the MCP URL, secrets, RabbitMQ and SQL Server not exposed, sample passwords replaced) are decided and recorded by the owner and follow the fork specification.

### 4.4 Expected answers (frozen only after I0 and the G4/G5 rerun)

Target shape, stated as semantic expectations rather than byte-identical output, to be re-checked against what the product returns after I0 before this section is frozen:

- `get_service_dependencies(WorkshopManagementAPI)` for the chosen environment and window: five `RESOLVED_SERVICE` dependency claims (one per receiver: AuditlogService, InvoiceService, NotificationService, ReportingService, WorkshopManagementEventHandler), each with `delivery.via` = Topic `Pitstop` and `delivery.subscription` = that receiver's queue; one Broker claim for `rabbitmq:pitstop-rabbitmq`; no `UNRESOLVED_IDENTITY` limitation. Every claim carries the **publisher's** qualification for that window (`CONFIRMED` when a `send` span lies in the window, otherwise `NOT_OBSERVED_IN_WINDOW` with coverage); the qualification is the same for all five claims.
- Per-receiver runtime evidence is visible only as `OBSERVED` refs in each claim's `resolution_evidence_refs` (one declared ref, plus an observed ref when a matching consumer span lies in the window, after H2). It is route evidence, not a per-Subscription qualification: a receiver whose queue was never observed still reads `CONFIRMED` through its publisher. The demo states this and never claims per-Subscription confirmation.
- ReportingService's claim carries declared evidence from its own overlay; AIP contains no document evidence for that claim. The claim the demo makes is exactly this: ReportingService is absent from the knowledge visible to the agent (its checkout and `docs/`), yet present in AIP's independently maintained, operator-declared architecture evidence, with runtime route evidence. It is not a claim that runtime found an unknown consumer.
- `get_architecture_drift`: only what the existing rules produce (declared-but-unexercised, not "undocumented").
- Every claim's evidence refs resolve through `get_evidence` **at the answer's own snapshot**. The snapshot id changes whenever any evidence is ingested and a stale snapshot is refused (intended design), so calling `get_evidence` "immediately" cannot by itself make the drill-down reliable on a continuously ingesting instance. **Client drill-down protocol (bounded):** call `get_evidence` with the answer's `snapshot_id`; if it refuses the snapshot as stale, re-run `get_service_dependencies` for the same observation context, then retry `get_evidence` with the new answer's refs and snapshot; after at most 3 attempts report an explicit drill-down failure naming the last snapshot ids rather than citing unresolved refs. Because a completed window's claims do not change under later traffic (H2), the re-run yields the same claims and only the refs' snapshot binding moves. The skill, `/aip:inspect` and the demo prompt use this protocol; the hosted instance may additionally reduce the race but is not required to prevent it. Whether differing snapshot ids need anything beyond this is decided after the G5 rerun.

## 5. I2 — Question ladder and agent conversation

| # | Question | Must show | Must not claim |
|---|---|---|---|
| Q1 | What does `WorkshopManagementAPI` publish, and through which broker? | `PUBLISHES_TO` Topic `Pitstop`; Broker claim with evidence | That the Broker implies queues, consumers or event types |
| Q2 | Which services does AIP resolve as receiving from `Pitstop`? (Asked through the publisher: AIP has no receiver-side question) | The Subscriptions/Services AIP can resolve from the publisher's answer, with the exchange-wide scope stated and the resolution limits | That the consumers are per event type or that any of them handles `MaintenanceJobFinished` |
| Q3 | Why believe `ReportingService` receives from it? | Its declared overlay evidence and its route's runtime evidence, resolved at the answer's own snapshot | Evidence from different snapshots; confirmation beyond the evidence refs |
| Q4 | What actually ran in the selected window? | The publisher-driven qualification of the claims for the explicit environment and window, and which receiver routes carry observed evidence | A per-Subscription qualification; that an unobserved route is unused |
| Q5 | Which of them read `StartTime` and `EndTime`? | An explicit, labelled boundary: AIP holds no payload or field-usage knowledge | Any field usage, billing or reporting consequence |
| Q6 | What should I inspect before replacing the two fields? | The agent's own plan: inspect each receiving Service AIP resolves, including ReportingService when resolved, for use of the two fields; account explicitly for any unresolved receiver boundary; treat each receiver as unknown until inspected; propose a phased migration | That the change is safe or that AIP identified the breaking consumers |

Q5 and Q6 are the point of the demo: AIP supplies the evidenced receiver set it can resolve and states what it cannot know; absence of further evidence is never presented as completeness. The agent turns that into a bounded inspection and migration plan instead of trusting the documented four.

## 6. I3 — Claude Code client assets (plugin required, mod optional)

Location: `examples/pitstop-demo/claude/`. These show how a coding agent consumes the four existing tools; they are not part of the product contract. **Required for the demo:** plugin with skill and `/aip:inspect` (§6.1). **Optional and non-blocking:** the mod (§6.2); the release does not wait for it and its absence changes no answer.

### 6.1 Plugin

```
claude/plugin/
  .claude-plugin/plugin.json
  .mcp.json                      -> the AIP MCP URL printed by run.sh
  skills/architecture-aware-development/SKILL.md
  commands/inspect.md            -> /aip:inspect
```

**Skill `architecture-aware-development`.** Triggers on tasks that change an event, message contract, shared data, deployment or service boundary. It instructs the agent to:

1. Call `get_service_dependencies` for the service whose contract changes, for the **publishing** service of the changed event; the receiving Services are the `RESOLVED_SERVICE` claims in that answer (there is no receiver-side question). Call `get_evidence` at the answer's own snapshot for any claim it relies on, following the bounded drill-down protocol of §4.4 (on a stale-snapshot refusal re-run the dependency question for the same context and retry, at most 3 attempts, then report the drill-down as failed).
2. Write an **Evidence** section in the plan: each relevant Service/Subscription, the claim's qualification (`CONFIRMED`, `OBSERVED_ONLY`, `NOT_OBSERVED_IN_WINDOW`, with coverage; it is the publisher's and identical for all receivers), whether its route has observed evidence, its evidence refs and the snapshot id.
3. Copy the answer's limitations and `NOT_ANSWERED` statements into the plan as unknowns, not as risks resolved.
4. Never state what a consumer does with a payload from AIP evidence; say "inspect the consumer" instead.
5. Compare with the repository's documents itself and say so when they differ, labelled as the agent's reading of the documents.

**Command `/aip:inspect`.** Infers the subject from the session (service folder, files touched, last prompt) and calls the tools; prints a table of claims with qualification, limitations and evidence refs. With an argument, inspects that Service.

### 6.2 Mod (UX layer) — optional, non-blocking

```
claude/mod/
  .claude-plugin/plugin.json     (types: ./types/index.d.ts)
  hooks/hooks.json               { "modules": ["./register.tsx"] }
  hooks/register.tsx
  hooks/judge.test.ts
  types/index.d.ts
```

| Element | API | Behaviour |
|---|---|---|
| Relevance judge | `on('prompt.submit')` + `$.model.complete` (one `haiku` call) | Typed `{ relevant, reason }`. Relevant: append one line to the prompt telling the agent to use the skill and the AIP tools. Not relevant, failure or timeout: pass through unchanged. Never blocks |
| Band above the prompt | `ui.render` on `AbovePrompt` | Quiet by default; "AIP: relevant, <reason>" after a verdict; "consulting AIP" while tools run; a summary line from the last answer |
| Evidence pane | `$.ui.open` + `ui.render` on `Pane` | Claims table: Service/Subscription, qualification, limitation, evidence ref, snapshot id. Opened by `/aip:inspect` or a button, never unasked |
| Status / toast | `$.ui.status`, `$.ui.toast` | One line each |
| Reading answers | `on('tool.call', { tool: 'mcp__aip__*' })` | After `next(e)`, read only fields the released v0.6 schemas define (claims, qualification, limitations, evidence refs, snapshot id). **To confirm:** the shape of an MCP result inside a mod; fallback: the pane is fed by `/aip:inspect` only |

The mod and the judge are optional and may ship after 0.6.2 without a new release gate. Without them the skill alone must still produce the Evidence section. If the mod is built, keep it minimal: judge, band and the `/aip:inspect` pane first; the status line, toast and automatic tool-result reading only after the rest works.

**Judge test set.** Relevant: the §1 task; rename `MaintenanceJobFinished`; add retry to event publishing; add or delete customer data. Not relevant: rename a private method inside `WorkshopPlanning`; add a unit test for `MaintenanceJobRules`; fix a typo in the reminder e-mail; change the hourly rate constant; fix the `hh` format of the invoice id. Accept 9 of 9 on two runs.

## 7. I4 — Sanity check and lightweight release

### 7.1 Sanity check, not a validation gate

Pitstop was chosen through the candidate selection (with/without AIP plan comparisons on the scenario); that result stays the rationale and is not re-proved here. The release goal is a realistic live product demo.

Before release, one end-to-end sanity run on the hosted instance: ask Q1–Q6 through the plugin and check that the answers match §4.4 and §5, that Q5 returns the labelled boundary, and that the agent's resulting plan (a) names the receivers AIP resolves including ReportingService, (b) states that field usage is unknown to AIP and plans the inspection, and (c) presents no invented field usage as evidence. A failure is a defect to fix, not a stop/narrow decision.

The earlier first-signal results used per-consumer field-usage lines that v0.6.x cannot serve, so they do not transfer and are not quoted as 0.6.2 results. Product validation against the ROADMAP gates, with pre-registered thresholds, belongs to a later pilot, not to this release.

### 7.2 Smoke test and release path

- I0 (§3.3) is merged and the G4/G5 spike tests are rerun against it before any other I1 work; the release record cites both.
- The smoke test runs in `--replay` mode against the frozen fixture and asserts the answer shapes (§4.4) and the question ladder (Q1–Q6), including that Q5 returns the labelled boundary, and runs the MCP drills. Release qualification additionally requires the hosted instance to hold a completed live window and checks the semantic expectations against it.
- Update the main README entry point and the demo README: prerequisites, execution, question ladder, agent setup (plugin, optional mod), teardown.
- Use the lightweight release pattern of v0.6.1: one release-prep PR; exact merged SHA as candidate; green exact-SHA CI/CodeQL and full gate; the v0.6.1 release golden path and both demos (Quarkus and Pitstop) against a clean candidate image; owner's GO; publish `v0.6.2`; anonymous pull verification; one `v0.6.2-release-record.md`.
- The hosted instance is part of the release: it must be running and ingesting before the release GO, and the release record states its host, environment name, overlay version and fork commit.
- Publishing remains owner-decided.

## 8. Done

A developer is about to change `MaintenanceJobFinished` in Pitstop. The hosted Live AIP Demo, a continuously running Pitstop with controlled traffic, gives them, and their coding agent, the evidenced broker, topic and the receiving Services AIP can resolve for the Pitstop exchange in an explicit observation window, with qualification, limitations and evidence, including a receiver that no document lists. The answer states that field usage is not something AIP knows, so the agent plans a bounded inspection and a phased migration instead of trusting the documented consumer list.

A one-command local replay reproduces the same semantic architecture answers (not the hosted live behaviour; `--live` is optional and needs a completed window). The same persistent demo is the base for the later API-aware and Intent demos. Quarkus remains functional. No new semantics, source families, schemas or MCP tools were added (the I0 hardening corrected two evidence-correctness defects only), and the Claude Code plugin, skill and (optional) mod are example client material that can be removed without changing any AIP answer.
