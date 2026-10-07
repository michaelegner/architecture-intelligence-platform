# FINOS FluxNova / CALM: Broker-only transcription

**Spec:** v0.6.1 §3 and §6.2. **Role:** the positive Broker-only case: broker-level connectivity is
answerable while richer messaging topology is not.
**Retrieval date:** 2026-10-06 (the upstream file was read at the pinned commit below; nothing else was fetched).

## Authored scenario data

Source (frozen): FINOS `architecture-as-code`, commit `c8c2811d28e10c12d0bf96be9434398585bb7d0e`,
`examples/fluxnova/fluxnova-microservices.architecture.json`
(<https://github.com/finos/architecture-as-code/blob/c8c2811d28e10c12d0bf96be9434398585bb7d0e/examples/fluxnova/fluxnova-microservices.architecture.json>).

What the upstream model authors about brokers (verified at that commit):

| CALM id | Kind | Meaning |
|---|---|---|
| `ms-payment-worker` | node | Payment Worker |
| `ms-notification-worker` | node | Notification Worker |
| `ms-message-broker` | node | Message Broker |
| `ms-payment-worker-to-broker` | relationship | `ms-payment-worker` -> `ms-message-broker`, protocol AMQP |
| `ms-notification-worker-to-broker` | relationship | `ms-notification-worker` -> `ms-message-broker`, protocol AMQP |

The upstream fixture identifies a broker-level connection but no Queue, Topic, Subscription or
Message, and a generic `connects` relation identifies no HTTP operation.

## Transcription package (operator-authored, disclosed)

These files are **not** upstream CALM files and **not** a CALM adapter; they are a small, disclosed
transcription of only the two broker links, authored from the pinned fixture:

- `declarations/<service>/openapi.yaml`: an identity-only OpenAPI declaration (`x-aip-service-id`,
  `paths: {}`) that establishes the existing phase-0 Service identity for each worker. It invents no
  Operation.
- `declarations/<service>/architecture.yaml`: an Architecture Manifest carrying only that Service's
  Broker use. The manifest format is one Service per document, so the transcription is **two small
  manifests, one per admitted Service** (spec §3 says "one manifest"; this is a documented
  deviation that follows the actual manifest model).
- Stable Broker id: `calm:finos-fluxnova:ms-message-broker`, derived from the source-native CALM node
  id, not from its display name "Message Broker", a host or the AMQP protocol.

The CALM ids above are qualification provenance recorded here; they are not new canonical Evidence
fields. These files land in the repository with the I3a change (the CI tests that consume them are
the deterministic form of the qualification). For the release qualification run against the clean
candidate image, the exact transcription commit is recorded in the I3 qualification record
(`docs/release-validation/v0.6.1-release-record.md`) **before** that run starts, and the run executes
from, or from a descendant of, that frozen commit. The transcription files must not be edited after
inspecting AIP output merely to improve an answer.

## Expected facts

- Exactly one Broker, `calm:finos-fluxnova:ms-message-broker`, and two `USES_BROKER` facts
  (Payment Worker and Notification Worker).
- Both Services answer with one BrokerClaim each (the v0.6 shape) and no dependency claim.

## Forbidden facts

- any Queue, Topic, Subscription, Message, Schema or Operation;
- any CALLS, SENDS, PUBLISHES_TO or other relation besides `USES_BROKER`;
- an HTTP operation, queue or topic invented from CALM `connects` or from the AMQP protocol.

## Unsupported / deferred

A general CALM adapter, CALM controls and patterns, and platform composition are out of scope
(`docs/landscape.md`). This transcription is a research-grade qualification input only.
