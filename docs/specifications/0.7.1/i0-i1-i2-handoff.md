# AIP v0.7.1 I0 — Handoff to I1 and I2

Decisions are in [`i0-semantic-decision.md`](i0-semantic-decision.md).

## I1 (Kafka source) may rely on
- Carrier fields and id (D1); attachment edge with capture time T (D2); lifecycle rules (D6).
- Own replay fixture: declared Topic, structured capture, mapping artifact (Kafka decision §2).
- Production input must be structured; CLI text is not accepted.

## I2 (mapping + attribution) may rely on
- The mapping artifact is the only authority, resolved through `decide_service_identity` (D3).
- Temporal compatibility (D4) and the four outcomes (D5).
- The I0 §8 cases are the test list, including "do not mint the destination" and "do not mint the Service".

## Open, owned later
- Mapping artifact format (I2).
- Public answer vocabulary and whether a sixth MCP tool is needed (I3; none is pre-authorized).
- RabbitMQ contrast case wording in qualification (I4).
