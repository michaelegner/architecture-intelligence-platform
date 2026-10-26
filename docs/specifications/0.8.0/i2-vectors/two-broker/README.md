# Two-broker fixture (v0.8 I2 §8.2)

**Authored**, not captured: a hand-written after-wave state for the I2b acceptance (B2, B3), before
I3 produces real captures. `expected.json` was written by hand from I2 §8.2 (parent §3.6) before the
projection code.

- `declarations/`: the I1 §4.1 after-wave rules. On Redpanda, Tenant publishes and the `catalog.*`
  topics are topic-only; Product Query and Category Query are service-only. On Kafka, Catalog and
  Image publish and `tenant.tenant.events` is topic-only.
- `captures/redpanda/`: the C1 allow-list. Catalog is `Empty`, Image is broker-reported `Dead`, and
  Product Query and Category Query are copied from C1.
- `captures/kafka/`: the allow-list {Catalog, Image}, with synthetic member text.
- `mapping/`: copies of the I1 §7 mappings.
