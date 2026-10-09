import { expect, test } from 'claude-code/testing'

import { summarize } from './logic'

const ANSWER = JSON.stringify({
  tool: 'get_service_dependencies',
  outcome: 'ANSWERED',
  snapshot: { snapshot_id: 'aip:snapshot:v1:abc12345' },
  limitations: [],
  claims: [
    { predicate: 'USES_BROKER', object: { name: 'rabbitmq:pitstop-rabbitmq' } },
    {
      predicate: 'DIRECT_DEPENDENCY',
      object: { name: 'ReportingService' },
      delivery: { subscription: { name: 'Reporting' } },
      qualification: 'CONFIRMED',
      coverage: null,
      resolution_evidence_refs: ['evidence:asyncapi:x', 'evidence:otel:pitstop-demo:2026-10-08:90fb'],
    },
  ],
})

test('summarize reads only the schema fields of an ANSWERED dependency answer', () => {
  expect(summarize(ANSWER)).toEqual({
    snapshotId: 'aip:snapshot:v1:abc12345',
    limitations: 0,
    rows: [{ receiver: 'ReportingService', queue: 'Reporting', qualification: 'CONFIRMED', coverage: null, observed: true, refs: 2 }],
  })
  expect(summarize('not json')).toBeNull()
  expect(summarize(JSON.stringify({ tool: 'get_evidence', outcome: 'ANSWERED' }))).toBeNull()
})

test('an AIP tool result is read from its text and drawn in the pane and the band', async ($, on) => {
  on('tool.call', { tool: /^mcp__plugin_aip_aip__/ }, () => ({ result: [], text: ANSWER }) as never)
  const ran = await $.tool.call({ tool: 'mcp__plugin_aip_aip__get_service_dependencies', request: {} } as never)
  expect((ran as { text?: string }).text).toBe(ANSWER)

  const pane = await $.ui.mount({ plugin: 'aip-mod', surface: 'terminal', component: 'Pane', props: {}, requestId: 'aip-evidence' } as never)
  const drawn = JSON.stringify(await pane.drawn())
  expect(drawn).toContain('ReportingService')
  expect(drawn).toContain('CONFIRMED')
  expect(drawn).toContain('observed')
  expect(drawn).toContain('aip:snapshot:v1:abc12345')

  const band = await $.ui.mount({ plugin: 'aip-mod', surface: 'terminal', component: 'AbovePrompt', props: { hasSurvey: false } } as never)
  expect(JSON.stringify(await band.drawn())).toContain('1 receivers')
})

test('a tool result that is not an AIP answer leaves the pane empty', async ($, on) => {
  on('tool.call', { tool: /^mcp__plugin_aip_aip__/ }, () => ({ result: [], text: 'Unauthorized' }) as never)
  await $.tool.call({ tool: 'mcp__plugin_aip_aip__get_service_dependencies', request: {} } as never)
  const pane = await $.ui.mount({ plugin: 'aip-mod', surface: 'terminal', component: 'Pane', props: {}, requestId: 'aip-evidence' } as never)
  expect(JSON.stringify(await pane.drawn())).toContain('No AIP answer yet')
})

test('a tool outside the plugin server is not read', async ($, on) => {
  on('tool.call', { tool: 'mcp__aip__get_service_dependencies' }, () => ({ result: [], text: ANSWER }) as never)
  await $.tool.call({ tool: 'mcp__aip__get_service_dependencies', request: {} } as never)
  const pane = await $.ui.mount({ plugin: 'aip-mod', surface: 'terminal', component: 'Pane', props: {}, requestId: 'aip-evidence' } as never)
  expect(JSON.stringify(await pane.drawn())).toContain('No AIP answer yet')
})

test('a later result that is not an AIP answer keeps the last good summary', async ($, on) => {
  let next = ANSWER
  on('tool.call', { tool: /^mcp__plugin_aip_aip__/ }, () => ({ result: [], text: next }) as never)
  await $.tool.call({ tool: 'mcp__plugin_aip_aip__get_service_dependencies', request: {} } as never)
  next = 'Unauthorized'
  await $.tool.call({ tool: 'mcp__plugin_aip_aip__get_service_dependencies', request: {} } as never)

  const pane = await $.ui.mount({ plugin: 'aip-mod', surface: 'terminal', component: 'Pane', props: {}, requestId: 'aip-evidence' } as never)
  expect(JSON.stringify(await pane.drawn())).toContain('ReportingService')
})

test('a route without observed evidence reads declared only', () => {
  const declared = JSON.stringify({
    ...JSON.parse(ANSWER),
    claims: [
      {
        predicate: 'DIRECT_DEPENDENCY',
        object: { name: 'AuditlogService' },
        delivery: { subscription: { name: 'Auditlog' } },
        qualification: 'CONFIRMED',
        coverage: null,
        resolution_evidence_refs: ['evidence:asyncapi:x'],
      },
    ],
  })
  expect(summarize(declared)?.rows[0]).toMatchObject({ receiver: 'AuditlogService', observed: false, refs: 1 })
})
