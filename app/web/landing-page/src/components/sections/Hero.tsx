import { motion } from 'framer-motion'
import { useInView, useCounter } from '@/hooks'
import { Button, ArrowRightIcon, PlayIcon } from '@/components/ui'
import { HeroChatPreview } from './HeroChatPreview'

const stats = [
  { value: 50, suffix: 'K+', label: 'Reviews' },
  { value: 200, suffix: '+', label: 'Reviewers' },
  { value: 15, suffix: 'K+', label: 'Products' },
]

function StatItem({ value, suffix, label, index }: { value: number; suffix: string; label: string; index: number }) {
  const { ref, isInView } = useInView<HTMLDivElement>()
  const count = useCounter(value, 2000, isInView)

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 0.5 + index * 0.1, ease: [0.16, 1, 0.3, 1] }}
      className="stat-block"
    >
      <div className="flex items-baseline gap-1">
        <span className="stat-value tabular-nums">{count}</span>
        <span className="text-xl font-serif text-[var(--color-accent-primary)]">{suffix}</span>
      </div>
      <span className="stat-label">{label}</span>
    </motion.div>
  )
}

export function Hero() {
  const scrollToDemo = () => {
    const demo = document.querySelector('#demo')
    if (demo) {
      const offsetTop = demo.getBoundingClientRect().top + window.scrollY - 80
      window.scrollTo({ top: offsetTop, behavior: 'smooth' })
    }
  }

  return (
    <section className="hero-section">
      <div className="hero-container">
        {/* Main Grid */}
        <div className="hero-grid">
          {/* Content Column */}
          <div className="hero-content">
            {/* Editorial Badge */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
              className="badge-editorial mb-8"
            >
              <span className="w-1.5 h-1.5 bg-[var(--color-emerald)] rounded-full animate-pulse-dot" />
              <span>Powered by Gemini AI</span>
            </motion.div>

            {/* Headline */}
            <motion.h1
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
              className="headline-display text-[clamp(3rem,5.5vw,4.5rem)] mb-6"
            >
              <span className="block text-[var(--color-text-primary)]">Cut through</span>
              <span className="block gradient-text italic">the noise.</span>
            </motion.h1>

            {/* Subheadline */}
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
              className="text-lg leading-relaxed text-[var(--color-text-secondary)] mb-10 max-w-[480px]"
            >
              ShopLens aggregates reviews from YouTube and tech blogs, then uses AI to extract the insights that matter. Ask questions, compare products, make confident decisions.
            </motion.p>

            {/* Actions */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: 0.3 }}
              className="flex flex-wrap gap-4 mb-14"
            >
              <Button size="large" variant="primary" onClick={scrollToDemo}>
                <span>Try the Demo</span>
                <ArrowRightIcon className="w-4 h-4" />
              </Button>
              <Button size="large" variant="ghost">
                <PlayIcon className="w-4 h-4" />
                <span>Watch Demo</span>
              </Button>
            </motion.div>

            {/* Stats Row */}
            <div className="flex items-center gap-8 lg:gap-10">
              {stats.map((stat, index) => (
                <div key={stat.label} className="flex items-center gap-8 lg:gap-10">
                  <StatItem {...stat} index={index} />
                  {index < stats.length - 1 && (
                    <div className="divider-vertical hidden sm:block" />
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Visual Column */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
            className="hero-visual"
          >
            {/* Ambient Glow */}
            <div
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[400px] pointer-events-none"
              style={{
                background: 'radial-gradient(ellipse, rgba(245, 158, 11, 0.06) 0%, transparent 70%)',
              }}
            />

            <HeroChatPreview />

            {/* Floating Info Cards */}
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.6 }}
              className="absolute hidden xl:flex top-[15%] -left-4 items-center gap-3 px-4 py-3 bg-[var(--color-bg-secondary)] glass-border rounded-[var(--radius-lg)] shadow-[var(--shadow-md)] animate-float-subtle"
            >
              <div className="w-10 h-10 flex items-center justify-center rounded-[var(--radius-md)] bg-[rgba(45,212,191,0.1)] text-[var(--color-teal)]">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                </svg>
              </div>
              <div className="flex flex-col">
                <span className="text-sm font-semibold text-[var(--color-text-primary)]">Multi-Source</span>
                <span className="text-xs text-[var(--color-text-tertiary)]">YouTube + Blogs</span>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.7 }}
              className="absolute hidden xl:flex bottom-[20%] -right-4 items-center gap-3 px-4 py-3 bg-[var(--color-bg-secondary)] glass-border rounded-[var(--radius-lg)] shadow-[var(--shadow-md)] animate-float-subtle"
              style={{ animationDelay: '-2s' }}
            >
              <div className="w-10 h-10 flex items-center justify-center rounded-[var(--radius-md)] bg-[rgba(52,211,153,0.1)] text-[var(--color-emerald)]">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
                </svg>
              </div>
              <div className="flex flex-col">
                <span className="text-sm font-semibold text-[var(--color-text-primary)]">92% Positive</span>
                <span className="text-xs text-[var(--color-text-tertiary)]">Consensus</span>
              </div>
            </motion.div>
          </motion.div>
        </div>
      </div>

      {/* Scroll Indicator */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8 }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-3"
      >
        <span className="text-xs font-medium tracking-widest uppercase text-[var(--color-text-muted)]">
          Explore
        </span>
        <div className="w-5 h-8 rounded-full border border-[var(--color-glass-border)] flex justify-center pt-2">
          <div className="w-1 h-2 rounded-full bg-[var(--color-accent-primary)] animate-scroll-indicator" />
        </div>
      </motion.div>
    </section>
  )
}
