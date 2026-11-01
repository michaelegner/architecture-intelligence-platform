# Verification record: binding picture (Catalog Management → Apache Kafka, local)

Artifact: `binding-picture/index.html` (self-contained HTML; data embedded; no network access).
Prepared: 2026-11-01. Environment in scope: local (k3d/Tilt values under
`src/ecommerce-infrastructure/environments/local/values/`).

## Session constraints that limited verification
- Shell (Bash) was denied in this session. No directory listing, grep, git, or browser was available.
  Files were opened by exact paths named in AGENTS.md files or reached by following imports and wiring.
- Revisions come from each repo's `.git/HEAD` (all detached HEADs). Working-tree cleanliness was **not** checked.
- No architecture-knowledge provider (API/MCP) was available, and no runtime captures were found.

## Checks performed
1. **Every factual statement has a reference.** In the data model, each statement in
   `est[]` carries `r[]` evidence IDs, and each interpretation lists `premises[]`. An inline
   self-check in the page renders a red "Integrity check FAILED" banner if any statement
   has no reference or cites an unknown ID. I reviewed the data by hand: every ID used exists in `EV`.
   This self-check has **not been executed**, because no browser was available.
2. **Bindings cross-checked directly against the source lines read in this session:**
   - **B1** (catalog → product-query, `catalog.product.events`): producer topic via `TopicFor`
     (`product_event_factory.go:67-85`), registry constant (`catalog-service-api/pkg/events/topics.go:11,18-19`),
     consumer config (`local/values/ecommerce-product-query-service.yaml:27-32`), and code registration
     by exact name `"catalog-events"` (`product-query .../kafka/fxconfig/module.go:14,19-24`). Direction confirmed:
     catalog produces, product-query consumes.
   - **B5** (tenant → catalog, `tenant.tenant.events`): producer (`tenant-service .../event_factory.go:19-43`),
     registry (`tenant-service-api/pkg/events/topics.go:11,16-17`), consumer module (`tenant-service-api/pkg/fxconfig/consumer.go:13,25-30`),
     composed in catalog (`catalog .../infrastructure/fxconfig/module.go:13`), and config (`local/values/ecommerce-catalog-service.yaml:37-42`).
     Direction confirmed: inbound to the selected side.
   - **B7** (catalog → image, internal): `image .../inbound/kafka/fxconfig/module.go:14,18-23` and
     `local/values/ecommerce-image-service.yaml:29-30`. The absence of retry/DLQ keys was confirmed by reading lines 23-36.
     The defaults chain was confirmed in `commons/pkg/kafka/config/defaults.go`, `constants.go:7`, and `consumer/fxconfig/module.go:84-89`.
   - **B10** (unresolved: topic provisioning): `kgo.AllowAutoTopicCreation()` confirmed at
     `commons/pkg/kafka/producer/fxconfig/module.go:35`. No topic declaration was found. Because there was no search tool,
     this stays "not found", not "absent".
   - **B14** (ambiguous: standalone broker addresses): `localhost:9092` (catalog standalone line 11) vs
     `localhost:29092` (image standalone line 15) vs compose port/advertise lines 16-19. The conflict is only between
     declarations. Connectivity was not tested.
3. **Boundary check.** The selected side is the task's definition. The page states that no ownership or
   architecture record was found. Counterparts were included only when a topic constant or config value
   matched exactly and a code registration matched by consumer name. No name-similarity matching was used.
4. **Provider check.** No provider input exists. Every binding has `provider: []`, and the detail view
   states that nothing comes from a provider. So removing provider input changes nothing, and no
   provider-only finding is shown as source-supported.

## Checks NOT performed
- Opening the artifact in a browser and clicking through it (binding selection, the direction/unresolved
  filters, evidence-link navigation). **Not performed**: no browser or shell was available. The JS was
  reviewed statically only.
- Running any service, querying the broker, or reading consumer-group offsets.
- Inspecting production values, the Nuxt UIs, `cmd/seeder`, or the tenant header-key implementation file.
- `git status` / commit dates.

## How to complete the open checks
1. Open `binding-picture/index.html` in a browser and confirm no red integrity banner appears.
2. Click row B7. The detail panel should show 6 established statements, then click `E-c-result` and confirm it scrolls and highlights.
3. Click "▼ Inbound". Only B5 and B6 should remain. Tick "only unresolved". Zero rows are expected (B5 and B6 are resolved).
   Reset to "All" with "only unresolved" ticked: B10, B11, B13, and B14 should show.
