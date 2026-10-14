# Round 4 — sminerport frozen revisions, baseline and feasibility

**Spec:** [spec-round4-finalist-technical-spike.md](spec-round4-finalist-technical-spike.md) §3, §5–§9  
**Reason evaluated:** Sokol111 was rejected ([feasibility](round4-sokol111-feasibility.md)), so the §3 fallback applies.

## 1. Frozen revisions (2026-10-13, default branch, `git rev-parse HEAD`)

| Repository | Role | Commit | Commit date |
|---|---|---|---|
| `sminerport/eCommerceSolution.ProductsService` | publisher | `7386ce0712d6f641b1ae6b301e9a5fddcff77fd4` | 2025-06-18 |
| `sminerport/eCommerceSolution.UsersService` | no messaging code (config only) | `ba98f02b956332ba090edd4020bd0bcbae6020f3` | 2025-06-18 |
| `sminerport/eCommerceSolution.OrdersService` | consumer | `05f8dd1fa165e506f16dbb0324c6ac5f321adf45` | 2025-06-18 |
| `sminerport/eCommerceMicroservices` | umbrella: AKS manifests, compose, frontend (submodule stubs empty) | `eef8b57b23ae55b84cb25de69f497aee5ec646e0` | 2025-07-07 |

## 2. Coding-agent/source baseline

Same method as the Sokol111 baseline: one fresh `claude -p` session, tools restricted to
`Read,Grep,Glob`, working directory containing only the four frozen checkouts, no files modified.
There is no `AGENTS.md`/`CLAUDE.md` in these repositories, so the baseline relies on source, config
and READMEs. Contamination disclosure as in the Sokol111 baseline: the AIP plugin skill was visible,
failed to run, and no AIP call was made.

**Prompt (verbatim):**

> You are working in a multi-repo workspace (all repositories are checked out in this directory). Task: a developer wants to change the message contract/header semantics of the `product.update` RabbitMQ message published by the Products service. Before any change is made, investigate and report: (1) which services/repositories you chose to inspect and why; (2) which distributed relationships (who publishes, who consumes, via which exchange/queue/binding, in which environments) you consider ESTABLISHED, with exact source/config evidence (file paths); (3) which relationships remain INFERRED or UNCERTAIN and why; (4) what you would change or check in each affected repository. Do not modify any files. Be concise and structured.

