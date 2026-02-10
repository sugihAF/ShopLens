import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { SendIcon } from '@/components/ui'
import { formatMarkdown } from '@/lib/utils'

const aiResponseText = `Based on 156 reviews, the **MacBook Pro 16" M3 Max** leads for video editing under $2000.

MKBHD rated it "the fastest laptop I've tested" with Dave2D praising its "all-day battery during 4K exports."

Key highlights:
- 40% faster renders than M2
- 22-hour battery life
- Best-in-class display`

function TypingIndicator() {
  return (
    <div className="flex gap-1.5 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 bg-[var(--color-accent-primary)] rounded-full animate-typing-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  )
}

export function HeroChatPreview() {
  const [displayedText, setDisplayedText] = useState('')
  const [isTyping, setIsTyping] = useState(true)

  useEffect(() => {
    const startDelay = setTimeout(() => {
      let i = 0
      const typeInterval = setInterval(() => {
        if (i < aiResponseText.length) {
          setDisplayedText(aiResponseText.slice(0, i + 1))
          i++
        } else {
          clearInterval(typeInterval)
          setIsTyping(false)
        }
      }, 25)

      return () => clearInterval(typeInterval)
    }, 800)

    return () => clearTimeout(startDelay)
  }, [])

  return (
    <div className="w-full max-w-[480px] relative">
      {/* Main Window */}
      <div className="bg-[var(--color-bg-secondary)] border border-[var(--color-glass-border)] rounded-[var(--radius-xl)] shadow-[var(--shadow-lg)] overflow-hidden">
        {/* Window Header */}
        <div className="flex items-center justify-between px-5 py-3.5 bg-[var(--color-bg-tertiary)] border-b border-[var(--color-glass-border)]">
          <div className="flex items-center gap-3">
            {/* Window Controls */}
            <div className="flex gap-2">
              <span className="w-3 h-3 rounded-full bg-[#ff5f57] shadow-[inset_0_-1px_0_rgba(0,0,0,0.2)]" />
              <span className="w-3 h-3 rounded-full bg-[#febc2e] shadow-[inset_0_-1px_0_rgba(0,0,0,0.2)]" />
              <span className="w-3 h-3 rounded-full bg-[#28c840] shadow-[inset_0_-1px_0_rgba(0,0,0,0.2)]" />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-[var(--color-emerald)] animate-pulse-dot" />
            <span className="text-xs font-semibold tracking-wide text-[var(--color-text-secondary)]">
              ShopLens AI
            </span>
          </div>

          <div className="w-16" /> {/* Spacer for centering */}
        </div>

        {/* Chat Area */}
        <div className="p-5 min-h-[320px] flex flex-col gap-5">
          {/* User Message */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="flex justify-end"
          >
            <div className="relative max-w-[90%]">
              <div className="px-4 py-3 bg-[var(--color-accent-primary)] text-[var(--color-bg-primary)] rounded-[var(--radius-lg)] rounded-br-[var(--radius-xs)] text-sm font-medium">
                What's the best laptop for video editing under $2000?
              </div>
            </div>
          </motion.div>

          {/* AI Message */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="flex gap-3 items-start"
          >
            {/* AI Avatar */}
            <div className="w-8 h-8 flex-shrink-0 rounded-[var(--radius-md)] bg-gradient-to-br from-[var(--color-accent-tertiary)] to-[var(--color-accent-primary)] flex items-center justify-center">
              <svg className="w-4 h-4 text-[var(--color-bg-primary)]" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="3" fill="currentColor" />
                <path
                  d="M12 2v4M12 18v4M2 12h4M18 12h4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </div>

            {/* Message Bubble */}
            <div className="flex-1 max-w-[90%]">
              <div className="px-4 py-3 bg-[var(--color-bg-tertiary)] border border-[var(--color-glass-border)] rounded-[var(--radius-lg)] rounded-tl-[var(--radius-xs)] text-sm text-[var(--color-text-secondary)] leading-relaxed">
                {isTyping && displayedText.length === 0 ? (
                  <TypingIndicator />
                ) : (
                  <div
                    className="[&_strong]:text-[var(--color-text-primary)] [&_strong]:font-semibold [&_ul]:mt-2 [&_ul]:space-y-1 [&_li]:flex [&_li]:items-start [&_li]:gap-2 [&_li]:before:content-['•'] [&_li]:before:text-[var(--color-accent-primary)] [&_li]:before:font-bold"
                    dangerouslySetInnerHTML={{ __html: formatMarkdown(displayedText) }}
                  />
                )}
              </div>
            </div>
          </motion.div>
        </div>

        {/* Input Area */}
        <div className="flex items-center gap-3 px-5 py-4 border-t border-[var(--color-glass-border)] bg-[var(--color-bg-tertiary)]">
          <div className="flex-1 relative">
            <input
              type="text"
              placeholder="Ask about any product..."
              disabled
              className="w-full px-4 py-2.5 bg-[var(--color-bg-secondary)] border border-[var(--color-glass-border)] rounded-[var(--radius-md)] text-sm text-[var(--color-text-tertiary)] placeholder:text-[var(--color-text-muted)] focus:outline-none"
            />
          </div>
          <button
            disabled
            className="w-10 h-10 flex items-center justify-center bg-[var(--color-bg-elevated)] border border-[var(--color-glass-border)] rounded-[var(--radius-md)] text-[var(--color-text-muted)] cursor-not-allowed transition-colors"
          >
            <SendIcon className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Decorative Elements */}
      <div className="absolute -bottom-3 -right-3 w-full h-full bg-[var(--color-bg-tertiary)] border border-[var(--color-glass-border)] rounded-[var(--radius-xl)] -z-10" />
      <div className="absolute -bottom-6 -right-6 w-full h-full bg-[var(--color-bg-elevated)] border border-[var(--color-glass-border)] rounded-[var(--radius-xl)] -z-20 opacity-50" />
    </div>
  )
}
