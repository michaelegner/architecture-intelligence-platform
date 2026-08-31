from real_world_validation.model import Finding, RelationFact
from real_world_validation.reporter import has_release_blocking_finding, render

_FACT = RelationFact(type="CALLS", source="service:a", target="operation:service:b:GET:/x")


def _finding(classification: str, severity: str, **kwargs) -> Finding:
    return Finding(
        id=f"id-{classification.lower()}",
        classification=classification,
        severity=severity,
        expected=kwargs.get("expected"),
        actual=kwargs.get("actual"),
    )


def test_render_counts_each_classification_once():
    findings = [
        _finding("CORRECT", "INFO", expected=_FACT, actual=_FACT),
        _finding("MISSING_SUPPORTED", "MAJOR", expected=_FACT),
        _finding("INCORRECT_SUPPORTED", "CRITICAL", expected=_FACT, actual=_FACT),
        _finding("UNSUPPORTED", "INFO"),
        _finding("UNRESOLVED_IDENTITY", "MINOR"),
        _finding("INSUFFICIENT_EVIDENCE", "MINOR"),
    ]

    report = render(findings)

    assert "Correct:                       1" in report
    assert "Missing supported:             1" in report
    assert "Incorrect supported:           1" in report
    assert "Unsupported constructs:        1" in report
    assert "Unresolved identities:         1" in report
    assert "Insufficient evidence:         1" in report
    assert "Critical semantic errors:      1" in report


def test_render_with_no_findings_is_all_zero():
    report = render([])

    assert "Critical semantic errors:      0" in report


def test_has_release_blocking_finding_true_only_for_critical_severity():
    assert has_release_blocking_finding([_finding("INCORRECT_SUPPORTED", "CRITICAL")])
    assert not has_release_blocking_finding([_finding("MISSING_SUPPORTED", "MAJOR")])
    assert not has_release_blocking_finding([])
