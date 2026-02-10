export function Background() {
  return (
    <div className="fixed inset-0 pointer-events-none z-[-1] overflow-hidden">
      {/* Warm Ambient Light - Top Right */}
      <div
        className="absolute w-[800px] h-[600px] opacity-30"
        style={{
          background: 'radial-gradient(ellipse at center, rgba(245, 158, 11, 0.15) 0%, transparent 70%)',
          top: '-200px',
          right: '-200px',
          filter: 'blur(100px)',
        }}
      />

      {/* Cool Accent - Bottom Left */}
      <div
        className="absolute w-[600px] h-[600px] opacity-20"
        style={{
          background: 'radial-gradient(circle, rgba(45, 212, 191, 0.15) 0%, transparent 70%)',
          bottom: '-200px',
          left: '-200px',
          filter: 'blur(100px)',
        }}
      />

      {/* Subtle Center Highlight */}
      <div
        className="absolute w-[500px] h-[500px] opacity-10"
        style={{
          background: 'radial-gradient(circle, rgba(251, 191, 36, 0.1) 0%, transparent 70%)',
          top: '40%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          filter: 'blur(80px)',
        }}
      />

      {/* Geometric Grid */}
      <div
        className="absolute inset-0 opacity-100"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255, 255, 255, 0.012) 1px, transparent 1px), linear-gradient(90deg, rgba(255, 255, 255, 0.012) 1px, transparent 1px)',
          backgroundSize: '64px 64px',
          maskImage: 'radial-gradient(ellipse 80% 60% at 50% 30%, black 0%, transparent 100%)',
        }}
      />

      {/* Noise Texture */}
      <div
        className="absolute inset-0 opacity-[0.015] mix-blend-overlay"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 512 512' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.7' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
        }}
      />

      {/* Vignette */}
      <div
        className="absolute inset-0"
        style={{
          background: 'radial-gradient(ellipse at center, transparent 0%, var(--color-bg-primary) 100%)',
          opacity: 0.4,
        }}
      />
    </div>
  )
}
