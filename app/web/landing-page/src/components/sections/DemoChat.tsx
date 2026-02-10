import { useState, useEffect, useCallback, useRef } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { useInView } from '@/hooks'
import { ArrowRightIcon, HeadphonesIcon, SmartphoneIcon, LaptopIcon, SearchIcon } from '@/components/ui'

const suggestions = [
  {
    icon: <HeadphonesIcon className="w-3.5 h-3.5" />,
    label: 'Headphones',
    fullLabel: 'Best noise-canceling headphones under $400?',
    query: "What's the best noise-canceling headphones under $400?",
  },
  {
    icon: <SmartphoneIcon className="w-3.5 h-3.5" />,
    label: 'Compare',
    fullLabel: 'iPhone 15 Pro vs S24 Ultra camera?',
    query: 'Compare iPhone 15 Pro vs Samsung S24 Ultra camera',
  },
  {
    icon: <LaptopIcon className="w-3.5 h-3.5" />,
    label: 'Battery',
    fullLabel: 'MacBook Pro M3 Max battery life?',
    query: 'What do reviewers say about the MacBook Pro M3 Max battery life?',
  },
]

const floatingLabels = [
  { text: '[ REVIEWS ]', x: '8%', y: '18%', delay: 0 },
  { text: '[ YOUTUBE ]', x: '85%', y: '25%', delay: 1.2 },
  { text: '[ ANALYSIS ]', x: '5%', y: '72%', delay: 0.6 },
  { text: '[ BLOG ]', x: '88%', y: '68%', delay: 1.8 },
  { text: '[ 200 OK ]', x: '15%', y: '88%', delay: 2.4 },
  { text: '[ .JSON ]', x: '78%', y: '85%', delay: 0.3 },
]

/* -------------------------------------------------- */
/* Animated Dot-Grid (pure CSS + minimal React state)  */
/* -------------------------------------------------- */
function DotGrid() {
  return (
    <div className="demo-grid-bg" aria-hidden="true">
      {/* Grid lines */}
      <div className="demo-grid-lines" />
      {/* Dot intersections rendered via CSS radial-gradient — see index.css */}
      <div className="demo-grid-dots" />
    </div>
  )
}

