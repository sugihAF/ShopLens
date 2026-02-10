import { LogoIcon, XIcon, GitHubIcon, DiscordIcon } from '@/components/ui'

const footerLinks = [
  {
    title: 'Product',
    links: ['Features', 'Pricing', 'API', 'Integrations'],
  },
  {
    title: 'Company',
    links: ['About', 'Blog', 'Careers', 'Contact'],
  },
  {
    title: 'Legal',
    links: ['Privacy', 'Terms', 'Cookie Policy'],
  },
]

const socialLinks = [
  { icon: <XIcon className="w-4 h-4" />, label: 'Twitter', href: 'https://x.com/sugihaf1' },
  { icon: <GitHubIcon className="w-4 h-4" />, label: 'GitHub', href: 'https://github.com/sugihAF' },
]

export function Footer() {
  return (
    <footer className="py-16 bg-[var(--color-bg-secondary)] border-t border-[var(--color-glass-border)]">
      <div className="section-container">
        <div className="footer-grid">
          {/* Brand */}
          <div className="footer-brand">
            <a href="#" className="inline-flex items-center gap-2.5 mb-4 group">
              <LogoIcon className="w-8 h-8 transition-transform duration-500 ease-[var(--ease-spring)] group-hover:rotate-[360deg]" />
              <span className="text-lg font-semibold tracking-tight">ShopLens</span>
            </a>
            <p className="text-sm text-[var(--color-text-tertiary)] leading-relaxed">
              AI-powered product intelligence. Make smarter purchasing decisions.
            </p>
          </div>

          {/* Links */}
          {footerLinks.map((column) => (
            <div key={column.title}>
              <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider mb-5">
                {column.title}
              </h4>
              <ul className="flex flex-col gap-3">
                {column.links.map((link) => (
                  <li key={link}>
                    <a
                      href="#"
                      className="text-sm text-[var(--color-text-tertiary)] transition-colors duration-200 hover:text-[var(--color-text-primary)]"
                    >
                      {link}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom */}
        <div className="footer-bottom">
          <p className="text-xs text-[var(--color-text-muted)]">
            &copy; {new Date().getFullYear()} ShopLens. All rights reserved.
          </p>
          <div className="flex gap-2">
            {socialLinks.map((social) => (
              <a
                key={social.label}
                href={social.href}
                aria-label={social.label}
                className="w-9 h-9 flex items-center justify-center bg-[var(--color-bg-tertiary)] border border-[var(--color-glass-border)] rounded-[var(--radius-md)] text-[var(--color-text-tertiary)] transition-all duration-300 ease-[var(--ease-out-expo)] hover:bg-[var(--color-bg-elevated)] hover:border-[var(--color-accent-primary)]/30 hover:text-[var(--color-text-primary)]"
              >
                {social.icon}
              </a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  )
}
