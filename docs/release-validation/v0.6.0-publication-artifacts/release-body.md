Published from qualified candidate `8102b8e4f1010c2c0d1395b91c79f3cd4c63429a` after [technical GO](https://github.com/michaelegner/architecture-intelligence-platform/blob/c3c8ef917ef70d5ab81caab8373af74bd72135c8/docs/release-validation/v0.6.0-release-readiness.md) and [owner publication authorization](https://github.com/michaelegner/architecture-intelligence-platform/blob/c265f90aedef6bcd8ee6ce92b7e8d092a4729ed0/docs/release-validation/v0.6.0-publication-decision.md). Published-artifact verification remains I6.5. The #323 fix is included and the issue is closed.

AIP adds the bounded question: **where are a Service's direct HTTP dependencies established, and
how do supported results differ between evidenced caller Workloads?** Discover candidate localities
without supplying Workload IDs, optionally compare selected Workloads at one snapshot, and drill
into scoped evidence through REST or negotiated MCP. There are exactly four read-only MCP tools.

The supported dimensions are environment, whole-UTC-day observation context, evidenced caller
cluster/namespace and exact captured Workload identity through CLIENT Pod UID and Kubernetes owner
chains. Region, tenant, service-version and messaging locality are deferred/unassigned. Target
runtime locality, local absence, global/exclusive dependency sets, Intent and causal paths are not
established by these answers. Inventory completeness describes the evaluated inventory and visible
bounds, not complete knowledge of all dependencies; local Workload coverage remains unavailable.

## Migration and contracts

Product, Producer and MCP server version become **0.6.0**. The original three tools retain public
schema **0.5**; locality request/answer use the published **0.6** schemas. These version numbers
serve different purposes.

Scoped evidence is now enabled by default. An existing configuration that omits the block adopts
v2/transition persistence when telemetry is processed; qualifying CLIENT identities can establish
isolated scoped observations. To retain legacy v1-only ingestion, configure:

```yaml
architecture_intelligence:
  telemetry:
    scoped-evidence:
      enabled: false
```

No identity is backfilled into legacy v1 aggregates. The cutover ledger and transition records
retain coexistence/accounting limits; see [configuration](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.6.0/docs/configuration.md) and the
[I2 decisions](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.6.0/docs/specifications/0.6.0/i2-decision-record.md). A graph supports one configured trace
stream; retention/compaction is not introduced. Without v2 observations the original canonical
snapshot remains unchanged, although default-on may create internal operational nodes. The
runtime-demo whole-graph oracle deliberately changes from 46 to 48 nodes.

The legacy natural-language path now requires every Evidence binding to use the inline exclusion
`(e:Evidence WHERE e.source_type <> 'KUBERNETES')`. Additional predicates belong in the outer WHERE.
Unfiltered or unprovable forms fail closed before execution. Non-Kubernetes evidence lookup remains
supported. This addresses [#323](https://github.com/michaelegner/architecture-intelligence-platform/issues/323)
under the owner's `FIX_BEFORE_RELEASE` disposition; issue closure and final security review remain
separate. The deterministic locality tool's authorized scoped-evidence access is unchanged.

## Evidence and limitations

The [walkthrough](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.6.0/docs/real-world-validation/v0.6.0/locality-walkthrough.md) distinguishes the actual
controlled two-Workload acquisition and independently adopted expectations from synthetic tests,
unchanged upstream Quarkus/Airflow truth and demo overlays. The controlled acquisition is not
production observation. Replay requires no live cluster, Kafka, upstream build or LLM after images
and dependencies are available.

Record rollout overlap while both Pod owner chains exist in C1. After authoritative C2 replacement,
retained P1 observations become unresolved; P2 remains independently supported. C1-bound requests
are stale/refused. Archived C1 files do not provide historical snapshot browsing.

The [I5 completion](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.6.0/docs/specifications/0.6.0/i5-completion-record.md) establishes bounded technical
qualification on its recorded candidates, not this release SHA. Accepted one-host I4 costs
and retained-state limitations remain bounded; production capacity and numerical SLOs are
unestablished. Product pilot is **NOT_RUN**, owned by Michael Egner with follow-up and product-value
gate carried to v1.0-rc stable-contract admission. No customer-benefit or stable-readiness claim.
