import type { Source } from '../api/types'
import { formatScore } from '../lib/citations'

interface SourcePanelProps {
  sources: Source[]
  activeLabel: number | null
  onSelect: (label: number) => void
}

export function SourcePanel({ sources, activeLabel, onSelect }: SourcePanelProps) {
  return (
    <section className="panel" data-testid="source-panel">
      <header className="panel-head">
        <h2>Sources</h2>
        <span className="muted">{sources.length}</span>
      </header>
      {sources.length === 0 ? (
        <p className="empty">Sources for the selected answer appear here.</p>
      ) : (
        <ol className="source-list">
          {sources.map((source) => (
            <li key={`${source.document_id}-${source.label}`}>
              <button
                type="button"
                className={`source-card ${source.cited ? 'is-cited' : ''} ${
                  activeLabel === source.label ? 'is-active' : ''
                }`}
                aria-label={`Source ${source.label}${source.page ? `, page ${source.page}` : ''}`}
                onClick={() => onSelect(source.label)}
              >
                <div className="source-top">
                  <span className="source-label">[{source.label}]</span>
                  <span className="source-name" title={source.document_name}>
                    {source.document_name}
                  </span>
                  {source.cited ? <span className="badge badge-cited">Cited</span> : (
                    <span className="badge badge-retrieved">Retrieved</span>
                  )}
                </div>
                <div className="source-meta">
                  {source.page ? <span>Page {source.page}</span> : <span>No page</span>}
                  <span title="Cosine similarity">Score {formatScore(source.score)}</span>
                </div>
                <div className="score-bar" aria-hidden="true">
                  <span style={{ width: `${Math.max(4, Math.min(100, source.score * 100))}%` }} />
                </div>
                {activeLabel === source.label ? (
                  <p className="source-snippet">{source.snippet}</p>
                ) : null}
              </button>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
