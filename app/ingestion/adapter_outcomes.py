"""Outcome and evidence helpers shared by the document adapters (OpenAPI, AsyncAPI, manifest): the
rejection outcomes, the validate -> remote-ref -> dialect-version prologue, and the declared-evidence
/ limitation-diagnostic epilogue. Not part of the public seam (`app.sources.registry`)."""

from collections.abc import Callable, Sequence

from app.canonical import ids
from app.canonical.model import ArchitectureModel, Relation
from app.provenance.model import Provenance
from app.sources.model import DiagnosticCode, IngestionDiagnostic, IngestionResult, LoadedSource
from app.sources.registry import AdapterOutcome
from app.sources.service_identity import ServiceIdentityOutcome, ServiceIdentityResolution
from app.validation.source_validation import (
    SourceValidationError,
    check_supported_dialect_version,
    find_remote_reference,
)

_IDENTITY_OUTCOME_TO_RESULT = {
    ServiceIdentityOutcome.REJECTED_UNSUPPORTED: IngestionResult.REJECTED_UNSUPPORTED,
    ServiceIdentityOutcome.REJECTED_CONFLICT: IngestionResult.REJECTED_CONFLICT,
    ServiceIdentityOutcome.REJECTED_INVALID: IngestionResult.REJECTED_INVALID,
}


def resolved_service_id(resolution: ServiceIdentityResolution) -> str:
    """The service id of a RESOLVED resolution (the caller has already checked the outcome)."""
    # ServiceIdentityResolution rejects a RESOLVED outcome without a service_id at construction.
    assert resolution.service_id is not None
    return resolution.service_id


def rejected_outcome(
    result: IngestionResult, diagnostics: Sequence[IngestionDiagnostic]
) -> AdapterOutcome:
    """A rejection: an empty model, no semantic-input digest, and the given diagnostics."""
    return AdapterOutcome(
        result=result,
        model=ArchitectureModel(),
        diagnostics=tuple(diagnostics),
        semantic_input_digest=None,
    )


def rejected_outcome_for_identity(resolution: ServiceIdentityResolution) -> AdapterOutcome:
    return rejected_outcome(_IDENTITY_OUTCOME_TO_RESULT[resolution.outcome], resolution.diagnostics)


def reject_if_invalid(loaded: LoadedSource, validate: Callable[..., None]) -> AdapterOutcome | None:
    """Runs the adapter's document validator (`validate(document, source_file=locator)`); a
    `SourceValidationError` becomes REJECTED_INVALID with one DOCUMENT_PARSE_INVALID diagnostic per
    message. `None` when the document is valid."""
    locator = loaded.descriptor.locator
    try:
        validate(loaded.document, source_file=locator)
    except SourceValidationError as exc:
        return rejected_outcome(
            IngestionResult.REJECTED_INVALID,
            [
                IngestionDiagnostic(
                    code=DiagnosticCode.DOCUMENT_PARSE_INVALID,
                    message=message,
                    source_pointer=locator,
                )
                for message in exc.errors
            ],
        )
    return None


_MAX_SAFE_INTEGER = 2**53 - 1


def _first_out_of_domain_integer(value: object, tokens: tuple[str, ...] = ()) -> str | None:
    """JSON Pointer to the first integer outside RFC 8785's safe domain, or None. Object members
    are visited in sorted key order, so the answer does not depend on the document's key order."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        if abs(value) <= _MAX_SAFE_INTEGER:
            return None
        return "".join(f"/{t.replace('~', '~0').replace('/', '~1')}" for t in tokens) or "/"
    if isinstance(value, dict):
        for key in sorted(value, key=str):
            found = _first_out_of_domain_integer(value[key], (*tokens, str(key)))
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found = _first_out_of_domain_integer(item, (*tokens, str(index)))
            if found is not None:
                return found
    return None


def rejected_for_integer_domain(loaded: LoadedSource) -> AdapterOutcome:
    """REJECTED_INVALID for a document whose canonical form cannot be computed because it holds an
    integer outside RFC 8785's safe domain (v0.6.3 I2, #305). The diagnostic names the JSON Pointer
    of the first such integer and never its value; the source contributes no model and no digest."""
    locator = loaded.descriptor.locator
    pointer = _first_out_of_domain_integer(loaded.document)
    where = f" at {pointer}" if pointer is not None else ""
    return rejected_outcome(
        IngestionResult.REJECTED_INVALID,
        [
            IngestionDiagnostic(
                code=DiagnosticCode.DOCUMENT_PARSE_INVALID,
                message=(
                    f"document contains an integer outside the RFC 8785 safe integer range "
                    f"(-(2^53 - 1) to 2^53 - 1){where}; canonical hashing is not defined for it"
                ),
                source_pointer=locator,
            )
        ],
    )


def reject_if_unsupported_dialect(
    loaded: LoadedSource, *, dialect_key: str, accepted_versions: frozenset[str]
) -> AdapterOutcome | None:
    """REJECTED_UNSUPPORTED for a remote/non-local `$ref` (checked first) or a dialect version
    outside `accepted_versions`; `None` when the document passes both."""
    document, locator = loaded.document, loaded.descriptor.locator
    remote_ref = find_remote_reference(document)
    if remote_ref is not None:
        return rejected_outcome(
            IngestionResult.REJECTED_UNSUPPORTED,
            [
                IngestionDiagnostic(
                    code=DiagnosticCode.REMOTE_REFERENCE_UNSUPPORTED,
                    message=f"remote/non-local reference is not supported: {remote_ref}",
                    source_pointer=locator,
                )
            ],
        )
    version_error = check_supported_dialect_version(
        document, dialect_key=dialect_key, accepted_versions=accepted_versions
    )
    if version_error is not None:
        return rejected_outcome(
            IngestionResult.REJECTED_UNSUPPORTED,
            [
                IngestionDiagnostic(
                    code=DiagnosticCode.UNSUPPORTED_DIALECT_VERSION,
                    message=version_error,
                    source_pointer=locator,
                )
            ],
        )
    return None


def declared_evidence(loaded: LoadedSource, source_type: str) -> Provenance:
    """The DECLARED `Provenance` record for one source document (`source_type` e.g. "OPENAPI")."""
    descriptor = loaded.descriptor
    return Provenance(
        id=ids.evidence_id(
            source_type, descriptor.source_instance_id, descriptor.declared_provider_revision
        ),
        source_type=source_type,
        source_file=descriptor.locator,
        source_revision=descriptor.declared_provider_revision,
    )


def stamp_evidence(relations: Sequence[Relation], evidence: Provenance) -> list[Relation]:
    """Every relation carrying `evidence` as its sole evidence id."""
    return [r.model_copy(update={"evidence_ids": [evidence.id]}) for r in relations]


def composition_limitation_diagnostic(locator: str, *, subject: str) -> IngestionDiagnostic:
    """SCHEMA_COMPOSITION_UNINTERPRETED for `subject` ("schemas", "payload schemas", ...)."""
    return IngestionDiagnostic(
        code=DiagnosticCode.SCHEMA_COMPOSITION_UNINTERPRETED,
        message=(
            f"one or more {subject} contain an allOf/oneOf/anyOf composition, preserved "
            "structurally in the canonical hash but not interpreted as an effective object shape"
        ),
        source_pointer=locator,
    )
