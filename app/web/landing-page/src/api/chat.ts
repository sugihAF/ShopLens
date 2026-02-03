import type { ChatRequest, ApiChatResponse } from '@/types'

const API_BASE_URL = '/api/v1'

export async function sendChatMessage(request: ChatRequest): Promise<ApiChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message: request.message,
      conversation_id: request.conversation_id || null,
    }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => null)
    throw new Error(errorData?.detail || 'Failed to send message')
  }

  return response.json()
}

export async function getConversationHistory(conversationId: string): Promise<ApiChatResponse[]> {
  const response = await fetch(`${API_BASE_URL}/chat/conversations/${conversationId}`)

  if (!response.ok) {
    throw new Error('Failed to fetch conversation')
  }

  return response.json()
}
