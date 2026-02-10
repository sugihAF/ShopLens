import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatMarkdown(text: string): string {
  // Split into lines for processing
  const lines = text.split('\n')
  const result: string[] = []
  let inList = false

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i]

    // Handle headers
    if (line.startsWith('#### ')) {
      if (inList) {
        result.push('</ul>')
        inList = false
      }
      const content = line.slice(5)
      result.push(`<h4 class="font-semibold text-[var(--color-text-primary)] mt-4 mb-2">${processInline(content)}</h4>`)
      continue
    }
    if (line.startsWith('### ')) {
      if (inList) {
        result.push('</ul>')
        inList = false
      }
      const content = line.slice(4)
      result.push(`<h3 class="font-semibold text-[var(--color-text-primary)] mt-5 mb-3 text-lg">${processInline(content)}</h3>`)
      continue
    }
    if (line.startsWith('## ')) {
      if (inList) {
        result.push('</ul>')
        inList = false
      }
      const content = line.slice(3)
      result.push(`<h2 class="font-semibold text-[var(--color-text-primary)] mt-6 mb-3 text-xl">${processInline(content)}</h2>`)
      continue
    }

    // Handle list items (both * and -)
    if (line.match(/^[\*\-]\s+/)) {
      if (!inList) {
        result.push('<ul class="space-y-2 my-3">')
        inList = true
      }
      const content = line.replace(/^[\*\-]\s+/, '')
      result.push(`<li class="flex items-start gap-2"><span class="text-[var(--color-accent-primary)] mt-1.5">•</span><span>${processInline(content)}</span></li>`)
      continue
    }

    // Close list if we hit a non-list line
    if (inList && line.trim() !== '') {
      result.push('</ul>')
      inList = false
    }

    // Handle empty lines
    if (line.trim() === '') {
      if (!inList) {
        result.push('<br>')
      }
      continue
    }

    // Regular paragraph
    result.push(`<p class="mb-2">${processInline(line)}</p>`)
  }

  // Close any open list
  if (inList) {
    result.push('</ul>')
  }

  return result.join('')
}

function processInline(text: string): string {
  return text
    // Bold text
    .replace(/\*\*([^*]+)\*\*/g, '<strong class="text-[var(--color-text-primary)] font-semibold">$1</strong>')
    // Italic text
    .replace(/\*([^*]+)\*/g, '<em class="text-[var(--color-accent-primary)]">$1</em>')
    // Links [text](url)
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-[var(--color-accent-primary)] hover:underline">$1</a>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 bg-[var(--color-bg-tertiary)] rounded text-sm font-mono">$1</code>')
}
