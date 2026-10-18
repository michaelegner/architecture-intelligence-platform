"""v0.7.1 I1.2: the separate Kafka capture step. It turns described consumer-group data into the
normalized capture file the source reads. The AIP server and import runtime never connect to Kafka;
the thin Admin API client lives in `harness/kafka-capture` and is not a project dependency."""
