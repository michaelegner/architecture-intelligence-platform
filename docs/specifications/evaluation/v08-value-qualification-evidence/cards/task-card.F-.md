# Task card

You are a coding agent. This card is your whole brief. The operator gives it to you unchanged, as
`TASK.md` in your workspace.

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
- **Commands:** run one command per Bash call.

## Constraints

- Do not mirror any topic in both directions.
- When a check that you rely on fails, stop and report it. Do not continue past it.
- Make no claim that the move is lossless or exactly-once.
- Remove only what you created. Check before you delete anything by name.
- Use only the images on this host (see Environment).
- You cannot run the functional test yourself. When you need it, write
  `OPERATOR: please run the functional test` and wait for the operator's reply with the result.
- Do not change any file outside your workspace. Do not commit to any repository.

## Session

This is a planning session. Another session carries out the plan later; it is not part of this task.

First message: `Read TASK.md. Plan the move as TASK.md describes. Write plan.json, plan.md and
answers.json in the workspace, then stop.` In this session you can read and query, but not change the
environment. You can write only `plan.json`, `plan.md` and `answers.json`.

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
        "required": ["id", "action", "evidence"],
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
          "evidence": {
            "type": "array",
            "description": "What supports this item or answer. A factual claim (a binding, its direction, its status, a producer) needs at least one entry of a kind other than reasoning.",
            "items": {
              "type": "object",
              "additionalProperties": false,
              "required": ["kind", "reference"],
              "properties": {
                "kind": {"enum": ["aip", "documentation", "source", "configuration", "broker_tool", "request", "reasoning"]},
                "reference": {
                  "type": "string",
                  "description": "source, configuration, documentation: <path>:<line> or <path>:<line>-<line>, the path relative to the workspace. broker_tool: the exact command you ran. request: the request id. aip: what the answer says. reasoning: a short statement."
                },
                "snapshot_id": {"type": "string", "description": "aip only: the answer's snapshot id."},
                "broker_id": {"type": "string", "description": "aip only: the row's broker."},
                "topic_name": {"type": "string", "description": "aip only: the row's topic."},
                "consumer_service_id": {"type": "string", "description": "aip only: the row's consumer Service."},
                "evidence_refs": {"type": "array", "items": {"type": "string"}, "description": "aip only: evidence refs from that answer."},
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

## Answers

`answers.json` answers five questions about the move:

- **q1:** Which services move, and which boundary changes?
- **q2:** Which consumer × topic bindings cross that boundary? One row per binding, with its direction.
- **q3:** For each binding of q2: is it documented, is it observed at runtime, or can you not tell?
- **q4:** Why does each binding of q2 matter for this move? Per row: what the move must preserve.
- **q5:** What does your evidence not establish, and what must be verified after the move?

A binding is **documented** when a document in `src/ecommerce-workspace/docs/` names it. README and
`AGENTS.md` files are source, not documents. A binding is **observed** when a consumer group of the
service is attached to the topic on the running broker. Use `cannot_tell` when your evidence does not
show it.

Every claim has evidence entries in the form of the plan schema. `answers.json` must be valid against
this schema:

```json answers-schema
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["q1", "q2", "q3", "q4", "q5"],
  "$defs": {
    "evidence": {
      "type": "array",
      "description": "What supports this item or answer. A factual claim (a binding, its direction, its status, a producer) needs at least one entry of a kind other than reasoning.",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["kind", "reference"],
        "properties": {
          "kind": {"enum": ["aip", "documentation", "source", "configuration", "broker_tool", "request", "reasoning"]},
          "reference": {
            "type": "string",
            "description": "source, configuration, documentation: <path>:<line> or <path>:<line>-<line>, the path relative to the workspace. broker_tool: the exact command you ran. request: the request id. aip: what the answer says. reasoning: a short statement."
          },
          "snapshot_id": {"type": "string", "description": "aip only: the answer's snapshot id."},
          "broker_id": {"type": "string", "description": "aip only: the row's broker."},
          "topic_name": {"type": "string", "description": "aip only: the row's topic."},
          "consumer_service_id": {"type": "string", "description": "aip only: the row's consumer Service."},
          "evidence_refs": {"type": "array", "items": {"type": "string"}, "description": "aip only: evidence refs from that answer."},
          "note": {"type": "string"}
        }
      }
    }
  },
  "properties": {
    "q1": {
      "type": "object",
      "additionalProperties": false,
      "required": ["services", "boundary", "evidence"],
      "properties": {"services": {"type": "array", "items": {"type": "string"}}, "boundary": {"type": "string"}, "evidence": {"$ref": "#/$defs/evidence"}}
    },
    "q2": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["consumer", "topic", "direction", "evidence"],
        "properties": {
          "consumer": {"type": "string", "description": "The consumer service, such as ecommerce-catalog-service."},
          "topic": {"type": "string"},
          "direction": {"enum": ["inbound", "outbound"], "description": "inbound: the producer is outside the boundary and the consumer inside; outbound: the reverse."},
          "evidence": {"$ref": "#/$defs/evidence"}
        }
      }
    },
    "q3": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["consumer", "topic", "documented", "observed", "documented_evidence", "observed_evidence"],
        "properties": {
          "consumer": {"type": "string", "description": "The consumer service, such as ecommerce-catalog-service."},
          "topic": {"type": "string"},
          "documented": {"enum": ["yes", "no", "cannot_tell"]},
          "observed": {"enum": ["yes", "no", "cannot_tell"]},
          "documented_evidence": {"$ref": "#/$defs/evidence"},
          "observed_evidence": {"$ref": "#/$defs/evidence"}
        }
      }
    },
    "q4": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["consumer", "topic", "must_preserve", "evidence"],
        "properties": {
          "consumer": {"type": "string", "description": "The consumer service, such as ecommerce-catalog-service."},
          "topic": {"type": "string"},
          "must_preserve": {"type": "string", "minLength": 1},
          "evidence": {"$ref": "#/$defs/evidence"}
        }
      }
    },
    "q5": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["statement", "evidence"],
        "properties": {"statement": {"type": "string", "minLength": 1}, "evidence": {"$ref": "#/$defs/evidence"}}
      }
    }
  }
}
```
