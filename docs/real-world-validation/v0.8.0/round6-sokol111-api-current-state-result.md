# Round 6 — Sokol111 API Current-State Result

**Spec:** [spec-round6-sokol111-api-current-state-probe.md](spec-round6-sokol111-api-current-state-probe.md)  
**Date:** 2026-10-18  
**Primary disposition:** **INSUFFICIENT_EVIDENCE**

Round 6 tested whether Sokol111's native API, Traefik, Logto and runtime evidence can satisfy the
released **source-independent v0.7 API Current-State contract** without changing the system.

APISIX is only the first implemented and qualified v0.7 source adapter. It is not part of the
semantic definition tested here. Round 6 therefore applies the existing v0.7 distinctions to a
second, non-APISIX evidence architecture.

## 1. Frozen inputs

| Repository | Revision | Use |
|---|---|---|
| `Sokol111/ecommerce-catalog-service-api` | `7cecb3e1131dbd5199ce25e9cf101d75d3365171` | ProductService contract |
| `Sokol111/ecommerce-catalog-service` | `e9f147483e6e33ec512851d478169d2985614b09` | handler registration and permission mapping |
| `Sokol111/ecommerce-infrastructure` | `07c059908b99e08448cf1c2c7dad6a865fe5ccf0` | Traefik/Ingress, Logto and environment configuration |
| `Sokol111/ecommerce-admin-ui` | `3abcf9ba4d4fd89c2ee247c0c2212c9453427352` | concrete Catalog API caller |
| `Sokol111/ecommerce-commons` | `d54bf55eba79566286b57b630f5d5b0d68b64302` | HTTP tracing and auth interceptor used by Catalog |

The first three and `ecommerce-commons` reuse the Round 4 freeze. The admin-ui revision was frozen
from its `master` head before using it as Round 6 evidence.

## 2. Bounded operation

The operation is `ProductService.GetProductList`.

The contract declares it in
`ecommerce-catalog-service-api/proto/catalog/v1/product.proto`. Catalog registers the ProductService
Connect handler and requires `products:read` for this procedure in
`ecommerce-catalog-service/internal/infrastructure/inbound/connect/fxconfig/module.go`.

The admin UI is a concrete source-level caller:
`ecommerce-admin-ui/server/utils/catalog-client.ts` creates a ProductService client and calls
`getProductList`.

## 3. Native evidence findings

### API exposure is environment-specific and not the admin-ui call path

In local configuration, Catalog has Traefik ingress enabled at
`ecommerce-catalog-service.127.0.0.1.nip.io`
(`environments/local/values/ecommerce-catalog-service.yaml`). In production, Catalog ingress is
explicitly disabled
(`environments/production/values/ecommerce-catalog-service.yaml`).

More importantly, admin-ui does not call Catalog through that ingress. Both local and production
admin-ui configuration set:

```text
NUXT_CATALOG_API_URL=http://ecommerce-catalog-service:8080
```

so the Nuxt server calls the internal Kubernetes Service directly. Traefik therefore establishes a
local exposure path, but not the `admin-ui -> GetProductList` relationship being tested.

### Logto establishes permissions, not a stable admin-ui consumer relationship

`cmd/logto-seed/seed.json` defines `admin-ui` as a Traditional application. It has no application
role assignment. User roles such as `super_admin`, `catalog_manager` and `viewer` carry
`products:read`; the separate `ecommerce-service` MachineToMachine application receives the
`service_account` role.

The admin UI obtains a logged-in user's access token and forwards that bearer token to Catalog
(`server/utils/auth-token.ts`, `server/utils/catalog-client.ts`). Its OIDC callback requests
`products:read` and checks the user's role/scopes
(`server/routes/auth/oidc/callback.get.ts`, `server/utils/auth-access.ts`).

Catalog independently maps `GetProductList` to `products:read`. This establishes an operation
permission rule, but the frozen configuration does not establish a v0.7-style configured
**application consumer -> API** relationship for admin-ui.

### Existing request telemetry does not establish consumer-attributed usage

Catalog tracing is enabled in both local and production configuration. The frozen
`ecommerce-commons` HTTP server wraps requests with `otelhttp.NewHandler`
(`pkg/http/server/fxconfig/module.go`), so a running Catalog can emit HTTP server spans.

The auth interceptor validates the bearer token, checks the procedure permission and stores claims
in request context (`pkg/security/validation/interceptor.go`). It does not emit a stable caller
application identity into the request telemetry path inspected here. No Traefik access-log
configuration or admin-ui OpenTelemetry instrumentation was found in the frozen sources used for
this probe.

No live Sokol111 runtime evidence was available. Round 4 already established that a realistic local
run requires the larger tenant/Logto/Postgres/MinIO stack. Round 6 did not recreate that stack:
source inspection already showed no existing evidence path that could safely attribute a
`GetProductList` request to admin-ui as a stable application consumer. A driven local request
would therefore demonstrate request execution, not the full consumer-attributed v0.7 relation.

## 4. Fit to the source-independent v0.7 contract

| v0.7 distinction | Result | Finding |
|---|---|---|
| API / operation | **SUPPORTED** | `ProductService.GetProductList` is explicit in the contract and registered implementation |
| API exposure | **PARTIAL** | Traefik exposes Catalog locally; production ingress is disabled; admin-ui uses the internal Service directly |
| consumer identity | **PARTIAL** | Logto has an admin-ui application identity, but the API call forwards a user token and no runtime evidence ties the request to that application identity |
| configured access | **PARTIAL** | `products:read` is explicit for the operation and user roles, but not as an admin-ui application-consumer access relationship |
| observed usage | **INSUFFICIENT_EVIDENCE** | no captured request evidence identifies both `GetProductList` and a stable application consumer |
| environment / window | **PARTIAL** | environment-specific deployment configuration exists, but no captured request supplies an observation window |

## 5. Disposition

Per the Round 6 ordering, the result is **INSUFFICIENT_EVIDENCE**.

The blocker occurs before adapter availability: Sokol111's current native evidence does not
establish the full configured-consumer plus consumer-attributed observed-usage question for this
operation.

This is **not** a limitation of the v0.7 semantic model and does not make APISIX part of that model.
The source-independent v0.7 distinctions remain applicable; the present Sokol111 evidence simply
does not satisfy them strongly enough to evaluate a new source adapter. No semantic extension is
indicated by this round.

This is also not evidence that the API is unused, that admin-ui lacks access, or that no other
consumer exists.

## 6. v0.8 consequence

Do **not** add the **current** Sokol111 API scenario to the later product-boundary comparison as-is.

The useful finding is narrower: to satisfy the already source-independent v0.7 contract, a native
evidence path must establish a stable consumer identity plus consumer-specific configured access and
independently observed usage. Sokol111's current Traefik + Logto + internal-service path does not
yet provide those facts strongly enough.

A follow-up experiment may enhance Sokol111 itself to expose a trustworthy application identity in
its normal identity/telemetry path and an explicit application-level configured-access relation,
then rerun the **unchanged v0.7 semantics**. If that evidence becomes sufficient but AIP cannot
ingest it, the expected result would be `SOURCE_ADAPTER_GAP`. Only a genuinely useful distinction
that cannot be represented safely by the existing v0.7 vocabulary would constitute
`SEMANTIC_GAP`.

The Sokol111 messaging scenario remains independent of this result.