/* -------------------------------------------------- */
/* Sparkle accent — the orange 4-point star in circle  */
/* -------------------------------------------------- */
function SparkleAccent({ x, y, size = 36, delay = 0 }: { x: string; y: string; size?: number; delay?: number }) {
  return (
    <motion.div
      className="demo-sparkle"
      style={{ left: x, top: y, width: size, height: size }}
      initial={{ opacity: 0, scale: 0.6 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.8, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      <svg viewBox="0 0 24 24" fill="none" width="14" height="14">
        <path
          d="M12 2l1.09 6.91L20 12l-6.91 1.09L12 20l-1.09-6.91L4 12l6.91-1.09L12 2z"
          fill="var(--color-accent-primary)"
        />
      </svg>
    </motion.div>
  )
}

/* -------------------------------------------------- */
/* Pixelated decorative block                          */
/* -------------------------------------------------- */
function PixelBlock({ x, y, delay = 0 }: { x: string; y: string; delay?: number }) {
  const pixels = [
    [1,1,0,1,1],
    [1,0,1,0,1],
    [0,1,1,1,0],
    [1,0,1,0,1],
    [1,1,0,1,1],
  ]
  return (
    <motion.div
      className="demo-pixel-block"
      style={{ left: x, top: y }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 0.25 }}
      transition={{ duration: 1.2, delay }}
    >
      {pixels.map((row, ri) => (
        <div key={ri} style={{ display: 'flex', gap: 2 }}>
          {row.map((on, ci) => (
            <div
              key={ci}
              style={{
                width: 5,
                height: 5,
                background: on ? 'rgba(255,255,255,0.7)' : 'transparent',
                borderRadius: 1,
              }}
            />
          ))}
        </div>
      ))}
    </motion.div>
  )
}

/* -------------------------------------------------- */
/* Typing placeholder effect                           */
/* -------------------------------------------------- */
const placeholders = [
  'Best noise-canceling headphones under $400?',
  'Compare iPhone 15 Pro vs Samsung S24 Ultra',
  'MacBook Pro M3 battery life reviews',
  'Is the Sony WH-1000XM5 worth it?',
]

function useTypingPlaceholder() {
  const [text, setText] = useState('')
  const [phraseIdx, setPhraseIdx] = useState(0)
  const [charIdx, setCharIdx] = useState(0)
  const [isDeleting, setIsDeleting] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  const tick = useCallback(() => {
    const phrase = placeholders[phraseIdx]
    if (!isDeleting) {
      setText(phrase.slice(0, charIdx + 1))
      if (charIdx + 1 === phrase.length) {
        timeoutRef.current = setTimeout(() => setIsDeleting(true), 2200)
        return
      }
      setCharIdx((c) => c + 1)
    } else {
      setText(phrase.slice(0, charIdx))
      if (charIdx === 0) {
        setIsDeleting(false)
        setPhraseIdx((p) => (p + 1) % placeholders.length)
        return
      }
      setCharIdx((c) => c - 1)
    }
  }, [charIdx, isDeleting, phraseIdx])

  useEffect(() => {
    const speed = isDeleting ? 30 : 55
    timeoutRef.current = setTimeout(tick, speed)
    return () => clearTimeout(timeoutRef.current)
  }, [tick, isDeleting])

  return text
}

/* ================================================== */
/*  MAIN COMPONENT                                     */
/* ================================================== */
export function DemoChat() {
  const { ref, isInView } = useInView<HTMLElement>()
  const [input, setInput] = useState('')
  const [activeSuggestion, setActiveSuggestion] = useState<number | null>(null)
  const navigate = useNavigate()
  const typingPlaceholder = useTypingPlaceholder()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return
    navigate(`/chat?q=${encodeURIComponent(input.trim())}`)
  }

  const handleSuggestionClick = (query: string, idx: number) => {
    setActiveSuggestion(idx)
    setTimeout(() => navigate(`/chat?q=${encodeURIComponent(query)}`), 180)
  }

  return (
    <section id="demo" ref={ref} className="demo-section">
      {/* ---- Animated background layer ---- */}
      <div className="demo-bg-layer" aria-hidden="true">
        <DotGrid />

        {/* Sparkle accents */}
        <SparkleAccent x="28%" y="22%" size={38} delay={0.4} />
        <SparkleAccent x="74%" y="20%" size={34} delay={1.0} />
        <SparkleAccent x="18%" y="62%" size={30} delay={1.6} />

        {/* Pixel blocks */}
        <PixelBlock x="10%" y="30%" delay={0.5} />
        <PixelBlock x="82%" y="55%" delay={1.1} />

        {/* Floating code labels */}
        {floatingLabels.map((label) => (
          <motion.span
            key={label.text}
            className="demo-float-label"
            style={{ left: label.x, top: label.y }}
            initial={{ opacity: 0 }}
            animate={isInView ? { opacity: 1 } : { opacity: 0 }}
            transition={{ duration: 0.8, delay: label.delay }}
          >
            {label.text}
          </motion.span>
        ))}

        {/* Radial glow behind input */}
        <div className="demo-center-glow" />
      </div>

      {/* ---- Content ---- */}
      <div className="section-container" style={{ position: 'relative', zIndex: 2 }}>
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="section-header mb-12"
        >
          <span className="badge-editorial mb-6">Try It</span>
          <h2 className="headline-editorial text-[clamp(2rem,4.5vw,3rem)] mb-5 text-[var(--color-text-primary)]">
            See ShopLens{' '}
            <span className="gradient-text italic">in action</span>
          </h2>
          <p className="text-base text-[var(--color-text-secondary)] leading-relaxed" style={{ maxWidth: 480, margin: '0 auto' }}>
            Experience how ShopLens transforms product research.
            <br className="hidden sm:block" />
            Try an example query or type your own.
          </p>
        </motion.div>

        {/* ---- Prominent Input Card ---- */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5, delay: 0.25, ease: [0.16, 1, 0.3, 1] }}
          className="demo-input-card"
        >
          <form onSubmit={handleSubmit} className="demo-input-form">
            {/* Search row */}
            <div className="demo-input-row">
              <SearchIcon className="demo-input-icon" />
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={typingPlaceholder + '\u200B'}
                className="demo-input-field"
              />
            </div>

            {/* Bottom bar: suggestions + send */}
            <div className="demo-input-bottom">
              <div className="demo-tab-row">
                {suggestions.map((s, i) => (
                  <button
                    key={s.query}
                    type="button"
                    onClick={() => handleSuggestionClick(s.query, i)}
                    className={`demo-tab${activeSuggestion === i ? ' demo-tab--active' : ''}`}
                  >
                    <span className="demo-tab-icon">{s.icon}</span>
                    <span className="hidden sm:inline">{s.fullLabel}</span>
                    <span className="sm:hidden">{s.label}</span>
                  </button>
                ))}
              </div>
              <button
                type="submit"
                disabled={!input.trim()}
                className="demo-send-btn"
                aria-label="Send query"
              >
                <ArrowRightIcon className="w-5 h-5" />
              </button>
            </div>
          </form>
        </motion.div>
      </div>
    </section>
  )
}
