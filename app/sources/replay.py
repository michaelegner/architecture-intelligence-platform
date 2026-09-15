from dataclasses import dataclass
from enum import StrEnum


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
    not a guaranteed mutation - whether the RECONCILE case actually advances the graph is decided by
    `app.sources.claim_reconciliation.plan_source_claim_reconciliation`'s `is_semantic_no_op`, once a
    later increment has real committed/newly-emitted claim sets to compare.
    """
    if not load_or_reevaluation_successful:
        return ReplayDecision(ReplayCase.FAILED_LOAD_PRESERVE_PRIOR, False)

    if committed_semantic_input_digest is None and committed_scope_definition_digest is None:
        return ReplayDecision(ReplayCase.FIRST_SUCCESSFUL_LOAD, True)

    if committed_scope_definition_digest != new_scope_definition_digest:
        return ReplayDecision(ReplayCase.SCOPE_CHANGED_PRESERVE_PENDING_TOMBSTONE, False)

    if committed_semantic_input_digest == new_semantic_input_digest:
        return ReplayDecision(ReplayCase.REPLAY_NO_OP, False)

    return ReplayDecision(ReplayCase.RECONCILE_SAME_SCOPE_CHANGED_SEMANTIC_DIGEST, True)
