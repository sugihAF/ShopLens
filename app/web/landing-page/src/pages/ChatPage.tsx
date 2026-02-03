import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useChat } from '@/hooks'
import { formatMarkdown } from '@/lib/utils'
import { LogoIcon, SendIcon } from '@/components/ui'
import type { ChatMessage } from '@/types'

// Icons
function ArrowLeftIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M19 12H5M12 19l-7-7 7-7" />
    </svg>
  )
}

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  )
}

function MenuIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  )
}

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

function MessageIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

// Typing indicator component
function TypingIndicator() {
  return (
    <div className="flex gap-1.5 py-1">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="w-2 h-2 bg-[var(--color-accent-primary)] rounded-full"
          animate={{ y: [0, -6, 0] }}
          transition={{
            duration: 0.6,
            repeat: Infinity,
            delay: i * 0.15,
            ease: 'easeInOut',
          }}
        />
      ))}
    </div>
  )
}

// AI Avatar component
function AIAvatar() {
  return (
    <div className="w-9 h-9 flex-shrink-0 rounded-xl bg-gradient-to-br from-[var(--color-accent-tertiary)] to-[var(--color-accent-primary)] flex items-center justify-center shadow-lg shadow-[rgba(245,158,11,0.15)]">
      <svg className="w-5 h-5 text-[var(--color-bg-primary)]" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="3" fill="currentColor" />
        <path
          d="M12 2v4M12 18v4M2 12h4M18 12h4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
    </div>
  )
}

// Message bubble component
function MessageBubble({ message, isTyping }: { message: ChatMessage; isTyping?: boolean }) {
  const isUser = message.role === 'user'

  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className={`flex gap-4 ${isUser ? 'justify-end' : 'items-start'}`}
    >
      {!isUser && <AIAvatar />}
      <div
        className={`relative max-w-[75%] ${
          isUser
            ? 'bg-[var(--color-accent-primary)] text-[var(--color-bg-primary)] rounded-2xl rounded-br-sm px-5 py-3.5 font-medium shadow-lg shadow-[rgba(245,158,11,0.2)]'
            : 'bg-[var(--color-bg-tertiary)] border border-[var(--color-glass-border)] text-[var(--color-text-secondary)] rounded-2xl rounded-tl-sm px-5 py-4'
        }`}
      >
        {isTyping ? (
          <TypingIndicator />
        ) : (
          <div
            className="text-[15px] leading-relaxed [&_strong]:text-[var(--color-text-primary)] [&_strong]:font-semibold [&_ul]:mt-3 [&_ul]:space-y-1.5 [&_li]:flex [&_li]:items-start [&_li]:gap-2 [&_p]:mb-2 [&_p:last-child]:mb-0"
            dangerouslySetInnerHTML={{ __html: formatMarkdown(message.content) }}
          />
        )}
      </div>
    </motion.div>
  )
}

// Welcome screen component
function WelcomeScreen({ onSuggestionClick }: { onSuggestionClick: (query: string) => void }) {
  const suggestions = [
    { icon: '🎧', text: 'Best noise-canceling headphones under $400?' },
    { icon: '📱', text: 'Compare iPhone 15 Pro vs Samsung S24 Ultra' },
    { icon: '💻', text: 'MacBook Pro M3 Max for video editing?' },
    { icon: '📷', text: 'Best mirrorless camera for beginners?' },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      className="flex flex-col items-center justify-center h-full text-center px-6"
    >
      {/* Logo Animation */}
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
        className="relative mb-8"
      >
        <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-[var(--color-accent-tertiary)] to-[var(--color-accent-primary)] flex items-center justify-center shadow-xl shadow-[rgba(245,158,11,0.25)]">
          <svg className="w-10 h-10 text-[var(--color-bg-primary)]" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="3" fill="currentColor" />
            <path
              d="M12 2v4M12 18v4M2 12h4M18 12h4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </div>
        {/* Ambient glow */}
        <div className="absolute inset-0 w-20 h-20 rounded-2xl bg-[var(--color-accent-primary)] opacity-20 blur-xl" />
      </motion.div>

      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="font-serif text-3xl md:text-4xl text-[var(--color-text-primary)] mb-4"
      >
        How can I help you{' '}
        <span className="gradient-text italic">today?</span>
      </motion.h1>

      <motion.p
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.3 }}
        className="text-[var(--color-text-secondary)] max-w-md mb-10 leading-relaxed"
      >
        Ask me anything about tech products. I analyze reviews from trusted sources to give you comprehensive insights.
      </motion.p>

      {/* Suggestion chips */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.4 }}
        className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl"
      >
        {suggestions.map((suggestion, index) => (
          <motion.button
            key={index}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.5 + index * 0.1 }}
            onClick={() => onSuggestionClick(suggestion.text)}
            className="group flex items-center gap-3 px-5 py-4 bg-[var(--color-bg-secondary)] border border-[var(--color-glass-border)] rounded-xl text-left transition-all duration-300 hover:bg-[var(--color-bg-tertiary)] hover:border-[var(--color-accent-primary)]/30 hover:shadow-lg hover:shadow-[rgba(245,158,11,0.05)]"
          >
            <span className="text-xl">{suggestion.icon}</span>
            <span className="text-sm text-[var(--color-text-secondary)] group-hover:text-[var(--color-text-primary)] transition-colors">
              {suggestion.text}
            </span>
          </motion.button>
        ))}
      </motion.div>
    </motion.div>
  )
}

