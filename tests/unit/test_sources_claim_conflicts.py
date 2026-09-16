from app.canonical.model import ArchitectureModel, Message, Schema
from app.sources.claim_conflicts import detect_shared_claim_content_conflicts
from app.sources.model import DiagnosticCode


def _model(*, schemas=(), messages=()) -> ArchitectureModel:
    return ArchitectureModel(schemas=list(schemas), messages=list(messages))


def test_no_conflict_when_only_one_source_claims_a_schema():
    model = _model(schemas=[Schema(id="schema:owned:x", name="X", canonical_hash="h1")])
    assert detect_shared_claim_content_conflicts([model]) == ()


def test_identical_hashes_across_sources_merge_silently():
    a = _model(schemas=[Schema(id="schema:X", name="X", canonical_hash="h1")])
    b = _model(schemas=[Schema(id="schema:X", name="X", canonical_hash="h1")])
    assert detect_shared_claim_content_conflicts([a, b]) == ()


def test_different_hashes_across_sources_conflict():
    a = _model(schemas=[Schema(id="schema:X", name="X", canonical_hash="h1")])
    b = _model(schemas=[Schema(id="schema:X", name="X", canonical_hash="h2")])
    diagnostics = detect_shared_claim_content_conflicts([a, b])
    assert len(diagnostics) == 1
    assert diagnostics[0].code is DiagnosticCode.SCHEMA_CONTENT_CONFLICT
    assert diagnostics[0].source_pointer == "schema:X"


def test_identical_contract_digests_across_sources_merge_silently():
    a = _model(messages=[Message(id="message:X", name="X", contract_digest="d1")])
    b = _model(messages=[Message(id="message:X", name="X", contract_digest="d1")])
    assert detect_shared_claim_content_conflicts([a, b]) == ()


def test_different_contract_digests_across_sources_conflict():
    a = _model(messages=[Message(id="message:X", name="X", contract_digest="d1")])
    b = _model(messages=[Message(id="message:X", name="X", contract_digest="d2")])
    diagnostics = detect_shared_claim_content_conflicts([a, b])
    assert len(diagnostics) == 1
    assert diagnostics[0].code is DiagnosticCode.MESSAGE_CONTENT_CONFLICT


def test_result_order_is_independent_of_input_model_order():
    a = _model(schemas=[Schema(id="schema:X", name="X", canonical_hash="h1")])
    b = _model(schemas=[Schema(id="schema:X", name="X", canonical_hash="h2")])
    forward = detect_shared_claim_content_conflicts([a, b])
    backward = detect_shared_claim_content_conflicts([b, a])
    assert forward == backward


def test_unrelated_schemas_and_messages_do_not_cross_contaminate():
    a = _model(
        schemas=[Schema(id="schema:X", name="X", canonical_hash="h1")],
        messages=[Message(id="message:X", name="X", contract_digest="d1")],
    )
    b = _model(
        schemas=[Schema(id="schema:Y", name="Y", canonical_hash="h2")],
        messages=[Message(id="message:Y", name="Y", contract_digest="d2")],
    )
    assert detect_shared_claim_content_conflicts([a, b]) == ()
