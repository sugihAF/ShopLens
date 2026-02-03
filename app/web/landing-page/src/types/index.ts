export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  sources?: SourceReference[]
}

export interface SourceReference {
  type: string
  id: number
  name: string
  url?: string
  snippet?: string
}

export interface ChatRequest {
  message: string
  conversation_id?: string
}

// Backend API response format
export interface ApiMessageResponse {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources: SourceReference[] | null
  attachments: unknown[] | null
  created_at: string
}

export interface ApiChatResponse {
  message: ApiMessageResponse
  conversation_id: string
  suggested_questions: string[] | null
  products_mentioned: number[] | null
}

// Legacy format (kept for compatibility)
export interface ChatResponse {
  response: string
  conversationId: string
  sources?: string[]
}

export interface Feature {
  icon: React.ReactNode
  title: string
  description: string
  iconColor?: 'violet' | 'cyan' | 'pink' | 'orange' | 'green' | 'blue'
}

export interface Step {
  number: string
  title: string
  description: string
  visual: React.ReactNode
}

export interface Stat {
  value: number
  suffix: string
  label: string
}
