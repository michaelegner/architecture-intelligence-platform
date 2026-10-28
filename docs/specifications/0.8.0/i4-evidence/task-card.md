# Task card

You are a coding agent. This card is your whole brief. The operator gives it to you unchanged in both
sessions, as `TASK.md` in your workspace.

## Goal

Move **Catalog Management** (the services `ecommerce-catalog-service` and `ecommerce-image-service`)
from Redpanda to Apache Kafka. Apache Kafka MirrorMaker 2 bridges the two brokers. All other services
stay on Redpanda.

Nothing that consumes events today may stop receiving them because of the move.

## Environment

- **Sokol111** is an e-commerce system. Its source repositories are in `src/` in your workspace, at the
  revisions that run. Its documentation is in `src/ecommerce-workspace/docs/`.
- **Kubernetes:** a local k3d cluster. The services run in the namespace `dev`. The Helm values are in
  `src/ecommerce-infrastructure/environments/local/values/`. The Tilt process that deployed them is
  stopped. Do not start Tilt.
- **Redpanda:** the container `redpanda`. Address `redpanda:29092` on the Docker network
  `shared-network` (the pods use it), `localhost:9092` from the host. Use `rpk` through
  `docker exec redpanda rpk ...`.
- **Apache Kafka:** the container `kafka`, already running and empty (single node, KRaft). Address
  `kafka:29092` on `shared-network`, `localhost:19092` from the host. Its image includes the Kafka
  command-line tools and MirrorMaker 2 under `/opt/kafka/bin/`.
- **Images:** use only images that are already on this host, by the reference you see in
  `docker image ls --digests`. The Kafka image is
  `apache/kafka:4.1.2@sha256:5cc2a2fd93fa2687b44015eee04fb2c3edd9e526bd64bf8bec5ff1e268772e0e`.
  Pull nothing.
- **AIP** (Architecture Intelligence Platform) is connected as the MCP server `aip`. It is a read-only
  view of the architecture of this system: the declared architecture and the broker evidence. Query it
  with `bounded_context_id` `catalog-management` and `environment` `local`. Its answers carry a
  `snapshot.snapshot_id`; cite that id. AIP only reads. It does not change the system.

## Constraints

- Do not mirror any topic in both directions.
- When a check that you rely on fails, stop and report it. Do not continue past it.
- Make no claim that the move is lossless or exactly-once.
- Remove only what you created. Check before you delete anything by name.
- Use only the images on this host (see Environment).
- You cannot run the functional test yourself. When you need it, write
  `OPERATOR: please run the functional test` and wait for the operator's reply with the result.
- Do not change any file outside your workspace. Do not commit to any repository.

## Sessions

There are two sessions. Each starts with a fixed first message.

- **Planning session.** First message: `Read TASK.md. Plan the move as TASK.md describes. Write
  plan.json and plan.md in the workspace, then stop.` In this session you can read and query, but not
  change the environment. You can write only `plan.json` and `plan.md`.
- **Execution session.** First message: `Read TASK.md, plan.json and plan.md. Carry out the plan.
  Record every change to the plan in amendments.json. Stop when a check fails or when the move is
  done, and report.` The operator freezes `plan.json` and `plan.md` before this session starts. Do not
  edit them. A new or changed plan item goes into `amendments.json`, with its reason and the UTC time.

## Plan format

`plan.md` is your rationale in prose. `plan.json` is the plan as data. It must be valid against this
schema:

```json plan-schema
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["items", "allow_lists"],
  "properties": {
    "items": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["id", "action", "architecture_citations", "implementation_justification"],
        "properties": {
          "id": {"type": "string", "pattern": "^[A-Za-z0-9._-]+$", "description": "Your item id, unique in the plan."},
          "action": {"type": "string", "minLength": 1, "description": "What this item does, in one or two sentences."},
          "topics": {"type": "array", "items": {"type": "string"}, "description": "The Kafka topic names this item is about."},
          "direction": {
            "type": "object",
            "additionalProperties": false,
            "required": ["source", "target"],
            "description": "For an item that copies data between the brokers: from which broker to which.",
            "properties": {
              "source": {"enum": ["redpanda", "kafka"]},
              "target": {"enum": ["redpanda", "kafka"]}
            }
          },
          "services": {"type": "array", "items": {"type": "string"}, "description": "Service names, such as ecommerce-catalog-service."},
          "files": {
            "type": "array",
            "description": "The files this item creates or changes, and the keys it changes in them.",
            "items": {
              "type": "object",
              "additionalProperties": false,
              "required": ["path"],
              "properties": {
                "path": {"type": "string"},
                "keys": {"type": "array", "items": {"type": "string"}}
              }
            }
          },
          "architecture_citations": {
            "type": "array",
            "description": "The AIP claims this item relies on. Each names the snapshot and either one row of the binding picture or evidence refs from that answer.",
            "items": {
              "type": "object",
              "additionalProperties": false,
              "required": ["snapshot_id"],
              "properties": {
                "snapshot_id": {"type": "string"},
                "broker_id": {"type": "string"},
                "topic_name": {"type": "string"},
                "consumer_service_id": {"type": "string"},
                "evidence_refs": {"type": "array", "items": {"type": "string"}}
              }
            }
          },
          "implementation_justification": {
            "type": "array",
            "description": "What supports the way this item is carried out. AIP claims do not belong here.",
            "items": {
              "type": "object",
              "additionalProperties": false,
              "required": ["kind", "reference"],
              "properties": {
                "kind": {"enum": ["source", "configuration", "broker_tool", "reasoning"]},
                "reference": {"type": "string", "description": "A file and line, a command, or a short statement."},
                "note": {"type": "string"}
              }
            }
          }
        }
      }
    },
    "allow_lists": {
      "type": "array",
      "description": "One entry per MirrorMaker 2 flow that the plan creates: its source, target and topic allow-list.",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["flow", "source", "target", "topics"],
        "properties": {
          "flow": {"type": "string"},
          "source": {"enum": ["redpanda", "kafka"]},
          "target": {"enum": ["redpanda", "kafka"]},
          "topics": {"type": "array", "items": {"type": "string"}}
        }
      }
    }
  }
}
```

`amendments.json` is a list. Each entry must be valid against this schema:

```json amendment-schema
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["utc", "item_id", "change", "reason"],
  "properties": {
    "utc": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$"},
    "item_id": {"type": "string"},
    "change": {"enum": ["added", "changed", "dropped"]},
    "item": {"type": "object", "description": "The new or changed item, in the plan item format."},
    "allow_lists": {"type": "array", "description": "The changed allow-lists, in the plan format."},
    "reason": {"type": "string", "minLength": 1}
  }
}
```
