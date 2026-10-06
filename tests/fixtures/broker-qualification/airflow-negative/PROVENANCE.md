# Apache Airflow 3.3.1: negative Broker-attribution boundary

**Spec:** v0.6.1 §3 and §6.2. **Role:** a real-system confirmation of the unresolved-manifest-Service
guard that `tests/unit/test_manifest_adapter_broker.py` exercises deterministically; not a separate
semantic rule.
**Retrieval date:** not applicable (the upstream inputs are the frozen v0.5.0 I5 Airflow dossier;
nothing is retrieved).

## Authored scenario data

- Frozen, unmodified inputs (referenced, not copied): the byte-identical upstream OpenAPI
  `docs/real-world-validation/v0.5.0/apache-airflow/runtime/declarations/airflow-apiserver/openapi.yml`
  and its identity binding `.../bindings/architecture-identity-bindings.yaml`, which together
  establish the only admitted Service, `service:airflow-apiserver`.
- Operator-authored negative: `declarations/airflow-worker/architecture.yaml` names the stable Broker
  id `airflow-3.3.1:celery-broker:redis` for `service:airflow-worker`, a Service no phase-0 source
  declares. The Redis broker URL in the dossier (`redis://:@redis:6379/0`) is deliberately **not**
  used as an identity: a URL never establishes Broker identity, and the id above is an explicit
  operator-authored value, not derived from the upstream files.

## Expected facts

- The manifest is `REJECTED_UNSUPPORTED` with `MANIFEST_CALL_SOURCE_UNRESOLVED` (pointer
  `/x-aip-service-id`); it emits **zero** canonical artifacts.
- No Broker and no `USES_BROKER` exists in the merged model; `service:airflow-apiserver` is
  unchanged and gains no Broker; no Queue/Topic is minted (the existing Airflow messaging negatives
  are unchanged).

## Forbidden facts

- attributing the Redis broker to `service:airflow-apiserver`;
- accepting the worker identity, or minting `service:airflow-worker` from the manifest;
- a Broker for the Redis URL, the executor setting or the `default` task queue.

## Unsupported / deferred

Process-role Service identity (scheduler, worker, task runner) and any Celery queue modelling stay
out of scope, as in v0.5.0.
