import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useCallback } from 'react'
import { sendChatMessageStream } from '@/api/chat'
import type { ChatMessage, ProgressStep } from '@/types'

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>([])
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: (request: { message: string; conversation_id?: string }) =>
      sendChatMessageStream(request, (step) => {
        setProgressSteps((prev) => {
          const existing = prev.findIndex((s) => s.step === step.step)
          if (existing >= 0) {
            const updated = [...prev]
            updated[existing] = step
            return updated
          }
          return [...prev, step]
        })
      }),
    onSuccess: (data) => {
      setConversationId(data.conversation_id)
      setProgressSteps([])

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
    onError: (error) => {
      setProgressSteps([])

      // Add error message to chat so user sees what went wrong
      const errorMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `Sorry, something went wrong: ${error.message}. Please try again.`,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
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
    setProgressSteps([])
  }, [])

  return {
    messages,
    sendMessage,
    clearChat,
    isLoading: mutation.isPending,
    error: mutation.error,
    progressSteps,
  }
}
