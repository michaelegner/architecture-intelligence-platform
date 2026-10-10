"""Pinned I4 benchmark identity and reproducible input records; development tooling only."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.architecture_intelligence.contracts import Producer
from app.version import package_version
from evaluation.i4.__main__ import verify_candidate

ROOT = Path(__file__).resolve().parents[1]


def producer(candidate_sha: str) -> Producer:
    verify_candidate(candidate_sha)
    for name in ("I4_CANDIDATE_SHA", "AIP_BUILD_REVISION"):
        if name in os.environ and os.environ[name] != candidate_sha:
            raise ValueError(f"{name} does not match the explicit candidate")
    return Producer(
        name="architecture-intelligence-platform",
        version=package_version(),
        build_revision=candidate_sha,
    )


def input_pins(root: Path) -> dict:
    """Retain generated source bytes before a replacement overwrites them."""
    return {
        str(path.relative_to(root)): {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "content": path.read_text(),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def metadata(
    candidate_sha: str, configured_producer: Producer, container, configuration: dict
) -> dict:
    verify_candidate(candidate_sha)
    assert configured_producer.build_revision == candidate_sha
    assert configured_producer.version == package_version()
    roots = [
        ROOT / "benchmarks",
        ROOT / "schemas/architecture_intelligence",
        ROOT / "docs/specifications/0.6.0",
        ROOT / "tests/integration/locality_oracle",
    ]
    pins = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for root in roots
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }
    for path in (
        ROOT / "tests/integration/test_v060_i4_bridges.py",
        ROOT / "tests/integration/test_scoped_applicability.py",
        ROOT / "tests/integration/test_locality_oracle.py",
    ):
        pins[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "candidate_sha": candidate_sha,
        "verified_head": candidate_sha,
        "producer": configured_producer.model_dump(mode="json"),
        "process_id": os.getpid(),
        "container_id": container.get_wrapped_container().id,
        "container_image": container.image,
        "command": sys.argv,
        "configuration": configuration,
        "configuration_sha256": hashlib.sha256(canonical_json_bytes(configuration)).hexdigest(),
        "input_pins": pins,
        "qualification_eligible": True,
    }
