import type { Row, Summary } from '../types'

// Reads only fields the released v0.6 answer schema defines, from the text of a get_service_dependencies result
// (a JSON document): outcome, tool, snapshot.snapshot_id, limitations and, per DIRECT_DEPENDENCY claim,
// destination_resolution, object.name and object.type, delivery.subscription.name, qualification, coverage and
// resolution_evidence_refs.
//
// Only a claim whose destination_resolution is RESOLVED_SERVICE is a receiver. Any other claim (the schema's
// DIRECT_TARGET_FALLBACK) names a destination AIP could not resolve to a Service, so it goes to `unresolved` and is
// never counted or drawn as a receiver. A route is "observed" when one of its resolution evidence references is an
// OpenTelemetry one.
export function summarize(text: string): Summary | null {
  let answer: any

  try {
    answer = JSON.parse(text)
  } catch {
    return null
  }

  if (answer?.tool !== 'get_service_dependencies' || answer.outcome !== 'ANSWERED') {
    return null
  }

  const rows: Row[] = (answer.claims ?? [])
    .filter((claim: any) => claim.predicate === 'DIRECT_DEPENDENCY')
    .map((claim: any) => {
      const refs: string[] = claim.resolution_evidence_refs ?? []

      return {
        name: claim.object?.name ?? '?',
        type: claim.object?.type ?? '?',
        queue: claim.delivery?.subscription?.name ?? null,
        resolution: claim.destination_resolution ?? '?',
        qualification: claim.qualification ?? '?',
        coverage: claim.coverage ?? null,
        observed: refs.some(ref => ref.startsWith('evidence:otel:')),
        refs: refs.length,
      }
    })

  return {
    snapshotId: answer.snapshot?.snapshot_id ?? '?',
    receivers: rows.filter(row => row.resolution === 'RESOLVED_SERVICE'),
    unresolved: rows.filter(row => row.resolution !== 'RESOLVED_SERVICE'),
    limitations: (answer.limitations ?? []).length,
  }
}
