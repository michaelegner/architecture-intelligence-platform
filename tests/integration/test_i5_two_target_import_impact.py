"""v0.5.0 I5 Slice 6: the two-target impact check that I5 §11 requires of every FIX.

The frozen dossiers' declarations and Kubernetes bundles are imported exactly as their frozen AIP
configs configure them. The test asserts the per-source outcomes observed in Slice 5
(`docs/real-world-validation/v0.5.0/finding-ledger.md`). With the F2 import report, it also pins
what Slice 5 could not observe:
- the namespaced Quarkus bundle's exact frozen limitation set (`ground-truth.md`: 25
  `K8S_RESOURCE_UNSUPPORTED` and 13 `NO_QUALIFIED_POD_MATCH`);
- the unmodified bundle's `K8S_RESOURCE_INVALID`;
- Airflow's `SCHEMA_COMPOSITION_UNINTERPRETED`;
- each source's adapter, dialect and Service ids, and the emitted counts of the manifest and the
  namespaced bundle.

A later FIX that changes any of these must fail here first.
"""

from collections import Counter
from pathlib import Path

import pytest

from app.graph.importer import import_all_sources, import_kubernetes_source
from app.settings import load_config

V05 = Path(__file__).resolve().parents[2] / "docs" / "real-world-validation" / "v0.5.0"
DATABASE = "neo4j"


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")


def _results(stats) -> dict[str, tuple[str, Counter]]:
    return {
        r.locator: (r.result.value, Counter(d.code.value for d in r.diagnostics))
        for r in stats.source_results
    }


def test_quarkus_declarations_and_kubernetes_bundles(driver, monkeypatch):
    runtime = V05 / "quarkus-super-heroes" / "runtime"
    monkeypatch.chdir(runtime)  # the frozen config's roots are relative to the runtime directory
    config = load_config(runtime / "config.quarkus-i5.yaml")

    (directory,) = config.sources.directories
    declarations = import_all_sources(driver, database=DATABASE, source_config=directory)
    assert declarations.committed is True
    assert {locator: result for locator, (result, _) in _results(declarations).items()} == {
        f"declarations/{name}": "ACCEPTED"
        for name in (
            "rest-fights/architecture.yaml",
            "rest-fights/openapi.yml",
            "rest-heroes/openapi.yml",
            "rest-narration/openapi.yml",
            "rest-villains/openapi.yml",
        )
    }
    by_locator = {r.locator.removeprefix("declarations/"): r for r in declarations.source_results}
    for name in ("fights", "heroes", "narration", "villains"):
        openapi = by_locator[f"rest-{name}/openapi.yml"]
        assert (openapi.adapter_identity, openapi.dialect_version) == ("openapi-adapter@1", "3.1.2")
        assert openapi.service_ids == (f"service:rest-{name}",)
    manifest = by_locator["rest-fights/architecture.yaml"]
    assert manifest.adapter_identity == "manifest-adapter@1"
    assert manifest.service_ids == ()
    assert manifest.emitted.relations == 7  # the frozen 7 CALLS

    clusters = {cluster.id: cluster for cluster in config.sources.clusters}
    namespaced = import_kubernetes_source(
        driver, database=DATABASE, source_config=clusters["qsh-k8s-namespaced"]
    )
    assert namespaced.committed is True
    [(result, codes)] = _results(namespaced).values()
    assert result == "ACCEPTED_WITH_LIMITATIONS"
    assert codes == Counter({"K8S_RESOURCE_UNSUPPORTED": 25, "NO_QUALIFIED_POD_MATCH": 13})
    # `ground-truth.md`: 13 Workloads, 13 Kubernetes Services and 1 Ingress; 13 WORKLOAD_EXISTS
    # claims and 2 Ingress routes.
    [bundle] = namespaced.source_results
    assert bundle.emitted.infrastructure_entities == 27
    assert bundle.emitted.infrastructure_claims == 15

    unmodified = import_kubernetes_source(
        driver, database=DATABASE, source_config=clusters["qsh-k8s-upstream-unmodified"]
    )
    assert unmodified.committed is False
    [(result, codes)] = _results(unmodified).values()
    assert result == "REJECTED_INVALID"
    assert codes == Counter({"K8S_RESOURCE_INVALID": 1})


def test_airflow_declarations(driver, monkeypatch):
    runtime = V05 / "apache-airflow" / "runtime"
    monkeypatch.chdir(runtime)
    config = load_config(runtime / "config.airflow-i5.yaml")

    (directory,) = config.sources.directories
    stats = import_all_sources(driver, database=DATABASE, source_config=directory)
    assert stats.committed is True
    [(result, codes)] = _results(stats).values()
    assert result == "ACCEPTED_WITH_LIMITATIONS"
    assert set(codes) == {"SCHEMA_COMPOSITION_UNINTERPRETED"}
