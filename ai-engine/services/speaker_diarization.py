"""
Speaker Diarization Service — PyAnnote-based speaker identification.
Runs on CPU to leave GPU free for other models (GTX 1650 optimization).
"""

import logging
import asyncio
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger("cinesync.diarization")


@dataclass
class SpeakerSegment:
    """A segment where a specific speaker is talking."""
    speaker_id: str
    start: float  # seconds
    end: float    # seconds
    confidence: float = 0.0

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_dict(self) -> dict:
        return {
            "speaker_id": self.speaker_id,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": round(self.duration, 3),
            "confidence": round(self.confidence, 2)
        }


class SpeakerDiarizationService:
    """
    Identifies who is speaking and when using pyannote.audio.
    
    Runs entirely on CPU to preserve GPU VRAM for other models.
    Processes audio in chunks (5-second windows).
    """

    def __init__(self, hf_token: Optional[str] = None, device: str = "cpu"):
        self.hf_token = hf_token
        self.device = device
        self._pipeline = None
        self._loaded = False
        self._segments: List[SpeakerSegment] = []
        self._speaker_map: Dict[str, int] = {}  # pyannote speaker → character_id

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self):
        """Load pyannote speaker diarization pipeline on CPU."""
        try:
            from pyannote.audio import Pipeline
            import torch

            logger.info("Loading pyannote diarization pipeline (CPU)...")
            self._pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token
            )
            # Force CPU
            self._pipeline.to(torch.device("cpu"))
            self._loaded = True
            logger.info("Speaker diarization pipeline loaded (CPU)")

        except ImportError:
            logger.warning("pyannote.audio not installed. Using mock diarization.")
            self._loaded = True  # mock mode
        except Exception as e:
            logger.error(f"Failed to load diarization pipeline: {e}")
            self._loaded = False

    def unload(self):
        """Unload pipeline."""
        self._pipeline = None
        self._loaded = False
        import gc
        gc.collect()
        logger.info("Diarization pipeline unloaded")

    async def process_audio(self, audio_path: str) -> List[SpeakerSegment]:
        """
        Process an audio file/chunk for speaker diarization.
        Runs on CPU in a thread pool to avoid blocking the event loop.
        """
        if self._pipeline is not None:
            return await asyncio.to_thread(self._diarize_real, audio_path)
        else:
            return self._diarize_mock(audio_path)

    def _diarize_real(self, audio_path: str) -> List[SpeakerSegment]:
        """Real pyannote diarization."""
        try:
            diarization = self._pipeline(audio_path)
            segments = []

            for turn, _, speaker in diarization.itertracks(yield_label=True):
                seg = SpeakerSegment(
                    speaker_id=speaker,
                    start=turn.start,
                    end=turn.end,
                    confidence=0.85  # pyannote doesn't expose per-segment confidence
                )
                segments.append(seg)

            self._segments.extend(segments)
            logger.info(f"Diarization: {len(segments)} segments, "
                       f"{len(set(s.speaker_id for s in segments))} speakers")
            return segments

        except Exception as e:
            logger.error(f"Diarization error: {e}")
            return []

    def _diarize_mock(self, audio_path: str) -> List[SpeakerSegment]:
        """Deterministic mock diarization (no randomness).
        Alternates speakers every ~2 seconds for consistent results."""
        speakers = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"]
        segments = []
        t = 0.0
        idx = 0

        while t < 5.0:  # 5-second chunk
            speaker = speakers[idx % len(speakers)]
            duration = 1.8  # fixed ~2s segments
            seg = SpeakerSegment(
                speaker_id=speaker,
                start=round(t, 3),
                end=round(min(t + duration, 5.0), 3),
                confidence=0.85
            )
            segments.append(seg)
            t += duration + 0.3  # fixed 300ms gap
            idx += 1

        self._segments.extend(segments)
        return segments

    def get_speaker_at_time(self, timestamp: float) -> Optional[str]:
        """Find who is speaking at a given timestamp."""
        for seg in reversed(self._segments):
            if seg.start <= timestamp <= seg.end:
                return seg.speaker_id
        return None

    def get_all_speakers(self) -> List[str]:
        """Get all unique speaker IDs."""
        return list(set(s.speaker_id for s in self._segments))

    def map_speaker_to_character(self, speaker_id: str, character_id: int):
        """Associate a pyannote speaker label with a character ID."""
        self._speaker_map[speaker_id] = character_id
        logger.info(f"Mapped {speaker_id} → Character {character_id}")

    def get_character_for_speaker(self, speaker_id: str) -> Optional[int]:
        """Get character ID for a speaker label."""
        return self._speaker_map.get(speaker_id)

    def get_segments_for_speaker(self, speaker_id: str) -> List[SpeakerSegment]:
        """Get all segments for a specific speaker."""
        return [s for s in self._segments if s.speaker_id == speaker_id]

    def get_all_segments(self) -> List[Dict]:
        """Get all segments as dicts."""
        return [s.to_dict() for s in self._segments]

    def clear(self):
        """Clear all segments."""
        self._segments.clear()
