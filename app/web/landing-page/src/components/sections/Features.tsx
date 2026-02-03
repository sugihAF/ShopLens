import { motion } from 'framer-motion'
import { useInView } from '@/hooks'
import { cn } from '@/lib/utils'
import { MessageIcon, GridIcon, SearchPlusIcon, ChartIcon, YouTubeIcon, BookIcon } from '@/components/ui'

const features = [
  {
    icon: <MessageIcon className="w-6 h-6" />,
    title: 'Conversational AI',
    description:
      'Ask questions in natural language. Our AI understands context, remembers your preferences, and provides nuanced answers based on aggregated reviewer opinions.',
    iconColor: 'amber' as const,
    large: true,
    visual: (
      <div className="bg-[var(--color-bg-tertiary)] border border-[var(--color-glass-border)] rounded-[var(--radius-lg)] p-5">
        <div className="flex flex-col gap-3">
          <div className="self-end bg-[var(--color-accent-primary)] text-[var(--color-bg-primary)] rounded-[var(--radius-lg)] rounded-br-[var(--radius-xs)] px-4 py-2.5 text-sm font-medium max-w-[90%]">
            "Is the battery life really that good?"
          </div>
          <div className="self-start bg-[var(--color-bg-secondary)] border border-[var(--color-glass-border)] rounded-[var(--radius-xs)] rounded-tl-[var(--radius-lg)] rounded-tr-[var(--radius-lg)] rounded-br-[var(--radius-lg)] px-4 py-2.5 text-sm text-[var(--color-text-secondary)] max-w-[90%] leading-relaxed">
            Based on 47 reviews, battery life averages 12.5 hours. MKBHD noted it "easily lasts a full workday"...
          </div>
        </div>
      </div>
    ),
  },
  {
    icon: <GridIcon className="w-6 h-6" />,
    title: 'Product Comparison',
    description:
      'Compare products side-by-side with AI-generated insights highlighting key differences and reviewer preferences.',
    iconColor: 'teal' as const,
  },
  {
    icon: <SearchPlusIcon className="w-6 h-6" />,
    title: 'Semantic Search',
    description:
      'Search by meaning, not just keywords. Find products that match your exact needs using vector-powered similarity search.',
    iconColor: 'sky' as const,
  },
  {
    icon: <ChartIcon className="w-6 h-6" />,
    title: 'Sentiment Analysis',
    description:
      'See at a glance what reviewers love and hate. Our AI extracts and categorizes opinions across all sources.',
    iconColor: 'rose' as const,
  },
  {
    icon: <YouTubeIcon className="w-6 h-6" />,
    title: 'YouTube Integration',
    description:
      'Automatically ingests and analyzes reviews from top tech YouTubers. Transcripts are processed for key insights.',
    iconColor: 'emerald' as const,
  },
  {
    icon: <BookIcon className="w-6 h-6" />,
    title: 'Blog Aggregation',
    description:
      'Scrapes and analyzes written reviews from trusted tech publications for comprehensive coverage.',
    iconColor: 'amber' as const,
  },
]

const iconColorClasses = {
  amber: 'bg-[rgba(245,158,11,0.1)] text-[var(--color-accent-primary)]',
  teal: 'bg-[rgba(45,212,191,0.1)] text-[var(--color-teal)]',
  sky: 'bg-[rgba(56,189,248,0.1)] text-[var(--color-sky)]',
  rose: 'bg-[rgba(251,113,133,0.1)] text-[var(--color-rose)]',
  emerald: 'bg-[rgba(52,211,153,0.1)] text-[var(--color-emerald)]',
}

function FeatureCard({
  icon,
  title,
  description,
  iconColor,
  large,
  visual,
  delay,
}: {
  icon: React.ReactNode
  title: string
  description: string
  iconColor: keyof typeof iconColorClasses
  large?: boolean
  visual?: React.ReactNode
  delay: number
}) {
  const { ref, isInView } = useInView<HTMLDivElement>()

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 24 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.5, delay: delay * 0.08, ease: [0.16, 1, 0.3, 1] }}
      className={cn(
        'feature-card group relative bg-[var(--color-bg-secondary)] border border-[var(--color-glass-border)] rounded-[var(--radius-xl)] p-7 card-hover overflow-hidden',
        large && 'feature-card-large'
      )}
    >
      {/* Hover accent line */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[var(--color-accent-primary)] to-transparent opacity-0 transition-opacity duration-400 group-hover:opacity-100" />

      <div>
        <div className="mb-5">
          <div
            className={cn(
              'feature-icon w-12 h-12 flex items-center justify-center rounded-[var(--radius-md)] transition-all duration-300 ease-[var(--ease-spring)] group-hover:scale-105',
              iconColorClasses[iconColor]
            )}
          >
            {icon}
          </div>
        </div>
        <h3 className="text-lg font-semibold mb-2 text-[var(--color-text-primary)]">{title}</h3>
        <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">{description}</p>
      </div>

      {visual && <div>{visual}</div>}
    </motion.div>
  )
}

export function Features() {
  const { ref, isInView } = useInView<HTMLElement>()

  return (
    <section id="features" ref={ref} className="py-24">
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

        {/* Grid */}
        <div className="features-grid">
          {features.map((feature, index) => (
            <FeatureCard key={feature.title} {...feature} delay={index} />
          ))}
        </div>
      </div>
    </section>
  )
}
