# AIP v0.7.1 I0 — Handoff to I1 and I2

Decisions are in [`i0-semantic-decision.md`](i0-semantic-decision.md).

## I1 (Kafka source) may rely on
- Carrier fields and id (D1); attachment edge with capture time T (D2); lifecycle rules (D6).
- Own replay fixture: declared Topic, structured capture, mapping artifact (Kafka decision §2).
- Production input must be structured; CLI text is not accepted.

## I2 (mapping + attribution) may rely on
- Accepted mapping sources follow the D3 rule (explicit, provenance-bearing, environment-compatible, exactly one existing Service). The operator mapping artifact is the first supported source, not the only possible one.
- The Service must resolve as DECLARED through `decide_service_identity`. Reject its `OBSERVED_ONLY` outcome (D3), otherwise a Service would be minted.
- Temporal compatibility (D4) and the four outcomes (D5).
- The I0 §8 cases are the test list, including "do not mint the destination" and "do not mint the Service".

## Open, owned later
- Mapping artifact format (I2).
- Public answer vocabulary and whether a sixth MCP tool is needed (I3; none is pre-authorized).
- RabbitMQ contrast case wording in qualification (I4).
