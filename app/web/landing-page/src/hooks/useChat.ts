import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useCallback } from 'react'
import { sendChatMessage } from '@/api/chat'
import type { ChatMessage } from '@/types'

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: sendChatMessage,
    onSuccess: (data) => {
      setConversationId(data.conversation_id)

      const assistantMessage: ChatMessage = {
        id: data.message.id,
        role: 'assistant',
        content: data.message.content,
        timestamp: new Date(data.message.created_at),
        sources: data.message.sources || undefined,
        attachments: data.message.attachments || undefined,
      }

      setMessages((prev) => [...prev, assistantMessage])

      // Invalidate any related queries
      queryClient.invalidateQueries({ queryKey: ['conversation', data.conversation_id] })
    },
  })

  const sendMessage = useCallback(
    (content: string) => {
      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content,
        timestamp: new Date(),
      }

      setMessages((prev) => [...prev, userMessage])

      mutation.mutate({
        message: content,
        conversation_id: conversationId ?? undefined,
      })
    },
    [conversationId, mutation]
  )

  const clearChat = useCallback(() => {
    setMessages([])
    setConversationId(null)
  }, [])

  return {
    messages,
    sendMessage,
    clearChat,
    isLoading: mutation.isPending,
    error: mutation.error,
  }
}
