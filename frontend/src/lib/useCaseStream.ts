import { useEffect, useRef } from 'react'
import { createSSEStream } from './api'

export function useCaseStream(caseId: string | null | undefined, onEvent: (event: any) => void) {
  const cleanup = useRef<(() => void) | null>(null)
  // Keep a stable ref to onEvent so we don't reopen SSE on every render
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  useEffect(() => {
    if (!caseId) return
    cleanup.current = createSSEStream(`/cases/${caseId}/stream`, (e) => onEventRef.current(e))
    return () => {
      cleanup.current?.()
    }
  }, [caseId]) // only re-open when caseId changes
}
