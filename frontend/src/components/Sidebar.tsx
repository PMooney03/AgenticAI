import { useRef, useState } from 'react'

import type { DocumentRecord, HealthResponse } from '../api/types'
import { formatBytes } from '../lib/citations'

const ACCEPTED = '.pdf,.txt,.md,application/pdf,text/plain,text/markdown'

interface SidebarProps {
  documents: DocumentRecord[]
  loading: boolean
  uploading: boolean
  error: string | null
  health: HealthResponse | null
  healthError: string | null
  onUpload: (file: File) => Promise<unknown>
  onDelete: (id: string) => Promise<unknown>
}

export function Sidebar({
  documents,
  loading,
  uploading,
  error,
  health,
  healthError,
  onUpload,
  onDelete,
}: SidebarProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<string | null>(null)

  async function handleFiles(files: FileList | File[]) {
    const file = files[0]
    if (!file) {
      return
    }
    await onUpload(file)
  }

  return (
    <aside className="sidebar">
      <header className="brand">
        <div className="brand-mark" aria-hidden="true">
          AS
        </div>
        <div>
          <h1>Agentic Second Brain</h1>
          <p className="brand-sub">Local documents, grounded answers</p>
        </div>
      </header>

      <HealthPill health={health} error={healthError} />

      <div
        className={`dropzone ${dragging ? 'is-dragging' : ''} ${uploading ? 'is-busy' : ''}`}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          void handleFiles(event.dataTransfer.files)
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          hidden
          onChange={(event) => {
            if (event.target.files) {
              void handleFiles(event.target.files)
              event.target.value = ''
            }
          }}
        />
        <button
          type="button"
          className="upload-btn"
          disabled={uploading}
          onClick={() => inputRef.current?.click()}
        >
          {uploading ? 'Indexing…' : 'Upload document'}
        </button>
        <p className="drop-hint">PDF, TXT or Markdown. Drop a file here.</p>
      </div>

      {error ? <p className="banner error">{error}</p> : null}

      <div className="doc-head">
        <h2>Documents</h2>
        <span className="muted">{documents.length}</span>
      </div>

      <ul className="doc-list">
        {loading ? <li className="muted">Loading…</li> : null}
        {!loading && documents.length === 0 ? (
          <li className="empty">No documents yet. Upload one to ground answers.</li>
        ) : null}
        {documents.map((doc) => (
          <li key={doc.id} className={`doc-item status-${doc.status}`}>
            <div className="doc-row">
              <span className="doc-name" title={doc.name}>
                {doc.name}
              </span>
              <StatusBadge status={doc.status} />
            </div>
            <div className="doc-meta">
              <span>{formatBytes(doc.size_bytes)}</span>
              {doc.page_count ? <span>{doc.page_count} pages</span> : null}
              {doc.chunk_count ? <span>{doc.chunk_count} chunks</span> : null}
            </div>
            {doc.error ? <p className="doc-error">{doc.error}</p> : null}
            {pendingDelete === doc.id ? (
              <div className="confirm-row">
                <span>Delete this document?</span>
                <button type="button" className="text-btn danger" onClick={() => void onDelete(doc.id)}>
                  Delete
                </button>
                <button type="button" className="text-btn" onClick={() => setPendingDelete(null)}>
                  Cancel
                </button>
              </div>
            ) : (
              <button type="button" className="text-btn" onClick={() => setPendingDelete(doc.id)}>
                Remove
              </button>
            )}
          </li>
        ))}
      </ul>
    </aside>
  )
}

function StatusBadge({ status }: { status: DocumentRecord['status'] }) {
  const label = status === 'ready' ? 'Ready' : status === 'failed' ? 'Failed' : 'Indexing'
  return <span className={`badge badge-${status}`}>{label}</span>
}

function HealthPill({ health, error }: { health: HealthResponse | null; error: string | null }) {
  if (error) {
    return (
      <div className="health health-down" title={error}>
        API unreachable
      </div>
    )
  }
  if (!health) {
    return <div className="health health-unknown">Checking services…</div>
  }
  const parts = [
    health.ollama.reachable ? 'Ollama' : 'Ollama down',
    health.embeddings.reachable ? 'embeddings' : 'embeddings down',
    health.qdrant.reachable ? 'Qdrant' : 'Qdrant down',
  ]
  return (
    <div
      className={`health ${health.status === 'ok' ? 'health-ok' : 'health-degraded'}`}
      title={`${health.ollama.model} · ${health.embeddings.model}`}
    >
      {health.status === 'ok' ? 'All local services up' : parts.join(' · ')}
    </div>
  )
}
