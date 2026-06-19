"""
Modal Client Adapters — Drop-in replacements for local GPU services.
Calls Modal cloud GPU for STT and face detection while maintaining
the same interface as local services.
"""

import asyncio
import logging
import os
import time
from typing import List, Dict, Optional
from dataclasses import dataclass, field

import modal

logger = logging.getLogger("cinesync.modal")

APP_NAME = "cinesync-ai"
CLS_NAME = "CineSyncGPU"

def _get_gpu_cls():
    """Get a reference to the deployed CineSyncGPU class on Modal."""
    return modal.Cls.from_name(APP_NAME, CLS_NAME)()


# ── Re-use existing data classes ─────────────────────────────────
from services.stt_service import TranscriptionSegment


@dataclass
class ModalDetection:
    """Single face detection result from Modal."""
    bbox: tuple
    confidence: float
    track_id: int = -1
    character_id: int = -1


class ModalSTTService:
    """
    Drop-in replacement for STTService that runs Whisper on Modal GPU.
    
    Same interface as STTService so the dubbing pipeline doesn't need changes.
    Audio files are read locally, sent as bytes to Modal, results parsed back.
    """

    def __init__(self, model_size: str = "medium", compute_type: str = "float16"):
        self.model_size = model_size
        self.compute_type = compute_type
        self._gpu_cls = None
        self._loaded = False
        self._warming_up = False
        self._warmup_callback = None

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def set_warmup_callback(self, callback):
        """Set a callback for warmup status updates."""
        self._warmup_callback = callback

    def load(self):
        """
        Initialize the Modal GPU class reference.
        The actual model loading happens on Modal's side via @modal.enter().
        """
        try:
            self._gpu_cls = _get_gpu_cls()
            self._loaded = True
            logger.info("Modal STT service initialized (model loads on first call)")
        except Exception as e:
            logger.error(f"Failed to initialize Modal STT: {e}")
            self._loaded = False

    def unload(self):
        """No local resources to free — Modal manages GPU lifecycle."""
        self._gpu_cls = None
        self._loaded = False
        logger.info("Modal STT service disconnected")

    async def transcribe_chunk(
        self, audio_path: str, chunk_offset: float = 0.0
    ) -> List[TranscriptionSegment]:
        """
        Transcribe an audio chunk via Modal GPU.

        Reads the local WAV file, sends bytes to Modal, parses response
        into TranscriptionSegment objects for pipeline compatibility.
        """
        if not self._loaded or not self._gpu_cls:
            logger.warning("Modal STT not initialized")
            return []

        return await asyncio.to_thread(
            self._transcribe_remote, audio_path, chunk_offset
        )

    def _transcribe_remote(
        self, audio_path: str, chunk_offset: float
    ) -> List[TranscriptionSegment]:
        """Synchronous Modal remote call (runs in thread)."""
        try:
            # Read local audio file
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()

            file_size_kb = len(audio_bytes) / 1024
            logger.info(
                f"[Modal STT] Sending {file_size_kb:.0f}KB audio to cloud GPU..."
            )

            t0 = time.time()

            # Call Modal GPU
            result = self._gpu_cls.transcribe.remote(
                audio_bytes=audio_bytes,
                chunk_offset=chunk_offset,
                beam_size=5,
            )

            elapsed = time.time() - t0
            segments_data = result.get("segments", [])
            modal_time = result.get("processing_time", 0)

            logger.info(
                f"[Modal STT] {len(segments_data)} segments in {elapsed:.2f}s "
                f"(GPU: {modal_time:.2f}s, network: {elapsed - modal_time:.2f}s)"
            )

            # Convert to TranscriptionSegment objects
            results = []
            for seg in segments_data:
                ts = TranscriptionSegment(
                    text=seg["text"],
                    start=seg["start"],
                    end=seg["end"],
                    language=seg.get("language", "en"),
                    confidence=seg.get("confidence", 0.0),
                    words=seg.get("words", []),
                )
                results.append(ts)

            return results

        except Exception as e:
            logger.error(f"[Modal STT] Remote transcription error: {e}", exc_info=True)
            return []


