import { useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { useInView } from '@/hooks'
import { SendIcon, HeadphonesIcon, SmartphoneIcon, LaptopIcon } from '@/components/ui'

const suggestions = [
  {
    icon: <HeadphonesIcon className="w-4 h-4" />,
    label: 'Best noise-canceling headphones under $400?',
    query: "What's the best noise-canceling headphones under $400?",
  },
  {
    icon: <SmartphoneIcon className="w-4 h-4" />,
    label: 'iPhone 15 Pro vs S24 Ultra camera?',
    query: 'Compare iPhone 15 Pro vs Samsung S24 Ultra camera',
  },
  {
    icon: <LaptopIcon className="w-4 h-4" />,
    label: 'MacBook Pro M3 Max battery life?',
    query: 'What do reviewers say about the MacBook Pro M3 Max battery life?',
  },
]

function WelcomeScreen() {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-6">
      <div className="w-14 h-14 mb-5 rounded-[var(--radius-lg)] bg-gradient-to-br from-[var(--color-accent-tertiary)] to-[var(--color-accent-primary)] flex items-center justify-center">
        <svg className="w-7 h-7 text-[var(--color-bg-primary)]" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="3" fill="currentColor" />
          <path
            d="M12 2v4M12 18v4M2 12h4M18 12h4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      </div>
      <h3 className="text-lg font-semibold mb-2 text-[var(--color-text-primary)]">Welcome to ShopLens</h3>
      <p className="text-sm text-[var(--color-text-secondary)] max-w-[360px] leading-relaxed">
        Ask me anything about tech products. I'll analyze reviews from trusted sources to give you comprehensive insights.
      </p>
    </div>
  )
}

export function DemoChat() {
  const { ref, isInView } = useInView<HTMLElement>()
  const [input, setInput] = useState('')
  const navigate = useNavigate()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return
    // Navigate to chat page with query
    navigate(`/chat?q=${encodeURIComponent(input.trim())}`)
  }

  const handleSuggestionClick = (query: string) => {
    // Navigate to chat page with suggestion query
    navigate(`/chat?q=${encodeURIComponent(query)}`)
  }

  return (
    <section id="demo" ref={ref} className="py-24">
      <div className="section-container">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="section-header mb-12"
        >
          <span className="badge-editorial mb-6">Try It</span>
          <h2 className="headline-editorial text-[clamp(2rem,4vw,2.75rem)] mb-5 text-[var(--color-text-primary)]">
            See ShopLens{' '}
            <span className="gradient-text italic">in action</span>
          </h2>
          <p className="text-base text-[var(--color-text-secondary)] leading-relaxed">
            Experience how ShopLens transforms product research. Try one of these example queries or type your own.
          </p>
        </motion.div>

        {/* Demo Container */}
        <div className="demo-container">
          {/* Suggestions */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.4, delay: 0.2 }}
            className="demo-suggestions"
          >
            {suggestions.map((suggestion) => (
              <button
                key={suggestion.query}
                onClick={() => handleSuggestionClick(suggestion.query)}
                className="inline-flex items-center gap-2 px-4 py-2.5 bg-[var(--color-bg-secondary)] border border-[var(--color-glass-border)] rounded-full text-sm text-[var(--color-text-secondary)] transition-all duration-300 ease-[var(--ease-out-expo)] hover:bg-[var(--color-bg-tertiary)] hover:border-[var(--color-accent-primary)]/30 hover:text-[var(--color-text-primary)]"
              >
                <span className="opacity-60">{suggestion.icon}</span>
                <span className="hidden sm:inline">{suggestion.label}</span>
                <span className="sm:hidden">{suggestion.label.split(' ').slice(0, 3).join(' ')}...</span>
              </button>
            ))}
          </motion.div>

          {/* Chat Window */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.4, delay: 0.3 }}
            className="bg-[var(--color-bg-secondary)] border border-[var(--color-glass-border)] rounded-[var(--radius-xl)] overflow-hidden shadow-[var(--shadow-lg)]"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3.5 bg-[var(--color-bg-tertiary)] border-b border-[var(--color-glass-border)]">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-[var(--color-emerald)] animate-pulse-dot" />
                <span className="text-sm font-semibold text-[var(--color-text-secondary)]">ShopLens AI</span>
              </div>
            </div>

            {/* Welcome Screen */}
            <div className="min-h-[280px]">
              <WelcomeScreen />
            </div>

            {/* Input */}
            <form
              onSubmit={handleSubmit}
              className="flex items-center gap-3 px-5 py-4 border-t border-[var(--color-glass-border)] bg-[var(--color-bg-tertiary)]"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about any tech product..."
                className="flex-1 px-4 py-2.5 bg-[var(--color-bg-secondary)] border border-[var(--color-glass-border)] rounded-[var(--radius-md)] text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] transition-all focus:outline-none focus:border-[var(--color-accent-primary)]/50 focus:shadow-[0_0_0_3px_rgba(245,158,11,0.1)]"
              />
              <button
                type="submit"
                disabled={!input.trim()}
                className="w-10 h-10 flex items-center justify-center bg-[var(--color-accent-primary)] rounded-[var(--radius-md)] text-[var(--color-bg-primary)] transition-all duration-300 ease-[var(--ease-out-expo)] hover:bg-[var(--color-accent-secondary)] hover:scale-105 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
              >
                <SendIcon className="w-4 h-4" />
              </button>
            </form>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
