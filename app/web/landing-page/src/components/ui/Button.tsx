import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'glass'
  size?: 'default' | 'large'
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'default', children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          'inline-flex items-center justify-center gap-2 font-semibold rounded-[var(--radius-md)] transition-all duration-300 ease-[var(--ease-out-expo)] whitespace-nowrap cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed',
          // Size variants
          size === 'default' && 'px-4 py-2.5 text-sm',
          size === 'large' && 'px-6 py-3 text-sm',
          // Style variants
          variant === 'primary' &&
            'bg-[var(--color-accent-primary)] text-[var(--color-bg-primary)] font-semibold shadow-[0_1px_2px_rgba(0,0,0,0.2),0_0_0_1px_rgba(217,119,6,0.5)] hover:bg-[var(--color-accent-secondary)] hover:translate-y-[-1px] hover:shadow-[0_4px_12px_rgba(245,158,11,0.25),0_0_0_1px_rgba(217,119,6,0.6)] active:translate-y-0 active:shadow-[0_1px_2px_rgba(0,0,0,0.2)]',
          variant === 'secondary' &&
            'bg-[var(--color-bg-tertiary)] text-[var(--color-text-primary)] border border-[var(--color-glass-border)] hover:bg-[var(--color-bg-elevated)] hover:border-[var(--color-text-muted)] hover:translate-y-[-1px]',
          variant === 'ghost' &&
            'bg-transparent text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-glass-bg)]',
          variant === 'glass' &&
            'bg-[var(--color-glass-bg)] text-[var(--color-text-primary)] border border-[var(--color-glass-border)] backdrop-blur-xl hover:bg-[var(--color-glass-hover)] hover:border-[var(--color-text-muted)]/20 hover:translate-y-[-1px]',
          className
        )}
        {...props}
      >
        {children}
      </button>
    )
  }
)

Button.displayName = 'Button'
