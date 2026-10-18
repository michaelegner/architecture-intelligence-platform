# AIP — Sokol111 API Current-State Probe, Round 6

**Status:** Completed — see [round6-sokol111-api-current-state-result.md](round6-sokol111-api-current-state-result.md)  
**Input:** Round 4 Sokol111 evidence plus the released v0.7.0 API-aware Current-State semantics  
**Purpose:** Test whether Sokol111's native API, ingress, identity/access and runtime evidence can support the v0.7 configured-vs-observed API question without adding APISIX or otherwise changing the system.

Round 6 is **not** a Teamscale comparison and is not a new AIP capability. It is a small source/semantic feasibility experiment.

## 1. Question

Round 6 SHALL answer:

> **Can Sokol111's existing native evidence establish the same bounded API Current-State distinctions that v0.7.0 models: API exposure, configured consumer access, and independently observed consumer-attributed usage in an explicit environment/window?**

The experiment must separate:

- what Sokol111 source/configuration says;
- what independent deployment/runtime evidence says;
- what fits existing v0.7 semantics;
- what current AIP can or cannot ingest.

A negative result is valid.

## 2. Bounded scenario

Use the Catalog API and one concrete operation:

> **`ProductService.GetProductList`**

Preliminary repository inspection suggests the following candidate evidence:

- a Connect-RPC Catalog API with explicit ProductService operations;
- Traefik ingress exposing the Catalog service;
- Logto roles/scopes including `products:read`;
- `ecommerce-admin-ui` calling `ProductService.GetProductList`.

These are **hypotheses for Round 6**, not yet qualification findings. Step 1 must confirm or reject them against the frozen revisions before they are used in the result.

The engineering framing is:

> **Before changing `ProductService.GetProductList`, what native Sokol111 evidence can establish about who can access it and who actually used it in a selected environment/window?**

Round 6 does not need to plan or implement the API change.

## 3. Inputs

Reuse and record the exact Round 4 frozen revisions where applicable:

- `Sokol111/ecommerce-catalog-service-api`;
- `Sokol111/ecommerce-catalog-service`;
- `Sokol111/ecommerce-infrastructure`;
- `Sokol111/ecommerce-workspace` where useful.

Add `Sokol111/ecommerce-admin-ui` because it is a candidate concrete Catalog API consumer. Freeze its exact revision before using its source as Round 6 evidence.

Do not add a gateway or modify Sokol111 merely to create evidence.

## 4. Native evidence to inspect

Inspect only enough to classify the v0.7 question.

| v0.7 distinction | Native Sokol111 evidence candidate |
|---|---|
| API / operation | protobuf / Connect-RPC contract and Catalog handlers |
| API exposure | Traefik / Kubernetes ingress for Catalog |
| consumer identity | Logto application identity and/or runtime request identity, if attributable |
| configured access | Logto application/role/scope configuration, but only where the access grant can be tied to the identified consumer |
| observed usage | existing request telemetry/logs, or an allowed local run, that identify both the operation and consumer |
| environment/window | deployment configuration plus timestamped runtime evidence |

Important guards:

- ingress exposure alone does not establish a configured consumer;
- a Logto role or scope alone does not establish that a specific application uses the API;
- a user role must not be promoted into a Service/application consumer identity;
- source calls from `admin-ui` are source evidence, not independently observed usage;
- missing runtime evidence must not become zero usage or non-use.

## 5. Method

### Step 1 — Freeze and establish the source-side facts

Before treating the §2 hypotheses as findings, freeze the Round 6 source revisions and record, with exact source paths:

- the operation definition;
- Catalog exposure through ingress;
- the `admin-ui` call site;
- relevant Logto applications, roles and scopes.

This establishes what the repositories/configuration say, not the v0.7 answer.

### Step 2 — Check independent evidence

First look for existing native evidence that could establish:

1. a stable consumer identity;
2. a request to `ProductService.GetProductList`;
3. the environment;
4. an observation time/window.

Prefer existing telemetry, access logs or identity-bearing request evidence.

A local run is allowed **only** when it uses unmodified Sokol111 components, existing instrumentation and identities created through Sokol111's normal configuration. Generated test traffic is allowed; fabricated consumer identities, added instrumentation or gateway changes are not.

If obtaining such a run requires expanding into the high-cost full-stack setup already identified in Round 4, the round may stop the runtime path and record `INSUFFICIENT_EVIDENCE` rather than modifying the system to make the experiment succeed.

If the available runtime evidence cannot associate a request with a consumer, record that explicitly and stop the observed-usage path there.

### Step 3 — Map to v0.7 semantics

For each distinction classify the fit as:

- **SUPPORTED** — native evidence has the meaning required by v0.7;
- **PARTIAL** — some required meaning is present but attribution/context is incomplete;
- **UNSUPPORTED** — the source meaning does not establish the v0.7 distinction;
- **INSUFFICIENT_EVIDENCE** — the available evidence cannot decide.

Do not reinterpret Traefik, Logto or application code merely to match the APISIX implementation.

## 6. Result classification

Round 6 ends with exactly one primary disposition. Choose it in this order:

1. **INSUFFICIENT_EVIDENCE** — the native evidence cannot establish the full bounded configured-consumer plus consumer-attributed observed-usage question.
2. **SEMANTIC_GAP** — the native evidence is sufficient, but it establishes a product-relevant distinction that existing v0.7 semantics cannot represent safely.
3. **SOURCE_ADAPTER_GAP** — the native evidence is sufficient and fits v0.7 semantics, but current AIP lacks the required source adapter or mapping.
4. **SUPPORTED_EVIDENCE_PATH** — the native evidence is sufficient, fits v0.7 semantics, and current AIP already has an applicable ingestion path.

The per-distinction table retains partial findings even when the primary disposition is decided earlier in this sequence.

With current Traefik/Logto support, `SUPPORTED_EVIDENCE_PATH` is a control outcome rather than an expected result; do not weaken `SOURCE_ADAPTER_GAP` merely to make it reachable.

A source-adapter gap must not be promoted into a semantic gap.

## 7. Explicit non-goals

Round 6 SHALL NOT:

- involve Teamscale;
- add APISIX;
- replace Traefik;
- add synthetic consumer identities;
- add or modify Sokol111 instrumentation for the purpose of the experiment;
- treat Logto permissions as gateway subscriptions;
- implement a Traefik or Logto adapter;
- change AIP semantics;
- compare coding-agent plans.

Those are later decisions only if this probe demonstrates a useful native evidence path.

## 8. Output and v0.8 consequence

Record the result in:

`docs/real-world-validation/v0.8.0/round6-sokol111-api-current-state-result.md`

Keep it compact:

1. frozen revisions;
2. bounded operation;
3. native evidence found;
4. v0.7 semantic-fit table;
5. one primary disposition;
6. one short consequence for later v0.8 product-boundary validation.

Round 6 does not itself perform or decide the v0.8 product-boundary comparison. If it establishes a semantically sufficient native API evidence path, that path may become an additional Current-State scenario in the later product-boundary validation. If it ends in `INSUFFICIENT_EVIDENCE` or `SEMANTIC_GAP`, record that limitation instead of constructing a comparison around it.

## 9. Exit

Round 6 is complete when it can answer:

> **Can Sokol111's native API/Traefik/Logto/runtime evidence support v0.7 API-aware Current State without system changes, and if not, is the blocker evidence availability, source ingestion, or semantics?**

No implementation is required to complete the round.
