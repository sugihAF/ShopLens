import { motion } from 'framer-motion'
import { useInView } from '@/hooks'
import { cn } from '@/lib/utils'
import { MessageIcon, GridIcon, SearchPlusIcon, ChartIcon, YouTubeIcon, BookIcon } from '@/components/ui'

/* -------------------------------------------------- */
/* Conceptual visual mockups for each feature          */
/* -------------------------------------------------- */

function ConversationalAIVisual() {
  return (
    <div className="feat-visual-container">
      <div className="flex flex-col gap-3">
        <div className="self-end" style={{ maxWidth: '85%' }}>
          <div className="feat-bubble feat-bubble--user">
            "Is the battery life really that good?"
          </div>
        </div>
        <div className="self-start" style={{ maxWidth: '88%' }}>
          <div className="feat-bubble feat-bubble--ai">
            <span className="text-[var(--color-text-primary)] font-medium">Based on 47 reviews,</span>{' '}
            battery life averages 12.5 hours. MKBHD noted it "easily lasts a full workday" while The Verge measured 11.8 hours in their standardized test...
          </div>
        </div>
        <div className="self-start" style={{ maxWidth: '60%' }}>
          <div className="feat-bubble feat-bubble--ai" style={{ opacity: 0.5 }}>
            <div className="flex gap-1.5 items-center">
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--color-accent-primary)] animate-pulse-dot" />
              <span className="text-xs text-[var(--color-text-muted)]">Analyzing 3 more sources...</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ComparisonVisual() {
  const products = [
    { name: 'iPhone 15 Pro', scores: { camera: 94, battery: 78, display: 91 } },
    { name: 'Galaxy S24 Ultra', scores: { camera: 92, battery: 88, display: 93 } },
  ]
  return (
    <div className="feat-visual-container">
      <div className="flex gap-3">
        {products.map((p) => (
          <div key={p.name} className="flex-1 feat-mini-card">
            <div className="text-xs font-semibold text-[var(--color-text-primary)] mb-3">{p.name}</div>
            {Object.entries(p.scores).map(([key, val]) => (
              <div key={key} className="mb-2.5">
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-[var(--color-text-muted)] capitalize">{key}</span>
                  <span className="text-[var(--color-text-secondary)] tabular-nums">{val}%</span>
                </div>
                <div className="h-1 rounded-full bg-[var(--color-bg-primary)]">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${val}%`,
                      background: val >= 90
                        ? 'var(--color-emerald)'
                        : val >= 80
                          ? 'var(--color-accent-primary)'
                          : 'var(--color-sky)',
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

function SemanticSearchVisual() {
  const results = [
    { label: 'Sony WH-1000XM5', score: 0.96, tag: 'Best Match' },
    { label: 'Bose QC Ultra', score: 0.91 },
    { label: 'AirPods Max', score: 0.84 },
  ]
  return (
    <div className="feat-visual-container">
      <div className="feat-mini-card mb-3">
        <div className="flex items-center gap-2">
          <SearchPlusIcon className="w-3.5 h-3.5 text-[var(--color-text-muted)]" />
          <span className="text-xs text-[var(--color-text-muted)]">comfortable headphones for long flights</span>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        {results.map((r) => (
          <div key={r.label} className="feat-mini-card flex items-center justify-between">
            <span className="text-xs text-[var(--color-text-primary)]">{r.label}</span>
            <div className="flex items-center gap-2">
              {r.tag && (
                <span className="text-[0.6rem] px-1.5 py-0.5 rounded-full bg-[rgba(245,158,11,0.15)] text-[var(--color-accent-primary)] font-medium">
                  {r.tag}
                </span>
              )}
              <span className="text-xs tabular-nums text-[var(--color-text-muted)]">{r.score}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function SentimentVisual() {
  const categories = [
    { label: 'Battery', positive: 82, negative: 18 },
    { label: 'Camera', positive: 91, negative: 9 },
    { label: 'Display', positive: 88, negative: 12 },
    { label: 'Price', positive: 45, negative: 55 },
  ]
  return (
    <div className="feat-visual-container">
      <div className="flex flex-col gap-3">
        {categories.map((c) => (
          <div key={c.label}>
            <div className="flex justify-between text-xs mb-1.5">
              <span className="text-[var(--color-text-secondary)]">{c.label}</span>
              <div className="flex gap-3">
                <span className="text-[var(--color-emerald)] tabular-nums text-[0.7rem]">+{c.positive}%</span>
                <span className="text-[var(--color-rose)] tabular-nums text-[0.7rem]">-{c.negative}%</span>
              </div>
            </div>
            <div className="flex h-1.5 rounded-full overflow-hidden bg-[var(--color-bg-primary)]">
              <div
                className="h-full"
                style={{ width: `${c.positive}%`, background: 'var(--color-emerald)' }}
              />
              <div
                className="h-full"
                style={{ width: `${c.negative}%`, background: 'var(--color-rose)', opacity: 0.6 }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function YouTubeVisual() {
  const channels = [
    { name: 'MKBHD', subscribers: '19M', verdict: 'Recommended' },
    { name: 'Dave2D', subscribers: '4.2M', verdict: 'Mixed' },
    { name: 'Linus Tech Tips', subscribers: '16M', verdict: 'Recommended' },
  ]
  return (
    <div className="feat-visual-container">
      <div className="flex flex-col gap-2">
        {channels.map((ch) => (
          <div key={ch.name} className="feat-mini-card flex items-center gap-3">
            <div className="w-7 h-7 rounded-full bg-[rgba(251,113,133,0.12)] flex items-center justify-center flex-shrink-0">
              <YouTubeIcon className="w-3.5 h-3.5 text-[var(--color-rose)]" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-[var(--color-text-primary)]">{ch.name}</div>
              <div className="text-[0.65rem] text-[var(--color-text-muted)]">{ch.subscribers} subs</div>
            </div>
            <span
              className={cn(
                'text-[0.6rem] px-1.5 py-0.5 rounded-full font-medium',
                ch.verdict === 'Recommended'
                  ? 'bg-[rgba(52,211,153,0.12)] text-[var(--color-emerald)]'
                  : 'bg-[rgba(245,158,11,0.12)] text-[var(--color-accent-primary)]'
              )}
            >
              {ch.verdict}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function BlogVisual() {
  const sources = [
    { name: 'The Verge', type: 'Full Review', status: 'Analyzed' },
    { name: 'Tom\'s Guide', type: 'Comparison', status: 'Analyzed' },
    { name: 'Wired', type: 'First Look', status: 'Processing' },
  ]
  return (
    <div className="feat-visual-container">
      <div className="flex flex-col gap-2">
        {sources.map((s) => (
          <div key={s.name} className="feat-mini-card flex items-center gap-3">
            <div className="w-7 h-7 rounded-[var(--radius-sm)] bg-[rgba(245,158,11,0.1)] flex items-center justify-center flex-shrink-0">
              <BookIcon className="w-3.5 h-3.5 text-[var(--color-accent-primary)]" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-[var(--color-text-primary)]">{s.name}</div>
              <div className="text-[0.65rem] text-[var(--color-text-muted)]">{s.type}</div>
            </div>
            <span
              className={cn(
                'text-[0.6rem] px-1.5 py-0.5 rounded-full font-medium',
                s.status === 'Analyzed'
                  ? 'bg-[rgba(52,211,153,0.12)] text-[var(--color-emerald)]'
                  : 'bg-[rgba(56,189,248,0.12)] text-[var(--color-sky)]'
              )}
            >
              {s.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

/* -------------------------------------------------- */
/* Feature data                                        */
/* -------------------------------------------------- */

const features = [
  {
    icon: <MessageIcon className="w-4 h-4" />,
    category: 'Conversational AI',
    headline: 'Natural language queries.',
    description: 'Ask anything about tech products and get nuanced answers based on aggregated reviewer opinions with full context awareness.',
    visual: <ConversationalAIVisual />,
    span: 'full' as const,
  },
  {
    icon: <GridIcon className="w-4 h-4" />,
    category: 'Product Comparison',
    headline: 'Side-by-side insights.',
    description: 'Compare products with AI-generated analysis highlighting key differences and reviewer preferences across every dimension.',
    visual: <ComparisonVisual />,
  },
  {
    icon: <SearchPlusIcon className="w-4 h-4" />,
    category: 'Semantic Search',
    headline: 'Search by meaning.',
    description: 'Find products that match your exact needs using vector-powered similarity search, not just keywords.',
    visual: <SemanticSearchVisual />,
  },
  {
    icon: <ChartIcon className="w-4 h-4" />,
    category: 'Sentiment Analysis',
    headline: 'Opinion at a glance.',
    description: 'See what reviewers love and hate instantly. AI extracts and categorizes opinions across all sources.',
    visual: <SentimentVisual />,
  },
  {
    icon: <YouTubeIcon className="w-4 h-4" />,
    category: 'YouTube Integration',
    headline: 'Video reviews, decoded.',
    description: 'Automatically ingests and analyzes reviews from top tech YouTubers. Transcripts processed for key insights.',
    visual: <YouTubeVisual />,
  },
  {
    icon: <BookIcon className="w-4 h-4" />,
    category: 'Blog Aggregation',
    headline: 'Written reviews, unified.',
    description: 'Scrapes and analyzes written reviews from trusted tech publications for comprehensive coverage.',
    visual: <BlogVisual />,
  },
]

/* -------------------------------------------------- */
/* Feature Card                                        */
/* -------------------------------------------------- */

function FeatureCard({
  icon,
  category,
  headline,
  description,
  visual,
  span,
  index,
}: {
  icon: React.ReactNode
  category: string
  headline: string
  description: string
  visual: React.ReactNode
  span?: 'full'
  index: number
}) {
  const { ref, isInView } = useInView<HTMLDivElement>()

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 28 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.55, delay: index * 0.07, ease: [0.16, 1, 0.3, 1] }}
      className={cn('feat-card group', span === 'full' && 'feat-card--full')}
    >
      {/* Hover accent */}
      <div className="feat-card-accent" />

      {/* Content area */}
      <div className={cn('feat-card-content', span === 'full' && 'feat-card-content--full')}>
        {/* Category label */}
        <div className="feat-category">
          <span className="feat-category-icon">{icon}</span>
          <span>{category}</span>
        </div>

        {/* Headline + description (Firecrawl style) */}
        <p className="feat-description">
          <strong className="feat-headline">{headline}</strong>{' '}
          <span className="feat-desc-text">{description}</span>
        </p>
      </div>

      {/* Visual area */}
      <div className={cn('feat-card-visual', span === 'full' && 'feat-card-visual--full')}>
        {visual}
      </div>
    </motion.div>
  )
}

/* -------------------------------------------------- */
/* Features Section                                    */
/* -------------------------------------------------- */

export function Features() {
  const { ref, isInView } = useInView<HTMLElement>()

  return (
    <section id="features" ref={ref} className="feat-section">
      <div className="section-container">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="section-header"
        >
          <span className="badge-editorial mb-6">Features</span>
          <h2 className="headline-editorial text-[clamp(2rem,4vw,2.75rem)] mb-5 text-[var(--color-text-primary)]">
            Everything you need to{' '}
            <span className="gradient-text italic">shop smarter</span>
          </h2>
          <p className="text-base text-[var(--color-text-secondary)] leading-relaxed">
            ShopLens combines multiple data sources with advanced AI to give you the most comprehensive product intelligence available.
          </p>
        </motion.div>

        {/* Feature grid */}
        <div className="feat-grid">
          {features.map((feature, index) => (
            <FeatureCard key={feature.category} {...feature} index={index} />
          ))}
        </div>
      </div>
    </section>
  )
}
