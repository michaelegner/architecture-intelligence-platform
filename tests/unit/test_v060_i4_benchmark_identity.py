"""Benchmarks must reject an unverified identity before starting Docker or measuring."""

import pytest

from app.version import package_version
from benchmarks import i4_metadata, locality_cost, scoped_churn_cost


@pytest.mark.parametrize("benchmark", [scoped_churn_cost, locality_cost])
def test_explicit_candidate_is_required(benchmark):
    with pytest.raises(SystemExit):
        benchmark.main(["--profile", "smoke"])


@pytest.mark.parametrize("benchmark", [scoped_churn_cost, locality_cost])
@pytest.mark.parametrize("candidate", ["placeholder", "f" * 40])
def test_invalid_or_wrong_candidate_is_rejected_before_docker(benchmark, candidate):
    with pytest.raises((ValueError, AssertionError)):
        benchmark.main(["--candidate-sha", candidate])


def test_producer_uses_verified_candidate_and_actual_package_version(monkeypatch):
    candidate = "a" * 40  # synthetic fixture, not qualification evidence
    monkeypatch.setattr(i4_metadata, "verify_candidate", lambda sha: candidate)
    monkeypatch.delenv("I4_CANDIDATE_SHA", raising=False)
    monkeypatch.delenv("AIP_BUILD_REVISION", raising=False)
    result = i4_metadata.producer(candidate)
    assert result.build_revision == candidate
    assert result.version == package_version()
    monkeypatch.setenv("AIP_BUILD_REVISION", "b" * 40)
    with pytest.raises(ValueError):
        i4_metadata.producer(candidate)


def test_generated_input_record_retains_both_capture_versions(tmp_path):
    capture = tmp_path / "capture.json"
    capture.write_text('{"revision":"C1"}')
    before = i4_metadata.input_pins(tmp_path)
    capture.write_text('{"revision":"C2"}')
    after = i4_metadata.input_pins(tmp_path)
    assert before["capture.json"]["sha256"] != after["capture.json"]["sha256"]
    assert before["capture.json"]["content"] == '{"revision":"C1"}'
