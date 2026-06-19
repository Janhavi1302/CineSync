import { contextBridge, ipcRenderer } from 'electron'

// ── Secure IPC Bridge ────────────────────────────────────────
// Exposes a safe API to the renderer process without exposing
// Node.js internals or raw IPC channels.

contextBridge.exposeInMainWorld('electronAPI', {
  // ── Window Controls ──
  minimize: () => ipcRenderer.send('window:minimize'),
  maximize: () => ipcRenderer.send('window:maximize'),
  close: () => ipcRenderer.send('window:close'),
  isMaximized: () => ipcRenderer.invoke('window:isMaximized'),

  // ── File Operations ──
  openFile: () => ipcRenderer.invoke('dialog:openFile'),
  getMediaUrl: (filePath) => ipcRenderer.invoke('media:getUrl', filePath),

  // ── AI Server Communication ──
  sendAICommand: (command) => ipcRenderer.send('ai:send', command),
  getAIStatus: () => ipcRenderer.invoke('ai:getStatus'),

  onAIMessage: (callback) => {
    const handler = (_, data) => callback(data)
    ipcRenderer.on('ai:message', handler)
    return () => ipcRenderer.removeListener('ai:message', handler)
  },

  onAIAudioChunk: (callback) => {
    const handler = (_, data) => callback(data)
    ipcRenderer.on('ai:audio-chunk', handler)
    return () => ipcRenderer.removeListener('ai:audio-chunk', handler)
  },

  onAIStatus: (callback) => {
    const handler = (_, data) => callback(data)
    ipcRenderer.on('ai:status', handler)
    return () => ipcRenderer.removeListener('ai:status', handler)
  }
})
