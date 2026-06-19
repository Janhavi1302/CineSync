import { useState, useEffect } from 'react'
import usePlayerStore from '../../stores/playerStore'

// ── SVG Icons ─────────────────────────────────────────────────
const MinimizeIcon = () => (
  <svg width="10" height="1" viewBox="0 0 10 1" fill="currentColor">
    <rect width="10" height="1" rx="0.5" />
  </svg>
)

const MaximizeIcon = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.2">
    <rect x="0.5" y="0.5" width="9" height="9" rx="1.5" />
  </svg>
)

const RestoreIcon = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.2">
    <rect x="0.5" y="2.5" width="7" height="7" rx="1" />
    <path d="M2.5 2.5V1.5C2.5 0.948 2.948 0.5 3.5 0.5H8.5C9.052 0.5 9.5 0.948 9.5 1.5V6.5C9.5 7.052 9.052 7.5 8.5 7.5H7.5" />
  </svg>
)

const CloseIcon = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.4">
    <path d="M1 1L9 9M9 1L1 9" />
  </svg>
)

export default function TitleBar() {
  const [isMaximized, setIsMaximized] = useState(false)
  const fileName = usePlayerStore(s => s.fileName)
  const aiConnected = usePlayerStore(s => s.aiConnected)
  const gpuMode = usePlayerStore(s => s.gpuMode)

  useEffect(() => {
    const check = async () => {
      const max = await window.electronAPI?.isMaximized()
      setIsMaximized(!!max)
    }
    check()
  }, [])

  const handleMinimize = () => window.electronAPI?.minimize()
  const handleMaximize = async () => {
    window.electronAPI?.maximize()
    const max = await window.electronAPI?.isMaximized()
    setIsMaximized(!!max)
  }
  const handleClose = () => window.electronAPI?.close()

  return (
    <div className="drag-region flex items-center justify-between h-10 px-4 glass-panel-solid border-b border-white/5 z-50 flex-shrink-0">
      {/* Left: Logo + Title */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 no-drag">
          <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-cs-accent-blue to-cs-accent-purple flex items-center justify-center shadow-glow-blue">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="white">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/>
            </svg>
          </div>
          <span className="text-sm font-bold tracking-wide">
            <span className="text-gradient-blue">Cine</span>
            <span className="text-cs-text-primary">Sync</span>
            <span className="text-cs-text-muted text-xs font-normal ml-1">AI</span>
          </span>
        </div>

        <div className="divider-v" />

        {/* File name */}
        {fileName && (
          <span className="text-xs text-cs-text-secondary truncate max-w-[300px]">
            {fileName}
          </span>
        )}
      </div>

      {/* Center: AI Status + GPU Mode */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className={`status-dot ${aiConnected ? 'status-dot-connected' : 'status-dot-disconnected'}`} />
          <span className="text-[10px] font-mono text-cs-text-muted uppercase tracking-wider">
            {aiConnected ? 'AI Engine Online' : 'AI Engine Offline'}
          </span>
        </div>
        {aiConnected && gpuMode === 'modal' && (
          <>
            <div className="divider-v" />
            <div className="flex items-center gap-1.5">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#7c3aed" strokeWidth="2">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
              <span className="text-[10px] font-mono text-cs-accent-purple uppercase tracking-wider">
                Modal T4
              </span>
            </div>
          </>
        )}
      </div>

      {/* Right: Window Controls */}
      <div className="flex items-center gap-0.5 no-drag">
        <button
          onClick={handleMinimize}
          className="w-10 h-8 flex items-center justify-center rounded text-cs-text-muted hover:text-cs-text-primary hover:bg-white/5 transition-all duration-150"
          title="Minimize"
        >
          <MinimizeIcon />
        </button>
        <button
          onClick={handleMaximize}
          className="w-10 h-8 flex items-center justify-center rounded text-cs-text-muted hover:text-cs-text-primary hover:bg-white/5 transition-all duration-150"
          title={isMaximized ? 'Restore' : 'Maximize'}
        >
          {isMaximized ? <RestoreIcon /> : <MaximizeIcon />}
        </button>
        <button
          onClick={handleClose}
          className="w-10 h-8 flex items-center justify-center rounded text-cs-text-muted hover:text-red-400 hover:bg-red-500/10 transition-all duration-150"
          title="Close"
        >
          <CloseIcon />
        </button>
      </div>
    </div>
  )
}
