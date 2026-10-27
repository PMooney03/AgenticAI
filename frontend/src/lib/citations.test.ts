import { describe, expect, it } from 'vitest'

import { citedLabels, formatBytes, splitCitations } from './citations'
import { pendingWorkflow } from './workflow'

describe('splitCitations', () => {
  it('turns [Source N] into citation parts', () => {
    const parts = splitCitations('Led by Dana [Source 2] with a high risk [Source 1].')
    expect(parts).toEqual([
      { kind: 'text', value: 'Led by Dana ' },
      { kind: 'citation', label: 2, value: '[Source 2]' },
      { kind: 'text', value: ' with a high risk ' },
      { kind: 'citation', label: 1, value: '[Source 1]' },
      { kind: 'text', value: '.' },
    ])
    expect(citedLabels('A [Source 2] B [source 1] [Source 2]')).toEqual([2, 1])
  })

  it('returns a single text part when there are no citations', () => {
    expect(splitCitations('No sources here.')).toEqual([
      { kind: 'text', value: 'No sources here.' },
    ])
  })
})

describe('formatBytes', () => {
  it('formats sizes', () => {
    expect(formatBytes(400)).toBe('400 B')
    expect(formatBytes(2048)).toBe('2.0 KB')
  })
})

describe('pendingWorkflow', () => {
  it('shows a single in-flight plan step', () => {
    const events = pendingWorkflow()
    expect(events).toEqual([{ id: 'plan', node: 'plan', label: 'Analysing request', done: false }])
  })
})
