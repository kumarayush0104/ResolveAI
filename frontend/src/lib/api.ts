const BASE = '/api'

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = localStorage.getItem('jwt')
  const res = await fetch(BASE + path, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export interface PublicConfig {
  paypal_client_id: string
  paypal_env: string
  ai_online: boolean
  enable_lab: boolean
}

export const api = {
  // Auth
  demoLogin: (role: string) => req<{ access_token: string; role: string }>('POST', '/auth/demo-login', { role }),

  // Config
  getPublicConfig: () => req<PublicConfig>('GET', '/config/public'),

  // Orders
  createOrder: (amount: number, currency: string) =>
    req<{ order_id: string; approval_url: string; status: string }>('POST', '/orders', { amount, currency }),
  getOrder: (id: string) => req<any>('GET', `/orders/${id}`),
  captureOrder: (id: string) => req<any>('POST', `/orders/${id}/capture`),

  // Cases
  createCase: (order_id: string) => req<any>('POST', '/cases', { order_id }),
  getCase: (id: string) => req<any>('GET', `/cases/${id}`),
  addMessage: (id: string, message: string) => req<any>('POST', `/cases/${id}/messages`, { message }),
  approveAction: (id: string, action: string, notes?: string) =>
    req<any>('POST', `/cases/${id}/actions/${action}/approve`, { notes }),

  // Metrics
  getMetrics: () => req<any>('GET', '/merchant/metrics'),

  // Lab
  labAction: (action: string, body: unknown) => req<any>('POST', `/lab/${action}`, body),
}

// SSE helper for GET /api/cases/{id}/stream
export function createSSEStream(path: string, onEvent: (data: any) => void, onError?: (e: Event) => void): () => void {
  const token = localStorage.getItem('jwt')
  const url = BASE + path + (token ? `?token=${token}` : '')
  const es = new EventSource(url)
  es.onmessage = (e) => {
    try {
      onEvent(JSON.parse(e.data))
    } catch {
      // ignore parse errors for ping heartbeats
    }
  }
  if (onError) es.onerror = onError
  return () => es.close()
}

// Streaming reader for POST /api/cases/{id}/investigate
export async function streamInvestigation(
  caseId: string,
  onEvent: (event: any) => void,
  onFinish?: () => void,
  onError?: (err: any) => void
): Promise<() => void> {
  const controller = new AbortController()
  const token = localStorage.getItem('jwt')

  ;(async () => {
    try {
      const res = await fetch(`${BASE}/cases/${caseId}/investigate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        signal: controller.signal,
      })

      if (!res.ok) {
        const errorText = await res.text()
        throw new Error(errorText || `HTTP ${res.status}`)
      }

      const reader = res.body?.getReader()
      if (!reader) throw new Error('No readable stream available')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (trimmed.startsWith('data: ')) {
            const jsonStr = trimmed.slice(6)
            try {
              const parsed = JSON.parse(jsonStr)
              onEvent(parsed)
            } catch {
              // ignore invalid json fragments
            }
          }
        }
      }
      onFinish?.()
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        onError?.(err)
      }
    }
  })()

  return () => controller.abort()
}
