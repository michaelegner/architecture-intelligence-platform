# Example Fixture Landscape

The directories in `examples/` are the reference architecture fixtures used by the local Quick Start
and across the test suite. Together, the four core service directories model a small mixed
REST-and-messaging system with both normal relationships and deliberate orphan-queue cases.

## Core topology

```text
OrderService
   |
   +---- REST call: getProduct ----------------------> ProductService
   |
   +---- publishes ----------------------------------> payment-q
                                                      |
                                                      v
                                                 PaymentService
                                                      |
                                                      +---- publishes ----> invoice-q
                                                                             |
                                                                             v
                                                                        InvoiceService

Orphan-analysis fixtures:
OrderService ---- publishes ----> unused-q              (no consumer)
unknown producer ----> unknown-producer-q ---- consumes PaymentService
```

The fixture intentionally includes two queue edge cases:

- `unused-q` has a sender but no consumer, exercising the A3 orphan-queue analysis.
- `unknown-producer-q` has a consumer but no known sender, exercising the A4 orphan-queue analysis.

`payment-q` also declares `payment-dlq` as its dead-letter queue.

## Service directories

| Directory | Files | What it represents |
| --- | --- | --- |
| [`order-service/`](order-service/) | `openapi.yaml`, `asyncapi.yaml`, `architecture.yaml` | Exposes the OrderService REST API, declares the REST call to `ProductService.getProduct`, and publishes to `payment-q` and `unused-q`. |
| [`product-service/`](product-service/) | `openapi.yaml` | Exposes `getProduct`; it has no messaging fixture. |
| [`payment-service/`](payment-service/) | `asyncapi.yaml` | Consumes `payment-q`, publishes `invoice-q`, and consumes `unknown-producer-q`. |
| [`invoice-service/`](invoice-service/) | `asyncapi.yaml` | Consumes `invoice-q`. |

## What the fixture files mean

- `openapi.yaml` describes a service's declared HTTP API surface and is consumed by AIP's OpenAPI
  ingestion path.
- `asyncapi.yaml` describes declared messaging channels, messages, publishers, consumers, and queue
  metadata for AIP's AsyncAPI ingestion path.
- `architecture.yaml` supplements source formats with architecture information they cannot express
  themselves. In this fixture it records that `order-service` calls `product-service` through
  `getProduct`.

The manifest is deliberately narrow: it adds the REST-caller relationship rather than duplicating
facts already present in the OpenAPI or AsyncAPI documents.

## Using the fixtures

The repository's default `config.yaml` points `sources.directories` at `examples/`, so after the
local development environment and Neo4j are running, `POST /api/import` imports this bundled
reference architecture without additional source configuration.

For setup, test commands, and the local import flow, see
[`docs/development.md`](../docs/development.md). For the contracts that declared and runtime source
adapters must satisfy, see [`docs/adapter-development.md`](../docs/adapter-development.md).

## Other examples

The top-level directory also contains two self-documented example areas that are separate from the
four declared-architecture fixture services:

- [`runtime-demo/`](runtime-demo/) walks through the Collector-based runtime telemetry demo.
- [`mcp-clients/`](mcp-clients/) contains candidate setup guides for connecting coding-agent client
  families to AIP's MCP endpoint.
