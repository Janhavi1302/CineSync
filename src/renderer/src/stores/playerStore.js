import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'

const usePlayerStore = create(subscribeWithSelector((set, get) => ({
  // ── Media State ──
  filePath: null,
  mediaUrl: null,
  fileName: null,
  duration: 0,
  currentTime: 0,
  isPlaying: false,
  volume: 0.8,
  isMuted: false,
  playbackRate: 1,
  isLoading: false,

  // ── UI State ──
  sidebarOpen: true,
  sidebarTab: 'characters', // characters | dubbing | diagnostics
  showOverlay: true,
  showTimeline: true,
  isFullscreen: false,

  // ── AI State ──
  aiConnected: false,
  aiProcessing: false,
  characters: [],
  activeCharacters: [],
  dubbingEnabled: false,
  targetLanguage: 'hi',
  syncPercentage: 0,

  // ── Dubbing State ──
  dubbingStatus: {
    stage: 'idle',      // idle | loading_stt | active | complete | error | stopped
    language: 'hi',
    progress: 0,
    message: '',
    processedTo: 0,
    totalSegments: 0,
    chunkTime: 0,
  },
  liveTranscripts: [],     // { start, end, originalText, translatedText, characterId, emotion }
  dubbedSegments: [],      // { start, end, translatedText, ... } (metadata only, no audio)
  dubbedTrackUrl: null,    // URL to the complete dubbed audio track
  currentSubtitle: null,   // { text, originalText, characterId }
  voiceAssignments: {},    // characterId → { voice, label }

  // ── GPU Warmup (Modal) ──
  gpuWarmup: {
    stage: 'idle',         // idle | warming | ready | error
    progress: 0,
    message: '',
    detail: '',
    elapsed: 0,
    maxWait: 120,
    gpu_info: null,
  },
  gpuMode: 'local',        // 'modal' or 'local'

  // ── Debug / Analytics ──
  debugMetrics: {
    fps: 0,
    latency: 0,
    syncAccuracy: 0,
    audioLevel: 0
  },
  aiMarkers: [],
  warnings: [],

  // ── Actions ──
  setFile: (filePath, mediaUrl, fileName) =>
    set({ filePath, mediaUrl, fileName, isLoading: true, currentTime: 0 }),

  setDuration: (duration) => set({ duration }),
  setCurrentTime: (currentTime) => set({ currentTime }),
  setIsPlaying: (isPlaying) => set({ isPlaying }),
  setIsLoading: (isLoading) => set({ isLoading }),
  setVolume: (volume) => set({ volume, isMuted: volume === 0 }),

  toggleMute: () => {
    const { isMuted, volume } = get()
    set({ isMuted: !isMuted })
  },

  setPlaybackRate: (playbackRate) => set({ playbackRate }),

  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarTab: (sidebarTab) => set({ sidebarTab }),
  toggleOverlay: () => set((s) => ({ showOverlay: !s.showOverlay })),
  toggleTimeline: () => set((s) => ({ showTimeline: !s.showTimeline })),
  setFullscreen: (isFullscreen) => set({ isFullscreen }),

  // AI actions
  setAIConnected: (aiConnected) => set({ aiConnected }),
  setAIProcessing: (aiProcessing) => set({ aiProcessing }),
  setCharacters: (characters) => set({ characters }),
  setActiveCharacters: (activeCharacters) => set({ activeCharacters }),

  toggleDubbing: () => set((s) => ({ dubbingEnabled: !s.dubbingEnabled })),
  setDubbingEnabled: (dubbingEnabled) => set({ dubbingEnabled }),
  setTargetLanguage: (targetLanguage) => set({ targetLanguage }),
  setSyncPercentage: (syncPercentage) => set({ syncPercentage }),
  setDebugMetrics: (debugMetrics) => set({ debugMetrics }),
  addAIMarker: (marker) => set((s) => ({ aiMarkers: [...s.aiMarkers, marker] })),
  addWarning: (warning) => set((s) => ({ warnings: [...s.warnings, warning] })),
  clearWarnings: () => set({ warnings: [] }),

  // Dubbing actions
  setDubbingStatus: (status) => set((s) => ({
    dubbingStatus: { ...s.dubbingStatus, ...status }
  })),

  addLiveTranscript: (transcript) => set((s) => ({
    liveTranscripts: [...s.liveTranscripts.slice(-50), transcript]
  })),

  addDubbedSegment: (segment) => set((s) => ({
    dubbedSegments: [...s.dubbedSegments, segment]
  })),

  setCurrentSubtitle: (subtitle) => set({ currentSubtitle: subtitle }),
  setVoiceAssignments: (assignments) => set({ voiceAssignments: assignments }),
  setDubbedTrackUrl: (url) => set({ dubbedTrackUrl: url }),

  // GPU Warmup actions
  setGpuWarmup: (warmup) => set((s) => ({
    gpuWarmup: { ...s.gpuWarmup, ...warmup }
  })),
  setGpuMode: (mode) => set({ gpuMode: mode }),

  clearDubbingState: () => set({
    liveTranscripts: [],
    dubbedSegments: [],
    dubbedTrackUrl: null,
    currentSubtitle: null,
    dubbingStatus: {
      stage: 'idle', language: 'hi', progress: 0,
      message: '', processedTo: 0, totalSegments: 0, chunkTime: 0,
    }
  }),

  // Reset
  reset: () =>
    set({
      filePath: null,
      mediaUrl: null,
      fileName: null,
      duration: 0,
      currentTime: 0,
      isPlaying: false,
      isLoading: false,
      characters: [],
      activeCharacters: [],
      aiMarkers: [],
      warnings: [],
      syncPercentage: 0,
      liveTranscripts: [],
      dubbedSegments: [],
      currentSubtitle: null,
      dubbingStatus: {
        stage: 'idle', language: 'hi', progress: 0,
        message: '', processedTo: 0, totalSegments: 0, chunkTime: 0,
      }
    })
})))

export default usePlayerStore
