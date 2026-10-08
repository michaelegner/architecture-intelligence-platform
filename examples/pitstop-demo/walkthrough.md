# Pitstop demo: question-by-question walkthrough

The task, from the [v0.6.2 spec](../../docs/specifications/0.6.2/specification.md) §1:

> In `MaintenanceJobFinished`, replace `StartTime` and `EndTime` with a single `Duration` field. The
> workshop only needs to report how long a job took. Plan the change.

Every answer below is a real AIP answer from `run.sh` on a clean checkout (ids shortened with `…`; they are
deterministic for these inputs). Blocks are kept apart:

- **AIP result**: returned by AIP, with its evidence.
- **Boundary**: what AIP states it cannot know. It is never filled in by a guess.
- **Agent suggestion**: what a coding agent should do with it. Not AIP output. (The agent's own plan comes
  with the Claude Code client assets, a later increment.)

Ask the **publisher**: AIP has no receiver-side question, so the receivers of the exchange are the claims in
`WorkshopManagementAPI`'s answer.

## Setup

```bash
examples/pitstop-demo/run.sh
CTX='environment=pitstop-demo&from=2026-10-06T00:00:00Z&to=2026-10-06T23:59:59Z'
```

The observation context is one whole UTC day wholly in the past: the only kind of window that is stable
under later evidence. The MCP calls pass it as
`{"environment": "pitstop-demo", "window_start": "2026-10-06T00:00:00Z", "window_end": "2026-10-06T23:59:59Z"}`.

In live mode (`run.sh --live`, see the README) the same questions are asked of a completed UTC day (the launcher
prints it); every consumer really receives there, so all five routes show an observed reference, `AuditlogService`
included, and the Q4 contrast below does not appear.

## Q1: What does `WorkshopManagementAPI` publish, and through which broker?

```bash
curl -s "http://localhost:8000/api/services/service:workshop-management-api/dependencies?$CTX"
# MCP: get_service_dependencies {service_id: "service:workshop-management-api", observation_context: {…}}
```

**AIP result** (`outcome: ANSWERED`, `schema_version: "0.6"`, no limitations): five `PUBLISHES_TO` claims, all
through the Topic `Pitstop`, and one Broker claim:

```json
{ "predicate": "USES_BROKER",
  "subject": {"name": "WorkshopManagementAPI"},
  "object": {"type": "BROKER", "name": "rabbitmq:pitstop-rabbitmq"},
  "evidence_refs": ["evidence:asyncapi:urn:aip:source:filesystem:8c45e452…"] }
```

**Boundary**: the Broker does not imply queues, consumers or event types. The Topic `Pitstop` is the fanout
exchange; AIP says nothing about which event types travel through it.

## Q2: Which services does AIP resolve as receiving from `Pitstop`?

The same answer. Each claim is `RESOLVED_SERVICE`, with the receiver as `object` and its queue as
`delivery.subscription`:

| Receiver (`object`) | Queue (`delivery.subscription`) | Qualification | Resolution refs |
|---|---|---|---|
| `AuditlogService` | `Auditlog` | `CONFIRMED` | 1 declared |
| `InvoiceService` | `Invoicing` | `CONFIRMED` | 1 declared, 1 observed |
| `NotificationService` | `Notifications` | `CONFIRMED` | 1 declared, 1 observed |
| `ReportingService` | `Reporting` | `CONFIRMED` | 1 declared, 1 observed |
| `WorkshopManagementEventHandler` | `WorkshopManagement` | `CONFIRMED` | 1 declared, 1 observed |

**Boundary**: receipt is per messaging destination (the exchange), **never per event type**. Nothing here says
that any receiver handles `MaintenanceJobFinished`.

**Agent suggestion**: list these five receivers as the set AIP can resolve. Compare with the repository's own
documents yourself and say so when they differ (for example, if a document lists fewer consumers), labelled as
your reading of the documents, not an AIP drift claim.

## Q3: Why believe `ReportingService` receives from it?

Resolve its claim's references at the answer's own snapshot:

```bash
# MCP: get_evidence {evidence_refs: [...the answer's evidence_refs...], snapshot_id: "<the answer's snapshot_id>"}
```

**AIP result**: its claim (`aip:claim:v1:…1495f41f4`) cites two resolution references:

- `evidence:asyncapi:urn:aip:source:filesystem:5b54bf8b…` is `DECLARED`, from `overlay/reporting-service/asyncapi.yaml`;
  it supports `RECEIVES_FROM` (`service:reporting-service` → the `Reporting` Subscription), `SUBSCRIPTION_OF`
  (that Subscription → Topic `Pitstop`) and `USES_BROKER`.
- `evidence:otel:pitstop-demo:2026-10-06:90fb53ddcf57` is `OBSERVED`, a `RECEIVES_FROM` for the same route.

**Boundary**: `ReportingService` is a fork addition that no upstream README, ADR or arc42 table lists. It is
present in AIP's **operator-declared** evidence (see [PROVENANCE.md](PROVENANCE.md)); runtime evidence
qualifies it but did not discover it.

**The bounded drill-down.** The snapshot id changes whenever any evidence is ingested, and a stale snapshot is
refused (intended design). Asking for a stale snapshot returns:

```json
{ "outcome": "NOT_ANSWERED", "data": null,
  "limitations": [{"code": "SNAPSHOT_NOT_AVAILABLE",
                   "message": "requested snapshot aip:snapshot:v1:0000…0000 is not the current stable snapshot"}] }
```

On that refusal, ask the dependency question again for the same window and retry `get_evidence` with the new
answer's references and snapshot, at most three times, then report the drill-down as failed. A completed
whole-UTC-day window yields the same claims each time; only the snapshot binding moves. In this replay nothing
ingests any more, so the first attempt resolves all eleven references (six declared, five observed).

## Q4: What actually ran in the selected window?

The same answer. Every claim reads `CONFIRMED`: that is the **publisher's** qualification, because one `send`
span from `WorkshopManagementAPI` lies in the window. AIP has no per-queue qualification, so `CONFIRMED` is
identical for all five receivers.

**AIP result**: four receiver routes (`Invoicing`, `Notifications`, `WorkshopManagement`, `Reporting`) also
carry an `OBSERVED` resolution reference. `Auditlog` carries only its declared one: this authored fixture
contains no receive span for it.

**Boundary**: an unobserved route is not an unused one. Which queue was never observed here is a property of
the fixture window, not a statement about the real system.

## Q5: Which of them read `StartTime` and `EndTime`?

**Boundary**: AIP holds no payload or field-level knowledge, and no answer, evidence record, overlay or
fixture here names `StartTime`, `EndTime`, a payload or an event type. The question has no AIP answer; the
smoke test asserts that no answer field contains them.

**Agent suggestion**: that is exactly what you must still inspect. Treat each of the five receivers as unknown
until you have read its code for use of the two fields, propose a phased migration, and do not present any
field usage, billing or reporting consequence as AIP evidence.

## Q6: What should I inspect before replacing the two fields?

This is the agent's own plan, built from the facts above: inspect each receiving service AIP resolves
(including `ReportingService`), account for any receiver AIP could not resolve, and propose a phased
migration. It is not AIP output. [`conversation-claude-code.md`](conversation-claude-code.md) records a real
Claude Code conversation over this demo (a scoped checkout of `WorkshopManagementAPI` and `docs/`, the `aip`
plugin loaded): it answers Q5 with "I can't say yet" and, for Q6, plans the inspection of all five receivers,
including `ReportingService`. It is an example, not qualification evidence, and its history section records two
earlier attempts that were discarded.
