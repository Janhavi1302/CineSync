"""
Speech-to-Text Service — faster-whisper based transcription.
Processes audio chunks and returns timestamped text segments.
Optimized for GTX 1650 (small model, int8 quantization).
"""

import asyncio
import logging
import os
from typing import List, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("cinesync.stt")


@dataclass
class TranscriptionSegment:
    """A single transcribed text segment with timing."""
    text: str
    start: float  # seconds
    end: float    # seconds
    speaker_id: Optional[str] = None
    words: List[Dict] = field(default_factory=list)
    language: str = "en"
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": round(self.end - self.start, 3),
            "speaker_id": self.speaker_id,
            "language": self.language,
            "confidence": round(self.confidence, 2),
            "words": self.words
        }


class STTService:
    """
    Speech-to-Text using faster-whisper.
    
    On GTX 1650 (int8): ~1.2GB VRAM, processes 5s chunks in ~1-2s.
    Falls back to CPU if GPU is occupied.
    """

    def __init__(self, model_size: str = "small", device: str = "auto",
                 compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self):
        """Load the Whisper model."""
        try:
            from faster_whisper import WhisperModel

            logger.info(f"Loading Whisper model: {self.model_size} "
                       f"(device={self.device}, compute={self.compute_type})")
            
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
            self._loaded = True
            logger.info("Whisper model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            logger.info("Falling back to CPU mode...")
            try:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8"
                )
                self._loaded = True
                logger.info("Whisper model loaded (CPU fallback)")
            except Exception as e2:
                logger.error(f"CPU fallback also failed: {e2}")
                self._loaded = False

    def unload(self):
        """Unload model and free memory."""
        self._model = None
        self._loaded = False
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        logger.info("Whisper model unloaded")

    async def transcribe_chunk(self, audio_path: str,
                                chunk_offset: float = 0.0) -> List[TranscriptionSegment]:
        """
        Transcribe an audio file/chunk.
        Runs in thread pool to avoid blocking the event loop.
        
        Args:
            audio_path: Path to WAV audio file
            chunk_offset: Time offset to add to segment timestamps
            
        Returns:
            List of TranscriptionSegment with absolute timestamps
        """
        if not self._loaded or not self._model:
            logger.warning("STT model not loaded")
            return []

        return await asyncio.to_thread(
            self._transcribe_sync, audio_path, chunk_offset
        )

    def _transcribe_sync(self, audio_path: str,
                          chunk_offset: float) -> List[TranscriptionSegment]:
        """Synchronous transcription (runs in thread)."""
        try:
            segments_iter, info = self._model.transcribe(
                audio_path,
                beam_size=5,
                word_timestamps=True,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=300,
                    speech_pad_ms=200
                )
            )

            detected_lang = info.language
            lang_prob = info.language_probability

            logger.debug(f"Detected language: {detected_lang} ({lang_prob:.0%})")

            results = []
            for seg in segments_iter:
                # Build word list with timestamps
                words = []
                if seg.words:
                    for w in seg.words:
                        words.append({
                            "word": w.word.strip(),
                            "start": round(w.start + chunk_offset, 3),
                            "end": round(w.end + chunk_offset, 3),
                            "probability": round(w.probability, 2)
                        })

                ts = TranscriptionSegment(
                    text=seg.text.strip(),
                    start=seg.start + chunk_offset,
                    end=seg.end + chunk_offset,
                    language=detected_lang,
                    confidence=round(
                        sum(w.probability for w in seg.words) / max(len(seg.words), 1)
                        if seg.words else 0.0, 2
                    ),
                    words=words
                )
                results.append(ts)

            logger.info(f"Transcribed {len(results)} segments from {audio_path}")
            return results

        except Exception as e:
            logger.error(f"Transcription error: {e}", exc_info=True)
            return []
