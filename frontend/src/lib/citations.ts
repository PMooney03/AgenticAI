export type AnswerPart =
  | { kind: 'text'; value: string }
  | { kind: 'citation'; label: number; value: string }

const CITATION = /\[Source\s+(\d+)\]/gi

export function splitCitations(answer: string): AnswerPart[] {
  const parts: AnswerPart[] = []
  let cursor = 0
  const seen = new Set<number>()
  for (const match of answer.matchAll(CITATION)) {
    const index = match.index ?? 0
    if (index > cursor) {
      parts.push({ kind: 'text', value: answer.slice(cursor, index) })
    }
    const label = Number(match[1])
    parts.push({ kind: 'citation', label, value: match[0] })
    seen.add(label)
    cursor = index + match[0].length
  }
  if (cursor < answer.length) {
    parts.push({ kind: 'text', value: answer.slice(cursor) })
  }
  return parts
}

export function citedLabels(answer: string): number[] {
  const labels: number[] = []
  for (const part of splitCitations(answer)) {
    if (part.kind === 'citation' && !labels.includes(part.label)) {
      labels.push(part.label)
    }
  }
  return labels
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatScore(score: number): string {
  return score.toFixed(2)
}
