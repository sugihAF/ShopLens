import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useChat } from '@/hooks'
import { formatMarkdown } from '@/lib/utils'
import { LogoIcon, SendIcon } from '@/components/ui'
import type {
  ChatMessage, ReviewerCard, MarketplaceListing, Attachment, ProgressStep,
  SemanticSearchResult, AspectSentiment, ComparisonProduct
} from '@/types'

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

// Progress steps component for streaming progress
function ProgressSteps({ steps }: { steps: ProgressStep[] }) {
  const doneCount = steps.filter((s) => s.status === 'done').length
  const total = steps.length

  return (
    <div className="mt-3 space-y-2">
      {steps.map((step) => (
        <div key={step.step} className="flex items-center gap-2.5">
          {step.status === 'done' ? (
            <svg className="w-4 h-4 text-emerald-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : (
            <motion.svg
              className="w-4 h-4 text-amber-400 flex-shrink-0"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            >
              <path d="M12 2a10 10 0 0 1 10 10" />
            </motion.svg>
          )}
          <span
            className={`text-sm ${
              step.status === 'done'
                ? 'text-[var(--color-text-muted)]'
                : 'text-[var(--color-text-secondary)]'
            }`}
          >
            {step.label}{step.status === 'running' ? '...' : ''}
          </span>
        </div>
      ))}

      {/* Progress bar */}
      {total > 1 && (
        <div className="flex items-center gap-2.5 pt-1">
          <div className="flex-1 h-1.5 bg-[var(--color-bg-primary)] rounded-full overflow-hidden">
            <motion.div
              className="h-full rounded-full"
              style={{
                background: 'linear-gradient(90deg, var(--color-accent-tertiary), var(--color-accent-primary))',
              }}
              initial={{ width: 0 }}
              animate={{ width: `${(doneCount / total) * 100}%` }}
              transition={{ duration: 0.4, ease: 'easeOut' }}
            />
          </div>
          <span className="text-xs text-[var(--color-text-muted)] tabular-nums">
            {doneCount}/{total}
          </span>
        </div>
      )}
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

// Play icon for video reviews
function PlayIcon({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} style={style}>
      <path d="M8 5v14l11-7z" />
    </svg>
  )
}

// External link icon
function ExternalLinkIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  )
}

// Chevron icon for "View Details"
function ChevronRightIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <polyline points="9 18 15 12 9 6" />
    </svg>
  )
}

// Check icon for pros
function CheckCircleIcon({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  )
}

// X icon for cons
function XCircleIcon({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <circle cx="12" cy="12" r="10" />
      <line x1="15" y1="9" x2="9" y2="15" />
      <line x1="9" y1="9" x2="15" y2="15" />
    </svg>
  )
}

