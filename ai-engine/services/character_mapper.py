"""
Character Mapper — Fuses face detection + speaker diarization into unified character profiles.
Supports 15+ simultaneous characters with persistent identity tracking.
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("cinesync.character_mapper")


@dataclass
class CharacterProfile:
    """Unified character profile combining visual and audio identification."""
    id: int
    name: str = ""
    
    # Visual identity
    face_track_id: int = -1
    face_detections: int = 0
    last_bbox: Optional[tuple] = None
    face_confidence: float = 0.0
    
    # Audio identity
    speaker_id: Optional[str] = None  # pyannote speaker label
    voice_profile: str = "Default"
    speaking_segments: int = 0
    total_speaking_time: float = 0.0
    
    # State
    is_active: bool = False
    is_speaking: bool = False
    last_seen: float = 0.0
    
    # Emotion (text-based)
    current_emotion: str = "neutral"
    emotion_confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name or f"Character {self.id}",
            "confidence": round(self.face_confidence, 2),
            "is_speaking": self.is_speaking,
            "is_active": self.is_active,
            "bbox": list(self.last_bbox) if self.last_bbox else None,
            "speaker_id": self.speaker_id,
            "voiceProfile": self.voice_profile,
            "emotion": self.current_emotion,
            "emotion_confidence": round(self.emotion_confidence, 2),
            "speaking_time": round(self.total_speaking_time, 1),
            "detections_count": self.face_detections,
        }


class CharacterMapper:
    """
    Fuses face detection results with speaker diarization to build
    persistent character profiles.
    
    Key capabilities:
    - Maps detected faces to speaker voices
    - Maintains character identity across scenes
    - Supports 15+ simultaneous characters
    - Tracks speaking state per character
    """

    def __init__(self, max_characters: int = 15):
        self.max_characters = max_characters
        self._profiles: Dict[int, CharacterProfile] = {}
        self._speaker_to_char: Dict[str, int] = {}
        self._next_id = 1

    def update_from_detections(self, detections: list, timestamp: float):
        """
        Update character profiles from face detection results.
        
        Args:
            detections: List of Detection objects from face_detection service
            timestamp: Current video timestamp
        """
        active_ids = set()

        for det in detections:
            track_id = det.track_id if hasattr(det, 'track_id') else det.get('track_id', -1)
            bbox = det.bbox if hasattr(det, 'bbox') else det.get('bbox')
            conf = det.confidence if hasattr(det, 'confidence') else det.get('confidence', 0)

            # Find or create character for this track
            char_id = self._find_char_by_track(track_id)
            if char_id is None:
                char_id = self._create_character(track_id)

            profile = self._profiles[char_id]
            profile.face_detections += 1
            profile.last_bbox = tuple(bbox) if bbox else None
            profile.last_seen = timestamp
            profile.is_active = True
            
            # Running average confidence
            n = profile.face_detections
            profile.face_confidence = ((n-1) * profile.face_confidence + conf) / n
            
            active_ids.add(char_id)

        # Mark inactive characters
        for cid, profile in self._profiles.items():
            if cid not in active_ids:
                if (timestamp - profile.last_seen) > 3.0:
                    profile.is_active = False

    def update_from_diarization(self, segments: list, timestamp: float):
        """
        Update character speaking state from diarization segments.
        
        Args:
            segments: List of SpeakerSegment dicts
            timestamp: Current processing timestamp
        """
        # Find which speakers are active at this timestamp
        active_speakers = set()
        for seg in segments:
            # Handle both dict and object segment types
            if isinstance(seg, dict):
                start = seg.get('start', 0)
                end = seg.get('end', 0)
                spk = seg.get('speaker_id', '')
            else:
                start = getattr(seg, 'start', 0)
                end = getattr(seg, 'end', 0)
                spk = getattr(seg, 'speaker_id', '')

            if start <= timestamp <= end:
                active_speakers.add(spk)

        # Update speaking state
        for cid, profile in self._profiles.items():
            if profile.speaker_id and profile.speaker_id in active_speakers:
                profile.is_speaking = True
            else:
                profile.is_speaking = False

    def auto_map_speakers(self, segments: list):
        """
        Automatically map speakers to characters based on temporal overlap.
        Uses a simple heuristic: the speaker most active when a face is visible
        is likely that character.
        """
        if not self._profiles or not segments:
            return

        # For each unassigned character, find the most overlapping speaker
        for cid, profile in self._profiles.items():
            if profile.speaker_id is not None:
                continue

            # Check which speakers are active during this character's visible time
            best_speaker = None
            best_overlap = 0.0
            char_time = profile.last_seen

            for seg in segments:
                if isinstance(seg, dict):
                    start = seg.get('start', 0)
                    end = seg.get('end', 0)
                    spk = seg.get('speaker_id', '')
                else:
                    start = getattr(seg, 'start', 0)
                    end = getattr(seg, 'end', 0)
                    spk = getattr(seg, 'speaker_id', '')

                if spk in self._speaker_to_char.values():
                    continue  # already assigned

                # Simple proximity check
                overlap = max(0, min(end, char_time + 1) - max(start, char_time - 1))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_speaker = spk

            if best_speaker:
                profile.speaker_id = best_speaker
                self._speaker_to_char[best_speaker] = cid
                logger.info(f"Auto-mapped {best_speaker} → Character {cid}")

    def _find_char_by_track(self, track_id: int) -> Optional[int]:
        """Find character ID associated with a face track."""
        for cid, profile in self._profiles.items():
            if profile.face_track_id == track_id:
                return cid
        return None

    def _create_character(self, track_id: int) -> int:
        """Create a new character profile."""
        char_id = self._next_id
        self._next_id += 1
        self._profiles[char_id] = CharacterProfile(
            id=char_id,
            face_track_id=track_id
        )
        logger.info(f"New character detected: ID={char_id} (track={track_id})")
        return char_id

    def set_character_name(self, char_id: int, name: str):
        """Set a user-defined name for a character."""
        if char_id in self._profiles:
            self._profiles[char_id].name = name

    def set_character_emotion(self, char_id: int, emotion: str, confidence: float = 0.0):
        """Update character's current emotion."""
        if char_id in self._profiles:
            self._profiles[char_id].current_emotion = emotion
            self._profiles[char_id].emotion_confidence = confidence

    def get_all_characters(self) -> List[Dict]:
        """Get all character profiles as dicts."""
        return [p.to_dict() for p in self._profiles.values()]

    def get_active_characters(self) -> List[Dict]:
        """Get currently visible characters."""
        return [p.to_dict() for p in self._profiles.values() if p.is_active]

    def get_speaking_characters(self) -> List[int]:
        """Get IDs of currently speaking characters."""
        return [p.id for p in self._profiles.values() if p.is_speaking]

    def get_character(self, char_id: int) -> Optional[Dict]:
        """Get a specific character profile."""
        if char_id in self._profiles:
            return self._profiles[char_id].to_dict()
        return None

    @property
    def character_count(self) -> int:
        return len(self._profiles)
