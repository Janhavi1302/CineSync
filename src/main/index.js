import { app, shell, BrowserWindow, ipcMain, dialog, protocol, net } from 'electron'
import { join, extname, dirname } from 'path'
import { existsSync } from 'fs'
import { pathToFileURL } from 'url'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import { WebSocket } from 'ws'
import { spawn } from 'child_process'

// ── Register media:// as privileged (MUST be before app.whenReady) ────
protocol.registerSchemesAsPrivileged([
  {
    scheme: 'media',
    privileges: {
      standard: true,
      secure: true,
      stream: true,
      supportFetchAPI: true,
      bypassCSP: true
    }
  }
])

// GPU acceleration — must be set before app.whenReady()
app.commandLine.appendSwitch('enable-gpu-rasterization')
app.commandLine.appendSwitch('enable-zero-copy')
app.commandLine.appendSwitch('ignore-gpu-blocklist')
app.commandLine.appendSwitch('enable-accelerated-video-decode')
app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required')

// ── AI Server WebSocket ──────────────────────────────────────
let aiSocket = null
let mainWindow = null
let aiProcess = null
let reconnectTimer = null
let isConnecting = false
const AI_SERVER_URL = 'ws://localhost:8765/ws'

function scheduleReconnect(delayMs = 5000) {
  // Prevent multiple reconnect timers from stacking
  if (reconnectTimer) return
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    connectToAIServer()
  }, delayMs)
}

function connectToAIServer() {
  // Guard: don't create parallel connections
  if (isConnecting) return
  isConnecting = true

  // Clean up any existing socket
  if (aiSocket) {
    try {
      aiSocket.removeAllListeners()
      aiSocket.close()
    } catch { /* ignore */ }
    aiSocket = null
  }

  try {
    aiSocket = new WebSocket(AI_SERVER_URL)

    aiSocket.on('open', () => {
      console.log('[CineSync] Connected to AI server ✓')
      isConnecting = false
      mainWindow?.webContents.send('ai:status', { connected: true })
    })

    aiSocket.on('message', (data) => {
      try {
        const msg = JSON.parse(data.toString())
        mainWindow?.webContents.send('ai:message', msg)
      } catch {
        // binary data (audio chunks)
        mainWindow?.webContents.send('ai:audio-chunk', data)
      }
    })

    aiSocket.on('close', () => {
      isConnecting = false
      mainWindow?.webContents.send('ai:status', { connected: false })
      scheduleReconnect(5000)
    })

    aiSocket.on('error', (err) => {
      // Error always fires before close — just mark not connecting
      // The 'close' handler will schedule the reconnect
      isConnecting = false
    })
  } catch {
    isConnecting = false
    scheduleReconnect(5000)
  }
}

// ── AI Engine Process Management ─────────────────────────────
let aiRestartCount = 0
const MAX_AI_RESTARTS = 5

function getAIEnginePath() {
  if (is.dev) {
    // Dev mode: ai-engine is in project root
    return join(process.cwd(), 'ai-engine')
  } else {
    // Production: ai-engine is bundled in resources
    return join(process.resourcesPath, 'ai-engine')
  }
}

function findPythonCmd() {
  // Try to find a working Python 3.11 command
  const { execSync } = require('child_process')
  
  // List of commands to try, in priority order
  const candidates = [
    { cmd: 'py', args: ['-3.11'] },       // Windows Python Launcher
    { cmd: 'py', args: ['-3'] },           // Any Python 3
    { cmd: 'python', args: [] },           // Generic python
    { cmd: 'python3', args: [] },          // Unix-style
  ]

  // Also check common install paths on Windows
  const commonPaths = [
    join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python311', 'python.exe'),
    join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python312', 'python.exe'),
    'C:\\Python311\\python.exe',
    'C:\\Python312\\python.exe',
  ]

  for (const p of commonPaths) {
    if (p && existsSync(p)) {
      candidates.push({ cmd: p, args: [] })
    }
  }

  // Test each candidate
  for (const { cmd, args } of candidates) {
    try {
      const testCmd = [cmd, ...args, '-c', '"print(1)"'].join(' ')
      execSync(testCmd, { timeout: 5000, stdio: 'pipe', shell: true })
      console.log(`[CineSync] Found Python: ${cmd} ${args.join(' ')}`)
      return { cmd, args }
    } catch {
      // Try next
    }
  }

  // Fallback
  console.error('[CineSync] No Python found! Falling back to py -3.11')
  return { cmd: 'py', args: ['-3.11'] }
}

