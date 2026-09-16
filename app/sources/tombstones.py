from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from app.sources.model import DiagnosticCode, IngestionDiagnostic


class Tombstone(BaseModel):
    """I1 spec §6: "An explicit tombstone SHALL contain the target SourceInstanceId, the
    DiscoveryScopeId, the expected prior committed inventory_revision, the scope digest, an
    attributable actor/reason, and the tombstone revision."
    """

    target_source_instance_id: str
    discovery_scope_id: str
    expected_prior_inventory_revision: str
    scope_definition_digest: str
    actor: str
    reason: str
    tombstone_revision: str


class TombstoneRejectionReason(StrEnum):
    STALE_PRIOR_REVISION = "STALE_PRIOR_REVISION"
    NO_COMMITTED_INVENTORY = "NO_COMMITTED_INVENTORY"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"


class InconsistentCommittedInventoryStateError(ValueError):
    """Raised when the three `committed_*` parameters disagree on whether an inventory has ever
    committed - all three must be `None` together (nothing committed yet) or all three set together
    (a real committed inventory exists). A partial combination is always a caller bug, not a
    legitimate state this function can validate a tombstone against.
    """


@dataclass(frozen=True)
class TombstoneValidation:
    accepted: bool
    rejection_reason: TombstoneRejectionReason | None
    diagnostic: IngestionDiagnostic | None


def validate_tombstone_against_committed_inventory(
    *,
    tombstone: Tombstone,
    committed_discovery_scope_id: str | None,
    committed_scope_definition_digest: str | None,
    committed_inventory_revision: str | None,
) -> TombstoneValidation:
    """I1 spec §6: "A tombstone whose expected prior revision does not match the committed
    inventory is stale and MUST be rejected without expiration."

    Extends that literal single-sentence rule with two further rejection reasons that block
    expiration for the same underlying "nothing legitimate to act on" reason, though the spec does
    not name them as "staleness" explicitly:
      - `NO_COMMITTED_INVENTORY`: nothing has ever committed for this scope, so there is nothing for
        the tombstone's expected prior revision to be stale *against*.
      - `SCOPE_MISMATCH`: the tombstone's own `discovery_scope_id`/`scope_definition_digest` do not
        match what is actually committed, even if `expected_prior_inventory_revision` happens to
        match by coincidence.

    Raises `InconsistentCommittedInventoryStateError` if exactly one or two of the three
    `committed_*` parameters are `None` - a real committed inventory always has all three fields
    set together, so a partial combination indicates a caller bug rather than a legitimate "nothing
    committed yet" or "something committed" state to validate against.
    """
    committed_fields = (
        committed_discovery_scope_id,
        committed_scope_definition_digest,
        committed_inventory_revision,
    )
    if any(field is None for field in committed_fields) and any(
        field is not None for field in committed_fields
    ):
        raise InconsistentCommittedInventoryStateError(
            "committed_discovery_scope_id, committed_scope_definition_digest, and "
            "committed_inventory_revision must be either all None or all set; got "
            f"{committed_fields!r}"
        )

    if committed_inventory_revision is None:
        return TombstoneValidation(
            accepted=False,
            rejection_reason=TombstoneRejectionReason.NO_COMMITTED_INVENTORY,
            diagnostic=IngestionDiagnostic(
                code=DiagnosticCode.TOMBSTONE_STALE,
                message="no committed inventory exists for this tombstone to act against",
                source_instance_id=tombstone.target_source_instance_id,
            ),
        )

    if (
        tombstone.discovery_scope_id != committed_discovery_scope_id
        or tombstone.scope_definition_digest != committed_scope_definition_digest
    ):
        return TombstoneValidation(
            accepted=False,
            rejection_reason=TombstoneRejectionReason.SCOPE_MISMATCH,
            diagnostic=IngestionDiagnostic(
                code=DiagnosticCode.TOMBSTONE_SCOPE_MISMATCH,
                message="tombstone scope does not match the committed inventory's scope",
                source_instance_id=tombstone.target_source_instance_id,
            ),
        )

    if tombstone.expected_prior_inventory_revision != committed_inventory_revision:
        return TombstoneValidation(
            accepted=False,
            rejection_reason=TombstoneRejectionReason.STALE_PRIOR_REVISION,
            diagnostic=IngestionDiagnostic(
                code=DiagnosticCode.TOMBSTONE_STALE,
                message=(
                    f"tombstone expected prior revision "
                    f"{tombstone.expected_prior_inventory_revision!r} does not match committed "
                    f"revision {committed_inventory_revision!r}"
                ),
                source_instance_id=tombstone.target_source_instance_id,
            ),
        )

    return TombstoneValidation(accepted=True, rejection_reason=None, diagnostic=None)


def load_tombstones(
    paths: Sequence[Path],
) -> tuple[tuple[Tombstone, ...], tuple[IngestionDiagnostic, ...]]:
    """Reads and parses every configured tombstone file (`app.settings.SourcesConfig.tombstones`),
    the I2 Draft 0.2 §3 prerequisite slice's minimal operator-facing surface for submitting an
    explicit whole-source/scope-transition tombstone (I1 spec §6). Mirrors
    `app.sources.migration_mappings.load_migration_mappings`'s "diagnose, never silently skip or
    fall back" discipline: a missing/unreadable file or one that isn't well-formed YAML containing a
    `tombstones:` list of valid `Tombstone` shapes is diagnosed rather than raised or ignored.

    Each file's top-level shape is `{"tombstones": [<Tombstone fields>, ...]}` - a list rather than
    a single object, since one file may declare tombstones for more than one configured source.
    """
    diagnostics: list[IngestionDiagnostic] = []
    tombstones: list[Tombstone] = []

    for path in paths:
        locator = str(path)
        try:
            raw_bytes = path.read_bytes()
        except OSError as exc:
            diagnostics.append(
                IngestionDiagnostic(
                    code=DiagnosticCode.TOMBSTONE_FILE_UNAVAILABLE,
                    message=f"{locator}: {exc}",
                    source_pointer=locator,
                )
            )
            continue

        try:
            parsed_yaml = yaml.safe_load(raw_bytes)
        except yaml.YAMLError as exc:
            diagnostics.append(
                IngestionDiagnostic(
                    code=DiagnosticCode.TOMBSTONE_SHAPE_INVALID,
                    message=f"{locator}: {exc}",
                    source_pointer=locator,
                )
            )
            continue
        if not isinstance(parsed_yaml, dict) or not isinstance(parsed_yaml.get("tombstones"), list):
            diagnostics.append(
                IngestionDiagnostic(
                    code=DiagnosticCode.TOMBSTONE_SHAPE_INVALID,
                    message=f"{locator}: expected a mapping with a top-level 'tombstones' list",
                    source_pointer=locator,
                )
            )
            continue

        for index, entry in enumerate(parsed_yaml["tombstones"]):
            try:
                tombstones.append(Tombstone.model_validate(entry))
            except ValidationError as exc:
                diagnostics.append(
                    IngestionDiagnostic(
                        code=DiagnosticCode.TOMBSTONE_SHAPE_INVALID,
                        message=f"{locator}: tombstones[{index}]: {exc}",
                        source_pointer=locator,
                    )
                )

    return tuple(tombstones), tuple(diagnostics)
