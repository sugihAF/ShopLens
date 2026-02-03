/**
 * ShopLens Landing Page - Interactive JavaScript
 * Prismatic Intelligence Theme
 */

(function() {
    'use strict';

    // ============================================
    // CONFIGURATION
    // ============================================

    const CONFIG = {
        typingSpeed: 30,
        typingDelay: 1000,
        scrollOffset: 100,
        counterDuration: 2000,
        apiBaseUrl: '/api/v1'
    };

    // Demo responses for the chat
    const DEMO_RESPONSES = {
        'headphones': `Based on my analysis of 127 reviews from trusted sources, here are the top noise-canceling headphones under $400:

**1. Sony WH-1000XM5** - $348
Reviewers consistently praise the exceptional noise cancellation and 30-hour battery life. MKBHD called them "the new benchmark" while The Verge noted "unmatched ANC performance."

**2. Bose QuietComfort Ultra** - $379
Tom's Guide highlighted the "incredibly comfortable fit" and RTINGS measured best-in-class noise isolation. Some reviewers noted the premium price.

**3. Apple AirPods Max** - $399
Dave2D emphasized the "premium build quality" though noted they're heavier than competitors. Best for Apple ecosystem users.

*Key insight: 89% of reviewers recommend the Sony XM5 for the best value proposition.*`,

        'iphone_samsung': `Analyzing 94 camera comparison reviews between iPhone 15 Pro and Samsung S24 Ultra:

**Photo Quality:**
- iPhone 15 Pro: Praised for natural color science (87% positive)
- S24 Ultra: Better zoom capabilities with 5x optical

**Video Performance:**
- iPhone leads in video stabilization and ProRes support
- Samsung excels in 8K recording capabilities

**Low Light:**
MKBHD noted "iPhone produces more usable shots in challenging conditions" while Dave2D found "Samsung's Night Mode is more aggressive but sometimes unnatural."

**Consensus:**
For most users, reviewers lean toward iPhone 15 Pro for overall camera system (62% preference). Samsung wins for zoom photography and Android users.`,

        'macbook_battery': `Aggregating 58 reviews mentioning MacBook Pro M3 Max battery life:

**Key Findings:**
- Average reported battery life: 15.2 hours
- Range: 12-18 hours depending on workload

**Reviewer Highlights:**

*MKBHD:* "Easily gets me through a full day of video editing, which was impossible before"

*Dave2D:* Measured 16.5 hours in his standardized test - "best laptop battery I've ever tested"

*The Verge:* "You can leave the charger at home for weekend trips"

**Workload Analysis:**
- Light use (web/docs): 17-18 hours
- Creative work (video/3D): 10-12 hours
- Development: 14-16 hours

*92% of reviewers rated battery life as "excellent" or "best in class"*`,

        'default': `I'd be happy to help you research that product! In the full version of ShopLens, I analyze reviews from:

- **200+ tech YouTubers** including MKBHD, Linus Tech Tips, Dave2D
- **50+ tech publications** like The Verge, Tom's Guide, RTINGS
- **Thousands of written reviews** from trusted sources

I can help you with:
- Product recommendations based on your needs
- Side-by-side comparisons
- Specific feature deep-dives
- Price-to-value analysis

This is a demo - sign up to unlock full access to our AI-powered review intelligence!`
    };

    // ============================================
    // DOM ELEMENTS
    // ============================================

    const elements = {
        nav: document.getElementById('nav'),
        mobileMenuBtn: document.getElementById('mobileMenuBtn'),
        mobileMenu: document.getElementById('mobileMenu'),
        demoChatMessages: document.getElementById('demoChatMessages'),
        demoChatInput: document.getElementById('demoChatInput'),
        demoSendBtn: document.getElementById('demoSendBtn'),
        clearChat: document.getElementById('clearChat'),
        suggestionChips: document.querySelectorAll('.suggestion-chip'),
        tryDemoBtn: document.getElementById('tryDemo'),
        statValues: document.querySelectorAll('.stat-value[data-count]'),
        aiResponse: document.getElementById('aiResponse'),
        typingIndicator: document.querySelector('.typing-indicator')
    };

    // ============================================
    // NAVIGATION
    // ============================================

    function initNavigation() {
        // Scroll effect
        let lastScroll = 0;

        window.addEventListener('scroll', () => {
            const currentScroll = window.pageYOffset;

            if (currentScroll > 50) {
                elements.nav.classList.add('scrolled');
            } else {
                elements.nav.classList.remove('scrolled');
            }

            lastScroll = currentScroll;
        });

        // Mobile menu toggle
        elements.mobileMenuBtn?.addEventListener('click', () => {
            elements.mobileMenuBtn.classList.toggle('active');
            elements.mobileMenu.classList.toggle('active');
            document.body.style.overflow = elements.mobileMenu.classList.contains('active') ? 'hidden' : '';
        });

        // Close mobile menu on link click
        document.querySelectorAll('.mobile-link').forEach(link => {
            link.addEventListener('click', () => {
                elements.mobileMenuBtn.classList.remove('active');
                elements.mobileMenu.classList.remove('active');
                document.body.style.overflow = '';
            });
        });

        // Smooth scroll for anchor links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function(e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    const offsetTop = target.offsetTop - 80;
                    window.scrollTo({
                        top: offsetTop,
                        behavior: 'smooth'
                    });
                }
            });
        });
    }

    // ============================================
    // SCROLL ANIMATIONS (AOS-like)
    // ============================================

    function initScrollAnimations() {
        const observerOptions = {
            root: null,
            rootMargin: '0px',
            threshold: 0.1
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('aos-animate');

                    // Handle staggered delays for child elements
                    const delay = entry.target.dataset.aosDelay;
                    if (delay) {
                        entry.target.style.transitionDelay = `${delay}ms`;
                    }
                }
            });
        }, observerOptions);

        document.querySelectorAll('[data-aos]').forEach(el => {
            observer.observe(el);
        });
    }

    // ============================================
    // STAT COUNTER ANIMATION
    // ============================================

    function initStatCounters() {
        const observerOptions = {
            root: null,
            threshold: 0.5
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animateCounter(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, observerOptions);

        elements.statValues.forEach(stat => {
            observer.observe(stat);
        });
    }

    function animateCounter(element) {
        const target = parseInt(element.dataset.count, 10);
        const duration = CONFIG.counterDuration;
        const startTime = performance.now();

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Ease out cubic
            const easeProgress = 1 - Math.pow(1 - progress, 3);
            const current = Math.floor(easeProgress * target);

            element.textContent = current;

            if (progress < 1) {
                requestAnimationFrame(update);
            }
        }

        requestAnimationFrame(update);
    }

    // ============================================
    // HERO CHAT PREVIEW TYPEWRITER
    // ============================================

    function initHeroTypewriter() {
        const response = `Based on 156 reviews, the **MacBook Pro 16" M3 Max** leads for video editing under $2000.

MKBHD rated it "the fastest laptop I've tested" with Dave2D praising its "all-day battery during 4K exports."

Key highlights:
- 40% faster renders than M2
- 22-hour battery life
- Best-in-class display`;

        setTimeout(() => {
            typeWriter(elements.aiResponse, response, () => {
                elements.typingIndicator.style.display = 'none';
                elements.aiResponse.classList.add('visible');
            });
        }, CONFIG.typingDelay);
    }

    function typeWriter(element, text, callback) {
        if (!element) return;

        let i = 0;
        element.innerHTML = '';
        element.classList.add('visible');
        elements.typingIndicator.style.display = 'none';

        function type() {
            if (i < text.length) {
                // Handle markdown-like formatting
                let char = text.charAt(i);
                element.innerHTML = formatMarkdown(text.substring(0, i + 1));
                i++;
                setTimeout(type, CONFIG.typingSpeed);
            } else if (callback) {
                callback();
            }
        }

        type();
    }

    function formatMarkdown(text) {
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');
    }

    // ============================================
    // DEMO CHAT FUNCTIONALITY
    // ============================================

    function initDemoChat() {
        // Send message on button click
        elements.demoSendBtn?.addEventListener('click', sendDemoMessage);

        // Send message on Enter key
        elements.demoChatInput?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendDemoMessage();
            }
        });

        // Suggestion chips
        elements.suggestionChips.forEach(chip => {
            chip.addEventListener('click', () => {
                const query = chip.dataset.query;
                elements.demoChatInput.value = query;
                sendDemoMessage();
            });
        });

        // Clear chat
        elements.clearChat?.addEventListener('click', clearDemoChat);

        // Try demo button scrolls to demo section
        elements.tryDemoBtn?.addEventListener('click', () => {
            const demoSection = document.getElementById('demo');
            if (demoSection) {
                const offsetTop = demoSection.offsetTop - 80;
                window.scrollTo({
                    top: offsetTop,
                    behavior: 'smooth'
                });
                setTimeout(() => {
                    elements.demoChatInput?.focus();
                }, 500);
            }
        });
    }

    function sendDemoMessage() {
        const message = elements.demoChatInput.value.trim();
        if (!message) return;

        // Hide welcome message
        const welcome = elements.demoChatMessages.querySelector('.demo-welcome');
        if (welcome) {
            welcome.style.display = 'none';
        }

        // Add user message
        addChatMessage(message, 'user');
        elements.demoChatInput.value = '';

        // Determine response
        const response = getResponseForQuery(message);

        // Show typing indicator then response
        setTimeout(() => {
            addChatMessage(response, 'ai', true);
        }, 500);
    }

    function getResponseForQuery(query) {
        const lowerQuery = query.toLowerCase();

        if (lowerQuery.includes('headphone') || lowerQuery.includes('noise-cancel') || lowerQuery.includes('noise cancel')) {
            return DEMO_RESPONSES.headphones;
        }
        if (lowerQuery.includes('iphone') || lowerQuery.includes('samsung') || lowerQuery.includes('camera') || lowerQuery.includes('s24')) {
            return DEMO_RESPONSES.iphone_samsung;
        }
        if (lowerQuery.includes('macbook') || lowerQuery.includes('battery') || lowerQuery.includes('m3')) {
            return DEMO_RESPONSES.macbook_battery;
        }

        return DEMO_RESPONSES.default;
    }

    function addChatMessage(content, type, animate = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `demo-message demo-message-${type}`;

        if (type === 'ai') {
            messageDiv.innerHTML = `
                <div class="demo-message-avatar">
                    <svg viewBox="0 0 24 24" fill="none">
                        <circle cx="12" cy="12" r="10" stroke="url(#msgGrad2)" stroke-width="1.5"/>
                        <circle cx="12" cy="12" r="4" fill="url(#msgGrad2)"/>
                        <defs>
                            <linearGradient id="msgGrad2" x1="0" y1="0" x2="24" y2="24">
                                <stop offset="0%" stop-color="#a855f7"/>
                                <stop offset="100%" stop-color="#06b6d4"/>
                            </linearGradient>
                        </defs>
                    </svg>
                </div>
                <div class="demo-message-content">
                    <div class="typing-indicator-inline">
                        <span></span><span></span><span></span>
                    </div>
                </div>
            `;
        } else {
            messageDiv.innerHTML = `<div class="demo-message-content">${escapeHtml(content)}</div>`;
        }

        elements.demoChatMessages.appendChild(messageDiv);
        elements.demoChatMessages.scrollTop = elements.demoChatMessages.scrollHeight;

        if (type === 'ai' && animate) {
            const contentEl = messageDiv.querySelector('.demo-message-content');
            const typingEl = messageDiv.querySelector('.typing-indicator-inline');

            // Add inline typing indicator styles if not present
            if (!document.querySelector('#typing-inline-styles')) {
                const style = document.createElement('style');
                style.id = 'typing-inline-styles';
                style.textContent = `
                    .typing-indicator-inline {
                        display: flex;
                        gap: 4px;
                        padding: 4px 0;
                    }
                    .typing-indicator-inline span {
                        width: 6px;
                        height: 6px;
                        background: var(--text-tertiary);
                        border-radius: 50%;
                        animation: typingBounce 1.4s ease-in-out infinite;
                    }
                    .typing-indicator-inline span:nth-child(2) { animation-delay: 0.2s; }
                    .typing-indicator-inline span:nth-child(3) { animation-delay: 0.4s; }
                `;
                document.head.appendChild(style);
            }

            setTimeout(() => {
                typingEl.remove();
                contentEl.innerHTML = formatMarkdown(content);
                elements.demoChatMessages.scrollTop = elements.demoChatMessages.scrollHeight;
            }, 1500);
        }
    }

    function clearDemoChat() {
        elements.demoChatMessages.innerHTML = `
            <div class="demo-welcome">
                <div class="demo-welcome-icon">
                    <svg viewBox="0 0 40 40" fill="none">
                        <circle cx="20" cy="20" r="18" stroke="url(#welcomeGrad2)" stroke-width="2"/>
                        <circle cx="20" cy="20" r="10" stroke="url(#welcomeGrad2)" stroke-width="2"/>
                        <circle cx="20" cy="20" r="4" fill="url(#welcomeGrad2)"/>
                        <defs>
                            <linearGradient id="welcomeGrad2" x1="0" y1="0" x2="40" y2="40">
                                <stop offset="0%" stop-color="#a855f7"/>
                                <stop offset="100%" stop-color="#06b6d4"/>
                            </linearGradient>
                        </defs>
                    </svg>
                </div>
                <h3>Welcome to ShopLens</h3>
                <p>Ask me anything about tech products. I'll analyze reviews from trusted sources to give you comprehensive insights.</p>
            </div>
        `;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ============================================
    // PARALLAX EFFECTS
    // ============================================

    function initParallax() {
        const prisms = document.querySelectorAll('.prism');

        window.addEventListener('scroll', () => {
            const scrollY = window.pageYOffset;

            prisms.forEach((prism, index) => {
                const speed = 0.1 + (index * 0.05);
                prism.style.transform = `translateY(${scrollY * speed}px)`;
            });
        });
    }

    // ============================================
    // BUTTON RIPPLE EFFECT
    // ============================================

    function initRippleEffect() {
        document.querySelectorAll('.btn-primary').forEach(button => {
            button.addEventListener('click', function(e) {
                const rect = this.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;

                const ripple = document.createElement('span');
                ripple.style.cssText = `
                    position: absolute;
                    background: rgba(255, 255, 255, 0.3);
                    border-radius: 50%;
                    transform: scale(0);
                    animation: ripple 0.6s ease-out;
                    pointer-events: none;
                    left: ${x}px;
                    top: ${y}px;
                    width: 100px;
                    height: 100px;
                    margin-left: -50px;
                    margin-top: -50px;
                `;

                this.style.position = 'relative';
                this.style.overflow = 'hidden';
                this.appendChild(ripple);

                setTimeout(() => ripple.remove(), 600);
            });
        });

        // Add ripple keyframes if not present
        if (!document.querySelector('#ripple-styles')) {
            const style = document.createElement('style');
            style.id = 'ripple-styles';
            style.textContent = `
                @keyframes ripple {
                    to {
                        transform: scale(4);
                        opacity: 0;
                    }
                }
            `;
            document.head.appendChild(style);
        }
    }

    // ============================================
    // FLOATING CARDS MOUSE INTERACTION
    // ============================================

    function initFloatingCardsInteraction() {
        const heroVisual = document.querySelector('.hero-visual');
        const floatingCards = document.querySelectorAll('.floating-card');

        if (!heroVisual || floatingCards.length === 0) return;

        heroVisual.addEventListener('mousemove', (e) => {
            const rect = heroVisual.getBoundingClientRect();
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;

            const moveX = (e.clientX - centerX) / 30;
            const moveY = (e.clientY - centerY) / 30;

            floatingCards.forEach((card, index) => {
                const multiplier = 1 + (index * 0.3);
                card.style.transform = `translate(${moveX * multiplier}px, ${moveY * multiplier}px)`;
            });
        });

        heroVisual.addEventListener('mouseleave', () => {
            floatingCards.forEach(card => {
                card.style.transform = 'translate(0, 0)';
                card.style.transition = 'transform 0.5s ease-out';
            });
        });
    }

    // ============================================
    // FEATURE CARDS HOVER EFFECT
    // ============================================

    function initFeatureCardsEffect() {
        document.querySelectorAll('.feature-card').forEach(card => {
            card.addEventListener('mousemove', function(e) {
                const rect = this.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;

                this.style.setProperty('--mouse-x', `${x}px`);
                this.style.setProperty('--mouse-y', `${y}px`);
            });
        });

        // Add radial gradient hover effect styles
        if (!document.querySelector('#card-hover-styles')) {
            const style = document.createElement('style');
            style.id = 'card-hover-styles';
            style.textContent = `
                .feature-card::after {
                    content: '';
                    position: absolute;
                    inset: 0;
                    background: radial-gradient(
                        400px circle at var(--mouse-x, 50%) var(--mouse-y, 50%),
                        rgba(168, 85, 247, 0.06),
                        transparent 40%
                    );
                    border-radius: inherit;
                    pointer-events: none;
                    opacity: 0;
                    transition: opacity 0.3s ease;
                }
                .feature-card:hover::after {
                    opacity: 1;
                }
            `;
            document.head.appendChild(style);
        }
    }

    // ============================================
    // ANALYSIS BARS ANIMATION
    // ============================================

    function initAnalysisBars() {
        const observerOptions = {
            root: null,
            threshold: 0.5
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const bars = entry.target.querySelectorAll('.analysis-fill');
                    bars.forEach(bar => {
                        bar.style.width = bar.style.width; // Trigger animation
                    });
                    observer.unobserve(entry.target);
                }
            });
        }, observerOptions);

        const analysisViz = document.querySelector('.analysis-viz');
        if (analysisViz) {
            observer.observe(analysisViz);
        }
    }

    // ============================================
    // KEYBOARD ACCESSIBILITY
    // ============================================

    function initKeyboardAccessibility() {
        // Focus trap for mobile menu
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                // Close mobile menu
                elements.mobileMenuBtn?.classList.remove('active');
                elements.mobileMenu?.classList.remove('active');
                document.body.style.overflow = '';
            }
        });
    }

    // ============================================
    // PERFORMANCE OPTIMIZATIONS
    // ============================================

    function initPerformanceOptimizations() {
        // Reduce motion for users who prefer it
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            document.documentElement.style.setProperty('--ease-out-expo', 'ease');
            document.querySelectorAll('.prism').forEach(prism => {
                prism.style.animation = 'none';
            });
        }

        // Lazy load images when implemented
        if ('loading' in HTMLImageElement.prototype) {
            document.querySelectorAll('img[data-src]').forEach(img => {
                img.src = img.dataset.src;
            });
        }
    }

    // ============================================
    // INITIALIZE
    // ============================================

    function init() {
        initNavigation();
        initScrollAnimations();
        initStatCounters();
        initHeroTypewriter();
        initDemoChat();
        initParallax();
        initRippleEffect();
        initFloatingCardsInteraction();
        initFeatureCardsEffect();
        initAnalysisBars();
        initKeyboardAccessibility();
        initPerformanceOptimizations();

        // Log initialization
        console.log('%c ShopLens ', 'background: linear-gradient(135deg, #a855f7, #06b6d4); color: white; padding: 8px 16px; border-radius: 4px; font-weight: bold;', 'Prismatic Intelligence Loaded');
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