function startAIEngine() {
  const aiEnginePath = getAIEnginePath()
  
  // Priority 1: Check for bundled standalone exe (PyInstaller build)
  const bundledExe = join(aiEnginePath, 'cinesync-ai-engine', 'cinesync-ai-engine.exe')
  const hasBundledExe = existsSync(bundledExe)

  // Priority 2: Check for Python + main.py
  const mainPy = join(aiEnginePath, 'main.py')
  const hasPython = existsSync(mainPy)

  if (!hasBundledExe && !hasPython) {
    console.error('[CineSync] AI engine not found at:', aiEnginePath)
    mainWindow?.webContents.send('ai:status', { 
      connected: false, 
      error: `AI engine not found at: ${aiEnginePath}` 
    })
    return
  }

  let cmd, spawnArgs, cwd

  if (hasBundledExe) {
    // Use the standalone exe — no Python required!
    cmd = bundledExe
    spawnArgs = ['--no-reload']
    cwd = join(aiEnginePath, 'cinesync-ai-engine')
    console.log(`[CineSync] Starting AI engine (standalone): ${bundledExe}`)
  } else {
    // Fallback to Python
    const python = findPythonCmd()
    cmd = python.cmd
    spawnArgs = [...python.args, mainPy, '--no-reload']
    cwd = aiEnginePath
    console.log(`[CineSync] Starting AI engine (Python): ${cmd} ${spawnArgs.join(' ')}`)
  }

  console.log(`[CineSync] Working dir: ${cwd}`)

  try {
    aiProcess = spawn(cmd, spawnArgs, {
      cwd: cwd,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: {
        ...process.env,
        PYTHONIOENCODING: 'utf-8',
        PYTHONUTF8: '1',
      },
      shell: process.platform === 'win32' && !hasBundledExe,
      detached: false,
    })

    aiProcess.stdout.on('data', (data) => {
      const lines = data.toString().trim()
      if (lines) console.log('[AI]', lines)
    })

    aiProcess.stderr.on('data', (data) => {
      const lines = data.toString().trim()
      if (lines) console.log('[AI-ERR]', lines)
    })

    aiProcess.on('error', (err) => {
      console.error('[CineSync] Failed to start AI engine:', err.message)
      aiProcess = null
      maybeRestartAIEngine()
    })

    aiProcess.on('exit', (code, signal) => {
      console.log(`[CineSync] AI engine exited (code=${code}, signal=${signal})`)
      aiProcess = null
      // Auto-restart if it crashed (non-zero exit) and we haven't exceeded retries
      if (code !== 0 && code !== null) {
        maybeRestartAIEngine()
      }
    })

    console.log('[CineSync] AI engine process started (PID:', aiProcess.pid, ')')

  } catch (err) {
    console.error('[CineSync] Error spawning AI engine:', err.message)
    maybeRestartAIEngine()
  }
}

function maybeRestartAIEngine() {
  if (aiRestartCount < MAX_AI_RESTARTS) {
    aiRestartCount++
    const delay = aiRestartCount * 3000 // 3s, 6s, 9s...
    console.log(`[CineSync] Restarting AI engine in ${delay/1000}s (attempt ${aiRestartCount}/${MAX_AI_RESTARTS})...`)
    setTimeout(startAIEngine, delay)
  } else {
    console.error('[CineSync] AI engine failed after', MAX_AI_RESTARTS, 'attempts. Giving up.')
    mainWindow?.webContents.send('ai:status', { 
      connected: false, 
      error: 'AI engine failed to start. Is Python 3.11 installed?' 
    })
  }
}

function stopAIEngine() {
  if (!aiProcess) return

  console.log('[CineSync] Stopping AI engine (PID:', aiProcess.pid, ')...')
  try {
    // On Windows, use taskkill to kill the process tree
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', String(aiProcess.pid), '/f', '/t'], { shell: true })
    } else {
      aiProcess.kill('SIGTERM')
      // Force kill after 3 seconds if it hasn't stopped
      setTimeout(() => {
        if (aiProcess && !aiProcess.killed) {
          aiProcess.kill('SIGKILL')
        }
      }, 3000)
    }
  } catch (err) {
    console.error('[CineSync] Error stopping AI engine:', err.message)
  }
  aiProcess = null
}

