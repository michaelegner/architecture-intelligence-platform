# AIP — Sokol111 API Current-State Probe, Round 6

**Status:** Draft  
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

This is suitable because the frozen Sokol111 sources already show:

- a Connect-RPC Catalog API with explicit ProductService operations;
- Traefik ingress exposing the Catalog service;
- Logto roles/scopes including `products:read`;
- `ecommerce-admin-ui` calling `ProductService.GetProductList`.

The engineering framing is:

> **Before changing `ProductService.GetProductList`, what native Sokol111 evidence can establish about who can access it and who actually used it in a selected environment/window?**

Round 6 does not need to plan or implement the API change.

## 3. Inputs

Reuse the Round 4 frozen revisions where applicable:

- `Sokol111/ecommerce-catalog-service-api`;
- `Sokol111/ecommerce-catalog-service`;
- `Sokol111/ecommerce-infrastructure`;
- `Sokol111/ecommerce-workspace` where useful.

Add `Sokol111/ecommerce-admin-ui` because it is a concrete Catalog API consumer. Freeze its exact revision before recording the result.

Do not add a gateway or modify Sokol111 merely to create evidence.

## 4. Native evidence to inspect

Inspect only enough to classify the v0.7 question.

| v0.7 distinction | Native Sokol111 evidence candidate |
|---|---|
| API / operation | protobuf / Connect-RPC contract and Catalog handlers |
| API exposure | Traefik / Kubernetes ingress for Catalog |
| consumer identity | Logto application identity and/or runtime request identity, if attributable |
| configured access | Logto application/role/scope configuration, but only if it actually establishes access for the identified consumer |
| observed usage | existing request telemetry/logs that identify both the operation and consumer |
| environment/window | deployment configuration plus timestamped runtime evidence |

Important guards:

- ingress exposure alone does not establish a configured consumer;
- a Logto role or scope alone does not establish that a specific application uses the API;
- a user role must not be promoted into a Service/application consumer identity;
- source calls from `admin-ui` are source evidence, not independently observed usage;
- missing runtime evidence must not become zero usage or non-use.

## 5. Method

### Step 1 — Establish the source-side facts

Record, with exact source paths:

- the operation definition;
- Catalog exposure through ingress;
- the `admin-ui` call site;
- relevant Logto applications, roles and scopes.

This establishes what the repositories/configuration say, not the v0.7 answer.

### Step 2 — Check independent evidence

Look for existing native evidence that could establish:

1. a stable consumer identity;
2. a request to `ProductService.GetProductList`;
3. the environment;
4. an observation time/window.

Prefer existing telemetry, access logs or identity-bearing request evidence. Do not add instrumentation merely to make the probe succeed.

If the system does not expose enough evidence to associate a request with a consumer, record that explicitly and stop the observed-usage path there.

### Step 3 — Map to v0.7 semantics

For each distinction classify the fit as:

- **SUPPORTED** — native evidence has the meaning required by v0.7;
- **PARTIAL** — some required meaning is present but attribution/context is incomplete;
- **UNSUPPORTED** — the source meaning does not establish the v0.7 distinction;
- **INSUFFICIENT_EVIDENCE** — the available evidence cannot decide.

Do not reinterpret Traefik, Logto or application code merely to match the APISIX implementation.

## 6. Result classification

Round 6 ends with exactly one primary disposition:

- **SUPPORTED_EVIDENCE_PATH** — native Sokol111 evidence can establish the full bounded v0.7 question and current AIP can consume it without semantic change;
- **SOURCE_ADAPTER_GAP** — the evidence is semantically sufficient for v0.7, but current AIP lacks the required source adapter/mapping;
- **SEMANTIC_GAP** — the native evidence establishes a product-relevant distinction that existing v0.7 semantics cannot represent safely;
- **INSUFFICIENT_EVIDENCE** — Sokol111's native evidence cannot establish the configured-consumer and/or consumer-attributed observed-usage question.

A source-adapter gap must not be promoted into a semantic gap.

## 7. Explicit non-goals

Round 6 SHALL NOT:

- involve Teamscale;
- add APISIX;
- replace Traefik;
- add synthetic consumer identities;
- modify Sokol111 instrumentation for the purpose of the experiment;
- treat Logto permissions as gateway subscriptions;
- implement a Traefik or Logto adapter;
- change AIP semantics;
- compare coding-agent plans.

Those are later decisions only if this probe demonstrates a useful native evidence path.

## 8. Output

Record the result in:

`docs/real-world-validation/v0.8.0/round6-sokol111-api-current-state-result.md`

Keep it compact:

1. frozen revisions;
2. bounded operation;
3. native evidence found;
4. v0.7 semantic-fit table;
5. one primary disposition;
6. one short consequence for later v0.8 product-boundary validation.

## 9. Exit

Round 6 is complete when it can answer:

> **Can Sokol111's native API/Traefik/Logto/runtime evidence support v0.7 API-aware Current State without system changes, and if not, is the blocker evidence availability, source ingestion, or semantics?**

No implementation is required to complete the round.
