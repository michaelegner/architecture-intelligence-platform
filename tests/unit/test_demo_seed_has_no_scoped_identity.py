"""v0.6.0 I2.5c (decision record D16): the golden-path demo can never produce scoped v2 evidence.

The demo phase pins `aip:snapshot:v1:0bfcbded…` (`examples/runtime-demo/fixture-state.json`). A v2
record, and so the conditional snapshot keys, can only come from a CLIENT whose Resource carries
`k8s.pod.uid` and `k8s.cluster.uid` (I1 matrix §10, guard I-2). The frozen demo batch carries no
`k8s.*` attribute at all, so enabling the flag can never move that snapshot. What enabling does add
are the operational D7/D8 nodes, which the demo's whole-database node count sees - the reason D16
defers the default flip to the next golden-path re-freeze.
"""

import importlib.util
import random
import sys
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parents[2] / "examples" / "runtime-demo"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, DEMO_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # seed_frozen_evidence imports traffic_generator by name
    spec.loader.exec_module(module)
    return module


def test_the_frozen_demo_batch_carries_no_kubernetes_identity():
    traffic_generator = _load("traffic_generator")
    seed = _load("seed_frozen_evidence")
    batch = traffic_generator.build_batch(
        now_nanos=seed._frozen_now_nanos, rng=random.Random(seed._SEED_RNG_SEED)
    )
    keys = set()
    for resource_spans in batch.resource_spans:
        keys.update(attribute.key for attribute in resource_spans.resource.attributes)
        for scope_spans in resource_spans.scope_spans:
            for span in scope_spans.spans:
                keys.update(attribute.key for attribute in span.attributes)
    assert batch.resource_spans
    assert "service.name" in keys  # the scan really sees the Resource attributes
    assert not {key for key in keys if key.startswith("k8s.")}
