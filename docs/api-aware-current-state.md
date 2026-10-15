# API-aware Current State (v0.7.0)

AIP v0.7.0 answers one bounded question, qualified for the **APISIX** gateway source only:

> **Which consumers have configured access to an API exposure, which of them have independently
> observed usage in a selected completed window, and what remains unresolved or unsupported?**

The answer is the fifth read-only MCP tool, `get_api_consumer_usage`, and the REST routes
`POST /api/api-consumer-usage` and `POST /api/api-consumer-usage/evidence`. It never says that a
change is safe, who owns an API, or whether a consumer is authorized. This page is the short guide;
every section links to the frozen specification that holds the detail.

## Why APISIX, and what was surveyed

The release started from a capability survey of four gateways (Kong, Gravitee, Apache APISIX and
Tyk) and two spikes on real instances. APISIX was selected because its Admin API gives a unique,
non-secret consumer identity and its Prometheus plugin gives consumer-attributed request counters
through an unauthenticated metrics endpoint. Tyk was kept only as a cross-check: its key alias is not
unique. See the [survey](specifications/0.7.0/i0-capability-survey-matrix.md) and the
[selection decision](specifications/0.7.0/i0-source-selection-decision.md).

## Two kinds of evidence, never merged

- **Configured access** is a fact from the gateway's configuration: an APISIX Route whose
  `consumer-restriction` allow-list names a Consumer. It is not a permission check, an approval or
  intent. The Consumer is an APISIX username on one gateway instance, not a person or an application.
  See the [gateway source contract](specifications/0.7.0/i1-gateway-source-contract.md).
- **Observed usage** comes from a measurement window: the difference between two scrapes of the
  Prometheus plugin's counters, attributed to a Consumer and a Route. Requests the gateway itself
  rejects are counted separately from requests passed to the upstream. See the
  [measurement contract](specifications/0.7.0/i2-measurement-contract.md).

Each answer row keeps the two propositions apart. `configured_access` is
`CONFIGURED_ACCESS_ESTABLISHED` or `NO_MATCHING_CONFIGURED_ACCESS_FACT`. `usage` is
`OBSERVED_USAGE`, `MEASURED_ZERO` (only when the measurement coverage allows a zero) or
`USAGE_UNESTABLISHED`. Traffic with no consumer label creates no consumer row; it is reported as an
unattributed limitation on the Route.

## Environment, window and coverage

The gateway does not report an environment, so the operator declares it with the capture. A window is
bounded by two settled scrapes. Absence of a series is not a zero: a zero is claimed only when the
Route's Prometheus plugin was enabled for the whole window and the boundaries were settled. Otherwise
the answer says `USAGE_UNESTABLISHED` and names the reason. See the measurement contract above.

## Identity: what is and is not the same thing

A Route is not an API Operation, a gateway Service is not an application Service, and an APISIX
Consumer is not a credential. The Route-to-Operation chain and the target-to-application-Service
chain are independent, and neither is inferred from names, paths or hosts:

- An association is established by an explicit statement (the optional `apisix-mapping.json` in the
  measurement source root, or an `aip/service` label on a Route or gateway Service for the Service
  chain) or, for Operations, by an exact path and method match.
- Otherwise it stays `UNRESOLVED`, and ambiguous or conflicting statements stay `AMBIGUOUS` or
  `CONFLICT`. **Without a mapping or an exact match, the association is unresolved by design.** In the
  pinned replay world every Route is unresolved until an operator supplies a mapping.

Subscriptions, products, plans, owners, authorization and architectural Intent are not inferred,
because APISIX's `consumer-restriction` is an allow-list on a Route and none of those concepts. See
the [identity dossier](specifications/0.7.0/i0-identity-reconciliation-dossier.md).

## Asking the question

Through negotiated MCP (see [`mcp.md`](mcp.md#get_api_consumer_usage-v070-i3) for the full contract):

```json
{"name": "get_api_consumer_usage",
 "arguments": {"request": {
   "mode": "query",
   "target": {"kind": "API_OPERATION", "id": "operation:service:order-service:POST:/orders"},
   "gateway_instance_id": "gw-prod-1", "environment": "prod",
   "window_start": "2026-10-13T10:00:00Z", "window_end": "2026-10-13T10:10:00Z"}}}
```

The same request without `mode` goes to `POST /api/api-consumer-usage` as the JSON body. The target
`kind` is `API_OPERATION`, `APPLICATION_SERVICE` or `GATEWAY_ROUTE`, and the ids are exact. Results
are paged; a continuation is bound to its snapshot.

## Evidence drill-down

Every row, Route and window carries opaque `api-evidence:` references. Resubmit the same query context
with `"mode": "evidence"`, the answer's `snapshot_id` and up to 20 references. References resolve only
at that snapshot and context. A forged, stale or cross-context reference is `NOT_RESOLVED`.

## Limitations and unsupported cases

- **APISIX 3.19.0 only**, over the Admin API with etcd; other versions produce a window reason.
- **The configured-access model is qualified for APISIX only.** A Tyk-style key-held, API-version
  scoped access cannot be carried without a reviewed amendment (a `MODEL_GAP`, scoped out of v0.7).
- **Mapping dependence**, as above. The consumer list is complete only for the Routes the answer
  names, never for an Operation as a whole.
- Environment and coverage are operator assertions; counters are cumulative and lag, so windows
  settle before they are read.
- Costs grow with the whole selection (F1), every request reads the whole canonical state (F2) and
  the evidence reference map is rebuilt per call (F3).
- No payload-field dependency, and no complete consumer population.

## How it was qualified, and how to replay it

The frozen expectations are written independently of the code and run twice on one exact commit with
byte-identical results across the service, REST and MCP. The real-source replay (captures from the
pinned APISIX 3.19.0, revisions R1 and R2) lives in
[`specifications/0.7.0/i4-replay/`](specifications/0.7.0/i4-replay/README.md); the release golden path
replays it against the supplied image (`examples/release-golden-path/`, phase `api-usage`). To
capture your own gateway see [`development.md`](development.md#capturing-an-apisix-measurement-window-v070-i22)
and `python -m app.gateway_capture.apisix --help`. The qualification record is
[`specifications/0.7.0/i4-execution-record.md`](specifications/0.7.0/i4-execution-record.md).

## Product-value pilot

One recorded coding-agent session on the pinned replay world ended in `CONTINUE`. It is one bounded
session, not user research. See the [pilot record](specifications/0.7.0/i4-pilot-record.md).
