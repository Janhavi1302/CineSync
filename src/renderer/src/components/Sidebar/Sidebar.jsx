import { useCallback } from 'react'
import usePlayerStore from '../../stores/playerStore'
import useWebSocket from '../../hooks/useWebSocket'

const LANGUAGES = [
  { code: 'hi', name: 'Hindi' },
  { code: 'es', name: 'Spanish' },
  { code: 'fr', name: 'French' },
  { code: 'de', name: 'German' },
  { code: 'ja', name: 'Japanese' },
  { code: 'ko', name: 'Korean' },
  { code: 'zh', name: 'Chinese' },
  { code: 'ar', name: 'Arabic' },
  { code: 'pt', name: 'Portuguese' },
  { code: 'ru', name: 'Russian' },
]

const EMOTION_COLORS = {
  anger: '#ef4444', sadness: '#3b82f6', joy: '#22c55e',
  fear: '#a855f7', surprise: '#f59e0b', excitement: '#ec4899',
  neutral: '#6b7280'
}

const STAGE_LABELS = {
  idle: 'Ready',
  loading_stt: 'Loading STT...',
  active: 'Processing',
  complete: 'Complete',
  error: 'Error',
  stopped: 'Stopped',
}

function CharacterCard({ char, isActive }) {
  const emotionColor = EMOTION_COLORS[char.emotion] || EMOTION_COLORS.neutral
  return (
    <div className={`flex items-center gap-3 p-2.5 rounded-lg transition-all duration-200 ${isActive ? 'bg-cs-accent-green/5 border border-cs-accent-green/20' : 'hover:bg-white/3 border border-transparent'}`}>
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold flex-shrink-0 ${isActive ? 'bg-cs-accent-green/15 text-cs-accent-green ring-2 ring-cs-accent-green/30' : 'bg-cs-bg-500 text-cs-text-secondary'}`}>
        {(char.name || 'C')[0].toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-cs-text-primary truncate">{char.name || `Character ${char.id}`}</span>
          {char.is_speaking && <span className="text-[8px] font-mono text-cs-accent-green bg-cs-accent-green/10 px-1 rounded animate-pulse">SPEAKING</span>}
          {isActive && !char.is_speaking && <span className="text-[8px] font-mono text-cs-accent-blue bg-cs-accent-blue/10 px-1 rounded">VISIBLE</span>}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          {char.emotion && char.emotion !== 'neutral' && (
            <span className="text-[8px] font-mono px-1 rounded" style={{ color: emotionColor, backgroundColor: emotionColor + '15', border: `1px solid ${emotionColor}30` }}>
              {char.emotion.toUpperCase()}
            </span>
          )}
          <span className="text-[10px] text-cs-text-muted font-mono">{char.voiceProfile || 'Default'}</span>
          {char.speaking_time > 0 && <span className="text-[9px] text-cs-text-muted font-mono">{char.speaking_time.toFixed(1)}s</span>}
        </div>
      </div>
      {char.confidence > 0 && <span className="text-[10px] font-mono text-cs-text-muted">{Math.round(char.confidence * 100)}%</span>}
    </div>
  )
}

function DiagnosticsCard({ label, value, unit, color, percent }) {
  return (
    <div className="flex items-center justify-between p-2 rounded-lg bg-white/[0.02]">
      <span className="text-[10px] font-mono text-cs-text-muted uppercase">{label}</span>
      <div className="flex items-center gap-2">
        {percent !== undefined && (
          <div className="w-16 h-1 rounded-full bg-white/5 overflow-hidden">
            <div className="h-full rounded-full transition-all duration-300" style={{ width: `${percent}%`, backgroundColor: color }} />
          </div>
        )}
        <span className="text-[11px] font-mono font-semibold" style={{ color }}>{value}{unit}</span>
      </div>
    </div>
  )
}

function TranscriptLine({ t, compact }) {
  const emotionColor = EMOTION_COLORS[t.emotion] || EMOTION_COLORS.neutral
  return (
    <div className="flex gap-2 py-1.5 border-b border-white/[0.03] last:border-0">
      <div className="flex-shrink-0 pt-0.5">
        <span className="text-[9px] font-mono text-cs-text-muted">{t.start?.toFixed(1)}s</span>
      </div>
      <div className="flex-1 min-w-0">
        {!compact && (
          <div className="text-[10px] text-cs-text-muted/60 line-through mb-0.5 truncate">{t.originalText}</div>
        )}
        <div className="text-xs text-cs-text-primary leading-snug">{t.translatedText}</div>
        <div className="flex items-center gap-1.5 mt-0.5">
          {t.emotion && t.emotion !== 'neutral' && (
            <span className="text-[7px] font-mono px-1 rounded" style={{ color: emotionColor, backgroundColor: emotionColor + '10' }}>
              {t.emotion.toUpperCase()}
            </span>
          )}
          <span className="text-[8px] font-mono text-cs-text-muted">
            {t.characterId || 'unknown'}
          </span>
        </div>
      </div>
    </div>
  )
}

export default function Sidebar() {
  const sidebarOpen = usePlayerStore(s => s.sidebarOpen)
  const sidebarTab = usePlayerStore(s => s.sidebarTab)
  const setSidebarTab = usePlayerStore(s => s.setSidebarTab)
  const characters = usePlayerStore(s => s.characters)
  const activeCharacters = usePlayerStore(s => s.activeCharacters)
  const targetLanguage = usePlayerStore(s => s.targetLanguage)
  const setTargetLanguage = usePlayerStore(s => s.setTargetLanguage)
  const dubbingEnabled = usePlayerStore(s => s.dubbingEnabled)
  const dubbingStatus = usePlayerStore(s => s.dubbingStatus)
  const liveTranscripts = usePlayerStore(s => s.liveTranscripts)
  const debugMetrics = usePlayerStore(s => s.debugMetrics)
  const syncPercentage = usePlayerStore(s => s.syncPercentage)
  const warnings = usePlayerStore(s => s.warnings)
  const aiConnected = usePlayerStore(s => s.aiConnected)
  const aiProcessing = usePlayerStore(s => s.aiProcessing)
  const filePath = usePlayerStore(s => s.filePath)
  const gpuMode = usePlayerStore(s => s.gpuMode)
  const gpuWarmup = usePlayerStore(s => s.gpuWarmup)

  const { sendCommand } = useWebSocket()

  const handleStartDubbing = useCallback(() => {
    if (!filePath) return
    sendCommand('start_dubbing', { language: targetLanguage })
  }, [filePath, targetLanguage, sendCommand])

  const handleStopDubbing = useCallback(() => {
    sendCommand('stop_dubbing')
  }, [sendCommand])

  if (!sidebarOpen) return null

  const tabs = [
    { id: 'characters', label: 'Characters', icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg> },
    { id: 'dubbing', label: 'Dubbing', icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/></svg> },
    { id: 'diagnostics', label: 'Diagnostics', icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg> },
  ]

  const isDubbingActive = dubbingStatus.stage === 'active' || dubbingStatus.stage === 'loading_stt'

  return (
    <div className="w-72 glass-panel-solid border-l border-white/5 flex flex-col flex-shrink-0 animate-slide-up overflow-hidden">
      {/* Tabs */}
      <div className="flex border-b border-white/5">
        {tabs.map(tab => (
          <button key={tab.id} onClick={() => setSidebarTab(tab.id)}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-[10px] font-semibold uppercase tracking-wider transition-all ${sidebarTab === tab.id ? 'text-cs-accent-blue border-b-2 border-cs-accent-blue bg-cs-accent-blue/5' : 'text-cs-text-muted hover:text-cs-text-secondary hover:bg-white/[0.02]'}`}>
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {sidebarTab === 'characters' && (
          <div className="p-3 space-y-1">
            <div className="sidebar-section-title">Detected Characters ({characters.length})</div>
            {aiProcessing && (
              <div className="flex items-center gap-2 p-2 rounded-lg bg-cs-accent-blue/5 border border-cs-accent-blue/10 mb-2">
                <div className="w-3 h-3 rounded-full border-2 border-cs-accent-blue/30 border-t-cs-accent-blue animate-spin" />
                <span className="text-[10px] font-mono text-cs-accent-blue">AI analyzing video...</span>
              </div>
            )}
            {characters.length === 0 && !aiProcessing ? (
              <div className="flex flex-col items-center py-8 gap-3">
                <div className="w-12 h-12 rounded-xl bg-cs-bg-500 flex items-center justify-center">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-cs-text-muted"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
                </div>
                <span className="text-xs text-cs-text-muted text-center">No characters detected yet.<br/>Load a video to begin AI analysis.</span>
              </div>
            ) : (
              characters.map((char, i) => (
                <CharacterCard key={char.id || i} char={char} isActive={activeCharacters.includes(char.id)} />
              ))
            )}
          </div>
        )}

        {sidebarTab === 'dubbing' && (
          <div className="p-3 space-y-4">
            {/* Language selector */}
            <div>
              <div className="sidebar-section-title">Target Language</div>
              <select value={targetLanguage} onChange={e => setTargetLanguage(e.target.value)}
                disabled={isDubbingActive}
                className="w-full bg-cs-bg-600 border border-white/10 rounded-lg px-3 py-2 text-sm text-cs-text-primary focus:outline-none focus:border-cs-accent-blue/50 appearance-none cursor-pointer disabled:opacity-50">
                {LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.name}</option>)}
              </select>
            </div>

            {/* Start/Stop dubbing button */}
            <div>
              {isDubbingActive ? (
                <button onClick={handleStopDubbing}
                  className="w-full px-4 py-2.5 rounded-lg bg-cs-accent-red/10 border border-cs-accent-red/30 text-cs-accent-red text-sm font-semibold hover:bg-cs-accent-red/20 transition-all flex items-center justify-center gap-2">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="1"/></svg>
                  Stop Dubbing
                </button>
              ) : (
                <button onClick={handleStartDubbing}
                  disabled={!filePath || !aiConnected}
                  className="w-full px-4 py-2.5 rounded-lg bg-cs-accent-green/10 border border-cs-accent-green/30 text-cs-accent-green text-sm font-semibold hover:bg-cs-accent-green/20 transition-all flex items-center justify-center gap-2 disabled:opacity-30 disabled:cursor-not-allowed">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                    <line x1="12" y1="19" x2="12" y2="23"/>
                  </svg>
                  Start Dubbing
                </button>
              )}
            </div>

            {/* Dubbing Status */}
            <div>
              <div className="sidebar-section-title">Pipeline Status</div>
              <div className={`p-3 rounded-lg border ${isDubbingActive ? 'bg-cs-accent-green/5 border-cs-accent-green/20' : 'bg-white/[0.02] border-white/5'}`}>
                <div className="flex items-center gap-2 mb-2">
                  <div className={`status-dot ${isDubbingActive ? 'status-dot-connected' : 'status-dot-disconnected'}`} />
                  <span className="text-xs font-medium">{STAGE_LABELS[dubbingStatus.stage] || dubbingStatus.stage}</span>
                </div>
                {isDubbingActive && (
                  <>
                    {/* Progress bar */}
                    <div className="w-full h-1.5 rounded-full bg-white/5 overflow-hidden mb-2">
                      <div
                        className="h-full rounded-full bg-cs-accent-green transition-all duration-500"
                        style={{ width: `${dubbingStatus.progress || 0}%` }}
                      />
                    </div>
                    <p className="text-[10px] text-cs-text-muted font-mono">
                      {dubbingStatus.message || 'Processing...'}
                    </p>
                    <div className="flex items-center justify-between mt-1.5">
                      <span className="text-[9px] font-mono text-cs-text-muted">
                        Segments: {dubbingStatus.totalSegments || 0}
                      </span>
                      <span className="text-[9px] font-mono text-cs-text-muted">
                        {(dubbingStatus.chunkTime || 0).toFixed(1)}s/chunk
                      </span>
                    </div>
                  </>
                )}
                {!isDubbingActive && (
                  <p className="text-[10px] text-cs-text-muted">
                    {filePath
                      ? 'Select a language and start dubbing to generate translated audio in real-time.'
                      : 'Load a video first to enable dubbing.'}
                  </p>
                )}
              </div>
            </div>

            {/* Pipeline Stages */}
            <div>
              <div className="sidebar-section-title">Pipeline Stages</div>
              {[
                { name: 'Speech Recognition', icon: '🎙️', key: 'stt' },
                { name: 'Translation', icon: '🌐', key: 'translate' },
                { name: 'Voice Generation', icon: '🗣️', key: 'tts' },
                { name: 'Audio Mixing', icon: '🎵', key: 'mix' },
              ].map((stage, i) => (
                <div key={stage.key} className="flex items-center gap-2 py-1.5">
                  <div className={`w-5 h-5 rounded flex items-center justify-center text-[9px] font-bold ${isDubbingActive ? 'bg-cs-accent-blue/15 text-cs-accent-blue' : 'bg-cs-bg-500 text-cs-text-muted'}`}>{i+1}</div>
                  <span className="text-[10px]">{stage.icon}</span>
                  <span className="text-xs text-cs-text-secondary">{stage.name}</span>
                  <div className="flex-1" />
                  <span className="text-[9px] font-mono text-cs-text-muted">{isDubbingActive ? '●' : '—'}</span>
                </div>
              ))}
            </div>

            {/* Live Transcripts */}
            {liveTranscripts.length > 0 && (
              <div>
                <div className="sidebar-section-title">Live Transcription ({liveTranscripts.length})</div>
                <div className="max-h-48 overflow-y-auto pr-1 space-y-0">
                  {liveTranscripts.slice(-15).reverse().map((t, i) => (
                    <TranscriptLine key={i} t={t} compact={false} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {sidebarTab === 'diagnostics' && (
          <div className="p-3 space-y-3">
            <div className="sidebar-section-title">Performance Metrics</div>
            <DiagnosticsCard label="Sync Accuracy" value={debugMetrics.syncAccuracy || 0} unit="%" color="#22c55e" percent={debugMetrics.syncAccuracy || 0} />
            <DiagnosticsCard label="FPS" value={debugMetrics.fps || 0} unit="" color="#00d4ff" percent={(debugMetrics.fps / 60) * 100} />
            <DiagnosticsCard label="Latency" value={debugMetrics.latency || 0} unit="ms" color={debugMetrics.latency > 500 ? '#ef4444' : '#f59e0b'} percent={Math.min(100, (debugMetrics.latency / 1000) * 100)} />
            <DiagnosticsCard label="Audio Level" value={debugMetrics.audioLevel || 0} unit="dB" color="#7c3aed" percent={Math.abs(debugMetrics.audioLevel || 0) / 60 * 100} />

            <div className="sidebar-section-title mt-4">AI Engine</div>
            <div className="p-3 rounded-lg bg-white/[0.02] border border-white/5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-cs-text-muted">Status</span>
                <div className="flex items-center gap-1.5">
                  <div className={`status-dot ${aiConnected ? 'status-dot-connected' : 'status-dot-disconnected'}`} />
                  <span className="text-[10px] font-mono">{aiConnected ? 'Connected' : 'Disconnected'}</span>
                </div>
              </div>

              {/* GPU Mode Toggle */}
              <div className="space-y-1.5">
                <span className="text-[10px] font-mono text-cs-text-muted">GPU Mode</span>
                <div className="flex rounded-lg overflow-hidden border border-white/10 bg-white/[0.02]">
                  <button
                    onClick={() => usePlayerStore.getState().setGpuMode('local')}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-2 px-3 text-[10px] font-mono transition-all duration-200 ${
                      gpuMode !== 'modal'
                        ? 'bg-cs-accent-amber/15 text-cs-accent-amber border-r border-cs-accent-amber/20'
                        : 'text-cs-text-muted hover:bg-white/[0.03] border-r border-white/5'
                    }`}
                  >
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="4" y="6" width="16" height="12" rx="2" />
                      <path d="M8 6V4M16 6V4M8 18v2M16 18v2" strokeLinecap="round" />
                    </svg>
                    Local GPU
                  </button>
                  <button
                    onClick={() => usePlayerStore.getState().setGpuMode('modal')}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-2 px-3 text-[10px] font-mono transition-all duration-200 ${
                      gpuMode === 'modal'
                        ? 'bg-cs-accent-purple/15 text-cs-accent-purple'
                        : 'text-cs-text-muted hover:bg-white/[0.03]'
                    }`}
                  >
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                    </svg>
                    Cloud T4
                  </button>
                </div>
              </div>

              {/* GPU Info */}
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-cs-text-muted">GPU</span>
                <span className={`text-[10px] font-mono ${gpuMode === 'modal' ? 'text-cs-accent-purple' : 'text-cs-accent-amber'}`}>
                  {gpuMode === 'modal' ? '⚡ Modal T4 (16GB)' : 'GTX 1650 (4GB)'}
                </span>
              </div>

              {/* GPU Status (Modal) */}
              {gpuMode === 'modal' && (
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono text-cs-text-muted">Cloud GPU</span>
                  <span className={`text-[10px] font-mono ${
                    gpuWarmup.stage === 'ready' ? 'text-cs-accent-green' :
                    gpuWarmup.stage === 'warming' ? 'text-cs-accent-amber animate-pulse' :
                    gpuWarmup.stage === 'error' ? 'text-cs-accent-red' :
                    'text-cs-text-muted'
                  }`}>
                    {gpuWarmup.stage === 'warming' ? `⏳ Warming ${gpuWarmup.progress}%` :
                     gpuWarmup.stage === 'ready' ? '● Online' :
                     gpuWarmup.stage === 'error' ? '✗ Error' :
                     '○ Standby'}
                  </span>
                </div>
              )}

              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-cs-text-muted">Dubbing</span>
                <span className={`text-[10px] font-mono ${isDubbingActive ? 'text-cs-accent-green' : 'text-cs-text-muted'}`}>
                  {isDubbingActive ? `Active (${dubbingStatus.totalSegments || 0} segs)` : 'Idle'}
                </span>
              </div>
            </div>

            {warnings.length > 0 && (
              <>
                <div className="sidebar-section-title mt-4">Warnings ({warnings.length})</div>
                {warnings.slice(-5).map((w, i) => (
                  <div key={i} className="p-2 rounded-lg bg-cs-accent-red/5 border border-cs-accent-red/10 text-[10px] text-cs-accent-red">
                    {w.message}
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
