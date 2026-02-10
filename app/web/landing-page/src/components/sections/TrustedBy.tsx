import { motion } from 'framer-motion'
import { useInView } from '@/hooks'

const reviewers = [
  'MKBHD',
  'Linus Tech Tips',
  'Dave2D',
  'The Verge',
  "Tom's Guide",
  'RTINGS',
]

export function TrustedBy() {
  const { ref, isInView } = useInView<HTMLElement>()

  return (
    <section
      ref={ref}
      className="py-14 border-y border-[var(--color-glass-border)] bg-[var(--color-bg-secondary)]"
    >
      <div className="section-container">
        <p className="text-center text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-widest mb-8">
          Aggregating reviews from trusted sources
        </p>
        <div className="flex justify-center items-center flex-wrap gap-x-10 gap-y-6">
          {reviewers.map((name, index) => (
            <motion.div
              key={name}
              initial={{ opacity: 0, y: 16 }}
              animate={isInView ? { opacity: 0.4, y: 0 } : {}}
              transition={{ duration: 0.4, delay: index * 0.08 }}
              whileHover={{ opacity: 1 }}
              className="transition-opacity duration-300"
            >
              <span className="text-lg font-semibold text-[var(--color-text-secondary)] tracking-tight">
                {name}
              </span>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
