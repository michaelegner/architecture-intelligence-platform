---
name: aip-reading-answers
description: Use when you call an AIP (Architecture Intelligence Platform) tool or report an AIP answer. States how to read AIP answers correctly - the observation context, qualification, evidence references, the snapshot retry, and the unknowns that an answer carries - and that AIP is read-only.
---

# Reading AIP answers

AIP answers from declared architecture and runtime observation. Each answer says how far each claim
is evidenced. Use AIP to bound your work. Do not use it as a replacement for reading the code.

## General rules (all tools)

- **Use AIP read-only.** The AIP tools perform no writes. Do not try to change AIP, and do not
  present an AIP answer as a change you made.
- **Never invent context.** Use the environment, the window and the ids that the user or the task
  gives you. If none is given, ask. Ids are exact canonical ids, never names, paths or hosts.
- **Report the unknowns.** Copy each `limitations` entry and each `NOT_ANSWERED` statement into your
  result as an unknown, never as a risk resolved. Insufficient evidence is a limitation, never
  absence.
- **No payload knowledge.** AIP holds no payload or field-level knowledge. Which consumer reads a
  field is something you must inspect in that consumer's code.
- **No evidence is not non-use.** A route or a row without observed evidence is not an unused route.
  An empty or short list is never proof that nothing else exists.
- **Evidence refs are opaque.** Do not parse them. Resolve them with the evidence mode or tool that
  belongs to the answer, at the answer's own `snapshot_id`.
- **The snapshot retry.** The snapshot id changes whenever evidence is ingested. A stale snapshot is
  refused with `NOT_ANSWERED` and the limitation `SNAPSHOT_NOT_AVAILABLE`. Then ask the same
  question again for the **same** context and retry the evidence call with the new answer's refs and
  snapshot. Make **at most three attempts** in total. If all fail, report the drill-down as failed,
  name the last snapshot ids, and do not cite unresolved refs.

## Observation context (`get_service_dependencies`, `get_architecture_drift`)

- These tools require an explicit `observation_context`: `environment`, `window_start` and
  `window_end`, each with an explicit UTC offset. There is no default window.
- Use one or more whole UTC days that are wholly in the past. A day that has not ended can still get
  new evidence.
- The window is inclusive. A whole-UTC-day window runs from `T00:00:00Z` of its first day through
  `T23:59:59Z` of its last day. Never end it at the next day's `T00:00:00Z`. The window must not
  exceed 31 days.
- `get_service_dependencies_by_locality` takes `first_day` and `last_day` (whole UTC days) instead.

## Dependency and drift answers (`get_service_dependencies`, `get_architecture_drift`, `get_evidence`)

- Each dependency claim carries a qualification: `CONFIRMED`, `OBSERVED_ONLY` or
  `NOT_OBSERVED_IN_WINDOW`, with coverage when it is not observed.
- For a message route (Queue or Topic), the qualification is the **publisher's**. It comes only from
  the publisher's own evidence and is the same for all receivers of that route. AIP has no
  per-receiver qualification.
- A claim's `evidence_refs` support the claim itself. For a message route these are the
  publisher's, and they say nothing about the receiver. A resolved receiver's route evidence is in
  the claim's `resolution_evidence_refs`.
- Receivers of a Topic are resolved per messaging destination, never per event type. An answer says
  nothing about which receiver handles which event.
- Resolve `evidence_refs` and `resolution_evidence_refs` with `get_evidence`, passing the same
  `snapshot_id`.
- `get_architecture_drift` returns only claims whose qualification is `OBSERVED_ONLY` or
  `NOT_OBSERVED_IN_WINDOW`. Report what it returns. `NOT_OBSERVED_IN_WINDOW` is declared but not
  observed in the window; it is not "unused" and not "undocumented".

## Other tools

- **`get_service_dependencies_by_locality`:** a positive result is never a complete list of the
  service's dependencies. A relationship that is missing from one Workload is not evidence that it
  is absent there. Resolve its refs with its own `"evidence"` mode, not with `get_evidence`.
- **`get_api_consumer_usage`:** configured access and observed usage are two separate statements.
  Established configured access is not approval or intent. Observed usage is not approved usage or a
  payload-field dependency. `USAGE_UNESTABLISHED` is not zero and not non-use. A missing
  configured-access fact is not denial or misconfiguration. Resolve its refs with its own
  `"evidence"` mode.
- **`get_destination_consumers`:** an attachment of a consumer group at capture time T is not
  message processing, and it does not mean that the Service still consumes the Topic after T. The
  Service attribution comes only from explicit mapping evidence; report an unresolved, ambiguous or
  conflicting attribution as it is. An evaluated answer is always `PARTIAL` with
  `CAPTURE_SCOPE_LIMITED`, so an empty or short list is never "no consumers". Resolve its refs with
  its own `"evidence"` mode.

## What not to claim

- Do not claim that a change is safe, or that AIP identified every affected consumer.
- Do not state what a consumer does with a payload, or which fields it reads, from AIP evidence.
  Say "inspect the consumer", and plan that inspection for each consumer that AIP resolves.
- Treat each consumer as unknown until you have inspected it. Absence of further evidence is never
  completeness.
