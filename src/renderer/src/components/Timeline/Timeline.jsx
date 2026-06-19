import { useRef, useCallback, useEffect, useState } from 'react'
import usePlayerStore from '../../stores/playerStore'
import useMediaPlayer from '../../hooks/useMediaPlayer'

function formatTime(s) {
  if (!s || isNaN(s)) return '00:00'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`
}

export default function Timeline() {
  const currentTime = usePlayerStore(s => s.currentTime)
  const duration = usePlayerStore(s => s.duration)
  const mediaUrl = usePlayerStore(s => s.mediaUrl)
  const aiMarkers = usePlayerStore(s => s.aiMarkers)
  const warnings = usePlayerStore(s => s.warnings)
  const showTimeline = usePlayerStore(s => s.showTimeline)
  const { seek } = useMediaPlayer()
  const trackRef = useRef(null)
  const [isDragging, setIsDragging] = useState(false)
  const [hoverTime, setHoverTime] = useState(null)
  const [hoverX, setHoverX] = useState(0)
  const [waveformData] = useState(() => Array.from({ length: 120 }, () => Math.random()))

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0

  const getTimeFromEvent = useCallback((e) => {
    if (!trackRef.current || !duration) return 0
    const rect = trackRef.current.getBoundingClientRect()
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width))
    return (x / rect.width) * duration
  }, [duration])

  const handleMouseDown = useCallback((e) => {
    setIsDragging(true)
    const time = getTimeFromEvent(e)
    seek(time)
  }, [getTimeFromEvent, seek])

  const handleMouseMove = useCallback((e) => {
    if (!trackRef.current) return
    const rect = trackRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    setHoverX(x)
    setHoverTime(getTimeFromEvent(e))
    if (isDragging) seek(getTimeFromEvent(e))
  }, [isDragging, getTimeFromEvent, seek])

  const handleMouseUp = useCallback(() => setIsDragging(false), [])

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
      return () => {
        window.removeEventListener('mousemove', handleMouseMove)
        window.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [isDragging, handleMouseMove, handleMouseUp])

  if (!mediaUrl || !showTimeline) return null

  return (
    <div className="glass-panel-solid border-t border-white/5 px-4 py-2 flex-shrink-0 z-30">
      {/* Waveform visualization */}
      <div className="flex items-end gap-[2px] h-8 mb-2 px-1">
        {waveformData.map((val, i) => {
          const pos = (i / waveformData.length) * 100
          const isPast = pos <= progress
          return (
            <div
              key={i}
              className={`flex-1 rounded-full transition-colors duration-75 ${
                isPast ? 'bg-cs-accent-blue/60' : 'bg-white/8'
              }`}
              style={{ height: `${Math.max(3, val * 28)}px` }}
            />
          )
        })}
      </div>

      {/* Timeline track */}
      <div
        ref={trackRef}
        className="timeline-track h-2 relative group cursor-pointer"
        onMouseDown={handleMouseDown}
        onMouseMove={(e) => {
          if (!isDragging) {
            const rect = trackRef.current.getBoundingClientRect()
            setHoverX(e.clientX - rect.left)
            setHoverTime(getTimeFromEvent(e))
          }
        }}
        onMouseLeave={() => setHoverTime(null)}
      >
        {/* Progress fill */}
        <div className="timeline-progress" style={{ width: `${progress}%` }} />

        {/* Playhead */}
        <div className="timeline-handle" style={{ left: `${progress}%` }} />

        {/* AI Markers */}
        {aiMarkers.map((marker, i) => {
          const pos = duration > 0 ? (marker.time / duration) * 100 : 0
          return (
            <div
              key={i}
              className="absolute top-0 h-full w-0.5"
              style={{ left: `${pos}%`, backgroundColor: marker.color || '#f59e0b' }}
              title={marker.label}
            />
          )
        })}

        {/* Warning markers */}
        {warnings.map((w, i) => {
          const pos = duration > 0 ? (w.time / duration) * 100 : 0
          return (
            <div
              key={`w-${i}`}
              className="absolute -top-1 w-2 h-2 rounded-full bg-cs-accent-red shadow-sm"
              style={{ left: `${pos}%`, transform: 'translateX(-50%)' }}
              title={w.message}
            />
          )
        })}

        {/* Hover tooltip */}
        {hoverTime !== null && (
          <div
            className="absolute -top-8 px-2 py-0.5 rounded bg-black/80 text-[10px] font-mono text-cs-text-primary pointer-events-none backdrop-blur-sm border border-white/10"
            style={{ left: `${hoverX}px`, transform: 'translateX(-50%)' }}
          >
            {formatTime(hoverTime)}
          </div>
        )}
      </div>

      {/* AI marker track labels */}
      <div className="flex items-center justify-between mt-1.5">
        <span className="text-[9px] font-mono text-cs-text-muted uppercase tracking-wider">Timeline</span>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <div className="w-1.5 h-1.5 rounded-full bg-cs-accent-blue" />
            <span className="text-[9px] font-mono text-cs-text-muted">Audio</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-1.5 h-1.5 rounded-full bg-cs-accent-amber" />
            <span className="text-[9px] font-mono text-cs-text-muted">AI Markers</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-1.5 h-1.5 rounded-full bg-cs-accent-red" />
            <span className="text-[9px] font-mono text-cs-text-muted">Warnings</span>
          </div>
        </div>
      </div>
    </div>
  )
}
