import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useScrolled } from '@/hooks'
import { Button, LogoIcon, ArrowRightIcon, MenuIcon, CloseIcon } from '@/components/ui'
import { cn } from '@/lib/utils'

const navLinks = [
  { href: '#demo', label: 'Demo' },
  { href: '#features', label: 'Features' },
  { href: '#how-it-works', label: 'How it Works' },
]

export function Navigation() {
  const isScrolled = useScrolled(50)
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

  const handleLinkClick = (href: string) => {
    setIsMobileMenuOpen(false)
    const target = document.querySelector(href)
    if (target) {
      const offsetTop = target.getBoundingClientRect().top + window.scrollY - 64
      window.scrollTo({ top: offsetTop, behavior: 'smooth' })
    }
  }

  return (
    <>
      <nav
        className={cn(
          'fixed top-0 left-0 right-0 z-50 transition-all duration-500 ease-[var(--ease-out-expo)]',
          isScrolled
            ? 'py-3 bg-[var(--color-bg-primary)]/90 backdrop-blur-xl border-b border-[var(--color-glass-border)]'
            : 'py-5'
        )}
      >
        <div className="nav-container">
          {/* Logo */}
          <a href="#" className="flex items-center gap-2.5 group">
            <LogoIcon className="w-9 h-9 transition-transform duration-500 ease-[var(--ease-spring)] group-hover:rotate-[360deg]" />
            <span className="text-lg font-semibold tracking-tight">ShopLens</span>
          </a>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => (
              <button
                key={link.href}
                onClick={() => handleLinkClick(link.href)}
                className="relative px-4 py-2 text-sm font-medium text-[var(--color-text-secondary)] transition-colors duration-300 hover:text-[var(--color-text-primary)] group"
              >
                {link.label}
                <span className="absolute bottom-1 left-4 right-4 h-px bg-[var(--color-accent-primary)] scale-x-0 transition-transform duration-300 ease-[var(--ease-out-expo)] origin-left group-hover:scale-x-100" />
              </button>
            ))}
          </div>

          {/* Desktop Actions */}
          <div className="hidden md:flex items-center gap-3">
            <Button variant="ghost" size="default">Log In</Button>
            <Button variant="primary" size="default">
              <span>Get Started</span>
              <ArrowRightIcon className="w-3.5 h-3.5" />
            </Button>
          </div>

          {/* Mobile Menu Button */}
          <button
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="md:hidden w-10 h-10 flex items-center justify-center rounded-[var(--radius-md)] text-[var(--color-text-secondary)] hover:bg-[var(--color-glass-bg)] hover:text-[var(--color-text-primary)] transition-colors"
            aria-label="Toggle menu"
          >
            {isMobileMenuOpen ? (
              <CloseIcon className="w-5 h-5" />
            ) : (
              <MenuIcon className="w-5 h-5" />
            )}
          </button>
        </div>
      </nav>

      {/* Mobile Menu */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40 bg-[var(--color-bg-primary)]/98 backdrop-blur-xl pt-20 md:hidden"
          >
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              transition={{ duration: 0.3, delay: 0.1 }}
              className="flex flex-col items-center gap-2 p-6"
            >
              {navLinks.map((link, index) => (
                <motion.button
                  key={link.href}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, delay: 0.1 + index * 0.05 }}
                  onClick={() => handleLinkClick(link.href)}
                  className="w-full py-4 text-xl font-medium text-[var(--color-text-primary)] hover:text-[var(--color-accent-primary)] transition-colors text-center border-b border-[var(--color-glass-border)]"
                >
                  {link.label}
                </motion.button>
              ))}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.3 }}
                className="flex flex-col gap-3 w-full max-w-[280px] mt-8"
              >
                <Button variant="ghost" className="w-full justify-center">
                  Log In
                </Button>
                <Button variant="primary" className="w-full justify-center">
                  Get Started
                </Button>
              </motion.div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
