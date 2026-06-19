import { createContext, useContext, useRef, useCallback, useEffect } from 'react'
import usePlayerStore from '../stores/playerStore'

const MediaPlayerContext = createContext(null)

/**
 * MediaPlayerProvider — syncs video + dubbed audio track.
 * Uses `new Audio()` instead of a DOM <audio> element for reliability in Electron.
 */
export function MediaPlayerProvider({ children }) {
  const videoRef = useRef(null)
  const dubbedAudioRef = useRef(null)   // will hold a JS Audio object (not DOM element)
  const frameCountRef = useRef(0)

  // ── Animation frame: update currentTime ~4x/sec for UI ──
  const tick = useCallback(() => {
    frameCountRef.current++
    const video = videoRef.current
    if (video && !video.paused && frameCountRef.current % 15 === 0) {
      usePlayerStore.setState({ currentTime: video.currentTime })
    }
    requestAnimationFrame(tick)
  }, [])

  useEffect(() => {
    const id = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(id)
  }, [tick])

  // ── Create the Audio object once ──
  useEffect(() => {
    const audio = new Audio()
    audio.preload = 'auto'
    dubbedAudioRef.current = audio

    // Debug
    audio.addEventListener('error', (e) => {
      console.error('[CineSync] Dubbed audio error:', audio.error?.message || e)
    })
    audio.addEventListener('playing', () => {
      console.log('[CineSync] ✓ Dubbed audio PLAYING, volume:', audio.volume, 'muted:', audio.muted)
    })

    return () => {
      audio.pause()
      audio.src = ''
      dubbedAudioRef.current = null
    }
  }, [])

  // ── Sync dubbed audio with video (every 250ms) ──
  useEffect(() => {
    const interval = setInterval(() => {
      const video = videoRef.current
      const audio = dubbedAudioRef.current
      if (!video || !audio || !audio.src) return

      const s = usePlayerStore.getState()

      // Keep video muted when dubbed track is active
      if (s.dubbedTrackUrl) {
        video.muted = true
        video.volume = 0
      }

      // Keep audio in sync with video (within 0.3s tolerance)
      const drift = Math.abs(video.currentTime - audio.currentTime)
      if (drift > 0.3) {
        audio.currentTime = video.currentTime
      }

      // Match play state
      if (!video.paused && audio.paused) {
        audio.play().catch(() => {})
      } else if (video.paused && !audio.paused) {
        audio.pause()
      }
    }, 250)
    return () => clearInterval(interval)
  }, [])

  // ── Watch for dubbed track URL changes ──
  useEffect(() => {
    const unsub = usePlayerStore.subscribe(
      (s) => s.dubbedTrackUrl,
      (url) => {
        const audio = dubbedAudioRef.current
        if (!audio) return

        if (url) {
          console.log('[CineSync] Loading dubbed track:', url)

          // Mute original video
          if (videoRef.current) {
            videoRef.current.muted = true
            videoRef.current.volume = 0
          }

          // Load the dubbed track into our Audio object
          audio.src = url
          audio.load()

          const s = usePlayerStore.getState()
          audio.volume = s.isMuted ? 0 : s.volume
          audio.muted = false

          // When audio is ready, auto-play from beginning
          const onReady = () => {
            audio.removeEventListener('canplaythrough', onReady)
            const video = videoRef.current
            if (!video) return

            video.currentTime = 0
            audio.currentTime = 0
            video.muted = true
            video.volume = 0

            // Play video, then audio
            video.play()
              .then(() => audio.play())
              .then(() => {
                console.log('[CineSync] ✓ Both playing! Audio vol:', audio.volume)
                usePlayerStore.setState({ isPlaying: true, currentTime: 0 })
              })
              .catch((e) => {
                console.warn('[CineSync] Auto-play issue:', e.message)
                // The sync interval will retry
              })
          }
          audio.addEventListener('canplaythrough', onReady, { once: true })

        } else {
          // No dubbed track — restore original audio
          audio.pause()
          audio.src = ''
          if (videoRef.current) {
            const s = usePlayerStore.getState()
            videoRef.current.muted = false
            videoRef.current.volume = s.isMuted ? 0 : s.volume
          }
        }
      }
    )
    return unsub
  }, [])

  // ── Volume changes ──
  useEffect(() => {
    const unsubVol = usePlayerStore.subscribe(
      (s) => s.volume,
      (vol) => {
        const s = usePlayerStore.getState()
        const audio = dubbedAudioRef.current
        if (s.dubbedTrackUrl && audio) {
          if (videoRef.current) { videoRef.current.muted = true; videoRef.current.volume = 0 }
          audio.volume = s.isMuted ? 0 : vol
        } else {
          if (videoRef.current) { videoRef.current.muted = s.isMuted; videoRef.current.volume = s.isMuted ? 0 : vol }
        }
      }
    )
    const unsubMute = usePlayerStore.subscribe(
      (s) => s.isMuted,
      (muted) => {
        const s = usePlayerStore.getState()
        const audio = dubbedAudioRef.current
        if (s.dubbedTrackUrl && audio) {
          if (videoRef.current) { videoRef.current.muted = true; videoRef.current.volume = 0 }
          audio.volume = muted ? 0 : s.volume
        } else {
          if (videoRef.current) { videoRef.current.muted = muted; videoRef.current.volume = muted ? 0 : s.volume }
        }
      }
    )
    return () => { unsubVol(); unsubMute() }
  }, [])

  // ── Playback controls ──
  const play = useCallback(() => {
    if (!videoRef.current) return
    const s = usePlayerStore.getState()
    const isDubbedMode = !!s.dubbedTrackUrl

    if (isDubbedMode) {
      videoRef.current.muted = true
      videoRef.current.volume = 0
    } else {
      videoRef.current.muted = s.isMuted
      videoRef.current.volume = s.isMuted ? 0 : s.volume
    }

    videoRef.current.play().catch(() => {})
    usePlayerStore.setState({ isPlaying: true })

    const audio = dubbedAudioRef.current
    if (isDubbedMode && audio?.src) {
      audio.currentTime = videoRef.current.currentTime
      audio.volume = s.isMuted ? 0 : s.volume
      audio.play().catch(() => {})
    }
  }, [])

  const pause = useCallback(() => {
    if (!videoRef.current) return
    videoRef.current.pause()
    usePlayerStore.setState({ isPlaying: false })
    dubbedAudioRef.current?.pause()
  }, [])

  const togglePlay = useCallback(() => {
    if (videoRef.current?.paused) play(); else pause()
  }, [play, pause])

  const seek = useCallback((time) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time
      usePlayerStore.setState({ currentTime: time })
      if (dubbedAudioRef.current?.src) {
        dubbedAudioRef.current.currentTime = time
      }
    }
  }, [])

  const seekRelative = useCallback((delta) => {
    if (videoRef.current) {
      const t = Math.max(0, Math.min(videoRef.current.duration || 0, videoRef.current.currentTime + delta))
      seek(t)
    }
  }, [seek])

  const onLoadedMetadata = useCallback(() => {
    if (videoRef.current) {
      usePlayerStore.setState({ duration: videoRef.current.duration, isLoading: false })
    }
  }, [])

  const onEnded = useCallback(() => {
    usePlayerStore.setState({ isPlaying: false })
    dubbedAudioRef.current?.pause()
  }, [])

  const onError = useCallback((e) => {
    console.error('[CineSync] Video error:', e.target?.error)
    usePlayerStore.setState({ isLoading: false })
  }, [])

  const value = {
    videoRef, dubbedAudioRef,
    play, pause, togglePlay, seek, seekRelative,
    onLoadedMetadata, onEnded, onError
  }

  return (
    <MediaPlayerContext.Provider value={value}>
      {children}
    </MediaPlayerContext.Provider>
  )
}

export default function useMediaPlayer() {
  const ctx = useContext(MediaPlayerContext)
  if (!ctx) throw new Error('useMediaPlayer must be inside MediaPlayerProvider')
  return ctx
}
