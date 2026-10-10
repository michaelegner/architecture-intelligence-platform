# Pitstop demo: input provenance

The demo describes a private fork of [EdwinVW/pitstop](https://github.com/EdwinVW/pitstop) (a .NET
garage-management sample on RabbitMQ). Both inputs below are **demo-owned**: neither is
upstream-supplied, and neither is qualification evidence.

| Revision | Value |
|---|---|
| Upstream pin | `306b5fbd0febceb6b0d0706f152a0520ca1a993a` (EdwinVW/pitstop, 2026-10-06) |
| Instrumented fork commit (live mode) | `15b21c6a0741c4d2a08cca57babfe9576f0b204c` — adds `send`/`process` spans to `Infrastructure.Messaging` (package `5.5.0-aip.3`), a local NuGet feed and `docker-compose.otel.yml`; `FORK.md` "Telemetry" describes it |
| Fork baseline commit | `7bf6674c30af749614c66069158bf78bfda54e94` — private, local repository (`pitstop-fork`, no remote); `FORK.md` records the pin and the fork's only addition, `ReportingService` |

Every citation below is `file:line` under the fork's `src/` at the fork baseline commit; all of them except
`ReportingService/` are identical to the upstream pin (a recursive `diff -rq` of the two `src/` trees lists only
`ReportingService/`, `docker-compose.yml`, `pitstop.sln` and four scripts, plus the ignored `.containerdata/`). To reproduce:
`git -C <fork> show 7bf6674c30af:src/<path>` and `git -C <upstream clone> show 306b5fbd0feb:src/<path>`.

| Input | Kind | Origin |
|---|---|---|
| [`overlay/`](overlay/) (9 files) | **Operator-authored** AsyncAPI declaration | This demo |
| [`fixtures/otlp.json`](fixtures/otlp.json) | **Authored** OTLP/JSON replay fixture | This demo |

## `overlay/`: operator-authored AsyncAPI for the RabbitMQ exchange `Pitstop`

Pitstop ships no AsyncAPI, so the overlay declares what the code does, as a team would: one fanout exchange
`Pitstop`, declared `fanout`, durable, on every publisher and consumer
(`Infrastructure.Messaging/RabbitMQMessagePublisher.cs:98`, `RabbitMQMessageHandler.cs:93`; the config key is
`"Exchange": "Pitstop"` in each service's `appsettings.Production.json:6`). Each consumer declares and binds
its own durable queue (`RabbitMQMessageHandler.cs:94-95`, consumed with manual ack at `:98`; routing key
empty). The message type travels in the `MessageType` header (`RabbitMQMessagePublisher.cs:81`,
`RabbitMQMessageHandler.cs:120`); there is no shared schema.

| Service (overlay `info.title`) | Role | Queue (`x-aip-subscription-name`) | Source |
|---|---|---|---|
| WorkshopManagementAPI | publishes | | `WorkshopManagementAPI/CommandHandlers/PlanMaintenanceJobCommandHandler.cs:35`, `FinishMaintenanceJobCommandHandler.cs:35` |
| CustomerManagementAPI | publishes | | `CustomerManagementAPI/Controllers/CustomersController.cs:47` |
| VehicleManagementAPI | publishes | | `VehicleManagementAPI/Controllers/VehiclesController.cs:54` |
| TimeService | publishes | | `TimeService/TimeWorker.cs:39` |
| InvoiceService | consumes | `Invoicing` | `InvoiceService/appsettings.Production.json:7`, dispatch `InvoiceWorker.cs:36-45` |
| NotificationService | consumes | `Notifications` | `NotificationService/appsettings.Production.json:7`, dispatch `NotificationWorker.cs:35-44` |
| WorkshopManagementEventHandler | consumes | `WorkshopManagement` | `WorkshopManagementEventHandler/appsettings.Production.json:7`, dispatch `EventHandlerWorker.cs:43-52` |
| AuditlogService | consumes | `Auditlog` | `AuditlogService/appsettings.Production.json:7`, `AuditLogWorker.cs:31-36` |
| ReportingService | consumes | `Reporting` | `ReportingService/appsettings.Production.json:7`, `ReportingWorker.cs:36` (handles only `MaintenanceJobFinished`) |

What the accepted overlay gives AIP: **declaration evidence** for four `PUBLISHES_TO` relations to Topic
`Pitstop`, five named Subscriptions of it with one `RECEIVES_FROM` each, and one Broker
`rabbitmq:pitstop-rabbitmq` used by all nine services. It declares **no message payload or field**: AIP holds
no field-level knowledge, and the demo never claims any.

**`ReportingService`.** It is the fork's only addition: it appears in no upstream README, ADR or arc42 table
(the arc42 §8.1 consumer table of `MaintenanceJobFinished` lists four consumers). Its overlay entry is derived
from the fork's own source at the baseline commit above. The claim the demo makes is exactly that it is present
in AIP's independently maintained, **operator-declared** architecture evidence — not that runtime discovered an
unknown consumer.

## `fixtures/otlp.json`: authored runtime observation

The fixture is **authored, not captured**: the fork has no OpenTelemetry instrumentation yet, so no real span
exists to transcribe. It is written from the flows above, with frozen timestamps inside the whole UTC day
`2026-10-06` (12:00–12:07Z), environment `pitstop-demo`: one `send` span per publisher
(`messaging.operation.type=send`) and one `process` span with `messaging.destination.subscription.name` for
four consumers. Every span carries `messaging.system=rabbitmq` and `messaging.destination.name=Pitstop`, and each
resource's `service.name` equals the overlay's `info.title` (AIP matches the declared Service **name**).
Span names carry no event type and no payload.

**`AuditlogService` has no receive span, deliberately.** The real service consumes every message; the fixture
omits it so the demo exercises the boundary that an unobserved route is not an unused one: the publisher's
claims read `CONFIRMED` for all five receivers, while only four routes carry observed evidence. This is an
authored choice about the fixture window, not a statement about the real system.

The live demo (`run.sh --live`) does not use this fixture: it runs spans emitted by the instrumented fork
(commit `15b21c6a0741`), where every consumer, `AuditlogService` included, really receives. The fixture is
replay-only: the default `run.sh` mode, tests and release qualification.
