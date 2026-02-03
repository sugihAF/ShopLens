import { motion } from 'framer-motion'
import { useInView } from '@/hooks'
import { YouTubeIcon, BookIcon, RssIcon, ChevronDownIcon } from '@/components/ui'

const steps = [
  {
    number: '01',
    title: 'Aggregate',
    description:
      'We continuously scrape and ingest reviews from YouTube channels, tech blogs, and publications. Every review is transcribed, parsed, and stored.',
    visual: (
      <div className="flex gap-3">
        {[
          { icon: <YouTubeIcon className="w-5 h-5" />, color: 'text-[var(--color-rose)]', bg: 'bg-[rgba(251,113,133,0.1)]' },
          { icon: <BookIcon className="w-5 h-5" />, color: 'text-[var(--color-teal)]', bg: 'bg-[rgba(45,212,191,0.1)]' },
          { icon: <RssIcon className="w-5 h-5" />, color: 'text-[var(--color-accent-primary)]', bg: 'bg-[rgba(245,158,11,0.1)]' },
        ].map((item, i) => (
          <motion.div
            key={i}
            whileHover={{ y: -3, scale: 1.05 }}
            transition={{ duration: 0.2 }}
            className={`w-11 h-11 flex items-center justify-center border border-[var(--color-glass-border)] rounded-[var(--radius-md)] ${item.color} ${item.bg}`}
          >
            {item.icon}
          </motion.div>
        ))}
      </div>
    ),
  },
  {
    number: '02',
    title: 'Analyze',
    description:
      'Our AI processes each review to extract specific opinions, pros/cons, and ratings. Content is embedded into vectors for semantic search capabilities.',
    visual: (
      <div className="flex flex-col gap-2.5 min-w-[180px]">
        {[
          { label: 'Sentiment', width: '78%', color: 'bg-[var(--color-emerald)]' },
          { label: 'Relevance', width: '92%', color: 'bg-[var(--color-accent-primary)]' },
          { label: 'Confidence', width: '85%', color: 'bg-[var(--color-teal)]' },
        ].map((bar) => (
          <div key={bar.label} className="flex items-center gap-3">
            <span className="text-[10px] font-medium tracking-wider uppercase text-[var(--color-text-muted)] min-w-[70px]">
              {bar.label}
            </span>
            <div className="flex-1 h-1.5 bg-[var(--color-bg-elevated)] rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                whileInView={{ width: bar.width }}
                transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                viewport={{ once: true }}
                className={`h-full rounded-full ${bar.color}`}
              />
            </div>
          </div>
        ))}
      </div>
    ),
  },
  {
    number: '03',
    title: 'Synthesize',
    description:
      'When you ask a question, Gemini AI synthesizes insights from all relevant reviews, citing specific reviewers and providing balanced, nuanced answers.',
    visual: (
      <div className="flex flex-col items-center gap-3">
        <div className="flex gap-2 flex-wrap justify-center">
          {['@MKBHD', '@Dave2D', 'The Verge'].map((tag) => (
            <span
              key={tag}
              className="px-3 py-1.5 bg-[var(--color-bg-elevated)] border border-[var(--color-glass-border)] rounded-full text-xs font-medium text-[var(--color-text-secondary)]"
            >
              {tag}
            </span>
          ))}
        </div>
        <motion.div
          animate={{ y: [0, 3, 0] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
          className="text-[var(--color-accent-primary)]"
        >
          <ChevronDownIcon className="w-5 h-5" />
        </motion.div>
        <div className="px-5 py-2 bg-[var(--color-accent-primary)] rounded-full text-xs font-semibold text-[var(--color-bg-primary)]">
          Unified Insight
        </div>
      </div>
    ),
  },
]

export function HowItWorks() {
  const { ref, isInView } = useInView<HTMLElement>()

  return (
    <section id="how-it-works" ref={ref} className="py-24 bg-[var(--color-bg-secondary)]">
      <div className="section-container">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="section-header"
        >
          <span className="badge-editorial mb-6">How It Works</span>
          <h2 className="headline-editorial text-[clamp(2rem,4vw,2.75rem)] mb-5 text-[var(--color-text-primary)]">
            From chaos to{' '}
            <span className="gradient-text italic">clarity</span>
          </h2>
          <p className="text-base text-[var(--color-text-secondary)] leading-relaxed">
            ShopLens processes thousands of reviews so you don't have to. Here's how we turn information overload into actionable insights.
          </p>
        </motion.div>

        {/* Steps */}
        <div className="steps-container">
          {steps.map((step, index) => (
            <motion.div
              key={step.number}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: index * 0.1, ease: [0.16, 1, 0.3, 1] }}
              viewport={{ once: true }}
              className="step-card group card-hover"
            >
              {/* Step Number */}
              <div className="step-number">
                {step.number}
              </div>

              {/* Content */}
              <div className="step-content">
                <h3 className="text-xl font-semibold mb-2 text-[var(--color-text-primary)]">{step.title}</h3>
                <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">{step.description}</p>
              </div>

              {/* Visual */}
              <div className="step-visual">{step.visual}</div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
