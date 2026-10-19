# Kafka consumer-state capture

Operator-run step that writes the capture file the v0.7.1 Kafka consumer-state source reads
([contract](../../docs/specifications/0.7.1/i1-kafka-source-contract.md)). It describes exactly the
groups you pass, through the Kafka Admin API. The AIP server never connects to Kafka.

```bash
export KAFKA_BOOTSTRAP_SERVERS=broker:9092 PYTHONPATH=.   # run from the repository root
uv run --with confluent-kafka==2.16.0 python harness/kafka-capture/capture.py \
  --broker-id kafka:cluster-a --environment prod \
  --group payment-service --group order-service --out kafka-consumer-state.json
```

- `--broker-id` must be the `x-aip-broker-id` of the declared Topics, not the bootstrap address.
- Exit code 1 means the file was written but is incomplete (a group could not be described); the
  source will reject it. A group mid-rebalance is written as is and is rejected by the source too.
- `--client-config` takes a JSON object of librdkafka properties (SASL/TLS). They are used to
  connect and are never written to the output.
- `kafka_version` is `not-established`: the Admin API exposes no broker version. The client library
  version is recorded in `tool_version`.
- The tool refuses to write (exit 3) if any secret-looking client setting value appears in the capture.
