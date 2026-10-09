import type { Row, Summary } from '../types'

// Reads only fields the released v0.6 answer schema defines, from the text of a get_service_dependencies result
// (a JSON document): outcome, tool, snapshot.snapshot_id, limitations and, per DIRECT_DEPENDENCY claim,
// object.name, delivery.subscription.name, qualification, coverage and resolution_evidence_refs.
// A route is "observed" when one of its resolution evidence references is an OpenTelemetry one.
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
        receiver: claim.object?.name ?? '?',
        queue: claim.delivery?.subscription?.name ?? '?',
        qualification: claim.qualification ?? '?',
        coverage: claim.coverage ?? null,
        observed: refs.some(ref => ref.startsWith('evidence:otel:')),
        refs: refs.length,
      }
    })

  return {
    snapshotId: answer.snapshot?.snapshot_id ?? '?',
    rows,
    limitations: (answer.limitations ?? []).length,
  }
}
