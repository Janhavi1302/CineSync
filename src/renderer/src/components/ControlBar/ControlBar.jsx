import { useCallback, useState } from 'react'
import usePlayerStore from '../../stores/playerStore'
import useMediaPlayer from '../../hooks/useMediaPlayer'
import useWebSocket from '../../hooks/useWebSocket'

function formatTime(s) {
  if (!s || isNaN(s)) return '00:00'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`
  return `${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`
}

// ── SVG Icon Components ──
const OpenFileIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
  </svg>
)

const FullscreenIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
  </svg>
)

const ExitFullscreenIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"/>
  </svg>
)

const ScreenshotIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
    <circle cx="12" cy="13" r="4"/>
  </svg>
)

const ExportIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="7 10 12 15 17 10"/>
    <line x1="12" y1="15" x2="12" y2="3"/>
  </svg>
)

const KeyboardIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="2" y="4" width="20" height="16" rx="2"/>
    <path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M8 12h.01M12 12h.01M16 12h.01M7 16h10"/>
  </svg>
)

// ── Keyboard Shortcuts Tooltip ──
function ShortcutsTooltip({ show }) {
  if (!show) return null
  const shortcuts = [
    { key: 'Space', action: 'Play / Pause' },
    { key: 'M', action: 'Mute / Unmute' },
    { key: 'F', action: 'Fullscreen' },
    { key: 'O', action: 'Toggle AI Overlay' },
    { key: 'B', action: 'Toggle Sidebar' },
    { key: 'D', action: 'Toggle Dubbing' },
    { key: 'T', action: 'Toggle Timeline' },
    { key: '←', action: 'Seek -5s' },
    { key: '→', action: 'Seek +5s' },
  ]
  return (
    <div className="absolute bottom-full right-0 mb-2 w-56 glass-panel rounded-xl p-3 z-50 animate-fade-in shadow-2xl">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-cs-text-muted mb-2">Keyboard Shortcuts</div>
      <div className="space-y-1">
        {shortcuts.map(s => (
          <div key={s.key} className="flex items-center justify-between py-0.5">
            <span className="text-[10px] text-cs-text-secondary">{s.action}</span>
            <kbd className="text-[9px] font-mono bg-white/5 border border-white/10 rounded px-1.5 py-0.5 text-cs-text-muted min-w-[28px] text-center">{s.key}</kbd>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function ControlBar() {
  const isPlaying = usePlayerStore(s => s.isPlaying)
  const currentTime = usePlayerStore(s => s.currentTime)
  const duration = usePlayerStore(s => s.duration)
  const volume = usePlayerStore(s => s.volume)
  const isMuted = usePlayerStore(s => s.isMuted)
  const playbackRate = usePlayerStore(s => s.playbackRate)
  const mediaUrl = usePlayerStore(s => s.mediaUrl)
  const showOverlay = usePlayerStore(s => s.showOverlay)
  const sidebarOpen = usePlayerStore(s => s.sidebarOpen)
  const dubbingStatus = usePlayerStore(s => s.dubbingStatus)
  const filePath = usePlayerStore(s => s.filePath)
  const aiConnected = usePlayerStore(s => s.aiConnected)
  const targetLanguage = usePlayerStore(s => s.targetLanguage)
  const dubbedTrackUrl = usePlayerStore(s => s.dubbedTrackUrl)
  const isFullscreen = usePlayerStore(s => s.isFullscreen)
  const setVolume = usePlayerStore(s => s.setVolume)
  const toggleMute = usePlayerStore(s => s.toggleMute)
  const setPlaybackRate = usePlayerStore(s => s.setPlaybackRate)
  const toggleOverlay = usePlayerStore(s => s.toggleOverlay)
  const toggleSidebar = usePlayerStore(s => s.toggleSidebar)
  const setFullscreen = usePlayerStore(s => s.setFullscreen)
  const { togglePlay, seekRelative } = useMediaPlayer()
  const { sendCommand } = useWebSocket()
  const [showShortcuts, setShowShortcuts] = useState(false)

  const speeds = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2]
  const nextSpeed = useCallback(() => {
    const idx = speeds.indexOf(playbackRate)
    setPlaybackRate(speeds[(idx + 1) % speeds.length])
  }, [playbackRate, setPlaybackRate])

  const handleDubbingToggle = useCallback(() => {
    const isDubbingActive = dubbingStatus.stage === 'active' || dubbingStatus.stage === 'loading_stt'
    if (isDubbingActive) {
      sendCommand('stop_dubbing')
    } else {
      if (filePath && aiConnected) {
        sendCommand('start_dubbing', { language: targetLanguage })
      }
    }
  }, [dubbingStatus.stage, filePath, aiConnected, targetLanguage, sendCommand])

  // ── Open New Video ──
  const handleOpenFile = useCallback(async () => {
    const newPath = await window.electronAPI?.openFile()
    if (newPath) {
      // Stop dubbing if active
      sendCommand('stop_dubbing')
      // Clear previous state
      usePlayerStore.getState().clearDubbingState()
      // Load new video
      const url = await window.electronAPI?.getMediaUrl(newPath)
      const name = newPath.split(/[/\\]/).pop()
      usePlayerStore.getState().setFile(newPath, url, name)
      window.electronAPI?.sendAICommand({ type: 'load_media', data: { filePath: newPath } })
      setTimeout(() => { window.electronAPI?.sendAICommand({ type: 'start_analysis', data: {} }) }, 500)
    }
  }, [sendCommand])

  // ── Fullscreen Toggle ──
  const handleFullscreen = useCallback(() => {
    if (document.fullscreenElement) {
      document.exitFullscreen()
      setFullscreen(false)
    } else {
      document.documentElement.requestFullscreen()
      setFullscreen(true)
    }
  }, [setFullscreen])

  // ── Screenshot ──
  const handleScreenshot = useCallback(() => {
    const video = document.querySelector('video')
    if (!video) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    ctx.drawImage(video, 0, 0)
    const link = document.createElement('a')
    link.download = `cinesync_${formatTime(currentTime).replace(/:/g, '-')}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  }, [currentTime])

  // ── Export Dubbed Audio ──
  const handleExportAudio = useCallback(() => {
    if (dubbedTrackUrl) {
      const link = document.createElement('a')
      link.download = 'cinesync_dubbed_track.wav'
      link.href = dubbedTrackUrl
      link.click()
    }
  }, [dubbedTrackUrl])

  if (!mediaUrl) return null

  const isDubbingActive = dubbingStatus.stage === 'active' || dubbingStatus.stage === 'loading_stt'
  const isDubbingComplete = dubbingStatus.stage === 'complete'

  return (
    <div className="glass-panel-solid border-t border-white/5 px-4 py-2 flex-shrink-0 z-30">
      <div className="flex items-center gap-3">
        {/* ── Left: Playback Controls ── */}
        <div className="flex items-center gap-1">
          <button onClick={() => seekRelative(-10)} className="glass-btn w-8 h-8 flex items-center justify-center text-cs-text-secondary hover:text-cs-text-primary" title="Back 10s (←)">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/></svg>
          </button>
          <button onClick={togglePlay} className="w-10 h-10 rounded-full bg-cs-accent-blue/10 border border-cs-accent-blue/30 flex items-center justify-center text-cs-accent-blue hover:bg-cs-accent-blue/20 hover:border-cs-accent-blue/50 transition-all duration-200 hover:shadow-glow-blue" title={isPlaying ? 'Pause (Space)' : 'Play (Space)'}>
            {isPlaying
              ? <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
              : <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>}
          </button>
          <button onClick={() => seekRelative(10)} className="glass-btn w-8 h-8 flex items-center justify-center text-cs-text-secondary hover:text-cs-text-primary" title="Forward 10s (→)">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/></svg>
          </button>
        </div>

        {/* Time */}
        <div className="flex items-center gap-1.5 font-mono text-xs min-w-[120px]">
          <span className="text-cs-text-primary">{formatTime(currentTime)}</span>
          <span className="text-cs-text-muted">/</span>
          <span className="text-cs-text-muted">{formatTime(duration)}</span>
        </div>

        <div className="flex-1" />

        {/* ── Center: Volume ── */}
        <div className="flex items-center gap-2 group">
          <button onClick={toggleMute} className="text-cs-text-secondary hover:text-cs-text-primary transition-colors" title="Mute (M)">
            {isMuted
              ? <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/></svg>
              : <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>}
          </button>
          <input type="range" min="0" max="1" step="0.01" value={isMuted ? 0 : volume} onChange={e => setVolume(parseFloat(e.target.value))}
            className="w-20 h-1 rounded-full appearance-none bg-white/10 accent-cs-accent-blue cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-cs-accent-blue opacity-60 group-hover:opacity-100 transition-opacity" />
        </div>

        <div className="divider-v" />

        {/* Speed */}
        <button onClick={nextSpeed} className="glass-btn text-[11px] font-mono text-cs-text-secondary hover:text-cs-accent-blue min-w-[42px] text-center" title="Playback Speed">{playbackRate}×</button>

        <div className="divider-v" />

        {/* ── Right: Feature Buttons ── */}

        {/* Open new file */}
        <button onClick={handleOpenFile} className="glass-btn w-8 h-8 flex items-center justify-center text-cs-text-muted hover:text-cs-accent-amber hover:border-cs-accent-amber/30 hover:bg-cs-accent-amber/5 transition-colors" title="Open New Video">
          <OpenFileIcon />
        </button>

        {/* Screenshot */}
        <button onClick={handleScreenshot} className="glass-btn w-8 h-8 flex items-center justify-center text-cs-text-muted hover:text-cs-accent-blue hover:border-cs-accent-blue/30 hover:bg-cs-accent-blue/5 transition-colors" title="Screenshot">
          <ScreenshotIcon />
        </button>

        {/* Export dubbed audio */}
        {dubbedTrackUrl && (
          <button onClick={handleExportAudio} className="glass-btn w-8 h-8 flex items-center justify-center text-cs-accent-green border-cs-accent-green/30 bg-cs-accent-green/5 hover:bg-cs-accent-green/15 transition-colors" title="Export Dubbed Audio">
            <ExportIcon />
          </button>
        )}

        <div className="divider-v" />

        {/* Dubbing toggle */}
        <button onClick={handleDubbingToggle}
          disabled={!filePath || !aiConnected}
          className={`glass-btn w-8 h-8 flex items-center justify-center transition-colors relative ${isDubbingActive ? 'text-cs-accent-green border-cs-accent-green/30 bg-cs-accent-green/10' : isDubbingComplete ? 'text-cs-accent-blue border-cs-accent-blue/30 bg-cs-accent-blue/5' : 'text-cs-text-muted'} disabled:opacity-30 disabled:cursor-not-allowed`}
          title={isDubbingActive ? 'Stop Dubbing' : isDubbingComplete ? 'Dubbing Complete ✓' : 'Start AI Dubbing (D)'}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/></svg>
          {isDubbingActive && (
            <div className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-cs-accent-green animate-pulse" />
          )}
          {isDubbingComplete && (
            <div className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-cs-accent-blue" />
          )}
        </button>

        {/* Overlay toggle */}
        <button onClick={toggleOverlay} className={`glass-btn w-8 h-8 flex items-center justify-center transition-colors ${showOverlay ? 'text-cs-accent-blue border-cs-accent-blue/30 bg-cs-accent-blue/10' : 'text-cs-text-muted'}`} title="AI Overlay (O)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>
        </button>

        {/* Fullscreen */}
        <button onClick={handleFullscreen} className="glass-btn w-8 h-8 flex items-center justify-center text-cs-text-muted hover:text-cs-text-primary transition-colors" title="Fullscreen (F)">
          {isFullscreen ? <ExitFullscreenIcon /> : <FullscreenIcon />}
        </button>

        {/* Sidebar toggle */}
        <button onClick={toggleSidebar} className={`glass-btn w-8 h-8 flex items-center justify-center transition-colors ${sidebarOpen ? 'text-cs-accent-purple border-cs-accent-purple/30 bg-cs-accent-purple/10' : 'text-cs-text-muted'}`} title="Sidebar (B)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M15 3v18"/></svg>
        </button>

        {/* Keyboard shortcuts */}
        <div className="relative">
          <button
            onClick={() => setShowShortcuts(!showShortcuts)}
            onBlur={() => setTimeout(() => setShowShortcuts(false), 200)}
            className="glass-btn w-8 h-8 flex items-center justify-center text-cs-text-muted hover:text-cs-text-primary transition-colors"
            title="Keyboard Shortcuts (?)"
          >
            <KeyboardIcon />
          </button>
          <ShortcutsTooltip show={showShortcuts} />
        </div>
      </div>
    </div>
  )
}
