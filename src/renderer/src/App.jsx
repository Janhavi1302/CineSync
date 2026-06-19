import { useEffect, useCallback } from 'react'
import { MediaPlayerProvider } from './hooks/useMediaPlayer'
import TitleBar from './components/TitleBar/TitleBar'
import VideoPlayer from './components/VideoPlayer/VideoPlayer'
import ControlBar from './components/ControlBar/ControlBar'
import Timeline from './components/Timeline/Timeline'
import Sidebar from './components/Sidebar/Sidebar'
import GPUWarmup from './components/GPUWarmup/GPUWarmup'
import usePlayerStore from './stores/playerStore'
import useWebSocket from './hooks/useWebSocket'

export default function App() {
  const mediaUrl = usePlayerStore(s => s.mediaUrl)
  useWebSocket()

  // Keyboard shortcuts
  const handleKeyDown = useCallback((e) => {
    // Don't capture when typing in inputs
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return

    const store = usePlayerStore.getState()
    switch (e.code) {
      case 'Space':
        e.preventDefault()
        store.setIsPlaying(!store.isPlaying)
        break
      case 'KeyM':
        store.toggleMute()
        break
      case 'KeyO':
        store.toggleOverlay()
        break
      case 'KeyB':
        store.toggleSidebar()
        break
      case 'KeyD':
        store.toggleDubbing()
        break
      case 'KeyT':
        store.toggleTimeline()
        break
      case 'KeyF':
        if (document.fullscreenElement) {
          document.exitFullscreen()
          store.setFullscreen(false)
        } else {
          document.documentElement.requestFullscreen()
          store.setFullscreen(true)
        }
        break
      case 'ArrowLeft':
        e.preventDefault()
        store.setCurrentTime(Math.max(0, store.currentTime - 5))
        break
      case 'ArrowRight':
        e.preventDefault()
        store.setCurrentTime(Math.min(store.duration, store.currentTime + 5))
        break
      default:
        break
    }
  }, [])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  // Handle file drop
  useEffect(() => {
    const handleDrop = async (e) => {
      e.preventDefault()
      const file = e.dataTransfer?.files?.[0]
      if (file) {
        const ext = file.name.split('.').pop()?.toLowerCase()
        if (['mp4', 'mkv', 'mov', 'avi', 'webm'].includes(ext)) {
          const url = await window.electronAPI?.getMediaUrl(file.path)
          if (url) {
            usePlayerStore.getState().setFile(file.path, url, file.name)
            // Notify AI server about the new file
            window.electronAPI?.sendAICommand({
              type: 'load_media',
              data: { filePath: file.path }
            })
            // Auto-start analysis after a short delay
            setTimeout(() => {
              window.electronAPI?.sendAICommand({ type: 'start_analysis', data: {} })
            }, 500)
          }
        }
      }
    }
    const handleDragOver = (e) => e.preventDefault()
    window.addEventListener('drop', handleDrop)
    window.addEventListener('dragover', handleDragOver)
    return () => {
      window.removeEventListener('drop', handleDrop)
      window.removeEventListener('dragover', handleDragOver)
    }
  }, [])

  return (
    <MediaPlayerProvider>
      <div className="flex flex-col h-screen w-screen bg-cs-bg-900 overflow-hidden">
        {/* GPU Warmup Overlay (Modal cold start) */}
        <GPUWarmup />

        {/* Title Bar */}
        <TitleBar />

        {/* Main Content */}
        <div className="flex flex-1 min-h-0 overflow-hidden">
          {/* Video + Controls */}
          <div className="flex flex-col flex-1 min-w-0">
            <VideoPlayer />
            <ControlBar />
            <Timeline />
          </div>

          {/* Sidebar */}
          <Sidebar />
        </div>
      </div>
    </MediaPlayerProvider>
  )
}