// Review detail modal component
function ReviewDetailModal({ card, onClose }: { card: ReviewerCard; onClose: () => void }) {
  const isVideo = card.review_type === 'video'
  const hasPros = card.pros && card.pros.length > 0
  const hasCons = card.cons && card.cons.length > 0

  // Close on escape key
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleEsc)
    return () => document.removeEventListener('keydown', handleEsc)
  }, [onClose])

  // Lock body scroll when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/75 backdrop-blur-md" />

      {/* Modal */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 24 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 24 }}
        transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
        onClick={(e) => e.stopPropagation()}
        className="review-detail-modal relative w-[calc(100%-2rem)] max-w-[680px] max-h-[90vh] flex flex-col rounded-2xl overflow-hidden"
        style={{
          background: 'var(--color-bg-secondary)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 0 0 1px rgba(255,255,255,0.03), 0 0 100px rgba(245, 158, 11, 0.06), 0 32px 80px rgba(0, 0, 0, 0.7)',
        }}
      >
        {/* ── Header ── */}
        <div className="relative flex-shrink-0" style={{ padding: '28px 32px 24px', background: 'var(--color-bg-tertiary)', borderBottom: '1px solid var(--color-glass-border)' }}>
          {/* Close */}
          <button
            onClick={onClose}
            className="absolute top-5 right-5 w-9 h-9 flex items-center justify-center rounded-full text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[rgba(255,255,255,0.06)] transition-all duration-200"
          >
            <CloseIcon className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-5">
            {/* Avatar */}
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center text-xl font-bold flex-shrink-0"
              style={{
                background: 'linear-gradient(135deg, var(--color-accent-tertiary), var(--color-accent-primary))',
                color: 'var(--color-bg-primary)',
                boxShadow: '0 4px 20px rgba(245, 158, 11, 0.25)',
              }}
            >
              {card.reviewer_name.charAt(0).toUpperCase()}
            </div>

            <div className="min-w-0 flex-1">
              <h3 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--color-text-primary)', lineHeight: 1.3 }}>
                {card.reviewer_name}
              </h3>
              <div className="flex items-center gap-3" style={{ marginTop: '8px' }}>
                <span
                  className="inline-flex items-center gap-1.5 text-xs font-medium rounded-full"
                  style={{
                    padding: '4px 12px',
                    background: isVideo ? 'rgba(239,68,68,0.12)' : 'rgba(59,130,246,0.12)',
                    color: isVideo ? '#f87171' : '#60a5fa',
                  }}
                >
                  {isVideo ? (
                    <><PlayIcon className="w-3 h-3" /> YouTube</>
                  ) : (
                    <><ExternalLinkIcon className="w-3 h-3" /> Blog</>
                  )}
                </span>
                {card.rating && (
                  <span className="flex items-center gap-1 text-sm">
                    <span className="font-bold" style={{ color: 'var(--color-accent-primary)' }}>{card.rating}</span>
                    <span style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem' }}>/10</span>
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* ── Scrollable body ── */}
        <div className="flex-1 overflow-y-auto" style={{ padding: '32px' }}>
          {/* Summary */}
          <div style={{ marginBottom: (hasPros || hasCons) ? '32px' : '0' }}>
            <div className="flex items-center gap-2" style={{ marginBottom: '14px' }}>
              <div style={{ width: '3px', height: '14px', borderRadius: '2px', background: 'var(--color-accent-primary)', opacity: 0.7 }} />
              <h4 style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--color-text-muted)' }}>
                Review Summary
              </h4>
            </div>
            <p style={{ fontSize: '0.9rem', lineHeight: 1.85, color: 'var(--color-text-secondary)' }}>
              {card.summary || 'No summary available'}
            </p>
          </div>

          {/* Pros & Cons */}
          {(hasPros || hasCons) && (
            <div style={{ display: 'grid', gridTemplateColumns: (hasPros && hasCons) ? '1fr 1fr' : '1fr', gap: '16px' }}>
              {hasPros && (
                <div
                  style={{
                    padding: '20px 22px',
                    borderRadius: '14px',
                    background: 'rgba(52, 211, 153, 0.04)',
                    border: '1px solid rgba(52, 211, 153, 0.10)',
                  }}
                >
                  <div className="flex items-center gap-2" style={{ marginBottom: '16px' }}>
                    <CheckCircleIcon className="w-4 h-4" style={{ color: '#6ee7b7' }} />
                    <h4 style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#6ee7b7' }}>
                      Pros
                    </h4>
                  </div>
                  <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    {card.pros.map((pro, i) => (
                      <li key={i} className="flex items-start gap-3" style={{ fontSize: '0.85rem', lineHeight: 1.65, color: 'var(--color-text-secondary)' }}>
                        <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'rgba(110, 231, 183, 0.5)', marginTop: '7px', flexShrink: 0 }} />
                        <span>{pro}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {hasCons && (
                <div
                  style={{
                    padding: '20px 22px',
                    borderRadius: '14px',
                    background: 'rgba(251, 113, 133, 0.04)',
                    border: '1px solid rgba(251, 113, 133, 0.10)',
                  }}
                >
                  <div className="flex items-center gap-2" style={{ marginBottom: '16px' }}>
                    <XCircleIcon className="w-4 h-4" style={{ color: '#fda4af' }} />
                    <h4 style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#fda4af' }}>
                      Cons
                    </h4>
                  </div>
                  <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    {card.cons.map((con, i) => (
                      <li key={i} className="flex items-start gap-3" style={{ fontSize: '0.85rem', lineHeight: 1.65, color: 'var(--color-text-secondary)' }}>
                        <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'rgba(253, 164, 175, 0.5)', marginTop: '7px', flexShrink: 0 }} />
                        <span>{con}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Footer ── */}
        {card.review_url && (
          <div className="flex-shrink-0" style={{ padding: '20px 32px', borderTop: '1px solid var(--color-glass-border)', background: 'var(--color-bg-tertiary)' }}>
            <a
              href={card.review_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-3 w-full transition-all duration-200"
              style={{
                padding: '14px 20px',
                borderRadius: '14px',
                fontSize: '0.875rem',
                fontWeight: 500,
                background: 'var(--color-bg-primary)',
                border: '1px solid var(--color-glass-border)',
                color: 'var(--color-text-secondary)',
                textDecoration: 'none',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'rgba(245,158,11,0.3)'
                e.currentTarget.style.color = 'var(--color-accent-primary)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--color-glass-border)'
                e.currentTarget.style.color = 'var(--color-text-secondary)'
              }}
            >
              {isVideo ? (
                <>
                  <PlayIcon className="w-4 h-4" style={{ color: '#f87171' }} />
                  <span>Watch Full Review on YouTube</span>
                </>
              ) : (
                <>
                  <ExternalLinkIcon className="w-4 h-4" />
                  <span>Read Full Review</span>
                </>
              )}
            </a>
          </div>
        )}
      </motion.div>
    </motion.div>
  )
}

// Single reviewer card component
function ReviewerCardItem({ card, index, onClick }: { card: ReviewerCard; index: number; onClick: () => void }) {
  const isVideo = card.review_type === 'video'

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.1, ease: [0.16, 1, 0.3, 1] }}
      onClick={onClick}
      className="bg-[var(--color-bg-secondary)] border border-[var(--color-glass-border)] rounded-xl overflow-hidden hover:border-[var(--color-accent-primary)]/30 transition-all duration-300 group cursor-pointer"
    >
      {/* Header with reviewer name and badge */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-glass-border)] bg-[var(--color-bg-tertiary)]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--color-accent-tertiary)] to-[var(--color-accent-primary)] flex items-center justify-center text-[var(--color-bg-primary)] text-sm font-bold">
            {card.reviewer_name.charAt(0).toUpperCase()}
          </div>
          <div>
            <h4 className="text-sm font-semibold text-[var(--color-text-primary)]">
              {card.reviewer_name}
            </h4>
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              isVideo
                ? 'bg-[rgba(239,68,68,0.15)] text-red-400'
                : 'bg-[rgba(59,130,246,0.15)] text-blue-400'
            }`}>
              {isVideo ? 'YouTube' : 'Blog'}
            </span>
          </div>
        </div>
        {card.rating && (
          <div className="flex items-center gap-1 text-[var(--color-accent-primary)]">
            <span className="text-lg font-bold">{card.rating}</span>
            <span className="text-xs text-[var(--color-text-muted)]">/10</span>
          </div>
        )}
      </div>

      {/* Summary */}
      <div className="px-4 py-3">
        <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed line-clamp-3">
          {card.summary || 'No summary available'}
        </p>
      </div>

      {/* Footer row: source link + view details hint */}
      <div className="px-4 pb-3 flex items-center justify-between gap-2">
        {card.review_url && (
          <a
            href={card.review_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-2 px-3 py-2 bg-[var(--color-bg-tertiary)] border border-[var(--color-glass-border)] rounded-lg text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-accent-primary)] hover:border-[var(--color-accent-primary)]/30 transition-all duration-200 group-hover:bg-[var(--color-bg-primary)]"
          >
            {isVideo ? (
              <>
                <PlayIcon className="w-4 h-4 text-red-400" />
                <span>Watch Review</span>
              </>
            ) : (
              <>
                <ExternalLinkIcon className="w-4 h-4" />
                <span>Read Review</span>
              </>
            )}
          </a>
        )}
        <span className="inline-flex items-center gap-1 text-xs text-[var(--color-text-muted)] group-hover:text-[var(--color-accent-primary)] transition-colors duration-200">
          Details
          <ChevronRightIcon className="w-3.5 h-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
        </span>
      </div>
    </motion.div>
  )
}

// Reviewer cards grid component
function ReviewerCards({ cards }: { cards: ReviewerCard[]; productName?: string }) {
  const [selectedCard, setSelectedCard] = useState<ReviewerCard | null>(null)

  if (!cards || cards.length === 0) return null

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="mt-4"
      >
        <div className="flex items-center gap-2 mb-3">
          <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">
            Expert Reviews
          </h3>
          <span className="text-xs text-[var(--color-text-muted)]">
            ({cards.length} sources)
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {cards.map((card, index) => (
            <ReviewerCardItem
              key={`${card.reviewer_name}-${index}`}
              card={card}
              index={index}
              onClick={() => setSelectedCard(card)}
            />
          ))}
        </div>
      </motion.div>

      {/* Detail modal */}
      <AnimatePresence>
        {selectedCard && (
          <ReviewDetailModal
            card={selectedCard}
            onClose={() => setSelectedCard(null)}
          />
        )}
      </AnimatePresence>
    </>
  )
}

// Marketplace listing card component
function MarketplaceListingCard({ listing, index }: { listing: MarketplaceListing; index: number }) {
  const isAmazon = listing.marketplace === 'amazon'

  return (
    <motion.a
      href={listing.url}
      target="_blank"
      rel="noopener noreferrer"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.08, ease: [0.16, 1, 0.3, 1] }}
      className="group flex gap-4 p-4 rounded-xl border transition-all duration-200"
      style={{
        background: 'var(--color-bg-secondary)',
        borderColor: 'var(--color-glass-border)',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = 'rgba(245,158,11,0.3)'
        e.currentTarget.style.background = 'var(--color-bg-tertiary)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'var(--color-glass-border)'
        e.currentTarget.style.background = 'var(--color-bg-secondary)'
      }}
    >
      {/* Marketplace icon */}
      <div
        className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
        style={{
          background: isAmazon ? 'rgba(255, 153, 0, 0.1)' : 'rgba(86, 130, 245, 0.1)',
        }}
      >
        {isAmazon ? (
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none">
            <path d="M3 17.5C7.5 20.5 13.5 21 18 18.5M19.5 17L21 18.5L19 20" stroke="#FF9900" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M4 12.5C4 8.5 7.5 5 12 5C16.5 5 20 8.5 20 12.5" stroke="#FF9900" strokeWidth="2" strokeLinecap="round" />
          </svg>
        ) : (
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none">
            <rect x="3" y="6" width="18" height="13" rx="2" stroke="#5682F5" strokeWidth="2" />
            <path d="M7 10L10 14L14 10L17 14" stroke="#5682F5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <h4 className="text-sm font-semibold text-[var(--color-text-primary)] truncate">
            {listing.title || 'View Listing'}
          </h4>
          <span
            className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full flex-shrink-0"
            style={{
              background: isAmazon ? 'rgba(255, 153, 0, 0.12)' : 'rgba(86, 130, 245, 0.12)',
              color: isAmazon ? '#FF9900' : '#5682F5',
            }}
          >
            {isAmazon ? 'Amazon' : 'eBay'}
          </span>
        </div>

        {listing.description && (
          <p className="text-xs text-[var(--color-text-muted)] line-clamp-1 mb-1.5">
            {listing.description}
          </p>
        )}

        {listing.price && (
          <span className="text-base font-bold text-[var(--color-accent-primary)]">
            {listing.price}
          </span>
        )}

        <div className="flex items-center gap-1 mt-1.5 text-xs text-[var(--color-text-muted)] group-hover:text-[var(--color-accent-primary)] transition-colors">
          <span className="truncate" style={{ maxWidth: '280px' }}>{listing.url}</span>
          <ExternalLinkIcon className="w-3 h-3 flex-shrink-0" />
        </div>
      </div>
    </motion.a>
  )
}

// Marketplace cards grid component
function MarketplaceCards({ listings, productName }: { listings: MarketplaceListing[]; productName?: string }) {
  if (!listings || listings.length === 0) return null

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="mt-4"
    >
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">
          Where to Buy{productName ? ` ${productName}` : ''}
        </h3>
        <span className="text-xs text-[var(--color-text-muted)]">
          ({listings.length} {listings.length === 1 ? 'listing' : 'listings'})
        </span>
      </div>
      <div className="flex flex-col gap-2.5">
        {listings.map((listing, index) => (
          <MarketplaceListingCard
            key={`${listing.marketplace}-${index}`}
            listing={listing}
            index={index}
          />
        ))}
      </div>
    </motion.div>
  )
}

// Search icon for semantic search results
function SearchIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  )
}

// Semantic search results component
function SemanticSearchResults({ results, query, total }: { results: SemanticSearchResult[]; query: string; total: number }) {
  if (!results || results.length === 0) return null

  const getScoreColor = (score: number | null) => {
    if (score === null) return 'text-[var(--color-text-muted)]'
    if (score >= 0.8) return 'text-emerald-400'
    if (score >= 0.6) return 'text-amber-400'
    return 'text-[var(--color-text-muted)]'
  }

  const getScoreBg = (score: number | null) => {
    if (score === null) return 'rgba(255,255,255,0.05)'
    if (score >= 0.8) return 'rgba(52, 211, 153, 0.1)'
    if (score >= 0.6) return 'rgba(251, 191, 36, 0.1)'
    return 'rgba(255,255,255,0.05)'
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="mt-4"
    >
      <div className="flex items-center gap-2 mb-3">
        <SearchIcon className="w-4 h-4 text-[var(--color-accent-primary)]" />
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">
          Search Results
        </h3>
        <span className="text-xs text-[var(--color-text-muted)]">
          ({total} matches for "{query}")
        </span>
      </div>
      <div className="flex flex-col gap-2.5">
        {results.map((result, index) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: index * 0.06 }}
            className="p-4 rounded-xl border border-[var(--color-glass-border)] bg-[var(--color-bg-secondary)]"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-[var(--color-text-primary)]">
                  {result.product_name}
                </span>
                <span className="text-xs text-[var(--color-text-muted)]">
                  by {result.reviewer_name}
                </span>
              </div>
              {result.score !== null && (
                <span
                  className={`text-xs font-semibold px-2 py-0.5 rounded-full ${getScoreColor(result.score)}`}
                  style={{ background: getScoreBg(result.score) }}
                >
                  {Math.round(result.score * 100)}%
                </span>
              )}
            </div>
            <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed line-clamp-3">
              {result.content}
            </p>
            <div className="flex items-center gap-3 mt-2">
              {result.aspect && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-[rgba(245,158,11,0.1)] text-[var(--color-accent-primary)]">
                  {result.aspect}
                </span>
              )}
              {result.source_url && (
                <a
                  href={result.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-accent-primary)] transition-colors flex items-center gap-1"
                >
                  <ExternalLinkIcon className="w-3 h-3" />
                  Source
                </a>
              )}
            </div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  )
}

// Sentiment chart component — diverging butterfly chart per aspect
function SentimentChart({ aspects, productName }: { aspects: AspectSentiment[]; productName: string }) {
  if (!aspects || aspects.length === 0) return null

  const formatAspect = (aspect: string) =>
    aspect.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

  const getSentimentLabel = (sentiment: number) => {
    if (sentiment >= 0.5) return 'Very Positive'
    if (sentiment >= 0.2) return 'Positive'
    if (sentiment >= -0.2) return 'Mixed'
    if (sentiment >= -0.5) return 'Negative'
    return 'Very Negative'
  }

  const getAgreementColor = (score: number) => {
    if (score >= 0.8) return '#34d399'
    if (score >= 0.6) return '#fbbf24'
    return '#fb7185'
  }

  // Sort by positive_pct descending for visual impact
  const sorted = [...aspects].sort((a, b) => b.positive_pct - a.positive_pct)

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
      className="mt-4"
    >
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        <div className="flex items-center gap-2">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <rect x="1" y="3" width="5" height="10" rx="1.5" fill="#34d399" opacity="0.7" />
            <rect x="10" y="5" width="5" height="8" rx="1.5" fill="#fb7185" opacity="0.7" />
            <line x1="8" y1="1" x2="8" y2="15" stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
          </svg>
          <h3 className="text-sm font-semibold text-[var(--color-text-primary)]" style={{ letterSpacing: '-0.01em' }}>
            Sentiment Analysis
          </h3>
        </div>
        <span
          className="text-[11px] font-medium px-2 py-0.5 rounded-full"
          style={{
            background: 'rgba(245, 158, 11, 0.1)',
            color: 'var(--color-accent-primary)',
            border: '1px solid rgba(245, 158, 11, 0.15)',
          }}
        >
          {productName}
        </span>
      </div>

      {/* Chart Container */}
      <div
        className="rounded-xl overflow-hidden"
        style={{
          background: 'var(--color-bg-secondary)',
          border: '1px solid var(--color-glass-border)',
        }}
      >
        {/* Column headers */}
        <div
          className="flex items-center px-4 py-2.5"
          style={{
            borderBottom: '1px solid var(--color-glass-border)',
            background: 'var(--color-bg-tertiary)',
          }}
        >
          <div className="flex items-center justify-end" style={{ width: '35%', paddingRight: '12px' }}>
            <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: '#fb7185', opacity: 0.7 }}>
              Negative
            </span>
          </div>
          <div className="flex items-center justify-center" style={{ width: '30%' }}>
            <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
              Aspect
            </span>
          </div>
          <div className="flex items-center" style={{ width: '35%', paddingLeft: '12px' }}>
            <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: '#34d399', opacity: 0.7 }}>
              Positive
            </span>
          </div>
        </div>

        {/* Rows */}
        <div>
          {sorted.map((aspect, index) => {
            const agreementPct = Math.round(aspect.agreement_score * 100)
            const sentimentLabel = getSentimentLabel(aspect.average_sentiment)
            const isPositive = aspect.positive_pct >= aspect.negative_pct

            return (
              <motion.div
                key={aspect.aspect}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.4, delay: 0.15 + index * 0.06 }}
                className="flex items-center px-4"
                style={{
                  minHeight: '52px',
                  borderBottom: index < sorted.length - 1 ? '1px solid rgba(255,255,255,0.03)' : undefined,
                  background: index % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                }}
              >
                {/* Left side — negative bar (grows right-to-left) */}
                <div className="flex items-center justify-end" style={{ width: '35%', paddingRight: '12px', gap: '8px' }}>
                  <span
                    className="text-[11px] font-medium tabular-nums flex-shrink-0"
                    style={{
                      color: aspect.negative_pct > 0 ? '#fb7185' : 'var(--color-text-muted)',
                      opacity: aspect.negative_pct > 0 ? 1 : 0.4,
                      minWidth: '32px',
                      textAlign: 'right',
                    }}
                  >
                    {aspect.negative_pct > 0 ? `${aspect.negative_pct}%` : '—'}
                  </span>
                  <div
                    className="relative overflow-hidden rounded-l-sm"
                    style={{
                      width: '100%',
                      maxWidth: '140px',
                      height: '18px',
                      background: 'rgba(255,255,255,0.03)',
                      borderRadius: '3px 0 0 3px',
                    }}
                  >
                    <motion.div
                      className="absolute top-0 right-0 h-full"
                      style={{
                        background: 'linear-gradient(270deg, rgba(251,113,133,0.85), rgba(251,113,133,0.4))',
                        borderRadius: '3px 0 0 3px',
                      }}
                      initial={{ width: 0 }}
                      animate={{ width: `${aspect.negative_pct}%` }}
                      transition={{ duration: 0.7, delay: 0.2 + index * 0.06, ease: [0.16, 1, 0.3, 1] }}
                    />
                  </div>
                </div>

                {/* Center — aspect label */}
                <div
                  className="flex flex-col items-center justify-center flex-shrink-0"
                  style={{
                    width: '30%',
                    borderLeft: '1px solid rgba(255,255,255,0.06)',
                    borderRight: '1px solid rgba(255,255,255,0.06)',
                    padding: '6px 8px',
                  }}
                >
                  <span
                    className="text-[12px] font-semibold text-center leading-tight"
                    style={{
                      color: 'var(--color-text-primary)',
                      letterSpacing: '-0.01em',
                    }}
                  >
                    {formatAspect(aspect.aspect)}
                  </span>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span
                      className="text-[9px] font-medium"
                      style={{
                        color: isPositive ? '#34d399' : '#fb7185',
                        opacity: 0.8,
                      }}
                    >
                      {sentimentLabel}
                    </span>
                    <span className="text-[9px]" style={{ color: 'var(--color-text-muted)' }}>·</span>
                    <div className="flex items-center gap-1" title={`${agreementPct}% reviewer agreement`}>
                      {/* Agreement dots — 5 dots to visualize agreement level */}
                      <div className="flex gap-px">
                        {[...Array(5)].map((_, i) => (
                          <div
                            key={i}
                            style={{
                              width: '4px',
                              height: '4px',
                              borderRadius: '1px',
                              background: i < Math.round(aspect.agreement_score * 5)
                                ? getAgreementColor(aspect.agreement_score)
                                : 'rgba(255,255,255,0.08)',
                              transition: 'background 0.3s',
                            }}
                          />
                        ))}
                      </div>
                      <span className="text-[9px] tabular-nums" style={{ color: 'var(--color-text-muted)' }}>
                        {aspect.review_count}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Right side — positive bar (grows left-to-right) */}
                <div className="flex items-center" style={{ width: '35%', paddingLeft: '12px', gap: '8px' }}>
                  <div
                    className="relative overflow-hidden"
                    style={{
                      width: '100%',
                      maxWidth: '140px',
                      height: '18px',
                      background: 'rgba(255,255,255,0.03)',
                      borderRadius: '0 3px 3px 0',
                    }}
                  >
                    <motion.div
                      className="absolute top-0 left-0 h-full"
                      style={{
                        background: 'linear-gradient(90deg, rgba(52,211,153,0.85), rgba(52,211,153,0.4))',
                        borderRadius: '0 3px 3px 0',
                      }}
                      initial={{ width: 0 }}
                      animate={{ width: `${aspect.positive_pct}%` }}
                      transition={{ duration: 0.7, delay: 0.2 + index * 0.06, ease: [0.16, 1, 0.3, 1] }}
                    />
                  </div>
                  <span
                    className="text-[11px] font-medium tabular-nums flex-shrink-0"
                    style={{
                      color: aspect.positive_pct > 0 ? '#34d399' : 'var(--color-text-muted)',
                      opacity: aspect.positive_pct > 0 ? 1 : 0.4,
                      minWidth: '32px',
                    }}
                  >
                    {aspect.positive_pct > 0 ? `${aspect.positive_pct}%` : '—'}
                  </span>
                </div>
              </motion.div>
            )
          })}
        </div>

        {/* Footer legend */}
        <div
          className="flex items-center justify-between px-4 py-2"
          style={{
            borderTop: '1px solid var(--color-glass-border)',
            background: 'var(--color-bg-tertiary)',
          }}
        >
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <div style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#34d399', opacity: 0.7 }} />
              <span className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>Positive</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#fb7185', opacity: 0.7 }} />
              <span className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>Negative</span>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="flex gap-px">
              {[...Array(5)].map((_, i) => (
                <div
                  key={i}
                  style={{
                    width: '4px',
                    height: '4px',
                    borderRadius: '1px',
                    background: i < 4 ? '#fbbf24' : 'rgba(255,255,255,0.08)',
                  }}
                />
              ))}
            </div>
            <span className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>Agreement</span>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

// Comparison table component — duel-style racing bars with side-by-side scores
function ComparisonTable({ products, aspectsCompared, aspectWinners, recommendation }: {
  products: ComparisonProduct[]
  aspectsCompared: string[]
  aspectWinners: Record<string, { winner: string; score: number }>
  recommendation: string
}) {
  if (!products || products.length === 0 || !aspectsCompared || aspectsCompared.length === 0) return null

  const formatAspect = (aspect: string) =>
    aspect.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

  const getScoreColor = (score: number) => {
    if (score >= 0.5) return '#34d399'
    if (score >= 0.2) return '#6ee7b7'
    if (score >= -0.2) return '#fbbf24'
    if (score >= -0.5) return '#fb7185'
    return '#ef4444'
  }

  const getScorePct = (score: number) => Math.round((score + 1) * 50)

  // Assign each product a distinct color for its bars
  const productColors = ['#38bdf8', '#f59e0b'] // sky blue vs amber
  const productColorsFaded = ['rgba(56,189,248,0.15)', 'rgba(245,158,11,0.15)']

  // Count wins per product
  const winCounts: Record<string, number> = {}
  products.forEach(p => { winCounts[p.name] = 0 })
  Object.values(aspectWinners).forEach(w => {
    if (w?.winner && winCounts[w.winner] !== undefined) winCounts[w.winner]++
  })

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
      className="mt-4"
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M2 4h5v8H2V4z" fill="#38bdf8" opacity="0.6" rx="1" />
          <path d="M9 4h5v8H9V4z" fill="#f59e0b" opacity="0.6" rx="1" />
          <path d="M7 2v12" stroke="rgba(255,255,255,0.2)" strokeWidth="1" />
        </svg>
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)]" style={{ letterSpacing: '-0.01em' }}>
          Product Comparison
        </h3>
      </div>

      <div
        className="rounded-xl overflow-hidden"
        style={{
          background: 'var(--color-bg-secondary)',
          border: '1px solid var(--color-glass-border)',
        }}
      >
        {/* Product header row */}
        <div
          className="flex items-stretch"
          style={{
            borderBottom: '1px solid var(--color-glass-border)',
            background: 'var(--color-bg-tertiary)',
          }}
        >
          {products.map((product, pIdx) => (
            <div
              key={product.name}
              className="flex-1 flex items-center justify-center gap-3 py-3 px-4"
              style={{
                borderRight: pIdx < products.length - 1 ? '1px solid var(--color-glass-border)' : undefined,
              }}
            >
              <div
                className="flex-shrink-0"
                style={{
                  width: '10px',
                  height: '10px',
                  borderRadius: '3px',
                  background: productColors[pIdx] || '#888',
                  boxShadow: `0 0 8px ${productColors[pIdx] || '#888'}40`,
                }}
              />
              <div className="text-center">
                <div className="text-[13px] font-semibold text-[var(--color-text-primary)]" style={{ letterSpacing: '-0.01em' }}>
                  {product.name}
                </div>
                {product.brand && (
                  <div className="text-[10px] text-[var(--color-text-muted)]">{product.brand}</div>
                )}
              </div>
              <span
                className="text-[10px] font-semibold tabular-nums px-1.5 py-0.5 rounded"
                style={{
                  background: productColorsFaded[pIdx],
                  color: productColors[pIdx],
                }}
              >
                {winCounts[product.name] || 0}W
              </span>
            </div>
          ))}
        </div>

        {/* Aspect rows — racing bar style */}
        <div>
          {aspectsCompared.map((aspect, index) => {
            const winner = aspectWinners[aspect]
            const scores = products.map(p => p.aspects[aspect])
            const hasAnyData = scores.some(s => s !== undefined)

            if (!hasAnyData) return null

            return (
              <motion.div
                key={aspect}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.4, delay: 0.15 + index * 0.06 }}
                className="px-4"
                style={{
                  paddingTop: '10px',
                  paddingBottom: '10px',
                  borderBottom: index < aspectsCompared.length - 1 ? '1px solid rgba(255,255,255,0.03)' : undefined,
                  background: index % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                }}
              >
                {/* Aspect label */}
                <div className="flex items-center justify-between mb-2">
                  <span
                    className="text-[11px] font-semibold uppercase"
                    style={{ color: 'var(--color-text-tertiary)', letterSpacing: '0.04em' }}
                  >
                    {formatAspect(aspect)}
                  </span>
                  {winner && (
                    <span
                      className="text-[9px] font-semibold px-1.5 py-0.5 rounded"
                      style={{
                        background: 'rgba(245,158,11,0.1)',
                        color: 'var(--color-accent-primary)',
                        border: '1px solid rgba(245,158,11,0.15)',
                      }}
                    >
                      {winner.winner.split(' ').slice(-1)[0]}
                    </span>
                  )}
                </div>

                {/* Racing bars — one per product */}
                <div className="flex flex-col gap-1.5">
                  {products.map((product, pIdx) => {
                    const aspectData = product.aspects[aspect]
                    const pct = aspectData ? getScorePct(aspectData.sentiment_score) : 0
                    const isWinner = winner?.winner === product.name
                    const color = productColors[pIdx] || '#888'

                    return (
                      <div key={product.name} className="flex items-center gap-2">
                        {/* Product initial */}
                        <span
                          className="text-[10px] font-semibold flex-shrink-0 tabular-nums"
                          style={{
                            color: aspectData ? color : 'var(--color-text-muted)',
                            minWidth: '18px',
                            textAlign: 'right',
                            opacity: aspectData ? 1 : 0.4,
                          }}
                        >
                          {product.name.split(' ')[0].charAt(0)}{product.name.split(' ').length > 1 ? product.name.split(' ').slice(-1)[0].charAt(0) : ''}
                        </span>

                        {/* Bar track */}
                        <div
                          className="flex-1 relative overflow-hidden"
                          style={{
                            height: '14px',
                            background: 'rgba(255,255,255,0.03)',
                            borderRadius: '3px',
                          }}
                        >
                          {aspectData ? (
                            <motion.div
                              className="absolute top-0 left-0 h-full"
                              style={{
                                background: isWinner
                                  ? `linear-gradient(90deg, ${color}dd, ${color}88)`
                                  : `linear-gradient(90deg, ${color}88, ${color}44)`,
                                borderRadius: '3px',
                                boxShadow: isWinner ? `0 0 12px ${color}30` : undefined,
                              }}
                              initial={{ width: 0 }}
                              animate={{ width: `${pct}%` }}
                              transition={{ duration: 0.8, delay: 0.2 + index * 0.06, ease: [0.16, 1, 0.3, 1] }}
                            />
                          ) : (
                            <div
                              className="absolute inset-0 flex items-center justify-center"
                              style={{ color: 'var(--color-text-muted)', fontSize: '9px', letterSpacing: '0.05em' }}
                            >
                              No reviews
                            </div>
                          )}
                        </div>

                        {/* Score label */}
                        <span
                          className="text-[11px] font-semibold tabular-nums flex-shrink-0"
                          style={{
                            color: aspectData ? getScoreColor(aspectData.sentiment_score) : 'var(--color-text-muted)',
                            minWidth: '30px',
                            textAlign: 'right',
                            opacity: aspectData ? 1 : 0.3,
                          }}
                        >
                          {aspectData ? `${pct}%` : '—'}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </motion.div>
            )
          })}
        </div>

        {/* Verdict banner */}
        {recommendation && (
          <div
            className="px-4 py-3 flex items-start gap-3"
            style={{
              borderTop: '1px solid var(--color-glass-border)',
              background: 'linear-gradient(135deg, rgba(245,158,11,0.06) 0%, rgba(245,158,11,0.02) 100%)',
            }}
          >
            <svg
              width="16" height="16" viewBox="0 0 16 16" fill="none"
              className="flex-shrink-0 mt-0.5"
              style={{ color: 'var(--color-accent-primary)' }}
            >
              <path d="M8 1l2.1 4.3 4.7.7-3.4 3.3.8 4.7L8 11.8 3.8 14l.8-4.7L1.2 6l4.7-.7L8 1z" fill="currentColor" opacity="0.8" />
            </svg>
            <div>
              <span
                className="text-[10px] font-semibold uppercase"
                style={{ color: 'var(--color-accent-primary)', letterSpacing: '0.06em' }}
              >
                Verdict
              </span>
              <p className="text-[12px] leading-relaxed mt-0.5" style={{ color: 'var(--color-text-secondary)' }}>
                {recommendation}
              </p>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}

// Attachments renderer
function MessageAttachments({ attachments }: { attachments: Attachment[] }) {
  return (
    <>
      {attachments.map((attachment, index) => {
        if (attachment.type === 'reviewer_cards') {
          const data = attachment.data as { product_name: string; cards: ReviewerCard[] }
          return (
            <ReviewerCards
              key={`attachment-${index}`}
              cards={data.cards}
              productName={data.product_name}
            />
          )
        }
        if (attachment.type === 'marketplace_listings') {
          const data = attachment.data as { product_name: string; listings: MarketplaceListing[] }
          return (
            <MarketplaceCards
              key={`attachment-${index}`}
              listings={data.listings}
              productName={data.product_name}
            />
          )
        }
        if (attachment.type === 'semantic_search_results') {
          const data = attachment.data as { query: string; results: SemanticSearchResult[]; total: number; search_type: string }
          return (
            <SemanticSearchResults
              key={`attachment-${index}`}
              results={data.results}
              query={data.query}
              total={data.total}
            />
          )
        }
        if (attachment.type === 'sentiment_analysis') {
          const data = attachment.data as { product_name: string; aspects: AspectSentiment[] }
          return (
            <SentimentChart
              key={`attachment-${index}`}
              aspects={data.aspects}
              productName={data.product_name}
            />
          )
        }
        if (attachment.type === 'comparison_table') {
          const data = attachment.data as {
            products: ComparisonProduct[]
            aspects_compared: string[]
            aspect_winners: Record<string, { winner: string; score: number }>
            recommendation: string
          }
          return (
            <ComparisonTable
              key={`attachment-${index}`}
              products={data.products}
              aspectsCompared={data.aspects_compared}
              aspectWinners={data.aspect_winners}
              recommendation={data.recommendation}
            />
          )
        }
        return null
      })}
    </>
  )
}

// Message bubble component
function MessageBubble({ message, isTyping, progressSteps }: { message: ChatMessage; isTyping?: boolean; progressSteps?: ProgressStep[] }) {
  const isUser = message.role === 'user'
  const hasAttachments = !isUser && message.attachments && message.attachments.length > 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      style={{ marginBottom: '1.5rem' }}
      className={`flex gap-4 ${isUser ? 'justify-end' : 'items-start flex-col'}`}
    >
      <div className={`flex gap-4 ${isUser ? 'justify-end' : 'items-start'} w-full`}>
        {!isUser && <AIAvatar />}
        <div
          className={`relative ${hasAttachments ? 'max-w-full' : 'max-w-[75%]'} ${
            isUser
              ? 'bg-[var(--color-accent-primary)] text-[var(--color-bg-primary)] rounded-2xl rounded-br-sm px-5 py-3.5 font-medium shadow-lg shadow-[rgba(245,158,11,0.2)]'
              : 'bg-[var(--color-bg-tertiary)] border border-[var(--color-glass-border)] text-[var(--color-text-secondary)] rounded-2xl rounded-tl-sm px-5 py-4'
          }`}
        >
          {isTyping ? (
            <>
              <TypingIndicator />
              {progressSteps && progressSteps.length > 0 && (
                <ProgressSteps steps={progressSteps} />
              )}
            </>
          ) : (
            <div
              className="text-[15px] leading-relaxed [&_strong]:text-[var(--color-text-primary)] [&_strong]:font-semibold [&_ul]:mt-3 [&_ul]:space-y-1.5 [&_li]:flex [&_li]:items-start [&_li]:gap-2 [&_p]:mb-2 [&_p:last-child]:mb-0"
              dangerouslySetInnerHTML={{ __html: formatMarkdown(message.content) }}
            />
          )}
        </div>
      </div>

      {/* Render attachments (reviewer cards, etc.) */}
      {hasAttachments && (
        <div className="pl-13 w-full">
          <MessageAttachments attachments={message.attachments!} />
        </div>
      )}
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
  const { messages, sendMessage, clearChat, isLoading, progressSteps } = useChat()
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
    // Clear the ?q= search param so the initial query doesn't re-fire
    if (searchParams.has('q')) {
      navigate('/chat', { replace: true })
    }
    // Reset the ref so a fresh navigation with ?q= can work again
    initialQuerySentRef.current = false
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
            <div className="max-w-3xl mx-auto px-4 md:px-6 py-8 pb-16">
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
                    progressSteps={progressSteps}
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
            <div className="relative flex items-end gap-3 p-2 bg-[var(--color-bg-secondary)] border border-[var(--color-glass-border)] rounded-2xl transition-all duration-200">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about any tech product..."
                disabled={isLoading}
                rows={1}
                className="flex-1 px-4 py-3 bg-transparent text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] resize-none disabled:opacity-50 text-[15px] leading-relaxed"
                style={{ maxHeight: '200px', outline: 'none' }}
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