**Result (agent output, verbatim):**

    I made no changes. This is from reading code and config only. I didn't query AIP, because the `aip:architecture-aware-development` skill failed to run. I loaded its three tool schemas but never called them, so none of this has AIP or runtime confirmation.

    ## 1. What I inspected and why
    - **`eCommerceSolution.ProductsService`**: it publishes `product.update`.
    - **`eCommerceSolution.OrdersService`**: a repo-wide search for `product.update`, the exchange name and the header names turned up its consumer.
    - **`eCommerceSolution.UsersService`**: it defines `RABBITMQ_PRODUCTS_EXCHANGE` in its per-environment configmaps, so I checked it for a consumer. I found no publisher, consumer, `QueueBind` or `BasicConsume` code for it. It only has config entries.
    - **`eCommerceMicroservices`**: the umbrella repo with the AKS manifests, the docker-compose files and a frontend. Its `eCommerceSolution.*` folders are empty submodule stubs (`.gitmodules`), so there is no duplicate code. I looked at it for deployment evidence.

    ## 2. Established relationships
    **Publisher:** Products → exchange `products.exchange` (headers type, durable). The exchange name is `RABBITMQ_PRODUCTS_EXCHANGE` (set in `ProductsMicroService.API/Dockerfile:38`).
    - Header names and values are set in `ProductsService/BusinessLogicLayer/Services/ProductsService.cs:88-94`: `event=product.update` and `row-count=1`. The same lines publish the body.
    - The body is the mapped `Product` entity (`productToUpdate`), not the saved `updatedProduct`. The JSON is serialized by `ProductsService/BusinessLogicLayer/RabbitMQ/RabbitMQPublisher.cs:65-95`.
    - The routing key is empty, `mandatory: true`, and the headers go into `BasicProperties.Headers` (same file).

    **Consumer:** Orders → queue `orders.product.update.queue` (durable). The queue is bound to `products.exchange` with arguments `x-match=all`, `event=product.update`, `row-count=1`.
    - Bound in `OrdersService/BusinessLogicLayer/RabbitMQ/RabbitMQProductUpdateConsumer.cs:57-86`.
    - Started via `DependencyInjection.cs:25,27`.
    - It deserializes the body to `ProductDTO` (`ProductID`, `ProductName`, `Category`, `UnitPrice`, `QuantityInStock`) and writes the product into the distributed cache (`HandleProductUpdationAsync`, lines 113-124).

    **Both sides use the same exchange name, `products.exchange`, in every environment I found:**
    - Orders: `k8s/{dev,qa,uat,staging,prod}/*-configmap.yaml` and `docker-compose.yml:31,69`.
    - Products: the Dockerfile `ENV`. Its `k8s/*/products-microservice-*-deployment.yaml` set the host, port and credentials but not the exchange.
    - AKS: `eCommerceMicroservices/aks/ecommerce-configmap.yaml:33`, applied to the Products and Orders deployments through `envFrom` (`aks/products-deployment.yaml:24`, `aks/orders-deployment.yaml:23`).

    **Broker:**
    - Each environment has its own broker: `ProductsService/k8s/{dev,qa,uat,staging,prod}/rabbitmq-*.yaml`, with `RABBITMQ_HOST=rabbitmq` and per-namespace deployments (for example `namespace: dev`).
    - AKS has a separate one: `eCommerceMicroservices/aks/rabbitmq-deployment.yaml`.
    - Local docker-compose has one too.

    **Coupling:** the consumer's binding needs exactly `event=product.update` and `row-count=1` to match. In a headers exchange with `x-match=all`, any change to either header value, or dropping one, means Orders' queue stops receiving the message. The failure is silent: the message is dropped, with no error on either side.

    ## 3. Inferred or uncertain
    - **Other consumers.** Queue bindings are created at runtime, so there may be bindings on the live broker that no repo declares. Only Orders is established as a consumer. I found nothing in Users, the frontend or the API gateway, but I can't rule out other bindings.
    - **Which environments actually run this.** The manifests exist for dev, qa, uat, staging, prod and AKS, but I can't tell which are deployed. The Products dev/qa/uat/staging/prod manifests also include their own gateway, MySQL, Redis and RabbitMQ.
    - **Exchange value in Products k8s.** It comes only from the Dockerfile default, so an environment could override it outside these repos. I saw no override in the files.
    - **Payload shape mismatch.**
      - The body is serialized from the `Product` entity, where `UnitPrice` and `QuantityInStock` are nullable (`DataAccessLayer/Entities/Product.cs`).
      - Orders deserializes them into non-nullable `double` and `int` in `ProductDTO` (`OrdersService/BusinessLogicLayer/DTO/ProductDTO.cs`).
      - A null price or quantity would fail deserialization. Whether that can happen depends on validation, which I didn't verify.
      - The two sides don't share a contract definition, so the sync is by convention only.
    - **Message content.** The body is `productToUpdate`, not the persisted entity. If the database update returns null, the message is still published first.
    - **Queue state.** Any messages already waiting in `orders.product.update.queue` during a rollout will use the old contract. Existing queue bindings on live brokers also persist, since the binding is declared but never removed.
    - **Deploy order.** The repos deploy independently, with separate `azure-pipelines.yml` files. I didn't check release ordering.

    ## 4. What I'd change or check, per repo
    - **ProductsService**
      - Change the headers at `ProductsService.cs:88-92` and keep the body unchanged unless the body is also changing.
      - Consider publishing the persisted entity (`updatedProduct`) instead of the pre-update one.
      - Check the unit tests in `ProductsUnitTests` that assert the publisher call.
      - Also check `RabbitMQPublisher.Publish` if the exchange type or routing is meant to change.
    - **OrdersService**
      - Update the binding arguments in `RabbitMQProductUpdateConsumer.cs:57-62` and `ProductDTO` if the body changes.
      - Don't change the queue's name or binding in place. A durable queue keeps its old binding, so either add a new binding alongside the old one during rollout, or unbind the old one explicitly.
      - Check the delete consumer for consistency, since it shares the `row-count` convention.
    - **Release order**
      - Support both old and new header values on the consumer side first.
      - Switch the publisher second.
      - Remove the old binding last.
    - **UsersService**
      - No change expected. Just confirm it doesn't bind to the exchange outside the repo.
    - **eCommerceMicroservices**
      - Nothing to change if the exchange name stays the same.
      - Otherwise `aks/ecommerce-configmap.yaml` and the compose files would need updating.
    - **Live brokers**
      - List the bindings on `products.exchange` in each environment before and after the change. This is the only way to settle the "other consumers" question.

