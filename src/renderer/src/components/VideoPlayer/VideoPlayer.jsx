import { memo, useCallback, useRef, useState, useEffect } from 'react'
import usePlayerStore from '../../stores/playerStore'
import useMediaPlayer from '../../hooks/useMediaPlayer'

const EMOTION_COLORS = {
  anger: '#ef4444', sadness: '#3b82f6', joy: '#22c55e',
  fear: '#a855f7', surprise: '#f59e0b', excitement: '#ec4899',
  neutral: '#e2e8f0'
}

// ── Stable video element — NEVER re-renders unless URL changes ──
const StableVideo = memo(function StableVideo({ videoRef, mediaUrl, onMeta, onEnd, onErr, onClick }) {
  return (
    <video
      ref={videoRef}
      src={mediaUrl}
      className="w-full h-full object-contain"
      onLoadedMetadata={onMeta}
      onEnded={onEnd}
      onError={onErr}
      onClick={onClick}
      playsInline
    />
  )
}, (prev, next) => prev.mediaUrl === next.mediaUrl)

// ── Subtitle overlay — polls video time, no store dependency on currentTime ──
function SubtitleOverlay({ videoRef }) {
  const [subtitle, setSubtitle] = useState(null)

  useEffect(() => {
    const interval = setInterval(() => {
      const s = usePlayerStore.getState()
      if (!s.dubbingEnabled || s.dubbedSegments.length === 0) {
        setSubtitle(null)
        return
      }
      const t = videoRef.current?.currentTime || 0
      const sub = s.dubbedSegments.find(seg => t >= seg.start && t <= seg.end)
      if (sub) {
        setSubtitle({
          text: sub.translatedText,
          original: sub.originalText,
          emotion: sub.emotion
        })
      } else {
        setSubtitle(null)
      }
    }, 250)
    return () => clearInterval(interval)
  }, [videoRef]) // only videoRef as dep — stable ref, never changes

  if (!subtitle) return null

  return (
    <div className="absolute bottom-16 left-0 right-0 flex justify-center z-30 pointer-events-none px-8">
      <div className="max-w-2xl text-center">
        <div
          className="text-lg font-semibold leading-snug drop-shadow-lg px-5 py-2.5 rounded-lg"
          style={{
            background: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(8px)',
            borderBottom: `2px solid ${EMOTION_COLORS[subtitle.emotion] || EMOTION_COLORS.neutral}`,
          }}
        >
          <span className="text-white">{subtitle.text}</span>
        </div>
        <div className="text-[11px] text-white/50 mt-1 font-mono">{subtitle.original}</div>
      </div>
    </div>
  )
}