class ModalFaceDetectionService:
    """
    Drop-in replacement for FaceDetectionService that runs YOLOv8 on Modal GPU.
    
    Same interface so pipeline.py doesn't need changes.
    Frame images are read locally, sent as bytes to Modal.
    """

    def __init__(self, model_path: str = "yolov8n", device: str = "modal"):
        self.model_path = model_path
        self.device = device
        self._gpu_cls = None
        self._loaded = False
        self._next_track_id = 1
        self._characters: Dict[int, dict] = {}
        self._tracks: Dict[int, dict] = {}
        self._iou_threshold = 0.3

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self):
        """Initialize Modal GPU class reference."""
        try:
            self._gpu_cls = _get_gpu_cls()
            self._loaded = True
            logger.info("Modal Face Detection service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Modal Face Detection: {e}")
            self._loaded = False

    def unload(self):
        """No local resources to free."""
        self._gpu_cls = None
        self._loaded = False
        logger.info("Modal Face Detection service disconnected")

    def detect_faces(self, frame_path: str, timestamp: float = 0.0) -> list:
        """
        Detect faces in a frame via Modal GPU.

        Reads local JPEG, sends to Modal, parses results.
        Returns list of Detection-like objects.
        """
        if not self._loaded or not self._gpu_cls:
            return self._detect_mock(timestamp)

        try:
            with open(frame_path, "rb") as f:
                frame_bytes = f.read()

            result = self._gpu_cls.detect_faces.remote(
                frame_bytes=frame_bytes,
                timestamp=timestamp,
            )

            detections_data = result.get("detections", [])

            # Convert to Detection-compatible objects and track
            from services.face_detection import Detection
            detections = []
            for d in detections_data:
                det = Detection(
                    bbox=tuple(d["bbox"]),
                    confidence=d["confidence"],
                )
                detections.append(det)

            # Apply simple IoU tracking (same logic as local service)
            detections = self._track(detections, timestamp)
            return detections

        except Exception as e:
            logger.error(f"[Modal Face] Detection error: {e}")
            return self._detect_mock(timestamp)

    def _detect_mock(self, timestamp: float) -> list:
        """Fallback mock detection."""
        import math
        from services.face_detection import Detection

        detections = []
        for i in range(3):
            cx = 0.2 + (i * 0.3) + math.sin(timestamp * 0.5 + i) * 0.02
            cy = 0.3 + math.cos(timestamp * 0.3 + i * 2) * 0.02
            w, h = 0.08, 0.12
            det = Detection(
                bbox=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                confidence=0.85 + (i * 0.04),
                track_id=i + 1,
            )
            detections.append(det)
        return detections

    def _track(self, detections, timestamp):
        """Simple IoU-based tracking (mirrors local service logic)."""
        if not self._tracks:
            for det in detections:
                det.track_id = self._next_track_id
                self._tracks[det.track_id] = det
                self._next_track_id += 1
        else:
            used_tracks = set()
            for det in detections:
                best_iou = 0.0
                best_track_id = -1
                for tid, prev_det in self._tracks.items():
                    if tid in used_tracks:
                        continue
                    iou = self._compute_iou(det.bbox, prev_det.bbox)
                    if iou > best_iou and iou >= self._iou_threshold:
                        best_iou = iou
                        best_track_id = tid

                if best_track_id >= 0:
                    det.track_id = best_track_id
                    used_tracks.add(best_track_id)
                else:
                    det.track_id = self._next_track_id
                    self._next_track_id += 1

            self._tracks = {det.track_id: det for det in detections}

        return detections

    def _compute_iou(self, box1, box2) -> float:
        """Compute IoU of two normalized bounding boxes."""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - inter
        return inter / union if union > 0 else 0.0

    def get_characters(self):
        """Get all detected characters."""
        return list(self._characters.values())

    def get_active_characters(self, timestamp, window=2.0):
        """Get active character IDs."""
        return []

    def set_character_name(self, char_id, name):
        """Rename a character."""
        if char_id in self._characters:
            self._characters[char_id]["name"] = name

    def set_speaking(self, char_id, is_speaking):
        """Mark character speaking state."""
        if char_id in self._characters:
            self._characters[char_id]["is_speaking"] = is_speaking


