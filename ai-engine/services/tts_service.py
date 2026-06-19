"""
TTS Service — Edge TTS with SSML emotion styling.
Generates premium neural voices with emotion-aware prosody.
Each character gets a unique voice from Microsoft Edge Neural TTS.
"""

import asyncio
import logging
import os
import tempfile
import hashlib
from typing import Optional, Dict, List
from dataclasses import dataclass

logger = logging.getLogger("cinesync.tts")

# ── Premium Neural Voices ─────────────────────────────────────
# Edge TTS voices with style support (emotion-capable)
# Organized so we can pick matching gender voices
VOICE_POOL = {
    "hi": {
        "male": [
            {"name": "hi-IN-MadhurNeural", "gender": "male", "label": "Madhur"},
            {"name": "hi-IN-MadhurNeural", "gender": "male", "label": "Madhur-Deep",
             "pitch_offset": "-20Hz"},
        ],
        "female": [
            {"name": "hi-IN-SwaraNeural", "gender": "female", "label": "Swara"},
            {"name": "hi-IN-SwaraNeural", "gender": "female", "label": "Swara-High",
             "pitch_offset": "+15Hz"},
        ],
    },
    "en": {
        "male": [
            {"name": "en-US-GuyNeural", "gender": "male", "label": "Guy"},
            {"name": "en-US-DavisNeural", "gender": "male", "label": "Davis"},
        ],
        "female": [
            {"name": "en-US-JennyNeural", "gender": "female", "label": "Jenny"},
            {"name": "en-US-AriaNeural", "gender": "female", "label": "Aria"},
        ],
    },
    "es": {
        "male": [{"name": "es-ES-AlvaroNeural", "gender": "male", "label": "Alvaro"}],
        "female": [{"name": "es-ES-ElviraNeural", "gender": "female", "label": "Elvira"}],
    },
    "fr": {
        "male": [{"name": "fr-FR-HenriNeural", "gender": "male", "label": "Henri"}],
        "female": [{"name": "fr-FR-DeniseNeural", "gender": "female", "label": "Denise"}],
    },
    "de": {
        "male": [{"name": "de-DE-ConradNeural", "gender": "male", "label": "Conrad"}],
        "female": [{"name": "de-DE-KatjaNeural", "gender": "female", "label": "Katja"}],
    },
    "ja": {
        "male": [{"name": "ja-JP-KeitaNeural", "gender": "male", "label": "Keita"}],
        "female": [{"name": "ja-JP-NanamiNeural", "gender": "female", "label": "Nanami"}],
    },
    "ko": {
        "male": [{"name": "ko-KR-InJoonNeural", "gender": "male", "label": "InJoon"}],
        "female": [{"name": "ko-KR-SunHiNeural", "gender": "female", "label": "SunHi"}],
    },
    "zh": {
        "male": [{"name": "zh-CN-YunxiNeural", "gender": "male", "label": "Yunxi"}],
        "female": [{"name": "zh-CN-XiaoxiaoNeural", "gender": "female", "label": "Xiaoxiao"}],
    },
    "ar": {
        "male": [{"name": "ar-SA-HamedNeural", "gender": "male", "label": "Hamed"}],
        "female": [{"name": "ar-SA-ZariyahNeural", "gender": "female", "label": "Zariyah"}],
    },
    "pt": {
        "male": [{"name": "pt-BR-AntonioNeural", "gender": "male", "label": "Antonio"}],
        "female": [{"name": "pt-BR-FranciscaNeural", "gender": "female", "label": "Francisca"}],
    },
    "ru": {
        "male": [{"name": "ru-RU-DmitryNeural", "gender": "male", "label": "Dmitry"}],
        "female": [{"name": "ru-RU-SvetlanaNeural", "gender": "female", "label": "Svetlana"}],
    },
}

# Emotion → edge-tts prosody mapping (strongly expressive)
# Rate: ±percentage, Pitch: ±Hz, Volume: ±percentage
EMOTION_PROSODY = {
    "anger":      {"rate": "+25%", "pitch": "+30Hz",  "volume": "+30%"},
    "sadness":    {"rate": "-30%", "pitch": "-25Hz",  "volume": "-20%"},
    "joy":        {"rate": "+15%", "pitch": "+25Hz",  "volume": "+20%"},
    "fear":       {"rate": "+30%", "pitch": "+40Hz",  "volume": "-10%"},
    "surprise":   {"rate": "+20%", "pitch": "+50Hz",  "volume": "+25%"},
    "excitement": {"rate": "+20%", "pitch": "+35Hz",  "volume": "+25%"},
    "disgust":    {"rate": "-10%", "pitch": "-15Hz",  "volume": "+10%"},
    "contempt":   {"rate": "-5%",  "pitch": "-10Hz",  "volume": "+5%"},
    "neutral":    {"rate": "+0%",  "pitch": "+0Hz",   "volume": "+0%"},
}


