import { useState, useEffect, useRef } from 'react'
import usePlayerStore from '../../stores/playerStore'

/**
 * GPU Warmup Overlay — A premium, cinematic loading screen
 * shown while Modal cloud GPU cold-starts (~30-120s).
 * Makes the user feel like a genius launching powerful infrastructure.
 */
export default function GPUWarmup() {
  const gpuWarmup = usePlayerStore((s) => s.gpuWarmup)
  const [particles, setParticles] = useState([])
  const [pulsePhase, setPulsePhase] = useState(0)
  const animFrameRef = useRef(null)

  // Generate floating particles
  useEffect(() => {
    const p = Array.from({ length: 30 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 3 + 1,
      speed: Math.random() * 0.5 + 0.2,
      opacity: Math.random() * 0.5 + 0.1,
      delay: Math.random() * 5,
    }))
    setParticles(p)
  }, [])

  // Pulse animation
  useEffect(() => {
    if (gpuWarmup.stage !== 'warming') return
    const interval = setInterval(() => {
      setPulsePhase((p) => (p + 1) % 360)
    }, 50)
    return () => clearInterval(interval)
  }, [gpuWarmup.stage])

  if (gpuWarmup.stage === 'idle' || gpuWarmup.stage === 'ready') return null

  const progress = gpuWarmup.progress || 0
  const message = gpuWarmup.message || 'Initializing...'
  const detail = gpuWarmup.detail || ''
  const elapsed = gpuWarmup.elapsed || 0
  const maxWait = gpuWarmup.maxWait || 120

  // Dynamic ring glow based on progress
  const ringGlow = Math.sin(pulsePhase * 0.05) * 0.3 + 0.7
  const progressDeg = (progress / 100) * 360

  return (
    <div
      id="gpu-warmup-overlay"
      className="fixed inset-0 z-[9999] flex items-center justify-center"
      style={{
        background:
          'radial-gradient(ellipse at center, rgba(0, 15, 30, 0.97) 0%, rgba(5, 5, 15, 0.99) 70%, #000 100%)',
        backdropFilter: 'blur(40px)',
      }}
    >
      {/* Floating particles */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {particles.map((p) => (
          <div
            key={p.id}
            className="absolute rounded-full"
            style={{
              left: `${p.x}%`,
              top: `${p.y}%`,
              width: `${p.size}px`,
              height: `${p.size}px`,
              background: `rgba(0, 212, 255, ${p.opacity})`,
              boxShadow: `0 0 ${p.size * 3}px rgba(0, 212, 255, ${p.opacity * 0.5})`,
              animation: `gpuParticleFloat ${3 + p.speed * 4}s ease-in-out infinite`,
              animationDelay: `${p.delay}s`,
            }}
          />
        ))}
      </div>

      {/* Ambient grid */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: `
            linear-gradient(rgba(0, 212, 255, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 212, 255, 0.03) 1px, transparent 1px)
          `,
          backgroundSize: '60px 60px',
          animation: 'gpuGridSlide 20s linear infinite',
        }}
      />

      {/* Central content */}
      <div className="relative flex flex-col items-center gap-8 max-w-lg px-8">
        {/* Circular progress ring */}
        <div className="relative w-48 h-48">
          {/* Outer ambient glow ring */}
          <div
            className="absolute inset-0 rounded-full"
            style={{
              background: `conic-gradient(
                from 0deg,
                rgba(0, 212, 255, ${0.05 * ringGlow}) 0deg,
                rgba(124, 58, 237, ${0.08 * ringGlow}) ${progressDeg * 0.5}deg,
                rgba(0, 212, 255, ${0.15 * ringGlow}) ${progressDeg}deg,
                transparent ${progressDeg}deg
              )`,
              filter: 'blur(20px)',
              transform: 'scale(1.3)',
            }}
          />

          {/* Background ring */}
          <svg
            className="absolute inset-0 w-full h-full -rotate-90"
            viewBox="0 0 200 200"
          >
            <circle
              cx="100"
              cy="100"
              r="85"
              fill="none"
              stroke="rgba(255,255,255,0.05)"
              strokeWidth="4"
            />
            {/* Progress arc */}
            <circle
              cx="100"
              cy="100"
              r="85"
              fill="none"
              stroke="url(#gpuGradient)"
              strokeWidth="4"
              strokeLinecap="round"
              strokeDasharray={`${(progress / 100) * 534} 534`}
              style={{
                filter: `drop-shadow(0 0 ${8 * ringGlow}px rgba(0, 212, 255, 0.6))`,
                transition: 'stroke-dasharray 0.8s ease-out',
              }}
            />
            {/* Animated dots along the ring */}
            <circle
              cx="100"
              cy="15"
              r="3"
              fill="#00d4ff"
              style={{
                filter: 'drop-shadow(0 0 6px rgba(0, 212, 255, 0.8))',
                opacity: ringGlow,
                transform: `rotate(${progressDeg}deg)`,
                transformOrigin: '100px 100px',
                transition: 'transform 0.8s ease-out',
              }}
            />
            <defs>
              <linearGradient id="gpuGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#00d4ff" />
                <stop offset="50%" stopColor="#7c3aed" />
                <stop offset="100%" stopColor="#00d4ff" />
              </linearGradient>
            </defs>
          </svg>

          {/* Center content */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            {/* GPU icon */}
            <div
              className="mb-2"
              style={{
                animation: 'gpuIconPulse 2s ease-in-out infinite',
              }}
            >
              <svg
                width="40"
                height="40"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <rect
                  x="4"
                  y="6"
                  width="16"
                  height="12"
                  rx="2"
                  stroke="url(#iconGrad)"
                  strokeWidth="1.5"
                />
                <path
                  d="M8 6V4M12 6V4M16 6V4M8 18v2M12 18v2M16 18v2"
                  stroke="url(#iconGrad)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <rect
                  x="7"
                  y="9"
                  width="4"
                  height="6"
                  rx="0.5"
                  fill="rgba(0, 212, 255, 0.3)"
                  stroke="rgba(0, 212, 255, 0.5)"
                  strokeWidth="0.5"
                />
                <rect
                  x="13"
                  y="9"
                  width="4"
                  height="6"
                  rx="0.5"
                  fill="rgba(124, 58, 237, 0.3)"
                  stroke="rgba(124, 58, 237, 0.5)"
                  strokeWidth="0.5"
                />
                <defs>
                  <linearGradient id="iconGrad" x1="4" y1="4" x2="20" y2="20">
                    <stop stopColor="#00d4ff" />
                    <stop offset="1" stopColor="#7c3aed" />
                  </linearGradient>
                </defs>
              </svg>
            </div>

            {/* Percentage */}
            <span
              className="text-3xl font-bold tracking-tighter font-mono"
              style={{
                background: 'linear-gradient(135deg, #00d4ff, #7c3aed)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              {progress}%
            </span>
          </div>
        </div>

        {/* Title */}
        <div className="text-center space-y-2">
          <h2
            className="text-xl font-semibold tracking-wide"
            style={{
              background: 'linear-gradient(135deg, #f0f0f5, #a0a0b8)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            Cloud GPU Initializing
          </h2>
          <p className="text-sm text-cs-text-secondary">{message}</p>
          <p className="text-xs text-cs-text-muted">{detail}</p>
        </div>

        {/* Progress bar (linear) */}
        <div className="w-full max-w-xs">
          <div className="h-1 rounded-full bg-white/5 overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{
                width: `${progress}%`,
                background:
                  'linear-gradient(90deg, #00d4ff, #7c3aed, #00d4ff)',
                backgroundSize: '200% 100%',
                animation: 'gpuBarShimmer 2s linear infinite',
                transition: 'width 0.8s ease-out',
                boxShadow: '0 0 12px rgba(0, 212, 255, 0.4)',
              }}
            />
          </div>
        </div>

        {/* Timer & info chips */}
        <div className="flex items-center gap-4">
          {/* Elapsed time */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10">
            <div
              className="w-1.5 h-1.5 rounded-full bg-cs-accent-blue"
              style={{ animation: 'pulseGlow 1.5s ease-in-out infinite' }}
            />
            <span className="text-xs font-mono text-cs-text-secondary">
              {elapsed.toFixed(0)}s / {maxWait}s
            </span>
          </div>

          {/* GPU chip */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10">
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#7c3aed"
              strokeWidth="2"
            >
              <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
            </svg>
            <span className="text-xs font-mono text-cs-text-secondary">
              NVIDIA T4 • 16GB
            </span>
          </div>
        </div>

        {/* Neural network visualization */}
        <div className="flex items-center gap-1 mt-2">
          {Array.from({ length: 12 }).map((_, i) => (
            <div
              key={i}
              className="rounded-full"
              style={{
                width: '3px',
                height: `${8 + Math.sin((pulsePhase + i * 30) * 0.05) * 12}px`,
                background:
                  i % 2 === 0
                    ? 'rgba(0, 212, 255, 0.6)'
                    : 'rgba(124, 58, 237, 0.6)',
                transition: 'height 0.15s ease',
                boxShadow:
                  i % 2 === 0
                    ? '0 0 6px rgba(0, 212, 255, 0.3)'
                    : '0 0 6px rgba(124, 58, 237, 0.3)',
              }}
            />
          ))}
        </div>

        {/* Bottom tip */}
        <p className="text-[10px] text-cs-text-muted/60 text-center max-w-xs">
          Provisioning a dedicated NVIDIA T4 GPU for AI inference.
          This takes 30–120 seconds on first launch.
        </p>
      </div>
    </div>
  )
}