// ── Debug overlay ──
function DebugOverlay() {
  const showOverlay = usePlayerStore(s => s.showOverlay)
  const debugMetrics = usePlayerStore(s => s.debugMetrics)
  const dubbingEnabled = usePlayerStore(s => s.dubbingEnabled)
  const dubbingStatus = usePlayerStore(s => s.dubbingStatus)
  const characters = usePlayerStore(s => s.characters)
  const activeCharacters = usePlayerStore(s => s.activeCharacters)

  if (!showOverlay) return null

  return (
    <div className="absolute inset-0 pointer-events-none z-20">
      {characters.filter(c => c.bbox).map((char, i) => {
        const isSpeaking = char.is_speaking || activeCharacters.includes(char.id)
        return (
          <div key={char.id || i} className="absolute transition-all duration-150"
            style={{
              left: `${(char.bbox?.[0] || 0) * 100}%`,
              top: `${(char.bbox?.[1] || 0) * 100}%`,
              width: `${((char.bbox?.[2] || 0) - (char.bbox?.[0] || 0)) * 100}%`,
              height: `${((char.bbox?.[3] || 0) - (char.bbox?.[1] || 0)) * 100}%`
            }}>
            <div className={`absolute inset-0 border-2 rounded-sm ${isSpeaking ? 'border-cs-accent-green' : 'border-cs-accent-blue/40'}`} />
            <div className="absolute -top-6 left-0">
              <span className="text-[10px] font-mono bg-black/70 px-1.5 py-0.5 rounded text-cs-text-primary">{char.name || `Char ${char.id}`}</span>
            </div>
          </div>
        )
      })}
      <div className="absolute top-3 right-3 glass-panel rounded-lg px-3 py-2 space-y-1">
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-mono text-cs-text-muted uppercase">FPS</span>
          <span className="text-[11px] font-mono text-cs-accent-blue font-semibold">{debugMetrics.fps || 0}</span>
        </div>
        {dubbingEnabled && (
          <div className="flex items-center gap-2 border-t border-white/5 pt-1 mt-1">
            <span className="text-[9px] font-mono text-cs-text-muted uppercase">DUB</span>
            <span className="text-[11px] font-mono text-cs-accent-green font-semibold">
              {dubbingStatus.stage === 'active' ? `${dubbingStatus.progress}%` : dubbingStatus.stage}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

export default function VideoPlayer() {
  const mediaUrl = usePlayerStore(s => s.mediaUrl)
  const isPlaying = usePlayerStore(s => s.isPlaying)
  const isLoading = usePlayerStore(s => s.isLoading)
  const { videoRef, togglePlay, onLoadedMetadata, onEnded, onError } = useMediaPlayer()

  const handleDoubleClick = useCallback(() => {
    if (document.fullscreenElement) document.exitFullscreen()
    else document.documentElement.requestFullscreen()
  }, [])

  return (
    <div className="video-container flex-1 relative group" onDoubleClick={handleDoubleClick}>
      {mediaUrl ? (
        <>
          <StableVideo
            videoRef={videoRef}
            mediaUrl={mediaUrl}
            onMeta={onLoadedMetadata}
            onEnd={onEnded}
            onErr={onError}
            onClick={togglePlay}
          />
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/60 z-10">
              <div className="flex flex-col items-center gap-4">
                <div className="w-12 h-12 rounded-full border-2 border-cs-accent-blue/20 border-t-cs-accent-blue animate-spin" />
                <span className="text-xs font-mono text-cs-text-muted">Loading media...</span>
              </div>
            </div>
          )}
          <DebugOverlay />
          <SubtitleOverlay videoRef={videoRef} />
          {!isPlaying && !isLoading && (
            <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
              <div className="w-20 h-20 rounded-full bg-black/40 backdrop-blur-sm flex items-center justify-center border border-white/10">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="white" className="ml-1"><path d="M8 5v14l11-7z" /></svg>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="flex flex-col items-center gap-6 animate-fade-in max-w-lg">
            {/* Logo + glow effect */}
            <div className="relative">
              <div className="absolute inset-0 blur-3xl opacity-20 bg-gradient-to-br from-cs-accent-blue to-cs-accent-purple rounded-full scale-150" />
              <div className="relative w-24 h-24 rounded-2xl bg-gradient-to-br from-cs-accent-blue/20 to-cs-accent-purple/20 flex items-center justify-center border border-white/5 shadow-lg">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" className="text-cs-accent-blue">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z" fill="currentColor" opacity="0.8"/>
                </svg>
              </div>
            </div>

            <div className="text-center space-y-2">
              <h1 className="text-3xl font-bold"><span className="text-gradient-blue">CineSync</span><span className="text-cs-text-primary"> AI</span></h1>
              <p className="text-sm text-cs-text-muted max-w-xs">AI-native cinematic dubbing platform</p>
            </div>

            {/* Drop zone */}
            <div className="w-full max-w-sm border-2 border-dashed border-white/10 hover:border-cs-accent-blue/40 rounded-2xl p-8 text-center transition-all duration-300 hover:bg-cs-accent-blue/3 cursor-pointer group"
              onClick={async () => {
                const filePath = await window.electronAPI?.openFile()
                if (filePath) {
                  const url = await window.electronAPI?.getMediaUrl(filePath)
                  const name = filePath.split(/[/\\]/).pop()
                  usePlayerStore.getState().setFile(filePath, url, name)
                  window.electronAPI?.sendAICommand({ type: 'load_media', data: { filePath } })
                  setTimeout(() => { window.electronAPI?.sendAICommand({ type: 'start_analysis', data: {} }) }, 500)
                }
              }}
            >
              <div className="flex flex-col items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-white/3 flex items-center justify-center group-hover:bg-cs-accent-blue/10 transition-colors">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-cs-text-muted group-hover:text-cs-accent-blue transition-colors">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="17 8 12 3 7 8"/>
                    <line x1="12" y1="3" x2="12" y2="15"/>
                  </svg>
                </div>
                <div>
                  <p className="text-sm text-cs-text-secondary font-medium group-hover:text-cs-text-primary transition-colors">Drop a video file here</p>
                  <p className="text-[11px] text-cs-text-muted mt-1">or click to browse</p>
                </div>
              </div>
            </div>

            {/* Supported formats */}
            <div className="flex items-center gap-3">
              {['MP4', 'MKV', 'MOV', 'AVI', 'WebM'].map(f => (
                <span key={f} className="text-[10px] font-mono text-cs-text-muted/50 px-2 py-0.5 rounded border border-white/5 hover:border-white/10 hover:text-cs-text-muted transition-colors">{f}</span>
              ))}
            </div>

            {/* Quick tips */}
            <div className="flex items-center gap-6 text-[10px] text-cs-text-muted/40">
              <span>Press <kbd className="font-mono bg-white/5 px-1 py-0.5 rounded text-cs-text-muted/60 mx-0.5">Space</kbd> Play/Pause</span>
              <span>Press <kbd className="font-mono bg-white/5 px-1 py-0.5 rounded text-cs-text-muted/60 mx-0.5">D</kbd> Dubbing</span>
              <span>Press <kbd className="font-mono bg-white/5 px-1 py-0.5 rounded text-cs-text-muted/60 mx-0.5">F</kbd> Fullscreen</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
