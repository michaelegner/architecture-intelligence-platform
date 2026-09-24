# AIP v0.5.0 Real-World Validation (I5)

This directory holds the v0.5.0 I5 cross-system qualification dossiers. It is governed by
[`i5-cross-system-qualification.md`](../../specifications/0.5.0/i5-cross-system-qualification.md).
The v0.3 method in [`../README.md`](../README.md) still applies, including the ground-truth
independence rule, the six classifications and the dossier structure. This file records only what
v0.5 changes.

## What changes for v0.5

| Area | v0.5 rule | I5 section |
| --- | --- | --- |
| Targets | Quarkus Super Heroes (plus its upstream Kubernetes manifests) and Apache Airflow 3.3.1, pinned. v0.3 results are research input only. | §5 |
| Ground truth | An agent may draft facts, but only from upstream evidence, with a citation per fact. The owner's merge freezes them before any qualifying output is inspected. | §6 |
| Inputs | Every input is classified as upstream-supplied, upstream-derived (only I5 §5's namespace injection), independently captured, or AIP operator configuration. Configuration is never ground truth. | §6 |
| Vocabulary | v0.3 relations, plus `PUBLISHES_TO`, `SUBSCRIPTION_OF`, `RECEIVES_FROM -> Subscription`, `CARRIES` from a Topic, public `DEPLOYED_AS` outcomes (`expected.deployments`), and negative expectations (`forbidden`). | §7 |
| Determinism | Paired byte-identity runs use one absolute checkout location. Location-dependent values are never normalized. | §12 |

## Tooling

`real_world_validation` implements the vocabulary (see its [README](../../../real_world_validation/README.md)):

```bash
uv run python -m real_world_validation capture ... --until <ts> --aip-config <config.yaml> --out actual.yaml
uv run python -m real_world_validation compare --expected expected.yaml --actual actual.yaml
```

## Layout

```text
v0.5.0/
  README.md                 this file
  _template/                copy per target, then fill in
  quarkus-super-heroes/     I5 Slice 2
  apache-airflow/           I5 Slice 3
```
