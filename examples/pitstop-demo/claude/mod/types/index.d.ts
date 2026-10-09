export type Row = {
  receiver: string
  queue: string
  qualification: string
  coverage: string | null
  observed: boolean
  refs: number
}

export type Summary = { snapshotId: string; rows: Row[]; limitations: number }

declare module 'claude-code' {
  interface PluginState {
    'aip-mod': { summary: Summary | null; busy: boolean }
  }
}
