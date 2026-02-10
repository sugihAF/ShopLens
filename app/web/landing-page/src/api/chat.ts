import type { ChatRequest, ApiChatResponse, ProgressStep } from '@/types'

const API_BASE_URL = '/api/v1'

export async function sendChatMessage(request: ChatRequest): Promise<ApiChatResponse> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 300_000) // 5 min

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

export async function sendChatMessageStream(
  request: ChatRequest,
  onProgress: (step: ProgressStep) => void,
): Promise<ApiChatResponse> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 300_000) // 5 min — review ingestion can take 2-3 min

  try {
    const response = await fetch(`${API_BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let result: ApiChatResponse | null = null

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        // Keep the last potentially incomplete line in the buffer
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue

          const jsonStr = trimmed.slice(6)
          let event: { type: string; step?: string; label?: string; status?: string; data?: ApiChatResponse; message?: string }
          try {
            event = JSON.parse(jsonStr)
          } catch {
            continue
          }

          if (event.type === 'progress') {
            onProgress({
              step: event.step!,
              label: event.label!,
              status: event.status as 'running' | 'done',
            })
          } else if (event.type === 'complete') {
            result = event.data!
          } else if (event.type === 'error') {
            throw new Error(event.message || 'Stream error')
          }
        }

        // Once we have the complete response, stop reading immediately
        // Don't wait for the stream to close — resolves the mutation right away
        if (result) break
      }
    } finally {
      // Cancel the reader to clean up the connection
      reader.cancel().catch(() => {})
    }

    if (!result) {
      throw new Error('Stream ended without a complete response')
    }

    return result
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Request timed out. The server is taking too long to respond.')
    }
    throw err
  } finally {
    clearTimeout(timeout)
  }
}

export async function getConversationHistory(conversationId: string): Promise<ApiChatResponse[]> {
  const response = await fetch(`${API_BASE_URL}/chat/conversations/${conversationId}`)

  if (!response.ok) {
    throw new Error('Failed to fetch conversation')
  }

  return response.json()
}
