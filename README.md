# 🎬 CineSync AI

**AI-native real-time cinematic dubbing platform**

CineSync AI is a desktop application that automatically dubs video content into multiple languages using AI. It performs real-time speech recognition, translation, voice synthesis with emotion-aware neural voices, and produces a complete dubbed audio track — all running locally on your GPU.

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Running the Application](#-running-the-application)
- [Usage Guide](#-usage-guide)
- [Keyboard Shortcuts](#-keyboard-shortcuts)
- [Project Structure](#-project-structure)
- [AI Pipeline](#-ai-pipeline)
- [WebSocket Protocol](#-websocket-protocol)
- [Configuration](#-configuration)
- [Supported Languages](#-supported-languages)
- [Troubleshooting](#-troubleshooting)

---

## ✨ Features

| Feature                       | Description                                                             |
| ----------------------------- | ----------------------------------------------------------------------- |
| 🎙️ **Speech Recognition**     | Real-time STT using `faster-whisper` (GPU-accelerated)                  |
| 🌐 **Translation**            | Multi-language translation via `deep-translator` (Google Translate API) |
| 🗣️ **Neural TTS**             | Premium Microsoft Edge Neural voices with emotion styling               |
| 🎭 **Emotion Detection**      | Keyword-based emotion classifier with punctuation boosting              |
| 👥 **Speaker Identification** | Per-segment pitch analysis for gender-consistent voice assignment       |
| 🔒 **Voice Locking**          | Each character keeps the same voice throughout the entire video         |
| 🎵 **Audio Mixing**           | Background audio preservation with TTS overlay                          |
| 📸 **Screenshot**             | Capture video frames as PNG                                             |
| ⬇️ **Export**                 | Download the complete dubbed audio track                                |
| 📊 **Live Metrics**           | Real-time FPS, latency, sync accuracy, and audio level                  |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Electron Desktop App                │
│  ┌───────────┐  ┌───────────┐  ┌──────────────────┐ │
│  │ TitleBar   │  │ VideoPlayer│  │ Sidebar          │ │
│  │           │  │ + Subtitle │  │ • Characters     │ │
│  │           │  │ + Overlay  │  │ • Dubbing        │ │
│  │           │  │           │  │ • Diagnostics    │ │
│  ├───────────┤  ├───────────┤  └──────────────────┘ │
│  │ ControlBar │  │ Timeline   │                      │
│  │ (controls) │  │ (waveform) │                      │
│  └───────────┘  └───────────┘                       │
│                         │                            │
│              WebSocket (ws://localhost:8765/ws)       │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────┐
│                Python AI Engine (FastAPI)             │
│  ┌────────┐ ┌──────────┐ ┌────────┐ ┌────────────┐  │
│  │ STT    │→│ Translate │→│ TTS    │→│ Audio Mix  │  │
│  │Whisper │ │  Google   │ │EdgeTTS │ │  pydub     │  │
│  └────────┘ └──────────┘ └────────┘ └────────────┘  │
│  ┌────────────────┐  ┌──────────────────────────┐    │
│  │ Speaker ID     │  │ Emotion Classifier        │    │
│  │ (pitch-based)  │  │ (keyword + punctuation)   │    │
│  └────────────────┘  └──────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

### Frontend (Electron + React)

| Technology        | Purpose                                          |
| ----------------- | ------------------------------------------------ |
| **Electron 33**   | Desktop shell, file dialogs, `media://` protocol |
| **React 18**      | UI framework                                     |
| **Vite 5**        | Dev server + HMR                                 |
| **Zustand 5**     | State management                                 |
| **TailwindCSS 3** | Styling                                          |
| **electron-vite** | Build tooling                                    |

### Backend (Python AI Engine)

| Technology          | Purpose                                  |
| ------------------- | ---------------------------------------- |
| **Python 3.11**     | Runtime                                  |
| **FastAPI**         | WebSocket server + REST endpoints        |
| **faster-whisper**  | Speech-to-text (GPU, `tiny` model, int8) |
| **edge-tts**        | Text-to-speech (Microsoft Neural voices) |
| **deep-translator** | Google Translate API wrapper             |
| **pydub**           | Audio manipulation and mixing            |
| **numpy / scipy**   | Pitch analysis for gender detection      |
| **imageio-ffmpeg**  | FFmpeg bindings for audio extraction     |

---

## 📦 Prerequisites

- **OS**: Windows 10/11
- **GPU**: NVIDIA GPU with CUDA support (optimized for GTX 1650 4GB)
- **Python**: 3.11+
- **Node.js**: 18+
- **FFmpeg**: Bundled via `imageio-ffmpeg` (no manual install needed)

---

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/Abhaypetkar/cinesync.git
cd cinesync
```

### 2. Install Node.js dependencies

```bash
npm install
```

### 3. Set up Python environment

```bash
cd ai-engine

# Install PyTorch with CUDA (do this first)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install remaining dependencies
pip install -r requirements.txt
```

### 4. Verify GPU

```bash
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}, GPU: {torch.cuda.get_device_name(0)}')"
```

---

## ▶️ Running the Application

### Option A: Launch Script (Recommended)

```powershell
# From project root
.\start.ps1
```

This starts both the AI engine and Electron app automatically.

### Option B: Manual Start

**Terminal 1 — AI Engine:**

```bash
cd ai-engine
python main.py
```

Wait for: `Uvicorn running on http://0.0.0.0:8765`

**Terminal 2 — Electron App:**

```bash
npm run dev
```

### Health Check

```
http://localhost:8765/health
```

---

## 📖 Usage Guide

### Loading a Video

1. Click **"Drop a video file here"** or use the file browser
2. Drag & drop a video file onto the app window
3. Supported formats: **MP4, MKV, MOV, AVI, WebM**

### Starting Dubbing

1. Open the **Dubbing** tab in the sidebar
2. Select your **Target Language** (Hindi, Spanish, French, etc.)
3. Click **"Start Dubbing"** (or press `D`)
4. Watch real-time progress in the sidebar

### During Dubbing

- **Live Transcription** appears in the Dubbing tab
- **Characters** tab shows detected speakers with gender, voice, emotion
- **Diagnostics** tab shows FPS, latency, sync accuracy
- **Subtitles** overlay on the video with emotion-colored borders

### After Dubbing

- The dubbed audio plays automatically over the video
- Click the **Export** button (↓) in the control bar to download the dubbed track
- Use **Screenshot** (📸) to capture frames

---

## ⌨️ Keyboard Shortcuts

| Key     | Action                 |
| ------- | ---------------------- |
| `Space` | Play / Pause           |
| `M`     | Mute / Unmute          |
| `F`     | Toggle Fullscreen      |
| `D`     | Toggle Dubbing         |
| `O`     | Toggle AI Overlay      |
| `B`     | Toggle Sidebar         |
| `T`     | Toggle Timeline        |
| `←`     | Seek back 5 seconds    |
| `→`     | Seek forward 5 seconds |

---

## 📁 Project Structure

```
cinesync/
├── ai-engine/                  # Python AI Backend
│   ├── main.py                 # FastAPI server + WebSocket hub
│   ├── config.py               # Hardware-aware settings
│   ├── requirements.txt        # Python dependencies
│   ├── core/
│   │   ├── pipeline.py         # Pipeline orchestrator (analysis + dubbing)
│   │   ├── media_processor.py  # FFmpeg audio/video extraction
│   │   └── ws_manager.py       # WebSocket connection manager
│   └── services/
│       ├── stt_service.py      # faster-whisper STT
│       ├── translation_service.py  # Google Translate via deep-translator
│       ├── tts_service.py      # Edge TTS with SSML emotion
│       ├── dubbing_pipeline.py # Full dubbing pipeline (STT→TTS→Mix)
│       ├── emotion.py          # Keyword-based emotion classifier
│       ├── speaker_diarization.py  # Speaker identification
│       ├── face_detection.py   # YOLOv8 face detection (Phase 2)
│       ├── character_mapper.py # Face ↔ speaker mapping
│       ├── audio_debug.py      # Audio diagnostics
│       └── gpu_manager.py      # GPU/VRAM management
│
├── src/
│   ├── main/
│   │   └── index.js            # Electron main process
│   ├── preload/
│   │   └── index.js            # Secure IPC bridge
│   └── renderer/
│       ├── index.html          # Entry HTML
│       └── src/
│           ├── App.jsx         # Root component + keyboard shortcuts
│           ├── main.jsx        # React entry point
│           ├── components/
│           │   ├── TitleBar/   # Custom title bar + AI status
│           │   ├── VideoPlayer/# Video + subtitle + debug overlay
│           │   ├── ControlBar/ # Playback, volume, features
│           │   ├── Timeline/   # Waveform + seek + markers
│           │   └── Sidebar/    # Characters, Dubbing, Diagnostics
│           ├── hooks/
│           │   ├── useMediaPlayer.jsx  # Video playback logic
│           │   └── useWebSocket.js     # AI server communication
│           ├── stores/
│           │   └── playerStore.js      # Zustand global state
│           └── styles/
│               └── index.css           # Global CSS + animations
│
├── package.json                # Node.js dependencies
├── electron.vite.config.mjs    # Electron-Vite build config
├── tailwind.config.js          # TailwindCSS theme
├── postcss.config.js           # PostCSS config
└── start.ps1                   # Launch script (PowerShell)
```

---

## 🧠 AI Pipeline

### Dubbing Flow

```
Video File
    │
    ▼
┌──────────────────┐
│ Extract Audio    │  FFmpeg extracts 5-second chunks
│ (media_processor)│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Speech-to-Text   │  faster-whisper (GPU, tiny model)
│ (stt_service)    │  → segments with text + timestamps
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Gender Detection │  Autocorrelation pitch analysis
│ (pitch_from_     │  on isolated speech segment
│  segment)        │  → male (< 165Hz) / female (> 165Hz)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Speaker Tracking │  Gap-based pseudo-diarization
│ (_get_stable_    │  → stable speaker_0, speaker_1, etc.
│  speaker)        │  → gender locked on first detection
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Emotion Classify │  Keyword matching + punctuation boost
│ (emotion.py)     │  → anger, joy, sadness, surprise, etc.
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Translation      │  deep-translator (Google Translate)
│ (translation_    │  → source language → target language
│  service)        │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Text-to-Speech   │  Edge TTS with SSML emotion styling
│ (tts_service)    │  → gender-matched neural voice
│                  │  → locked per character
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Audio Mixing     │  pydub overlays TTS onto original
│ (dubbing_        │  → preserves background audio
│  pipeline)       │  → exports dubbed_track.wav
└──────────────────┘
```

### Voice Assignment Logic

1. **Per-segment pitch analysis**: Each speech segment is sliced from the audio chunk using STT timestamps. Autocorrelation pitch detection runs on JUST the voice (no background music).
2. **Gender threshold**: Median F0 > 165 Hz → female, ≤ 165 Hz → male.
3. **Speaker tracking**: Segments within 1.5s are the same speaker. Gaps > 1.5s = speaker change.
4. **Voice locking**: Once `speaker_0` is assigned "male → Madhur", it stays that way for the entire video.

### Emotion Pipeline

```
Input text → Keyword scan → Punctuation boost → Emotion label

Keywords: "angry", "hate" → anger
          "happy", "love" → joy
          "sad", "miss"   → sadness
          "scared", "fear" → fear

Punctuation: "!" → excitement (if neutral)
             "?" → surprise (if neutral)
```

---

## 🔌 WebSocket Protocol

All communication between Electron and the AI Engine uses WebSocket JSON messages.

### Client → Server

| Message Type       | Data           | Description                 |
| ------------------ | -------------- | --------------------------- |
| `load_media`       | `{ filePath }` | Load a video file           |
| `start_analysis`   | `{}`           | Start face/speaker analysis |
| `stop_analysis`    | `{}`           | Stop analysis               |
| `start_dubbing`    | `{ language }` | Start dubbing pipeline      |
| `stop_dubbing`     | `{}`           | Stop dubbing                |
| `playback_time`    | `{ time }`     | Current playback position   |
| `seek`             | `{ time }`     | Seek to timestamp           |
| `get_characters`   | `{}`           | Request character list      |
| `get_status`       | `{}`           | Request pipeline status     |
| `rename_character` | `{ id, name }` | Rename a character          |
| `ping`             | —              | Heartbeat                   |

### Server → Client

| Message Type          | Data                        | Description                   |
| --------------------- | --------------------------- | ----------------------------- |
| `connected`           | `{ gpu, vram, pipeline }`   | Initial connection info       |
| `media_loaded`        | `{ filePath, status }`      | Media ready                   |
| `analysis_status`     | `{ stage, progress }`       | Analysis progress             |
| `characters_detected` | `[{ id, name, ... }]`       | Detected characters           |
| `active_speakers`     | `[ids]`                     | Currently speaking characters |
| `dubbing_status`      | `{ stage, progress, ... }`  | Dubbing progress              |
| `live_transcript`     | `{ start, end, text, ... }` | Real-time transcript          |
| `dubbed_track_ready`  | `{ audioPath, segments }`   | Dubbing complete              |
| `debug_metrics`       | `{ fps, latency, ... }`     | Performance metrics           |
| `warning`             | `{ message, time }`         | Pipeline warnings             |
| `pong`                | —                           | Heartbeat response            |

---

## ⚙️ Configuration

All settings are in [`ai-engine/config.py`](ai-engine/config.py):

```python
@dataclass
class Settings:
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8765

    # GPU (GTX 1650)
    GPU_VRAM: int = 4          # GB total
    MAX_VRAM_USAGE: float = 3.5  # GB usable (leave headroom)

    # Whisper STT
    WHISPER_MODEL: str = "tiny"       # tiny|small|medium
    WHISPER_COMPUTE_TYPE: str = "int8"  # int8 for low VRAM

    # Processing
    CHUNK_DURATION: float = 5.0    # seconds per chunk
    BUFFER_AHEAD: float = 15.0     # pre-process buffer
    MAX_CHARACTERS: int = 15
```

### VRAM Budget (GTX 1650, 4GB)

| Component            | VRAM        |
| -------------------- | ----------- |
| Whisper (tiny, int8) | ~0.4 GB     |
| System overhead      | ~0.5 GB     |
| **Available**        | **~3.1 GB** |

Models are loaded sequentially to avoid VRAM overflow.

---

## 🌍 Supported Languages

| Code | Language   | TTS Voice (Male)       | TTS Voice (Female)      |
| ---- | ---------- | ---------------------- | ----------------------- |
| `hi` | Hindi      | MadhurNeural           | SwaraNeural             |
| `en` | English    | GuyNeural, DavisNeural | JennyNeural, AriaNeural |
| `es` | Spanish    | AlvaroNeural           | ElviraNeural            |
| `fr` | French     | HenriNeural            | DeniseNeural            |
| `de` | German     | ConradNeural           | KatjaNeural             |
| `ja` | Japanese   | KeitaNeural            | NanamiNeural            |
| `ko` | Korean     | InJoonNeural           | SunHiNeural             |
| `zh` | Chinese    | YunxiNeural            | XiaoxiaoNeural          |
| `ar` | Arabic     | HamedNeural            | ZariyahNeural           |
| `pt` | Portuguese | AntonioNeural          | FranciscaNeural         |
| `ru` | Russian    | DmitryNeural           | SvetlanaNeural          |

---

## 🔧 Troubleshooting

### AI Engine shows "OFFLINE" in title bar

- Check that the Python server is running on port `8765`
- Run `curl http://localhost:8765/health` to verify
- The Electron app auto-reconnects every 5 seconds

### No dubbed audio produced

- Check the AI engine logs for errors
- Ensure `faster-whisper` is installed: `pip install faster-whisper`
- Ensure `edge-tts` is installed: `pip install edge-tts`
- Verify internet connection (Edge TTS requires internet)

### All voices are the same gender

- The pitch detection threshold is 165 Hz
- If the video has unusual audio (heavy music), pitch detection may fail
- Check logs for `Pitch: XXX Hz → male/female` entries

### Video won't play

- Ensure the video format is supported (MP4, MKV, MOV, AVI, WebM)
- The `media://` protocol handles local file streaming
- Check the Electron console for `MEDIA_ELEMENT_ERROR`

### CUDA out of memory

- Reduce `WHISPER_MODEL` to `"tiny"` in `config.py`
- Set `WHISPER_COMPUTE_TYPE` to `"int8"`
- Close other GPU applications

---

## 📝 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with ❤️ by <strong>Janhavi</strong>
</p>
#   C i n e s y n c 
 
 "# CineSync"
