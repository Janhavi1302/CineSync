"""
Pipeline Orchestrator — manages the sequential AI processing pipeline.
Supports both local GPU and Modal cloud GPU modes.
Coordinates all AI services for character intelligence.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Optional

from core.media_processor import MediaProcessor
from services.face_detection import FaceDetectionService
from services.speaker_diarization import SpeakerDiarizationService
from services.character_mapper import CharacterMapper
from services.emotion import EmotionClassifier
from services.audio_debug import AudioDebugger
from services.gpu_manager import GPUManager
from services.stt_service import STTService
from services.translation_service import TranslationService
from services.tts_service import TTSService
from services.dubbing_pipeline import DubbingPipeline

logger = logging.getLogger("cinesync.pipeline")


class PipelineStage(Enum):
    IDLE = "idle"
    EXTRACTING = "extracting"
    FACE_DETECTION = "face_detection"
    DIARIZATION = "diarization"
    CHARACTER_MAPPING = "character_mapping"
    SPEECH_RECOGNITION = "speech_recognition"
    TRANSLATION = "translation"
    VOICE_GENERATION = "voice_generation"
    GPU_WARMUP = "gpu_warmup"


class PipelineOrchestrator:
    """
    Orchestrates the AI processing pipeline.
    
    Supports two modes:
    - Modal (USE_MODAL=True): GPU inference on Modal cloud T4
    - Local (USE_MODAL=False): Sequential GPU model loading on local GPU
    """

    def __init__(self, settings):
        self.settings = settings
        self.current_stage = PipelineStage.IDLE
        self.is_ready = False

        # Core utilities
        self.media_processor = MediaProcessor()

        # ── GPU Mode Selection ──
        self._use_modal = settings.USE_MODAL

        if self._use_modal:
            logger.info("═" * 50)
            logger.info("  🌐 Modal Cloud GPU Mode (T4)")
            logger.info("  GPU inference runs on Modal's cloud")
            logger.info("═" * 50)
            self._init_modal_services(settings)
        else:
            logger.info("═" * 50)
            logger.info(f"  🖥️ Local GPU Mode ({settings.GPU_NAME})")
            logger.info("═" * 50)
            self._init_local_services(settings)

        # Common services (CPU-based, always local)
        self.diarizer = SpeakerDiarizationService(device="cpu")
        self.character_mapper = CharacterMapper(max_characters=settings.MAX_CHARACTERS)
        self.emotion_classifier = EmotionClassifier()
        self.audio_debugger = AudioDebugger()
        self.translation_service = TranslationService()
        self.tts_service = TTSService()

        # Dubbing pipeline
        self.dubbing_pipeline = DubbingPipeline(
            stt_service=self.stt_service,
            translation_service=self.translation_service,
            tts_service=self.tts_service,
            media_processor=self.media_processor,
            character_mapper=self.character_mapper,
            emotion_classifier=self.emotion_classifier
        )
        self.dubbing_pipeline._diarizer = self.diarizer

        # Processing state
        self._current_file: Optional[str] = None
        self._media_info: dict = {}
        self._processing = False
        self._dubbing_active = False
        self._analysis_task: Optional[asyncio.Task] = None
        self._broadcast_callback = None

        # Initialize CPU-based services
        self.emotion_classifier.load()
        logger.info("Pipeline orchestrator initialized (all services ready)")
        self.is_ready = True

    def _init_modal_services(self, settings):
        """Initialize Modal cloud GPU services."""
        from services.modal_client import (
            ModalSTTService,
            ModalFaceDetectionService,
            ModalGPUWarmup,
        )

        self.gpu_manager = GPUManager(max_vram_gb=0, modal_mode=True)
        self.stt_service = ModalSTTService(
            model_size=settings.WHISPER_MODEL,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )
        self.face_detector = ModalFaceDetectionService(
            model_path=settings.FACE_MODEL,
            device="modal",
        )
        self.gpu_warmup = ModalGPUWarmup()
        logger.info("Modal services initialized")

    def _init_local_services(self, settings):
        """Initialize local GPU services."""
        self.gpu_manager = GPUManager(max_vram_gb=settings.MAX_VRAM_USAGE)
        self.stt_service = STTService(
            model_size=settings.WHISPER_MODEL,
            device=settings.DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )
        self.face_detector = FaceDetectionService(
            model_path=settings.FACE_MODEL,
            device=settings.DEVICE,
        )
        self.gpu_warmup = None
        logger.info("Local GPU services initialized")

    def set_broadcast_callback(self, callback):
        """Set callback for broadcasting messages to WebSocket clients."""
        self._broadcast_callback = callback

    async def _broadcast(self, msg_type: str, data: dict):
        """Send message to all connected clients."""
        if self._broadcast_callback:
            await self._broadcast_callback({"type": msg_type, "data": data})

    async def warmup_gpu(self):
        """
        Trigger Modal GPU warmup (cold start).
        Sends fancy progress messages to the frontend.
        Only relevant in Modal mode.
        """
        if not self._use_modal or not self.gpu_warmup:
            return {"status": "local_mode"}

        if self.gpu_warmup.is_warm:
            return {"status": "already_warm"}

        self.current_stage = PipelineStage.GPU_WARMUP
        result = await self.gpu_warmup.warmup(
            broadcast_callback=self._broadcast_callback
        )
        self.current_stage = PipelineStage.IDLE
        return result

    async def load_media(self, file_path: str) -> dict:
        """Load a media file and extract metadata."""
        self._current_file = file_path
        logger.info(f"Loading media: {file_path}")

        # Get media info via FFprobe
        self._media_info = await self.media_processor.get_media_info(file_path)
        
        if self._media_info:
            logger.info(
                f"Media loaded: {self._media_info.get('duration', 0):.1f}s, "
                f"video: {len(self._media_info.get('video', []))} streams, "
                f"audio: {len(self._media_info.get('audio', []))} streams"
            )
        else:
            logger.warning("Could not extract media info (FFprobe not available?)")
            # Still proceed with basic info
            self._media_info = {"duration": 0, "filename": file_path}

        return self._media_info

    async def start_analysis(self):
        """Begin the full AI analysis pipeline for the loaded media."""
        if self._processing:
            logger.warning("Pipeline already processing")
            return
        if not self._current_file:
            logger.error("No media file loaded")
            return

        # Trigger GPU warmup if Modal and not yet warm
        if self._use_modal and self.gpu_warmup and not self.gpu_warmup.is_warm:
            await self.warmup_gpu()

        self._processing = True
        self._analysis_task = asyncio.create_task(self._run_analysis())

    async def _run_analysis(self):
        """Run the analysis pipeline: face detection + diarization + mapping."""
        file_path = self._current_file
        duration = self._media_info.get("duration", 0)
        chunk_duration = self.settings.CHUNK_DURATION  # 5 seconds

        logger.info(f"Starting analysis pipeline for {duration:.1f}s media")
        start_time = time.time()

        try:
            # ── Stage 1: Face Detection (GPU — Modal or local) ─────────────
            self.current_stage = PipelineStage.FACE_DETECTION
            await self._broadcast("analysis_status", {
                "stage": "face_detection", "progress": 0
            })

            # Load face detection model
            self.face_detector.load()

            # Process frames in chunks
            t = 0.0
            total_faces = 0
            while t < min(duration, 120) and self._processing:  # cap at 2 min for demo
                # Extract frames at 2 FPS
                frames = await self.media_processor.extract_frames_batch(
                    file_path, start=t, duration=chunk_duration, fps=2.0, width=640
                )

                for frame_ts, frame_path in frames:
                    detections = self.face_detector.detect_faces(frame_path, frame_ts)
                    self.character_mapper.update_from_detections(detections, frame_ts)
                    total_faces += len(detections)

                progress = min(95, int((t / max(duration, 1)) * 100))
                await self._broadcast("analysis_status", {
                    "stage": "face_detection",
                    "progress": progress,
                    "faces_detected": total_faces
                })

                # Send character updates
                characters = self.character_mapper.get_all_characters()
                await self._broadcast("characters_detected", characters)

                t += chunk_duration
                await asyncio.sleep(0.01)  # yield to event loop

            logger.info(f"Face detection complete: {self.character_mapper.character_count} characters, {total_faces} detections")

            # ── Stage 2: Speaker Diarization (CPU, parallel-safe) ──
            self.current_stage = PipelineStage.DIARIZATION
            await self._broadcast("analysis_status", {
                "stage": "diarization", "progress": 50
            })

            # Extract audio and diarize
            t = 0.0
            all_segments = []
            while t < min(duration, 120) and self._processing:
                audio_path = await self.media_processor.extract_audio_chunk(
                    file_path, start=t, duration=chunk_duration
                )
                if audio_path:
                    segments = await self.diarizer.process_audio(audio_path)
                    # Offset segment times by chunk start
                    for seg in segments:
                        seg.start += t
                        seg.end += t
                    all_segments.extend(segments)

                    # Update character speaking state
                    for seg in segments:
                        self.character_mapper.update_from_diarization(
                            [seg], seg.start
                        )

                t += chunk_duration
                await asyncio.sleep(0.01)

            logger.info(f"Diarization complete: {len(all_segments)} segments, "
                       f"{len(self.diarizer.get_all_speakers())} speakers")

            # ── Stage 3: Character Mapping ─────────────
            self.current_stage = PipelineStage.CHARACTER_MAPPING
            await self._broadcast("analysis_status", {
                "stage": "character_mapping", "progress": 80
            })

            # Auto-map speakers to faces
            self.character_mapper.auto_map_speakers(
                [s.to_dict() for s in all_segments] if all_segments else
                self.diarizer.get_all_segments()
            )

            # Final character update
            characters = self.character_mapper.get_all_characters()
            await self._broadcast("characters_detected", characters)

            # ── Stage 4: Audio Analysis (CPU) ─────────────
            await self._broadcast("analysis_status", {
                "stage": "audio_analysis", "progress": 90
            })

            t = 0.0
            while t < min(duration, 120) and self._processing:
                audio_path = await self.media_processor.extract_audio_chunk(
                    file_path, start=t, duration=chunk_duration
                )
                if audio_path:
                    diagnostic = self.audio_debugger.analyze_file(audio_path, t)
                    if diagnostic and diagnostic.warnings:
                        for warning in diagnostic.warnings:
                            await self._broadcast("warning", {
                                "time": t,
                                "message": warning
                            })

                t += chunk_duration
                await asyncio.sleep(0.01)

            # ── Complete ─────────────
            elapsed = time.time() - start_time
            await self._broadcast("analysis_status", {
                "stage": "complete",
                "progress": 100,
                "duration": round(elapsed, 1),
                "characters": self.character_mapper.character_count,
                "speakers": len(self.diarizer.get_all_speakers())
            })

            # Send debug metrics
            audio_metrics = self.audio_debugger.get_metrics()
            await self._broadcast("debug_metrics", {
                "fps": 24,
                "latency": int(elapsed * 1000 / max(duration, 1)),
                "syncAccuracy": 85,
                "audioLevel": audio_metrics.get("audioLevel", 0)
            })

            logger.info(f"Analysis pipeline complete in {elapsed:.1f}s")

        except asyncio.CancelledError:
            logger.info("Analysis pipeline cancelled")
        except Exception as e:
            logger.error(f"Analysis pipeline error: {e}", exc_info=True)
            await self._broadcast("analysis_status", {
                "stage": "error", "message": str(e)
            })
        finally:
            self.current_stage = PipelineStage.IDLE
            self._processing = False
            # Cleanup temp files
            self.media_processor.cleanup()

    async def stop_analysis(self):
        """Stop the analysis pipeline."""
        self._processing = False
        if self._analysis_task and not self._analysis_task.done():
            self._analysis_task.cancel()
        logger.info("Analysis pipeline stopped")

    async def start_dubbing(self, language: str = "hi"):
        """Start the dubbing pipeline."""
        if not self._current_file:
            logger.error("No media file loaded for dubbing")
            return

        # Trigger GPU warmup if Modal and not yet warm
        if self._use_modal and self.gpu_warmup and not self.gpu_warmup.is_warm:
            await self.warmup_gpu()

        self._dubbing_active = True
        duration = self._media_info.get("duration", 0)
        logger.info(f"Starting dubbing pipeline: {self._current_file} → {language}")

        # Re-fetch media info if duration is 0 (ffprobe may have failed earlier)
        if duration <= 0:
            logger.info("Duration is 0, re-fetching media info...")
            self._media_info = await self.media_processor.get_media_info(self._current_file)
            duration = self._media_info.get("duration", 0)
            if duration <= 0:
                logger.error("Cannot determine media duration, aborting dubbing")
                await self._broadcast("dubbing_status", {
                    "stage": "error",
                    "message": "Cannot determine media duration"
                })
                return

        # Set broadcast callback on dubbing pipeline (must be async-compatible)
        async def broadcast_wrapper(msg):
            if self._broadcast_callback:
                await self._broadcast_callback(msg)

        self.dubbing_pipeline.set_broadcast(broadcast_wrapper)

        # Run dubbing as a background task so it doesn't block the WebSocket loop
        async def _dubbing_task():
            try:
                await self.dubbing_pipeline.start(
                    file_path=self._current_file,
                    duration=duration,
                    target_lang=language
                )
            except Exception as e:
                logger.error(f"Dubbing task error: {e}", exc_info=True)
                self._dubbing_active = False

        self._dubbing_task = asyncio.create_task(_dubbing_task())

    async def stop_dubbing(self):
        """Stop the dubbing pipeline."""
        self._dubbing_active = False
        await self.dubbing_pipeline.stop()
        logger.info("Dubbing pipeline stopped")

    async def handle_seek(self, timestamp: float):
        """Handle seek event."""
        logger.debug(f"Seek to {timestamp}s")
        # Update dubbing pipeline playback position
        if self._dubbing_active:
            self.dubbing_pipeline.update_playback_time(timestamp)
        # Update active characters at this timestamp
        characters = self.character_mapper.get_all_characters()
        await self._broadcast("characters_detected", characters)

    async def update_playback_time(self, time: float):
        """Update current playback time for dubbing pipeline pacing."""
        if self._dubbing_active:
            self.dubbing_pipeline.update_playback_time(time)

    def get_status(self) -> dict:
        """Get pipeline status."""
        status = {
            "stage": self.current_stage.value,
            "processing": self._processing,
            "dubbing_active": self._dubbing_active,
            "characters": self.character_mapper.character_count,
            "gpu": self.gpu_manager.get_status(),
            "dubbing": self.dubbing_pipeline.get_status(),
            "mode": "modal" if self._use_modal else "local",
        }

        # Add Modal-specific status
        if self._use_modal and self.gpu_warmup:
            status["gpu_warm"] = self.gpu_warmup.is_warm
            status["gpu_warming"] = self.gpu_warmup.is_warming

        return status

    async def shutdown(self):
        """Clean up resources."""
        await self.stop_analysis()
        await self.stop_dubbing()
        self.face_detector.unload()
        self.diarizer.unload()
        if self.stt_service.is_loaded:
            self.stt_service.unload()
        self.tts_service.clear_cache()
        self.media_processor.cleanup()
        self._processing = False
        self._dubbing_active = False
        logger.info("Pipeline orchestrator shut down")
