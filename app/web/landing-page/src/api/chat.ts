import type { ApiChatResponse, ChatRequest } from '@/types'

const API_BASE_URL = '/api/v1'

export async function sendChatMessage(request: ChatRequest): Promise<ApiChatResponse> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 600_000) // 10 min

  try {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: request.message,
        conversation_id: request.conversation_id || null,
      }),
      signal: controller.signal,
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => null)
      throw new Error(errorData?.detail || 'Failed to send message')
    }

    return response.json()
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Request timed out. The server is taking too long to respond.')
    }
    throw err
  } finally {
    clearTimeout(timeout)
  }
}

// =====================================================================
// WebSocket chat client
// =====================================================================
// See: docs/superpowers/specs/2026-05-15-chat-websocket-design.md
// Replaces the previous sendChatMessageStream (SSE).
// =====================================================================

export interface ProgressEvent {
  request_id: string
  step: string
  label?: string
  status: 'running' | 'done'
  detail?: string
}

export interface QuestionEvent {
  request_id: string
  prompt: string
  choices?: unknown[]
  [extra: string]: unknown
}

export interface CancelledEvent {
  request_id: string
  reason: 'user' | 'superseded'
}

export interface ErrorEvent {
  request_id?: string
  code: string
  message: string
}

export interface ChatSocketEvents {
  onReady?: (userId: number | null) => void
  onProgress?: (event: ProgressEvent) => void
  onQuestion?: (event: QuestionEvent) => void
  onComplete?: (event: { request_id: string; data: ApiChatResponse }) => void
  onCancelled?: (event: CancelledEvent) => void
  onError?: (event: ErrorEvent) => void
  onClose?: (event: CloseEvent) => void
  onOpen?: () => void
}

export interface ChatSocketHandle {
  send(text: string, requestId: string, conversationId?: string | null): void
  cancel(requestId: string): void
  confirm(requestId: string, answer: unknown): void
  close(): void
  readyState: () => number
}

export function openChatSocket(
  events: ChatSocketEvents,
  opts: { token?: string | null } = {}
): ChatSocketHandle {
  const url = new URL('/api/v1/chat/ws', window.location.origin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'

  const ws = new WebSocket(url.toString())

  ws.addEventListener('open', () => {
    ws.send(JSON.stringify({ type: 'auth', token: opts.token ?? null }))
    events.onOpen?.()
  })

  ws.addEventListener('message', (evt) => {
    let parsed: { type?: string; [extra: string]: unknown }
    try {
      parsed = JSON.parse(evt.data)
    } catch {
      return
    }
    switch (parsed.type) {
      case 'ready':
        events.onReady?.((parsed.user_id as number | null) ?? null)
        break
      case 'progress':
        events.onProgress?.(parsed as unknown as ProgressEvent)
        break
      case 'question':
        events.onQuestion?.(parsed as unknown as QuestionEvent)
        break
      case 'complete':
        events.onComplete?.(parsed as unknown as { request_id: string; data: ApiChatResponse })
        break
      case 'cancelled':
        events.onCancelled?.(parsed as unknown as CancelledEvent)
        break
      case 'error':
        events.onError?.(parsed as unknown as ErrorEvent)
        break
      case 'pong':
        break
    }
  })

  ws.addEventListener('close', (evt) => events.onClose?.(evt))

  const sendFrame = (frame: object) => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(frame))
    }
  }

  return {
    send(text, requestId, conversationId) {
      sendFrame({
        type: 'message',
        request_id: requestId,
        text,
        conversation_id: conversationId ?? null,
      })
    },
    cancel(requestId) {
      sendFrame({ type: 'cancel', request_id: requestId })
    },
    confirm(requestId, answer) {
      sendFrame({ type: 'confirm', request_id: requestId, answer })
    },
    close() {
      ws.close()
    },
    readyState: () => ws.readyState,
  }
}

export async function getConversationHistory(conversationId: string): Promise<ApiChatResponse[]> {
  const response = await fetch(`${API_BASE_URL}/chat/conversations/${conversationId}`)

  if (!response.ok) {
    throw new Error('Failed to fetch conversation')
  }

  return response.json()
}
