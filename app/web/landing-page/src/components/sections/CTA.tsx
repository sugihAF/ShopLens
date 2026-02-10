import { motion } from 'framer-motion'
import { useInView } from '@/hooks'
import { Button, ArrowRightIcon } from '@/components/ui'

export function CTA() {
  const { ref, isInView } = useInView<HTMLElement>()

  return (
    <section ref={ref} className="py-24">
      <div className="section-container">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="relative text-center py-16 px-8 bg-[var(--color-bg-secondary)] border border-[var(--color-glass-border)] rounded-[var(--radius-2xl)] overflow-hidden"
        >
          {/* Ambient glow */}
          <div
            className="absolute top-0 left-1/2 -translate-x-1/2 w-[500px] h-[300px] pointer-events-none"
            style={{
              background: 'radial-gradient(ellipse, rgba(245, 158, 11, 0.1) 0%, transparent 70%)',
            }}
          />

          {/* Decorative lines */}
          <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[var(--color-accent-primary)]/20 to-transparent" />

          <h2 className="relative headline-editorial text-[clamp(2rem,4vw,2.75rem)] mb-5 text-[var(--color-text-primary)]">
            Ready to shop{' '}
            <span className="gradient-text italic">smarter?</span>
          </h2>
          <p className="relative text-base text-[var(--color-text-secondary)] max-w-[440px] mx-auto mb-8 leading-relaxed">
            Join thousands of users who make better purchasing decisions with ShopLens. Start your free trial today.
          </p>
          <div className="relative">
            <Button size="large" variant="primary">
              <span>Get Started Free</span>
              <ArrowRightIcon className="w-4 h-4" />
            </Button>
            <p className="mt-4 text-xs text-[var(--color-text-muted)]">No credit card required</p>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
