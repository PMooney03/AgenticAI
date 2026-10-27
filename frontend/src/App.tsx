import { useState } from 'react'

import { AgentActivity } from './components/AgentActivity'
import { ApprovalCard } from './components/ApprovalCard'
import { Chat } from './components/Chat'
import { MetricsPanel } from './components/MetricsPanel'
import { Sidebar } from './components/Sidebar'
import { SourcePanel } from './components/SourcePanel'
import { useChat } from './hooks/useChat'
import { useDocuments } from './hooks/useDocuments'
import { useHealth } from './hooks/useHealth'
import { pendingWorkflow } from './lib/workflow'

export default function App() {
  const documents = useDocuments()
  const chat = useChat()
  const { health, error: healthError } = useHealth()
  const [activeLabel, setActiveLabel] = useState<number | null>(null)

  const sources = chat.selected?.sources ?? []
  const events =
    chat.sending && !chat.pendingApproval ? pendingWorkflow() : (chat.selected?.workflow ?? [])

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
        pending={Boolean(chat.pendingApproval)}
      />
      <aside className="right">
        <SourcePanel
          sources={sources}
          activeLabel={activeLabel}
          onSelect={setActiveLabel}
        />
        <AgentActivity events={events} />
        <MetricsPanel />
        <ApprovalCard
          tool={chat.pendingApproval?.tool ?? null}
          description={chat.pendingApproval?.description ?? null}
          preview={chat.pendingApproval?.preview ?? null}
          busy={chat.sending}
          onApprove={() => void chat.decide(true)}
          onReject={() => void chat.decide(false)}
        />
      </aside>
    </div>
  )
}
