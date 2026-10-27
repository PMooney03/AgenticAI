import { useEffect, useRef, useState } from 'react'

import type { ChatMessage } from '../hooks/useChat'
import { splitCitations } from '../lib/citations'

interface ChatProps {
  messages: ChatMessage[]
  sending: boolean
  error: string | null
  useDocuments: boolean
  onToggleDocuments: (value: boolean) => void
  onSend: (text: string) => Promise<void>
  onSelect: (id: string) => void
  selectedId: string | null
  onCite: (label: number) => void
  pending?: boolean
}

export function Chat({
  messages,
  sending,
  error,
  useDocuments,
  onToggleDocuments,
  onSend,
  onSelect,
  selectedId,
  onCite,
  pending = false,
}: ChatProps) {
  const [draft, setDraft] = useState('')
  const scroller = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const node = scroller.current
    if (node) {
      node.scrollTop = node.scrollHeight
    }
  }, [messages, sending])

  async function submit() {
    const text = draft
    setDraft('')
    await onSend(text)
  }

  return (
    <section className="chat">
      <header className="chat-header">
        <div>
          <h2>Ask your documents</h2>
          <p className="muted">
            {useDocuments
              ? 'Answers are grounded in retrieved chunks and must cite sources.'
              : 'Plain chat — retrieval is off for this turn.'}
          </p>
        </div>
        <label className="toggle">
          <input
            type="checkbox"
            checked={useDocuments}
            onChange={(event) => onToggleDocuments(event.target.checked)}
          />
          Use documents
        </label>
      </header>

      <div className="transcript" ref={scroller} data-testid="transcript">
        {messages.length === 0 && !sending ? (
          <div className="welcome">
            <p>
              Upload a PDF, Markdown or text file, then ask a question. The model will search
              your library and answer only from what it finds.
            </p>
            <p className="muted">Try: “How many days of annual leave do employees get?”</p>
          </div>
        ) : null}

        {messages.map((message) => (
          <article
            key={message.id}
            className={`bubble ${message.role} ${selectedId === message.id ? 'is-selected' : ''}`}
            onClick={() => message.role === 'assistant' && onSelect(message.id)}
          >
            <span className="who">{message.role === 'user' ? 'You' : 'Assistant'}</span>
            {message.role === 'assistant' ? (
              <p className="bubble-body">
                {splitCitations(message.content).map((part, index) =>
                  part.kind === 'citation' ? (
                    <button
                      key={`${message.id}-${index}`}
                      type="button"
                      className="cite"
                      onClick={(event) => {
                        event.stopPropagation()
                        onSelect(message.id)
                        onCite(part.label)
                      }}
                    >
                      {part.value}
                    </button>
                  ) : (
                    <span key={`${message.id}-${index}`}>{part.value}</span>
                  ),
                )}
              </p>
            ) : (
              <p className="bubble-body">{message.content}</p>
            )}
            {message.role === 'assistant' && (message.latencyMs != null || message.retrieval) ? (
              <p className="bubble-meta">
                {message.retrieval
                  ? `${message.retrieval.retrieved_chunks} chunks · `
                  : ''}
                {message.latencyMs} ms · {message.promptVersion}
              </p>
            ) : null}
          </article>
        ))}

        {sending ? (
          <article className="bubble assistant loading" data-testid="loading">
            <span className="who">Assistant</span>
            <p className="bubble-body">
              <span className="dots" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
              {pending
                ? 'Resuming after your decision…'
                : useDocuments
                  ? 'Planning, searching, and composing an answer…'
                  : 'Planning and answering…'}
            </p>
          </article>
        ) : null}
      </div>

      {error ? <p className="banner error">{error}</p> : null}

      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault()
          void submit()
        }}
      >
        <textarea
          value={draft}
          rows={2}
          placeholder="Ask a question about your documents…"
          disabled={sending || pending}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              void submit()
            }
          }}
        />
        <button type="submit" disabled={sending || pending || !draft.trim()}>
          Send
        </button>
      </form>
    </section>
  )
}
