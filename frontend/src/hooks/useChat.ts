import { useCallback, useState } from 'react'

import { ApiError, api } from '../api/client'
import type { ChatMode, RetrievalStats, Source } from '../api/types'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  mode?: ChatMode
  sources?: Source[]
  retrieval?: RetrievalStats | null
  model?: string
  promptVersion?: string
  requestId?: string
  latencyMs?: number
}

function nextId(): string {
  return crypto.randomUUID()
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [useDocuments, setUseDocuments] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const selected = messages.find((message) => message.id === selectedId) ??
    [...messages].reverse().find((message) => message.role === 'assistant') ??
    null

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || sending) {
        return
      }
      const userMessage: ChatMessage = { id: nextId(), role: 'user', content: trimmed }
      const history = messages
        .filter((message) => message.role === 'user' || message.role === 'assistant')
        .map((message) => ({ role: message.role, content: message.content }))

      setMessages((current) => [...current, userMessage])
      setSending(true)
      setError(null)

      try {
        const result = await api.chat({
          message: trimmed,
          history,
          use_documents: useDocuments,
        })
        const assistant: ChatMessage = {
          id: nextId(),
          role: 'assistant',
          content: result.answer,
          mode: result.mode,
          sources: result.sources,
          retrieval: result.retrieval,
          model: result.model,
          promptVersion: result.prompt_version,
          requestId: result.request_id,
          latencyMs: result.latency_ms,
        }
        setMessages((current) => [...current, assistant])
        setSelectedId(assistant.id)
      } catch (err) {
        const message = err instanceof ApiError ? err.message : 'Chat request failed.'
        setError(message)
      } finally {
        setSending(false)
      }
    },
    [messages, sending, useDocuments],
  )

  const clear = useCallback(() => {
    setMessages([])
    setSelectedId(null)
    setError(null)
  }, [])

  return {
    messages,
    sending,
    error,
    useDocuments,
    setUseDocuments,
    selected,
    setSelectedId,
    send,
    clear,
  }
}
