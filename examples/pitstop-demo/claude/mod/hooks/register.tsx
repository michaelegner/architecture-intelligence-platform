import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import { summarize } from './logic'

const PANE = 'aip-evidence'
const summary = atom({ plugin: 'aip-mod', key: 'summary' } as const, null)
const busy = atom({ plugin: 'aip-mod', key: 'busy' } as const, false)

// Optional UX layer (spec §6.2): shows the last AIP answer next to the agent's plan. It only reads the result of
// the plugin's AIP tools; it never changes a prompt, a plan, a tool call or a tool result, and any failure here
// leaves the session exactly as it would be without the mod.
export const register: Register = on => {
  // The pane opens on the person's own action (this command or the band's Evidence button), which seats it at
  // any terminal width. An open triggered by a hook (for example from /aip:inspect) is not reliable.
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'aip-evidence', description: 'Show the last AIP answer in a pane' })

    return next(e)
  })

  on('command.run', { command: 'aip-evidence' }, async $ => {
    await $.ui.open({ id: PANE, title: 'AIP evidence' })

    return { text: 'AIP evidence pane opened.' }
  })

  // Only the plugin's own AIP tools (a RegExp: the matcher takes no glob). The answer is the result's text.
  on('tool.call', { tool: /^mcp__plugin_aip_aip__/ }, async ($, e, next) => {
    await update($, busy, () => true).catch(() => undefined)
    const ran = await next(e)

    try {
      if (ran.deny === undefined && ran.isError !== true && typeof ran.text === 'string') {
        const answer = summarize(ran.text)

        // A later call that is not a dependency answer (or fails to parse) keeps the last good summary.
        if (answer !== null) {
          await update($, summary, () => answer)
        }
      }
    } catch {
      // keep the last good summary
    }

    await update($, busy, () => false).catch(() => undefined)

    return ran
  }).catch(($, e, next) => next(e))

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const isBusy = await read($, busy)
    const last = await read($, summary)

    if (e.props.hasSurvey || (!isBusy && last === null)) {
      return next(e)
    }

    const { Box, Button, Text } = $.ui.resolve(e)
    const unresolved = last !== null && last.unresolved.length > 0 ? `, ${last.unresolved.length} unresolved` : ''
    const line = isBusy || last === null
      ? 'AIP: consulting'
      : `AIP: ${last.receivers.length} receivers${unresolved}, snapshot ${last.snapshotId.slice(-8)}, limitations ${last.limitations}`

    return (
      <Box>
        <Text dimColor>{line} </Text>
        {!isBusy && (
          <Button key="open" label="Evidence" onPress={() => void $.ui.open({ id: PANE, title: 'AIP evidence' })} />
        )}
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const last = await read($, summary)

    return (
      <Box flexDirection="column">
        {last === null && <Text dimColor>No AIP answer yet.</Text>}
        {last !== null &&
          last.receivers.map(row => (
            <Text>
              {row.name} / {row.queue ?? '?'}: {row.qualification}
              {row.coverage ? ` (${row.coverage})` : ''} {row.observed ? 'observed' : 'declared only'}
            </Text>
          ))}
        {last !== null && last.unresolved.length > 0 && (
          <Text dimColor>Unresolved destinations (AIP could not resolve a receiving Service; not receivers):</Text>
        )}
        {last !== null &&
          last.unresolved.map(row => (
            <Text>
              {row.type} {row.name}: {row.resolution}, {row.qualification}
              {row.coverage ? ` (${row.coverage})` : ''}
            </Text>
          ))}
        {last !== null && (
          <Text dimColor>
            snapshot {last.snapshotId} · limitations {last.limitations}
          </Text>
        )}
      </Box>
    )
  })
}