@dataclass
class TTSResult:
    """Result of a TTS synthesis."""
    audio_path: str
    duration: float  # seconds
    voice_name: str
    character_id: Optional[str] = None
    emotion: str = "neutral"

    def to_dict(self) -> dict:
        return {
            "audio_path": self.audio_path,
            "duration": round(self.duration, 3),
            "voice_name": self.voice_name,
            "character_id": self.character_id,
            "emotion": self.emotion,
        }


class TTSService:
    """
    Premium Text-to-Speech using Microsoft Edge Neural TTS.
    
    Features:
    - Emotion-aware prosody via SSML (rate, pitch, volume)
    - Gender-matched voices (uses pitch analysis to detect gender)
    - Unique voice per character (auto-assigned from voice pool)
    - Caches generated audio to avoid re-synthesis
    - No GPU needed — uses Microsoft's cloud neural voices
    """

    def __init__(self):
        self._voice_assignments: Dict[str, str] = {}  # character_id → voice_name
        self._voice_configs: Dict[str, Dict] = {}  # character_id → full voice config
        self._gender_cache: Dict[str, str] = {}  # character_id → "male"/"female"
        self._male_counter: Dict[str, int] = {}  # language → next male voice index
        self._female_counter: Dict[str, int] = {}  # language → next female voice index
        self._cache_dir = os.path.join(tempfile.gettempdir(), "cinesync_tts")
        os.makedirs(self._cache_dir, exist_ok=True)

    def assign_voice(self, character_id: str, language: str,
                     gender: Optional[str] = None) -> str:
        """Assign a unique voice to a character, matching gender."""
        if character_id in self._voice_assignments:
            return self._voice_assignments[character_id]

        lang_pool = VOICE_POOL.get(language, VOICE_POOL.get("en", {}))
        
        # Determine gender
        if gender and gender in ("male", "female"):
            resolved_gender = gender
        elif character_id in self._gender_cache:
            resolved_gender = self._gender_cache[character_id]
        else:
            # Default: alternate male/female for fairness
            total_assigned = len(self._voice_assignments)
            resolved_gender = "male" if total_assigned % 2 == 0 else "female"

        # Pick from the right gender pool
        voices = lang_pool.get(resolved_gender, lang_pool.get("male", []))
        if not voices:
            # Fallback: use any voice from the language
            voices = lang_pool.get("male", []) + lang_pool.get("female", [])
        
        # Round-robin within the gender pool
        counter_key = f"{language}_{resolved_gender}"
        idx = self._male_counter.get(counter_key, 0) if resolved_gender == "male" \
              else self._female_counter.get(counter_key, 0)
        voice = voices[idx % len(voices)]
        
        if resolved_gender == "male":
            self._male_counter[counter_key] = idx + 1
        else:
            self._female_counter[counter_key] = idx + 1

        self._voice_assignments[character_id] = voice["name"]
        self._voice_configs[character_id] = voice
        self._gender_cache[character_id] = resolved_gender

        logger.info(f"Assigned voice '{voice['label']}' ({voice['name']}, {resolved_gender}) "
                    f"to character {character_id}")
        return voice["name"]

    def set_gender(self, character_id: str, gender: str):
        """Set the gender for a character ONLY if no voice is assigned yet.
        Once a voice is locked, gender changes are ignored to maintain consistency."""
        if character_id in self._voice_assignments:
            return  # Voice already locked — don't change
        if character_id in self._gender_cache:
            return  # Gender already set from first detection
        self._gender_cache[character_id] = gender
        logger.info(f"Gender for {character_id}: {gender}")

    def get_voice_for_character(self, character_id: str,
                                 language: str = "hi") -> str:
        """Get the assigned voice name for a character."""
        if character_id not in self._voice_assignments:
            gender = self._gender_cache.get(character_id)
            return self.assign_voice(character_id, language, gender)
        return self._voice_assignments[character_id]

    def get_voice_label(self, voice_name: str) -> str:
        """Get human-readable label for a voice."""
        for lang_pool in VOICE_POOL.values():
            for gender_voices in lang_pool.values():
                for v in gender_voices:
                    if v["name"] == voice_name:
                        return v["label"]
        return voice_name

    async def synthesize(
        self, text: str, voice_name: str,
        emotion: str = "neutral",
        character_id: Optional[str] = None
    ) -> Optional[TTSResult]:
        """
        Synthesize text to speech with emotion-aware prosody.

        Args:
            text: The text to speak
            voice_name: Edge TTS voice name
            emotion: Emotion for prosody adjustment
            character_id: Character identifier

        Returns:
            TTSResult with path to generated audio file
        """
        if not text or not text.strip():
            return None

        # Check cache
        cache_key = hashlib.md5(
            f"{text}|{voice_name}|{emotion}".encode()
        ).hexdigest()
        cache_path = os.path.join(self._cache_dir, f"{cache_key}.mp3")

        if os.path.exists(cache_path):
            duration = await self._get_audio_duration(cache_path)
            return TTSResult(
                audio_path=cache_path,
                duration=duration,
                voice_name=voice_name,
                character_id=character_id,
                emotion=emotion
            )

        try:
            import edge_tts

            # Get prosody settings for the emotion
            prosody = EMOTION_PROSODY.get(emotion, EMOTION_PROSODY["neutral"])

            # Apply pitch_offset from voice config for voice differentiation
            pitch = prosody["pitch"]
            if character_id and character_id in self._voice_configs:
                voice_cfg = self._voice_configs[character_id]
                offset = voice_cfg.get("pitch_offset", "")
                if offset:
                    try:
                        base_hz = int(pitch.replace("Hz", "").replace("+", ""))
                        offset_hz = int(offset.replace("Hz", "").replace("+", ""))
                        combined = base_hz + offset_hz
                        pitch = f"{'+' if combined >= 0 else ''}{combined}Hz"
                    except ValueError:
                        pass

            communicate = edge_tts.Communicate(
                text, voice_name,
                rate=prosody["rate"],
                pitch=pitch,
                volume=prosody["volume"]
            )

            await communicate.save(cache_path)

            duration = await self._get_audio_duration(cache_path)

            logger.debug(f"Synthesized [{emotion}] '{text[:40]}...' → "
                        f"{voice_name} ({duration:.1f}s)")

            return TTSResult(
                audio_path=cache_path,
                duration=duration,
                voice_name=voice_name,
                character_id=character_id,
                emotion=emotion
            )

        except Exception as e:
            logger.error(f"TTS error: {e}", exc_info=True)
            return None

    async def _get_audio_duration(self, file_path: str) -> float:
        """Get duration of an audio file using pydub or fallback."""
        try:
            from pydub import AudioSegment
            audio = await asyncio.to_thread(AudioSegment.from_file, file_path)
            return len(audio) / 1000.0
        except Exception:
            # Rough estimate: 150 words per minute avg
            return 2.0

    async def synthesize_batch(
        self, segments: List[Dict],
        language: str = "hi"
    ) -> List[TTSResult]:
        """
        Synthesize multiple text segments.
        Each segment should have: text, character_id, emotion
        """
        results = []
        for seg in segments:
            text = seg.get("text", "")
            char_id = seg.get("character_id", "unknown")
            emotion = seg.get("emotion", "neutral")
            voice = self.get_voice_for_character(char_id, language)

            result = await self.synthesize(text, voice, emotion, char_id)
            if result:
                results.append(result)

        return results

    def get_all_assignments(self) -> Dict[str, str]:
        """Get all character → voice assignments."""
        return {
            char_id: {
                "voice": voice,
                "label": self.get_voice_label(voice),
                "gender": self._gender_cache.get(char_id, "unknown"),
            }
            for char_id, voice in self._voice_assignments.items()
        }

    def clear_cache(self):
        """Clear TTS audio cache."""
        import shutil
        if os.path.exists(self._cache_dir):
            shutil.rmtree(self._cache_dir, ignore_errors=True)
            os.makedirs(self._cache_dir, exist_ok=True)
        # Also clear voice assignments so they can be re-assigned
        self._voice_assignments.clear()
        self._voice_configs.clear()
        self._gender_cache.clear()
        self._male_counter.clear()
        self._female_counter.clear()
        logger.info("TTS cache and voice assignments cleared")
