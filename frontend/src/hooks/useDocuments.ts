import { useCallback, useEffect, useState } from 'react'

import { ApiError, api } from '../api/client'
import type { DocumentRecord } from '../api/types'

export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const result = await api.listDocuments()
      setDocuments(result.documents)
      setError(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load documents.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const upload = useCallback(async (file: File) => {
    setUploading(true)
    setError(null)
    try {
      const record = await api.uploadDocument(file)
      setDocuments((current) => [record, ...current.filter((doc) => doc.id !== record.id)])
      return record
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Upload failed.'
      setError(message)
      throw err
    } finally {
      setUploading(false)
    }
  }, [])

  const remove = useCallback(async (id: string) => {
    setError(null)
    const previous = documents
    setDocuments((current) => current.filter((doc) => doc.id !== id))
    try {
      await api.deleteDocument(id)
    } catch (err) {
      setDocuments(previous)
      const message = err instanceof ApiError ? err.message : 'Delete failed.'
      setError(message)
      throw err
    }
  }, [documents])

  return { documents, loading, uploading, error, refresh, upload, remove }
}