// Conversation history item
function ConversationItem({ title, isActive, onClick }: { title: string; isActive?: boolean; onClick: () => void }) {
  return (
    <motion.button
      whileHover={{ x: 4 }}
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all duration-200 ${
        isActive
          ? 'bg-[var(--color-bg-tertiary)] border border-[var(--color-accent-primary)]/20 text-[var(--color-text-primary)]'
          : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]'
      }`}
    >
      <MessageIcon className="w-4 h-4 flex-shrink-0 opacity-60" />
      <span className="text-sm truncate">{title}</span>
    </motion.button>
  )
}

// Sidebar component
function Sidebar({ isOpen, onClose, onNewChat }: { isOpen: boolean; onClose: () => void; onNewChat: () => void }) {
  // Mock conversation history
  const conversations = [
    { id: '1', title: 'Best headphones comparison' },
    { id: '2', title: 'MacBook Pro M3 review' },
    { id: '3', title: 'Camera recommendations' },
  ]

  return (
    <>
      {/* Overlay */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        initial={false}
        animate={{ x: isOpen ? 0 : '-100%' }}
        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        className="fixed inset-y-0 left-0 z-50 w-72 bg-[var(--color-bg-secondary)] border-r border-[var(--color-glass-border)] flex flex-col"
      >
        {/* Sidebar header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--color-glass-border)]">
          <span className="text-sm font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider">
            History
          </span>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)] transition-colors"
          >
            <CloseIcon className="w-4 h-4" />
          </button>
        </div>

        {/* New chat button */}
        <div className="p-4">
          <button
            onClick={onNewChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-[var(--color-accent-primary)] text-[var(--color-bg-primary)] font-semibold rounded-xl transition-all duration-300 hover:bg-[var(--color-accent-secondary)] hover:shadow-lg hover:shadow-[rgba(245,158,11,0.25)]"
          >
            <PlusIcon className="w-4 h-4" />
            <span>New Chat</span>
          </button>
        </div>

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
          {conversations.map((conv) => (
            <ConversationItem
              key={conv.id}
              title={conv.title}
              isActive={conv.id === '1'}
              onClick={() => {}}
            />
          ))}
        </div>

        {/* Sidebar footer */}
        <div className="p-4 border-t border-[var(--color-glass-border)]">
          <div className="flex items-center gap-3 px-3 py-2">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[var(--color-accent-tertiary)] to-[var(--color-accent-primary)] flex items-center justify-center text-[var(--color-bg-primary)] text-sm font-semibold">
              U
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-[var(--color-text-primary)] truncate">User</p>
              <p className="text-xs text-[var(--color-text-muted)]">Free tier</p>
            </div>
          </div>
        </div>
      </motion.aside>
    </>
  )
}

// Main ChatPage component
export function ChatPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [input, setInput] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { messages, sendMessage, clearChat, isLoading } = useChat()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const initialQuerySentRef = useRef(false)

  // Get initial query from URL params
  const initialQuery = searchParams.get('q')

  // Send initial query if present (only once)
  useEffect(() => {
    if (initialQuery && messages.length === 0 && !initialQuerySentRef.current) {
      initialQuerySentRef.current = true
      sendMessage(initialQuery)
    }
  }, [initialQuery])

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 200) + 'px'
    }
  }, [input])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return
    sendMessage(input.trim())
    setInput('')
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleSuggestionClick = (query: string) => {
    sendMessage(query)
  }

  const handleNewChat = () => {
    clearChat()
    setSidebarOpen(false)
  }

  return (
    <div className="h-screen flex bg-[var(--color-bg-primary)] overflow-hidden">
      {/* Background effects */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div
          className="absolute w-[600px] h-[600px] opacity-20"
          style={{
            background: 'radial-gradient(circle, rgba(245, 158, 11, 0.1) 0%, transparent 70%)',
            top: '-200px',
            right: '-100px',
            filter: 'blur(80px)',
          }}
        />
        <div
          className="absolute w-[400px] h-[400px] opacity-15"
          style={{
            background: 'radial-gradient(circle, rgba(45, 212, 191, 0.1) 0%, transparent 70%)',
            bottom: '-100px',
            left: '-100px',
            filter: 'blur(80px)',
          }}
        />
      </div>

      {/* Sidebar */}
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} onNewChat={handleNewChat} />

      {/* Main content */}
      <div className="w-full flex flex-col min-w-0 relative z-10">
        {/* Header */}
        <header className="flex items-center justify-between px-4 md:px-6 py-4 border-b border-[var(--color-glass-border)] bg-[var(--color-bg-primary)]/80 backdrop-blur-xl">
          <div className="flex items-center gap-2">
            {/* Menu button */}
            <button
              onClick={() => setSidebarOpen(true)}
              className="w-10 h-10 flex items-center justify-center rounded-xl text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)] transition-colors"
            >
              <MenuIcon className="w-5 h-5" />
            </button>

            {/* Back button */}
            <button
              onClick={() => navigate('/')}
              className="flex items-center gap-2 px-3 py-2 rounded-xl text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)] transition-all duration-200"
            >
              <ArrowLeftIcon className="w-4 h-4" />
              <span className="hidden sm:inline text-sm font-medium">Back</span>
            </button>
          </div>

          {/* Logo */}
          <div className="flex items-center gap-2.5">
            <LogoIcon className="w-8 h-8" />
            <span className="text-lg font-semibold tracking-tight">ShopLens</span>
          </div>

          {/* New chat button */}
          <button
            onClick={handleNewChat}
            className="flex items-center gap-2 px-4 py-2.5 bg-[var(--color-bg-secondary)] border border-[var(--color-glass-border)] rounded-xl text-sm font-medium text-[var(--color-text-secondary)] transition-all duration-200 hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)] hover:border-[var(--color-accent-primary)]/30"
          >
            <PlusIcon className="w-4 h-4" />
            <span className="hidden sm:inline">New Chat</span>
          </button>
        </header>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 && !isLoading ? (
            <WelcomeScreen onSuggestionClick={handleSuggestionClick} />
          ) : (
            <div className="max-w-3xl mx-auto px-4 md:px-6 py-8 space-y-6">
              <AnimatePresence mode="popLayout">
                {messages.map((message) => (
                  <MessageBubble key={message.id} message={message} />
                ))}
                {isLoading && (
                  <MessageBubble
                    message={{
                      id: 'loading',
                      role: 'assistant',
                      content: '',
                      timestamp: new Date(),
                    }}
                    isTyping
                  />
                )}
              </AnimatePresence>
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input area */}
        <div className="border-t border-[var(--color-glass-border)] bg-[var(--color-bg-primary)]/80 backdrop-blur-xl">
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto px-4 md:px-6 py-4">
            <div className="relative flex items-end gap-3 p-2 bg-[var(--color-bg-secondary)] border border-[var(--color-glass-border)] rounded-2xl transition-all duration-200 focus-within:border-[var(--color-accent-primary)]/50 focus-within:shadow-[0_0_0_4px_rgba(245,158,11,0.1)]">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about any tech product..."
                disabled={isLoading}
                rows={1}
                className="flex-1 px-4 py-3 bg-transparent text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] resize-none focus:outline-none disabled:opacity-50 text-[15px] leading-relaxed"
                style={{ maxHeight: '200px' }}
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                className="flex-shrink-0 w-11 h-11 flex items-center justify-center bg-[var(--color-accent-primary)] rounded-xl text-[var(--color-bg-primary)] transition-all duration-300 hover:bg-[var(--color-accent-secondary)] hover:scale-105 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 shadow-lg shadow-[rgba(245,158,11,0.2)]"
              >
                <SendIcon className="w-5 h-5" />
              </button>
            </div>
            <p className="text-center text-xs text-[var(--color-text-muted)] mt-3">
              ShopLens analyzes reviews from trusted tech sources to provide insights.
            </p>
          </form>
        </div>
      </div>
    </div>
  )
}
