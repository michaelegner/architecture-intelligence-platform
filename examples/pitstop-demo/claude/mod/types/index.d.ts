// One DIRECT_DEPENDENCY claim. A claim whose destination is `RESOLVED_SERVICE` names a receiving Service; any other
// resolution (`DIRECT_TARGET_FALLBACK`) names the unresolved destination itself (a Topic, a Queue, an Operation), which
// AIP could not resolve to a receiver: it is never shown or counted as a receiver.
export type Row = {
  name: string
  type: string
  queue: string | null
  resolution: string
  qualification: string
  coverage: string | null
  observed: boolean
  refs: number
}

export type Summary = { snapshotId: string; receivers: Row[]; unresolved: Row[]; limitations: number }

declare module 'claude-code' {
  interface PluginState {
    'aip-mod': { summary: Summary | null; busy: boolean }
  }
}
