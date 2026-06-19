import { useEffect, useCallback, useRef } from 'react'
import usePlayerStore from '../stores/playerStore'

export default function useWebSocket() {
  // Use refs for store actions to avoid re-renders
  // Actions are stable functions, so we only need to get them once
  const actionsRef = useRef(null)
  if (!actionsRef.current) {
    const s = usePlayerStore.getState()
    actionsRef.current = {
      setAIConnected: s.setAIConnected,
      setCharacters: s.setCharacters,
      setActiveCharacters: s.setActiveCharacters,
      setSyncPercentage: s.setSyncPercentage,
      setDebugMetrics: s.setDebugMetrics,
      addWarning: s.addWarning,
      setDubbingStatus: s.setDubbingStatus,
      addLiveTranscript: s.addLiveTranscript,
      addDubbedSegment: s.addDubbedSegment,
      setVoiceAssignments: s.setVoiceAssignments,
      setDubbedTrackUrl: s.setDubbedTrackUrl,
      setDubbingEnabled: s.setDubbingEnabled,
      setAIProcessing: s.setAIProcessing,
      setGpuWarmup: s.setGpuWarmup,
      setGpuMode: s.setGpuMode,
    }
  }

  useEffect(() => {
    const api = window.electronAPI
    if (!api) return

    const a = actionsRef.current

    const unsubStatus = api.onAIStatus((status) => {
      a.setAIConnected(status.connected)
    })

    const unsubMessage = api.onAIMessage((msg) => {
      switch (msg.type) {
        case 'connected':
          a.setAIConnected(true)
          console.log('[CineSync] AI server connected:', msg.data)
          // Set GPU mode from server
          if (msg.data.mode) {
            a.setGpuMode(msg.data.mode)
          }
          // Auto-trigger GPU warmup for Modal mode
          if (msg.data.mode === 'modal') {
            console.log('[CineSync] Modal mode detected — triggering GPU warmup')
            window.electronAPI?.sendAICommand({ type: 'warmup_gpu', data: {} })
          }
          break
        case 'characters_detected':
          a.setCharacters(msg.data)
          break
        case 'active_speakers':
          a.setActiveCharacters(msg.data)
          break
        case 'sync_update':
          a.setSyncPercentage(msg.data.percentage)
          break
        case 'debug_metrics':
          a.setDebugMetrics(msg.data)
          break
        case 'warning':
          a.addWarning(msg.data)
          break
        case 'analysis_status':
          console.log('[CineSync] Analysis:', msg.data.stage, msg.data.progress + '%')
          a.setAIProcessing(
            msg.data.stage !== 'complete' && msg.data.stage !== 'error'
          )
          break
        case 'media_loaded':
          console.log('[CineSync] Media loaded:', msg.data.filePath)
          break

        // ── Dubbing messages ──
        case 'dubbing_status':
          a.setDubbingStatus(msg.data)
          if (msg.data.stage === 'active' || msg.data.stage === 'loading_stt') {
            a.setDubbingEnabled(true)
          } else if (msg.data.stage === 'stopped' || msg.data.stage === 'error') {
            a.setDubbingEnabled(false)
          }
          break

        case 'dubbed_segment':
          a.addDubbedSegment(msg.data)
          break

        case 'dubbed_track_ready':
          console.log('[CineSync] Dubbed track ready:', msg.data.totalSegments, 'segments')
          if (msg.data.segments) {
            for (const seg of msg.data.segments) {
              a.addDubbedSegment(seg)
            }
          }
          // Use the media:// protocol (same as video) to serve the dubbed audio
          // This bypasses cross-origin issues with http://localhost:8765
          if (msg.data.audioPath && window.electronAPI?.getMediaUrl) {
            window.electronAPI.getMediaUrl(msg.data.audioPath).then((mediaUrl) => {
              console.log('[CineSync] Dubbed track media URL:', mediaUrl)
              a.setDubbedTrackUrl(mediaUrl)
            })
          } else {
            // Fallback to HTTP
            a.setDubbedTrackUrl(
              `http://localhost:8765/dubbed-track?t=${Date.now()}`
            )
          }
          break

        case 'live_transcript':
          a.addLiveTranscript(msg.data)
          break

        case 'voice_assignments':
          a.setVoiceAssignments(msg.data)
          break

        // ── GPU Warmup (Modal) ──
        case 'gpu_warmup':
          a.setGpuWarmup(msg.data)
          if (msg.data.stage === 'ready') {
            console.log('[CineSync] 🎉 Cloud GPU is ready!', msg.data.gpu_info)
            // Auto-dismiss after 2s
            setTimeout(() => {
              a.setGpuWarmup({ stage: 'idle' })
            }, 2000)
          } else if (msg.data.stage === 'error') {
            console.error('[CineSync] GPU warmup failed:', msg.data.detail)
            setTimeout(() => {
              a.setGpuWarmup({ stage: 'idle' })
            }, 5000)
          }
          break

        default:
          break
      }
    })

    // Check initial status — also set GPU mode if already connected
    // (fixes race condition where 'connected' msg arrives before hook registers)
    api.getAIStatus().then((status) => {
      a.setAIConnected(status.connected)
      if (status.connected) {
        // Backend is running Modal mode — set it
        a.setGpuMode('modal')
      }
    })

    // Send playback time to AI every 5s (for dubbing pacing)
    const timeInterval = setInterval(() => {
      const s = usePlayerStore.getState()
      if (s.dubbingEnabled && s.currentTime > 0) {
        api.sendAICommand({
          type: 'playback_time',
          data: { time: s.currentTime }
        })
      }
    }, 5000)

    return () => {
      if (typeof unsubStatus === 'function') unsubStatus()
      if (typeof unsubMessage === 'function') unsubMessage()
      clearInterval(timeInterval)
    }
  }, [])

  const sendCommand = useCallback((type, data = {}) => {
    window.electronAPI?.sendAICommand({ type, data })
  }, [])

  return { sendCommand }
}
