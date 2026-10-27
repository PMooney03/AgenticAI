import { useState } from 'react'

import { AgentActivity } from './components/AgentActivity'
import { ApprovalCard } from './components/ApprovalCard'
import { Chat } from './components/Chat'
import { Sidebar } from './components/Sidebar'
import { SourcePanel } from './components/SourcePanel'
import { useChat } from './hooks/useChat'
import { useDocuments } from './hooks/useDocuments'
import { useHealth } from './hooks/useHealth'
import { workflowEvents } from './lib/workflow'

export default function App() {
  const documents = useDocuments()
  const chat = useChat()
  const { health, error: healthError } = useHealth()
  const [activeLabel, setActiveLabel] = useState<number | null>(null)

  const sources = chat.selected?.sources ?? []
  const events = workflowEvents(
    chat.sending ? (chat.useDocuments ? 'rag' : 'chat') : chat.selected?.mode,
    chat.selected?.retrieval,
    chat.sending,
  )

  return (
    <div className="shell">
      <Sidebar
        documents={documents.documents}
        loading={documents.loading}
        uploading={documents.uploading}
        error={documents.error}
        health={health}
        healthError={healthError}
        onUpload={documents.upload}
        onDelete={documents.remove}
      />
      <Chat
        messages={chat.messages}
        sending={chat.sending}
        error={chat.error}
        useDocuments={chat.useDocuments}
        onToggleDocuments={chat.setUseDocuments}
        onSend={chat.send}
        onSelect={(id) => {
          chat.setSelectedId(id)
          setActiveLabel(null)
        }}
        selectedId={chat.selected?.id ?? null}
        onCite={setActiveLabel}
      />
      <aside className="right">
        <SourcePanel
          sources={sources}
          activeLabel={activeLabel}
          onSelect={setActiveLabel}
        />
        <AgentActivity events={events} />
        <ApprovalCard description={null} onApprove={() => undefined} onReject={() => undefined} />
      </aside>
    </div>
  )
}