// ── MIME type map ────────────────────────────────────────────
const MIME_TYPES = {
  '.mp4': 'video/mp4',
  '.mkv': 'video/x-matroska',
  '.mov': 'video/quicktime',
  '.avi': 'video/x-msvideo',
  '.webm': 'video/webm',
  '.mp3': 'audio/mpeg',
  '.wav': 'audio/wav',
  '.ogg': 'audio/ogg',
  '.srt': 'text/plain',
  '.ass': 'text/plain',
  '.vtt': 'text/vtt',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.png': 'image/png',
  '.webp': 'image/webp'
}

// ── Window Creation ──────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1280,
    minHeight: 720,
    frame: false,
    titleBarStyle: 'hidden',
    backgroundColor: '#0a0a0f',
    show: false,
    webPreferences: {
      preload: join(__dirname, '../preload/index.mjs'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false
    }
  })


  mainWindow.on('ready-to-show', () => {
    mainWindow.show()
    // Open DevTools in dev mode to catch renderer errors
    if (is.dev) mainWindow.webContents.openDevTools({ mode: 'detach' })
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  // Load the app
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

// ── Custom media:// protocol ─────────────────────────────────
function registerMediaProtocol() {
  protocol.handle('media', (request) => {
    // Parse the URL properly: media://file/<encodedPath>
    let filePath
    try {
      const url = new URL(request.url)
      filePath = decodeURIComponent(url.pathname.slice(1)) // remove leading /
    } catch {
      filePath = decodeURIComponent(request.url.replace(/^media:\/\/[^/]*\//, ''))
    }

    if (!filePath || !existsSync(filePath)) {
      console.error('[CineSync] File not found:', filePath)
      return new Response('File not found', { status: 404 })
    }

    // Use pathToFileURL for correct Windows path → file:// conversion
    const fileUrl = pathToFileURL(filePath).href

    // CRITICAL: Forward request headers (especially Range) for video streaming
    // Without this, the video element only gets the first ~2s of data and stalls
    return net.fetch(fileUrl, {
      method: request.method,
      headers: request.headers
    })
  })
}

// ── IPC Handlers ─────────────────────────────────────────────

// Window controls
ipcMain.on('window:minimize', () => mainWindow?.minimize())
ipcMain.on('window:maximize', () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize()
  } else {
    mainWindow?.maximize()
  }
})
ipcMain.on('window:close', () => mainWindow?.close())
ipcMain.handle('window:isMaximized', () => mainWindow?.isMaximized())

// File dialog
ipcMain.handle('dialog:openFile', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Open Media File',
    filters: [
      {
        name: 'Video Files',
        extensions: ['mp4', 'mkv', 'mov', 'avi', 'webm']
      },
      {
        name: 'Audio Files',
        extensions: ['mp3', 'wav', 'ogg', 'flac']
      },
      { name: 'All Files', extensions: ['*'] }
    ],
    properties: ['openFile']
  })

  if (result.canceled) return null
  return result.filePaths[0]
})

// Get media URL for renderer
ipcMain.handle('media:getUrl', (_, filePath) => {
  // Use media:// protocol for proper streaming/range request support
  const url = `media://file/${encodeURIComponent(filePath)}`
  console.log('[CineSync] Serving media:', filePath, '→', url)
  return url
})

// AI Server commands
ipcMain.on('ai:send', (_, command) => {
  if (aiSocket?.readyState === WebSocket.OPEN) {
    aiSocket.send(JSON.stringify(command))
  }
})

ipcMain.handle('ai:getStatus', () => {
  return { connected: aiSocket?.readyState === WebSocket.OPEN }
})

// ── App Lifecycle ────────────────────────────────────────────
app.whenReady().then(() => {
  electronApp.setAppUserModelId('com.cinesync.ai')
  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  registerMediaProtocol()
  createWindow()

  // Start AI engine FIRST, then connect once it's ready
  startAIEngine()
  // Give the Python server ~3s to boot before first WS connection attempt
  setTimeout(connectToAIServer, 3000)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  // Stop AI engine when app closes
  stopAIEngine()
  if (aiSocket) {
    aiSocket.close()
    aiSocket = null
  }
  if (process.platform !== 'darwin') app.quit()
})

// Also cleanup on explicit quit (e.g., Cmd+Q on macOS)
app.on('before-quit', () => {
  stopAIEngine()
})

