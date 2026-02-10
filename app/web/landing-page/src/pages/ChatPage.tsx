import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useChat } from '@/hooks'
import { formatMarkdown } from '@/lib/utils'
import { LogoIcon, SendIcon } from '@/components/ui'
import type { ChatMessage, ReviewerCard, MarketplaceListing, Attachment, ProgressStep } from '@/types'

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
