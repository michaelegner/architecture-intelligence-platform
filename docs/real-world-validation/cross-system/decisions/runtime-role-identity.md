# Decision: Service, Role, and Instance Identity

Spec §11 / §9 question 2. Covers ledger finding `airflow-runtime-role-identity`.

## Context

Airflow's architecture has four independently deployed component roles - scheduler, DAG
processor, worker, triggerer - that are architecturally distinct but were left `UNRESOLVED_IDENTITY`
in I3 rather than modeled as separate canonical `Service` instances, because every native OTel span
this qualifying profile produces reports the identical generic `service.name: unknown_service`
regardless of which component emitted it (`airflow-runtime-role-identity` in
`docs/real-world-validation/apache-airflow/findings.md`; independently reconfirmed in I3.2's Phase B
raw-telemetry inspection). I4 must decide whether this justifies a canonical model change - adding a
`Process`/`RuntimeRole`/`Deployment`/`ServiceInstance` concept - or whether preservation remains
correct.

## Independent evidence

```text
app/canonical/model.py (re-read for this decision): Service is {id: str, name: str} only -
    no role, instance, deployment, or process hierarchy exists in the Canonical Model today.

Airflow (I3.1/I3.2): four architecturally distinct roles, one indistinguishable service.name
    at the OTel layer for all of them.

Quarkus Super Heroes (I2): four REST services (rest-fights, rest-heroes, rest-villains,
    rest-narration) plus one async producer role - each with a distinct, correctly resolved
    service.name. No role/instance ambiguity was ever encountered; every Quarkus finding in
    findings.md is either CORRECT or an unrelated UNSUPPORTED/DEFER (gRPC, Kafka), none touching
    Service identity.
```

## Alternatives considered

1. **Preserve the current flat `Service` model.** Chosen - see Decision.
2. **Add a `RuntimeRole`/`Process` concept now**, keyed off Airflow's four named components.
   Rejected: spec §11's gate requires the change be "justified beyond one upstream naming
   convention" and that "both systems require the same general distinction." Quarkus's evidence
   does not exhibit this problem at all - a model change motivated by exactly one system's naming
   convention is precisely what §11 prohibits admitting into I4. It would also fail §11's
   "identifiers and reconciliation rules can be deterministic" and "declared and observed
   identities can reconcile without guessing" gates: Airflow's own OTel evidence cannot even
   supply a per-role `service.name` today (`unknown_service` for all four), so there is no
   deterministic signal to key a new identity tier on without inventing one.
3. **Repair the ambiguity with a heuristic** (e.g. infer role from hostname, container name, or
   process argv). Rejected outright - spec §10.3 explicitly forbids repairing ambiguous identities
   with name/hostname/container/queue-specific heuristics, and spec §11 requires reconciliation
   without guessing.

## Decision

`DEFER` (not `NO_CHANGE`): the missing capability is real and named, but not yet justified across
systems. `airflow-runtime-role-identity` remains `UNRESOLVED_IDENTITY`, unchanged from I3.

## General semantic rule

None adopted. The Canonical Model's `Service` stays `{id, name}` with no role/instance hierarchy.
`UNRESOLVED_IDENTITY` remains the correct, safe representation for a case where independent
evidence suggests a distinction that cannot be safely resolved without guessing (I1's finding
vocabulary definition, applied here exactly as intended).

## Consequences

- No graph, API, analysis, or adapter change.
- `airflow-runtime-role-identity` continues to correctly withhold a per-role `Service` claim
  rather than inventing one from Airflow's component naming convention.
- Answers spec §9 question 2 directly: a runtime role/instance distinction is not needed to
  prevent a false supported claim - `UNRESOLVED_IDENTITY` already prevents it, safely.

## Production changes

None.

## Regression coverage

None required (no implementation change).

## Quarkus impact

None. Quarkus's `Service` identities remain exactly as resolved by I2.

## Airflow impact

None. `airflow-runtime-role-identity` stands exactly as I3.1/I3.2 left it.

## Deferred work

A future iteration MAY introduce a role/instance identity tier if a second system independently
exhibits the same general ambiguity (an architecturally distinct component set that OTel cannot
disambiguate by `service.name`) AND that system's evidence can supply a deterministic signal to
key the new tier on - closing the gap this decision explicitly leaves open in Airflow's own
evidence today.
