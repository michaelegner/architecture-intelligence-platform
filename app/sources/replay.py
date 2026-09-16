from dataclasses import dataclass
from enum import StrEnum


class InconsistentReplayStateError(ValueError):
    """Raised when `classify_replay_case` is called with digest state that cannot legitimately
    occur - e.g. only one of a committed digest pair is `None`, or a successful load did not supply
    its new digests. This is always a caller bug, not a decision this function can make sense of.
    """


class ReplayCase(StrEnum):
    """I1 spec §5.4's four literal cases, plus `FIRST_SUCCESSFUL_LOAD` - this PR's own addition,
    since §5.4's table is written for replay against *existing* committed state and does not cover
    a source's very first successful load.
    """

    FAILED_LOAD_PRESERVE_PRIOR = "FAILED_LOAD_PRESERVE_PRIOR"
    FIRST_SUCCESSFUL_LOAD = "FIRST_SUCCESSFUL_LOAD"
    SCOPE_CHANGED_PRESERVE_PENDING_TOMBSTONE = "SCOPE_CHANGED_PRESERVE_PENDING_TOMBSTONE"
    REPLAY_NO_OP = "REPLAY_NO_OP"
    RECONCILE_SAME_SCOPE_CHANGED_SEMANTIC_DIGEST = "RECONCILE_SAME_SCOPE_CHANGED_SEMANTIC_DIGEST"


@dataclass(frozen=True)
class ReplayDecision:
    case: ReplayCase
    graph_revision_advance_possible: bool


def classify_replay_case(
    *,
    load_or_reevaluation_successful: bool,
    committed_semantic_input_digest: str | None,
    new_semantic_input_digest: str | None,
    committed_scope_definition_digest: str | None,
    new_scope_definition_digest: str | None,
) -> ReplayDecision:
    """I1 spec §5.4:

        same SourceInstanceId + same semantic_input_digest
          -> mapping replay no-op; no duplicate ownership/evidence; no graph-revision advance
          -> inventory validation and scope/removal checks still execute

        same SourceInstanceId + changed semantic_input_digest
          + same completed scope_definition_digest
          -> deterministic source-owned diff; expire claims no longer emitted

        same SourceInstanceId + changed scope digest
          -> preserve claims absent from the new scope
          -> expire them only through an explicit inventory transition/tombstone

        invalid or incomplete load or reevaluation
          -> commit nothing; preserve last successful source state

    Checked in this exact order:

    1. A failed/incomplete load or reevaluation always wins, regardless of any digest - a failed
       load may never have produced comparable digests at all.
    2. No prior committed digest for this source at all -> its first successful load (not one of
       the spec's four literal replay cases).
    3. A changed `scope_definition_digest` is checked *before* comparing the semantic digest,
       because the spec's own content-diff case is explicitly conditioned on "same **completed**
       scope_definition_digest" - a scope change always routes here regardless of what the semantic
       digest did.
    4. Only once scope is confirmed unchanged do we compare the semantic digest: unchanged -> no-op,
       changed -> reconcile.

    `graph_revision_advance_possible=True` means a graph-revision advance is *eligible* to happen,
    not guaranteed - it is `False` only for `FAILED_LOAD_PRESERVE_PRIOR` (no load, no write) and
    `REPLAY_NO_OP` (semantic_input_digest is byte-identical to what's already committed, so nothing
    could have changed), both of which skip the check below entirely. For every other case,
    `app.graph.importer._import_source_tx` still decides whether anything real changed by comparing
    (a) `app.sources.claim_reconciliation.plan_source_claim_reconciliation`'s claim-KEY-set diff
    (added/removed/expired) and (b) a direct before/after snapshot of each emitted node/relation's
    own properties, taken immediately around this source's write. Neither signal alone is
    sufficient: the claim-set diff misses a property-only change on a claim this source retains
    (e.g. an OpenAPI `info.title` edit reaching `SET n += $props` with no claim key added or
    removed - a real bug this fixed, where such a change wrote to the graph but never advanced the
    fence a stable read relies on to detect it), while `semantic_input_digest` alone over-triggers
    on a raw-input change the canonical model never surfaces at all (e.g. `info.description`, unlike
    `info.title` unmapped to any canonical field - also a real bug found in review). In particular,
    `SCOPE_CHANGED_PRESERVE_PENDING_TOMBSTONE` does **not** mean "nothing may change": §5.4 only
    requires that claims *absent from the new scope* not be auto-expired without an explicit
    tombstone/transition (see `app.sources.removal_authority.authorize_source_removal`) - it does
    not prohibit adding newly emitted claims or reconciling retained ones.

    Raises `InconsistentReplayStateError` if `committed_semantic_input_digest` and
    `committed_scope_definition_digest` disagree on whether prior state exists (exactly one is
    `None`), or if a successful load did not supply both new digests - both indicate a caller bug,
    not a legitimate replay state this function can classify.
    """
    if (committed_semantic_input_digest is None) != (committed_scope_definition_digest is None):
        raise InconsistentReplayStateError(
            "committed_semantic_input_digest and committed_scope_definition_digest must be both "
            "None (no prior committed state) or both set (prior state exists); got "
            f"{committed_semantic_input_digest!r} and {committed_scope_definition_digest!r}"
        )
    if load_or_reevaluation_successful and (
        new_semantic_input_digest is None or new_scope_definition_digest is None
    ):
        raise InconsistentReplayStateError(
            "a successful load/reevaluation must supply both new_semantic_input_digest and "
            "new_scope_definition_digest"
        )

    if not load_or_reevaluation_successful:
        return ReplayDecision(ReplayCase.FAILED_LOAD_PRESERVE_PRIOR, False)

    if committed_semantic_input_digest is None and committed_scope_definition_digest is None:
        return ReplayDecision(ReplayCase.FIRST_SUCCESSFUL_LOAD, True)

    if committed_scope_definition_digest != new_scope_definition_digest:
        return ReplayDecision(ReplayCase.SCOPE_CHANGED_PRESERVE_PENDING_TOMBSTONE, True)

    if committed_semantic_input_digest == new_semantic_input_digest:
        return ReplayDecision(ReplayCase.REPLAY_NO_OP, False)

    return ReplayDecision(ReplayCase.RECONCILE_SAME_SCOPE_CHANGED_SEMANTIC_DIGEST, True)
