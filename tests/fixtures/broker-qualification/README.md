# Broker qualification fixtures (v0.6.1 I3)

Hand-authored expectations and operator-authored inputs for `tests/integration/test_broker_qualification.py`,
`tests/integration/test_broker_qualification_systems.py` and
`tests/unit/test_broker_qualification_airflow.py` (spec §6.1/§6.2). Nothing here is generated from AIP
output. `SHA256SUMS` pins every file; see each `PROVENANCE.md` for what is authored, what is expected,
what is forbidden, and why the Pub/Sub expectations are siblings of (not edits to) the frozen
`tests/fixtures/pubsub` trees.

| Directory | Role |
|---|---|
| `azure-service-bus/`, `google-pubsub/`, `kafka/` | Broker expectations over the untouched `tests/fixtures/pubsub/<name>/declarations` |
| `calm-fluxnova/` | the disclosed FINOS FluxNova/CALM transcription package (Broker-only positive) |
| `airflow-negative/` | the negative Redis-Broker manifest for an unadmitted Airflow worker |