**Assessment.** The baseline is strong for the static relationship: publisher, consumer, exchange
(`products.exchange`, headers type), queue (`orders.product.update.queue`), binding arguments
(`x-match=all`, `event=product.update`, `row-count=1`) and per-environment configuration. It
correctly identifies the silent-failure coupling. What it explicitly **cannot** settle is the
broker's live state: bindings created at runtime that no repository declares, other consumers, and
which environments actually run.

## 3. Independent distributed evidence

- **OpenTelemetry:** none. No OpenTelemetry package or instrumentation exists in either service
  (`grep -i opentelemetry` over `*.csproj`/`*.cs` finds nothing), so there are no messaging spans.
- **Broker topology** (RabbitMQ management API / definitions: exchange → queue bindings with header
  arguments, active consumers) would be genuinely independent and answers the open question above.
  It exists only on a running broker; **it was not captured** in this round (the Round 4 live
  preference applies to the leading candidate, and this candidate had no ingestible evidence path;
  see below).

## 4. AIP feasibility (from current AIP docs and code; no AIP code changed)

| Question | Finding |
|---|---|
| Can AIP ingest RabbitMQ broker topology (management API, definitions export)? | No such source exists (`app/` references AMQP only in `asyncapi_adapter.py` for AsyncAPI bindings). **Ingestion gap** |
| Can AIP represent a headers-exchange binding (`x-match` + header predicates) as a relation? | No code or doc handles `x-match`/header-matching routing; a Topic needs `x-aip-destination-kind: topic` plus a stable broker id, and routing predicates have no home in the Canonical Model. **Semantic gap** |
| Can AIP use declared AsyncAPI for these services? | None exists for these repositories; it would have to be authored for the evaluation, and could express a Topic/Queue but not the header predicate |
| Can OTel qualify it? | No spans are emitted. **No relevant evidence** |

Classification: **semantic gap** (header-based routing) plus **ingestion gap** (broker topology) plus
**no relevant evidence** (runtime spans). A semantic gap weighs strongly against selection (§8).

## 5. Comparison record (spec §9)

| Field | Content |
|---|---|
| Candidate | sminerport eCommerceSolution Products/Orders/Users + umbrella, revisions in §1 |
| Change | `product.update` RabbitMQ message contract/header semantics |
| Expected boundary | Products (publisher), `products.exchange`, Orders queue and consumer, configmaps |
| Coding-agent/source result | Complete static boundary incl. the silent header-mismatch failure mode |
| Unresolved source question | Runtime bindings, other consumers, which environments run |
| Distributed evidence | Broker topology would answer it; not captured; no OTel |
| AIP feasibility | Cannot ingest or represent it |
| AIP gap | Semantic + ingestion + no OTel evidence |
| Plausible investigation difference? | **Unclear for the question; no for current AIP** — the open question is real and broker-answerable, but AIP cannot represent the answer |
| Setup cost | Medium (full compose stack: MySQL, Mongo, Postgres, Redis, RabbitMQ) |
| Reproducibility | Not demonstrated |
| Public-demo value | Weak (small sample, no telemetry) |
| Verdict | **Reject** |
