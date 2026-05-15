import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { openChatSocket, type ChatSocketHandle } from '@/api/chat'
import type { ChatMessage, ProgressStep } from '@/types'

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const socketRef = useRef<ChatSocketHandle | null>(null)
  const currentRequestIdRef = useRef<string | null>(null)
  const queryClient = useQueryClient()

  useEffect(() => {
    const handle = openChatSocket({
      onProgress: (event) => {
        if (event.request_id !== currentRequestIdRef.current) return
        setProgressSteps((prev) => {
          const idx = prev.findIndex((s) => s.step === event.step)
          const step: ProgressStep = {
            step: event.step,
            label: event.label ?? event.step,
            status: event.status,
          }
          if (idx >= 0) {
            const updated = [...prev]
            updated[idx] = step
            return updated
          }
          return [...prev, step]
        })
      },
      onComplete: ({ request_id, data }) => {
        if (request_id !== currentRequestIdRef.current) return
        currentRequestIdRef.current = null
        setConversationId(data.conversation_id)
        setProgressSteps([])
        setIsLoading(false)

        const assistantMessage: ChatMessage = {
          id: data.message.id,
          role: 'assistant',
          content: data.message.content,
          timestamp: new Date(data.message.created_at),
          sources: data.message.sources || undefined,
          attachments: data.message.attachments || undefined,
        }
        setMessages((prev) => [...prev, assistantMessage])
        queryClient.invalidateQueries({ queryKey: ['conversation', data.conversation_id] })
      },
      onCancelled: ({ request_id, reason }) => {
        if (request_id !== currentRequestIdRef.current) return
        currentRequestIdRef.current = null
        setProgressSteps([])
        setIsLoading(false)
        if (reason === 'user') {
          const stoppedMessage: ChatMessage = {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: '_Stopped._',
            timestamp: new Date(),
          }
          setMessages((prev) => [...prev, stoppedMessage])
        }
        // For reason === 'superseded' we drop silently — a fresh turn is starting.
      },
      onError: (event) => {
        if (event.request_id && event.request_id !== currentRequestIdRef.current) return
        currentRequestIdRef.current = null
        setProgressSteps([])
        setIsLoading(false)
        const err = new Error(event.message)
        setError(err)
        const errorMessage: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `Sorry, something went wrong: ${event.message}. Please try again.`,
          timestamp: new Date(),
        }
        setMessages((prev) => [...prev, errorMessage])
      },
      onClose: () => {
        socketRef.current = null
      },
    })

    socketRef.current = handle

    return () => {
      handle.close()
      socketRef.current = null
    }
  }, [queryClient])

  const sendMessage = useCallback(
    (content: string) => {
      const handle = socketRef.current
      if (!handle) {
        setError(new Error('Chat connection not ready. Please refresh and try again.'))
        return
      }
      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, userMessage])

      const requestId = crypto.randomUUID()
      currentRequestIdRef.current = requestId
      setError(null)
      setIsLoading(true)
      handle.send(content, requestId, conversationId ?? null)
    },
    [conversationId]
  )

  const cancel = useCallback(() => {
    const handle = socketRef.current
    const requestId = currentRequestIdRef.current
    if (handle && requestId) {
      handle.cancel(requestId)
    }
  }, [])

  const clearChat = useCallback(() => {
    setMessages([])
    setConversationId(null)
    setProgressSteps([])
    setError(null)
    setIsLoading(false)
    currentRequestIdRef.current = null
  }, [])

  return {
    messages,
    sendMessage,
    cancel,
    clearChat,
    isLoading,
    error,
    progressSteps,
  }
}
