"""
CineSync AI — Python AI Server
FastAPI + WebSocket hub for real-time AI inference pipeline.
Supports both local GPU and Modal cloud GPU modes.
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from core.ws_manager import ConnectionManager
from core.pipeline import PipelineOrchestrator
from config import Settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger("cinesync")

settings = Settings()
manager = ConnectionManager()
pipeline = PipelineOrchestrator(settings)


async def broadcast_to_clients(message: dict):
    """Callback for pipeline to broadcast messages."""
    await manager.broadcast(message)

pipeline.set_broadcast_callback(broadcast_to_clients)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("=" * 60)
    logger.info("  🎬 CineSync AI Engine")
    logger.info("=" * 60)
    logger.info(f"  Mode:   {settings.get_mode_display()}")
    if settings.USE_MODAL:
        logger.info(f"  GPU:    Modal Cloud {settings.MODAL_GPU} (16GB VRAM)")
        logger.info(f"  Model:  Whisper {settings.WHISPER_MODEL} ({settings.WHISPER_COMPUTE_TYPE})")
        logger.info(f"  Note:   First request triggers ~30-120s GPU warmup")
    else:
        logger.info(f"  GPU:    {settings.GPU_NAME} ({settings.GPU_VRAM}GB VRAM)")
        logger.info(f"  Mode:   Sequential model loading")
    logger.info(f"  Server: ws://localhost:{settings.PORT}/ws")
    logger.info(f"  Health: http://localhost:{settings.PORT}/health")
    logger.info("=" * 60)
    yield
    logger.info("🎬 CineSync AI Engine shutting down...")
    await pipeline.shutdown()


app = FastAPI(
    title="CineSync AI Engine",
    description="Real-time AI dubbing and cinematic debugging server",
    version="2.0.0",
    lifespan=lifespan
)

# CORS — allow Electron renderer to fetch dubbed audio tracks
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)


@app.get("/dubbed-track")
async def get_dubbed_track():
    """Serve the dubbed audio track file."""
    from fastapi.responses import FileResponse
    status = pipeline.get_status()
    dubbing = status.get("dubbing", {})
    output_path = dubbing.get("outputPath")
    if output_path and os.path.exists(output_path):
        return FileResponse(
            output_path,
            media_type="audio/wav",
            headers={"Accept-Ranges": "bytes"}
        )
    return {"error": "No dubbed track available"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "online",
        "mode": "modal" if settings.USE_MODAL else "local",
        "gpu": settings.get_gpu_display_name(),
        "vram": 16 if settings.USE_MODAL else settings.GPU_VRAM,
        "whisper_model": settings.WHISPER_MODEL,
        "pipeline": pipeline.get_status()
    }


@app.get("/modal-status")
async def modal_status():
    """Check Modal GPU warmup status."""
    if not settings.USE_MODAL:
        return {"mode": "local", "message": "Not using Modal"}

    status = pipeline.get_status()
    return {
        "mode": "modal",
        "gpu": f"Modal {settings.MODAL_GPU}",
        "gpu_warm": status.get("gpu_warm", False),
        "gpu_warming": status.get("gpu_warming", False),
        "whisper_model": settings.WHISPER_MODEL,
        "compute_type": settings.WHISPER_COMPUTE_TYPE,
    }


@app.post("/warmup")
async def trigger_warmup():
    """Manually trigger GPU warmup."""
    if not settings.USE_MODAL:
        return {"status": "local_mode", "message": "Using local GPU, no warmup needed"}

    result = await pipeline.warmup_gpu()
    return {"status": "ok", "result": result}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for Electron client communication."""
    await manager.connect(websocket)
    logger.info(f"Client connected. Active: {manager.active_count}")

    # Set up broadcast callback so pipeline messages reach the client
    async def broadcast_to_client(msg):
        try:
            await websocket.send_json(msg)
        except Exception:
            pass  # Connection may be closed

    pipeline.set_broadcast_callback(broadcast_to_client)

    # Send initial status
    await websocket.send_json({
        "type": "connected",
        "data": {
            "gpu": settings.get_gpu_display_name(),
            "vram": 16 if settings.USE_MODAL else settings.GPU_VRAM,
            "mode": "modal" if settings.USE_MODAL else "local",
            "whisperModel": settings.WHISPER_MODEL,
            "pipeline": pipeline.get_status()
        }
    })

    # Auto-trigger GPU warmup for Modal mode (don't rely on frontend timing)
    if settings.USE_MODAL:
        logger.info("Auto-triggering Modal GPU warmup on client connect...")
        asyncio.create_task(pipeline.warmup_gpu())

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type", "")
            msg_data = message.get("data", {})

            logger.debug(f"Received: {msg_type}")

            # ── Heartbeat ──
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            # ── GPU Warmup (Modal) ──
            elif msg_type == "warmup_gpu":
                if settings.USE_MODAL:
                    asyncio.create_task(pipeline.warmup_gpu())
                else:
                    await websocket.send_json({
                        "type": "gpu_warmup",
                        "data": {
                            "stage": "ready",
                            "progress": 100,
                            "message": "Local GPU ready",
                        }
                    })

            # ── Media Loading ──
            elif msg_type == "load_media":
                file_path = msg_data.get("filePath", "")
                logger.info(f"Loading media: {file_path}")
                media_info = await pipeline.load_media(file_path)
                await websocket.send_json({
                    "type": "media_loaded",
                    "data": {
                        "filePath": file_path,
                        "status": "ready",
                        "info": media_info
                    }
                })

            # ── Start AI Analysis ──
            elif msg_type == "start_analysis":
                logger.info("Starting AI analysis pipeline...")
                await pipeline.start_analysis()

            # ── Stop Analysis ──
            elif msg_type == "stop_analysis":
                await pipeline.stop_analysis()

            # ── Start Dubbing ──
            elif msg_type == "start_dubbing":
                language = msg_data.get("language", "hi")
                logger.info(f"Starting dubbing → {language}")
                await pipeline.start_dubbing(language)

            # ── Stop Dubbing ──
            elif msg_type == "stop_dubbing":
                await pipeline.stop_dubbing()

            # ── Seek ──
            elif msg_type == "seek":
                timestamp = msg_data.get("time", 0)
                await pipeline.handle_seek(timestamp)

            # ── Playback Time Update (for dubbing pacing) ──
            elif msg_type == "playback_time":
                t = msg_data.get("time", 0)
                await pipeline.update_playback_time(t)

            # ── Rename Character ──
            elif msg_type == "rename_character":
                char_id = msg_data.get("id")
                name = msg_data.get("name", "")
                if char_id is not None:
                    pipeline.character_mapper.set_character_name(char_id, name)
                    chars = pipeline.character_mapper.get_all_characters()
                    await manager.broadcast({"type": "characters_detected", "data": chars})

            # ── Get Characters ──
            elif msg_type == "get_characters":
                chars = pipeline.character_mapper.get_all_characters()
                await websocket.send_json({"type": "characters_detected", "data": chars})

            # ── Get Pipeline Status ──
            elif msg_type == "get_status":
                await websocket.send_json({
                    "type": "pipeline_status",
                    "data": pipeline.get_status()
                })

            # ── Get Audio Diagnostics ──
            elif msg_type == "get_diagnostics":
                diagnostics = pipeline.audio_debugger.get_all_diagnostics()
                metrics = pipeline.audio_debugger.get_metrics()
                await websocket.send_json({
                    "type": "diagnostics_data",
                    "data": {"diagnostics": diagnostics, "metrics": metrics}
                })

            else:
                logger.warning(f"Unknown message type: {msg_type}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"Client disconnected. Remaining: {manager.active_count}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    import sys

    # NEVER use reload when running as a child process of Electron.
    # Uvicorn's reloader spawns subprocesses that crash on Windows
    # with WinError 10055 (socket buffer exhaustion).
    # NOTE: Pass `app` object directly (not "main:app" string) so it works
    # with PyInstaller frozen executables where module import fails.
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        log_level="info"
    )