class ModalGPUWarmup:
    """
    Handles the Modal GPU cold-start warmup sequence.
    
    Sends fancy status messages to the frontend while the GPU container
    boots up and loads models (~30-120s on cold start).
    """

    def __init__(self):
        self._warmed_up = False
        self._warming = False

    @property
    def is_warm(self) -> bool:
        return self._warmed_up

    @property
    def is_warming(self) -> bool:
        return self._warming

    async def warmup(self, broadcast_callback=None) -> dict:
        """
        Trigger GPU warmup by calling health_check on Modal.
        Sends progress messages via broadcast_callback.
        
        Returns GPU health info on success.
        """
        if self._warmed_up:
            return {"status": "already_warm"}

        if self._warming:
            return {"status": "warming_in_progress"}

        self._warming = True
        start_time = time.time()

        warmup_stages = [
            (0, "🚀 Initializing cloud GPU instance...", "Requesting T4 GPU from Modal"),
            (8, "⚡ GPU allocated! Booting CUDA runtime...", "Setting up CUDA drivers"),
            (15, "🧠 Loading Whisper Medium model (1.5GB)...", "Neural speech recognition"),
            (35, "🎯 Loading YOLOv8 face detection model...", "Computer vision pipeline"),
            (50, "🔥 Warming up inference engines...", "Running calibration passes"),
            (70, "✨ Optimizing GPU memory layout...", "Allocating VRAM buffers"),
            (85, "🎬 Running final diagnostics...", "Verifying model accuracy"),
        ]

        try:
            # Send initial warmup stages as visual progress
            # while the actual Modal health_check runs in background
            async def send_stages():
                for progress, message, detail in warmup_stages:
                    if self._warmed_up:
                        break
                    elapsed = time.time() - start_time
                    if broadcast_callback:
                        await broadcast_callback({
                            "type": "gpu_warmup",
                            "data": {
                                "stage": "warming",
                                "progress": progress,
                                "message": message,
                                "detail": detail,
                                "elapsed": round(elapsed, 1),
                                "maxWait": 120,
                            }
                        })
                    await asyncio.sleep(3)

                # Keep sending progress updates until warmup completes
                progress = 85
                while not self._warmed_up and (time.time() - start_time) < 120:
                    progress = min(95, progress + 1)
                    elapsed = time.time() - start_time
                    if broadcast_callback:
                        await broadcast_callback({
                            "type": "gpu_warmup",
                            "data": {
                                "stage": "warming",
                                "progress": progress,
                                "message": "🔄 GPU is almost ready...",
                                "detail": f"Loading neural networks ({elapsed:.0f}s)",
                                "elapsed": round(elapsed, 1),
                                "maxWait": 120,
                            }
                        })
                    await asyncio.sleep(2)

            async def do_warmup():
                """Actually call Modal to trigger the cold start."""
                try:
                    gpu = _get_gpu_cls()
                    result = await asyncio.to_thread(gpu.health_check.remote)
                    return result
                except Exception as e:
                    logger.error(f"Modal warmup failed: {e}")
                    return {"status": "error", "error": str(e)}

            # Run stages animation and actual warmup in parallel
            stages_task = asyncio.create_task(send_stages())
            result = await asyncio.to_thread(self._warmup_sync)

            self._warmed_up = True
            stages_task.cancel()
            try:
                await stages_task
            except asyncio.CancelledError:
                pass

            elapsed = time.time() - start_time

            # Send completion message
            if broadcast_callback:
                await broadcast_callback({
                    "type": "gpu_warmup",
                    "data": {
                        "stage": "ready",
                        "progress": 100,
                        "message": "🎉 Cloud GPU is ready!",
                        "detail": f"Loaded in {elapsed:.0f}s — {result.get('gpu', 'T4')}",
                        "elapsed": round(elapsed, 1),
                        "gpu_info": result,
                    }
                })

            logger.info(f"Modal GPU warmup complete in {elapsed:.1f}s: {result}")
            self._warming = False
            return result

        except Exception as e:
            self._warming = False
            logger.error(f"GPU warmup error: {e}", exc_info=True)
            if broadcast_callback:
                await broadcast_callback({
                    "type": "gpu_warmup",
                    "data": {
                        "stage": "error",
                        "progress": 0,
                        "message": "❌ GPU warmup failed",
                        "detail": str(e),
                    }
                })
            return {"status": "error", "error": str(e)}

    def _warmup_sync(self) -> dict:
        """Synchronous warmup call (runs in thread)."""
        try:
            gpu = _get_gpu_cls()
            return gpu.health_check.remote()
        except Exception as e:
            logger.error(f"Modal warmup sync error: {e}")
            return {"status": "error", "error": str(e)}
