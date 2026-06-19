"""
Dubbing Pipeline — generates a complete dubbed audio track.

Flow: Extract audio → STT → Translation → TTS → Mix into single track
The mixed track replaces original voices while preserving background sounds.

Supports two backends:
- Bhashini (preferred for Indian languages): AI4Bharat IndicTrans + TTS
- Fallback: deep-translator (Google) + Edge TTS (Microsoft)
"""

import asyncio
import logging
import os
import tempfile
import time
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass, field

from services.bhashini_service import BhashiniService

logger = logging.getLogger("cinesync.dubbing")


@dataclass
class DubbedSegment:
    """A single dubbed audio segment."""
    start: float
    end: float
    original_text: str
    translated_text: str
    audio_path: str
    character_id: str = "unknown"
    emotion: str = "neutral"
    voice_name: str = ""
    duration: float = 0.0

    def to_dict(self) -> dict:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "originalText": self.original_text,
            "translatedText": self.translated_text,
            "characterId": self.character_id,
            "emotion": self.emotion,
            "voiceName": self.voice_name,
            "duration": round(self.duration, 3),
        }


class DubbingPipeline:
    """
    Generates a complete dubbed audio track.
    
    Instead of streaming individual segments via WebSocket,
    this pipeline produces a single audio file that can be
    synced with the video for perfect playback.
    """

    def __init__(self, stt_service, translation_service, tts_service,
                 media_processor, character_mapper, emotion_classifier):
        self.stt = stt_service
        self.translator = translation_service
        self.tts = tts_service
        self.media_processor = media_processor
        self.character_mapper = character_mapper
        self.emotion_classifier = emotion_classifier

        # Bhashini — preferred backend for Indian languages
        self.bhashini = BhashiniService()
        if self.bhashini.is_available:
            logger.info("🇮🇳 Bhashini enabled for Indian language dubbing")
        else:
            logger.info("Bhashini not configured — using Edge TTS + Google Translate")

        self._active = False
        self._target_lang = "hi"
        self._current_file: Optional[str] = None
        self._duration: float = 0.0
        self._playback_time: float = 0.0
        self._processed_up_to: float = 0.0
        self._task: Optional[asyncio.Task] = None
        self._broadcast: Optional[Callable] = None

        self._dubbed_segments: List[DubbedSegment] = []
        self._chunk_duration = 5.0
        self._buffer_ahead = 30.0

        # Stats
        self._total_segments = 0
        self._total_time = 0.0

        # Pseudo-diarization
        self._last_seg_end: float = 0.0
        self._current_speaker_idx: int = 0
        self._speaker_gap_threshold: float = 1.5

        # Output
        self._output_path: Optional[str] = None

    def set_broadcast(self, callback: Callable):
        self._broadcast = callback

    async def _send(self, msg_type: str, data: dict):
        if self._broadcast:
            await self._broadcast({"type": msg_type, "data": data})

    async def start(self, file_path: str, duration: float,
                    target_lang: str = "hi"):
        """Start the dubbing pipeline."""
        if self._active:
            await self.stop()

        self._current_file = file_path
        self._duration = duration
        self._target_lang = target_lang
        self._active = True
        self._processed_up_to = 0.0
        self._dubbed_segments = []
        self._total_segments = 0
        self._total_time = 0.0
        self._last_seg_end = 0.0
        self._current_speaker_idx = 0
        self._output_path = None
        self._speaker_genders = {}  # speaker_id → "male"/"female" (locked)

        self.tts.clear_cache()

        # Load STT model
        if not self.stt.is_loaded:
            await self._send("dubbing_status", {
                "stage": "loading_stt", "progress": 0,
                "message": "Loading speech recognition model..."
            })
            await asyncio.to_thread(self.stt.load)

        # Assign voices to known characters
        characters = self.character_mapper.get_all_characters()
        for char in characters:
            char_id = str(char.get("id", "unknown"))
            gender = char.get("gender", None)
            self.tts.assign_voice(char_id, target_lang, gender)

        await self._send("dubbing_status", {
            "stage": "active", "language": target_lang,
            "progress": 0, "message": "Starting dubbing pipeline..."
        })

        self._task = asyncio.create_task(self._process_all())
        logger.info(f"Dubbing pipeline started: {file_path} → {target_lang}")

    async def stop(self):
        """Stop the dubbing pipeline."""
        self._active = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self.stt.is_loaded:
            self.stt.unload()

        await self._send("dubbing_status", {
            "stage": "stopped",
            "totalSegments": self._total_segments,
            "totalTime": round(self._total_time, 1)
        })
        logger.info(f"Dubbing stopped. {self._total_segments} segments")

    async def _process_all(self):
        """Process entire video: extract full audio → STT → Translate → TTS → Mix."""
        try:
            total_start = time.time()

            # ── Phase 1: Extract FULL audio from video ──
            await self._send("dubbing_status", {
                "stage": "active",
                "language": self._target_lang,
                "progress": 5,
                "message": "Extracting full audio from video..."
            })

            audio_path = await self.media_processor.extract_audio_chunk(
                self._current_file, start=0, duration=self._duration
            )
            if not audio_path:
                logger.error("Failed to extract audio")
                return

            # ── Phase 2: Transcribe entire audio at once (single STT call) ──
            await self._send("dubbing_status", {
                "stage": "active",
                "language": self._target_lang,
                "progress": 10,
                "message": f"Transcribing full audio ({self._duration:.0f}s)..."
            })

            t0 = time.time()
            all_segments = await self.stt.transcribe_chunk(audio_path, chunk_offset=0)
            stt_elapsed = time.time() - t0
            logger.info(f"Full STT completed: {len(all_segments)} segments in {stt_elapsed:.1f}s")

            if not all_segments:
                logger.warning("No speech segments detected")
                return

            await self._send("dubbing_status", {
                "stage": "active",
                "language": self._target_lang,
                "progress": 30,
                "message": f"Found {len(all_segments)} speech segments in {stt_elapsed:.1f}s"
            })

            # ── Phase 3: Process each segment (emotion → speaker → translate → TTS) ──
            total_segs = len(all_segments)
            for i, seg in enumerate(all_segments):
                if not self._active:
                    return

                # Emotion classification
                emotion_label, emotion_conf = self.emotion_classifier.classify(seg.text)
                seg_emotion = emotion_label or "neutral"
                if "!" in seg.text and seg_emotion == "neutral":
                    seg_emotion = "excitement"
                elif "?" in seg.text and seg_emotion == "neutral":
                    seg_emotion = "surprise"

                # Speaker identification (gender detection from full audio)
                seg_gender = await self._detect_segment_gender(
                    audio_path, seg.start, seg.end
                )
                char_id = self._get_stable_speaker(seg.start, seg.end, seg_gender)

                # Translate + TTS
                source_lang = seg.language or "en"
                translated = None
                tts_result = None
                bhashini_used = False

                # ── Try Bhashini first (Indian languages, combined pipeline) ──
                if self.bhashini.is_available:
                    spk_gender = self._speaker_genders.get(char_id, "female")
                    result = await self.bhashini.translate_and_speak(
                        seg.text, source_lang, self._target_lang, spk_gender
                    )
                    if result:
                        translated, bhashini_audio_path = result
                        # Wrap in a TTS-like result
                        from dataclasses import dataclass as _dc
                        @_dc
                        class _BhashiniResult:
                            audio_path: str
                            voice_name: str
                            duration: float
                        # Get duration from file
                        try:
                            from pydub import AudioSegment as _AS
                            _audio = _AS.from_file(bhashini_audio_path)
                            _dur = len(_audio) / 1000.0
                        except Exception:
                            _dur = seg.end - seg.start
                        tts_result = _BhashiniResult(
                            audio_path=bhashini_audio_path,
                            voice_name=f"Bhashini-{spk_gender}",
                            duration=_dur,
                        )
                        bhashini_used = True
                        logger.debug(f"Bhashini pipeline used for segment {i+1}")

                # ── Fallback: deep-translator + Edge TTS ──
                if not bhashini_used:
                    translated = await self.translator.translate(
                        seg.text, self._target_lang, source_lang
                    )
                    voice = self.tts.get_voice_for_character(char_id, self._target_lang)
                    tts_result = await self.tts.synthesize(
                        translated, voice, seg_emotion, char_id
                    )

                if tts_result:
                    dubbed = DubbedSegment(
                        start=seg.start,
                        end=seg.end,
                        original_text=seg.text,
                        translated_text=translated,
                        audio_path=tts_result.audio_path,
                        character_id=char_id,
                        emotion=seg_emotion,
                        voice_name=tts_result.voice_name,
                        duration=tts_result.duration,
                    )
                    self._dubbed_segments.append(dubbed)
                    self._total_segments += 1

                    # Send live transcript
                    await self._send("live_transcript", {
                        "start": round(seg.start, 3),
                        "end": round(seg.end, 3),
                        "originalText": seg.text,
                        "translatedText": translated,
                        "characterId": char_id,
                        "emotion": seg_emotion,
                        "language": self._target_lang,
                    })

                # Progress: 30% (STT done) → 90% (all segments processed)
                seg_progress = 30 + int((i + 1) / total_segs * 60)
                elapsed = time.time() - total_start
                await self._send("dubbing_status", {
                    "stage": "active",
                    "language": self._target_lang,
                    "progress": seg_progress,
                    "processedTo": round(seg.end, 1),
                    "totalSegments": self._total_segments,
                    "chunkTime": round(elapsed, 2),
                    "message": f"Processing segment {i+1}/{total_segs} ({seg.start:.0f}s–{seg.end:.0f}s)"
                })

                # Send discovered speakers as "characters"
                if self._speaker_genders:
                    voice_assignments = self.tts.get_all_assignments()
                    chars = []
                    for spk_id, gender in self._speaker_genders.items():
                        assignment = voice_assignments.get(spk_id, {})
                        spk_segs = [s for s in self._dubbed_segments if s.character_id == spk_id]
                        total_time = sum(s.end - s.start for s in spk_segs)
                        last_emotion = spk_segs[-1].emotion if spk_segs else "neutral"
                        chars.append({
                            "id": spk_id,
                            "name": f"{'♂' if gender == 'male' else '♀'} {assignment.get('label', spk_id)}",
                            "confidence": 0.9,
                            "is_speaking": False,
                            "is_active": True,
                            "bbox": None,
                            "speaker_id": spk_id,
                            "voiceProfile": assignment.get("label", "Default"),
                            "emotion": last_emotion,
                            "emotion_confidence": 0.7,
                            "speaking_time": round(total_time, 1),
                            "detections_count": len(spk_segs),
                        })
                    await self._send("characters_detected", chars)

                await asyncio.sleep(0.02)

            self._processed_up_to = self._duration
            self._total_time = time.time() - total_start

            # ── Phase 2: Mix all TTS segments into one audio track ──
            await self._send("dubbing_status", {
                "stage": "active",
                "language": self._target_lang,
                "progress": 92,
                "message": "Mixing dubbed audio track..."
            })

            output_path = await self._mix_audio_track()

            if output_path and self._active:
                self._output_path = output_path
                total_elapsed = time.time() - total_start

                # Send the dubbed track path to frontend
                await self._send("dubbed_track_ready", {
                    "audioPath": output_path,
                    "totalSegments": self._total_segments,
                    "totalTime": round(total_elapsed, 1),
                    "language": self._target_lang,
                    "segments": [s.to_dict() for s in self._dubbed_segments]
                })

                await self._send("dubbing_status", {
                    "stage": "complete",
                    "language": self._target_lang,
                    "progress": 100,
                    "totalSegments": self._total_segments,
                    "totalTime": round(total_elapsed, 1),
                    "message": f"Dubbing complete — {self._total_segments} segments in {total_elapsed:.0f}s"
                })

                logger.info(f"Dubbing complete: {self._total_segments} segments, "
                           f"track: {output_path}")
            else:
                await self._send("dubbing_status", {
                    "stage": "complete",
                    "progress": 100,
                    "totalSegments": 0,
                    "message": "No speech detected in video"
                })

        except asyncio.CancelledError:
            logger.info("Dubbing cancelled")
        except Exception as e:
            logger.error(f"Dubbing error: {e}", exc_info=True)
            await self._send("dubbing_status", {
                "stage": "error", "message": str(e)
            })

    async def _mix_audio_track(self) -> Optional[str]:
        """Mix all TTS segments into the original audio, ducking vocals."""
        if not self._dubbed_segments:
            return None

        return await asyncio.to_thread(self._mix_audio_sync)

    def _mix_audio_sync(self) -> Optional[str]:
        """Synchronous audio mixing using pydub."""
        try:
            from pydub import AudioSegment

            # Extract full original audio
            logger.info("Extracting original audio...")
            orig_audio_path = os.path.join(
                tempfile.gettempdir(), "cinesync_media", "original_full.wav"
            )
            os.makedirs(os.path.dirname(orig_audio_path), exist_ok=True)

            import subprocess
            ffmpeg = self.media_processor.ffmpeg
            cmd = [
                ffmpeg, "-y", "-i", self._current_file,
                "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                orig_audio_path
            ]
            subprocess.run(cmd, capture_output=True, timeout=120)

            if not os.path.exists(orig_audio_path):
                logger.error("Failed to extract original audio")
                return None

            # Tell pydub where ffmpeg is
            import pydub
            import pydub.utils
            pydub.AudioSegment.converter = ffmpeg
            # Also set ffprobe via pydub utils
            try:
                ffprobe_path = ffmpeg.replace('ffmpeg-win-x86_64', 'ffprobe-win-x86_64').replace('ffmpeg.exe', 'ffprobe.exe')
                if os.path.exists(ffprobe_path):
                    pydub.utils.PROBER = ffprobe_path
            except:
                pass

            # Load original audio
            original = AudioSegment.from_wav(orig_audio_path)
            logger.info(f"Original audio: {len(original)}ms")

            # Sort segments by start time to prevent ordering issues
            sorted_segments = sorted(self._dubbed_segments, key=lambda s: s.start)

            # Process each dubbed segment
            for i, seg in enumerate(sorted_segments):
                try:
                    if not os.path.exists(seg.audio_path):
                        logger.warning(f"TTS file missing: {seg.audio_path}")
                        continue

                    # Convert MP3 → WAV using ffmpeg subprocess (bypass pydub's from_file)
                    temp_wav = seg.audio_path + ".wav"
                    result = subprocess.run(
                        [ffmpeg, "-y", "-i", seg.audio_path, "-acodec", "pcm_s16le",
                         "-ar", "44100", "-ac", "2", temp_wav],
                        capture_output=True, timeout=30
                    )
                    if result.returncode != 0 or not os.path.exists(temp_wav):
                        logger.warning(f"FFmpeg convert failed for {seg.audio_path}: {result.stderr[:200]}")
                        continue

                    tts_audio = AudioSegment.from_wav(temp_wav)

                    start_ms = int(seg.start * 1000)
                    end_ms = int(seg.end * 1000)
                    slot_duration_ms = end_ms - start_ms

                    # Ensure we don't go past the end
                    if start_ms >= len(original):
                        continue

                    # ── Time-fit TTS to prevent overlap ──
                    # If TTS is longer than the original slot, speed it up
                    # If TTS is much shorter, leave a natural pause
                    tts_duration_ms = len(tts_audio)
                    if tts_duration_ms > slot_duration_ms and slot_duration_ms > 200:
                        speed_ratio = tts_duration_ms / slot_duration_ms
                        # Cap speed-up at 1.6x to keep speech intelligible
                        speed_ratio = min(speed_ratio, 1.6)
                        # Use ffmpeg atempo filter for clean time-stretching
                        tempo_wav = seg.audio_path + ".tempo.wav"
                        # atempo supports 0.5-2.0 range
                        tempo_cmd = [
                            ffmpeg, "-y", "-i", temp_wav,
                            "-filter:a", f"atempo={speed_ratio}",
                            "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                            tempo_wav
                        ]
                        tempo_result = subprocess.run(tempo_cmd, capture_output=True, timeout=30)
                        if tempo_result.returncode == 0 and os.path.exists(tempo_wav):
                            tts_audio = AudioSegment.from_wav(tempo_wav)
                            try: os.remove(tempo_wav)
                            except: pass
                            logger.debug(f"Time-stretched {speed_ratio:.2f}x at {seg.start:.1f}s")

                    # Final safety: hard-truncate to slot duration to prevent any bleed
                    if len(tts_audio) > slot_duration_ms:
                        tts_audio = tts_audio[:slot_duration_ms]

                    # Duck the original audio at this segment (reduce by 20dB)
                    # This preserves background sounds at ~10% volume
                    seg_end = min(end_ms, len(original))
                    ducked_portion = original[start_ms:seg_end] - 20
                    original = original[:start_ms] + ducked_portion + original[seg_end:]

                    # Overlay TTS audio at the correct position
                    original = original.overlay(tts_audio, position=start_ms)

                    # Cleanup temp wav
                    try: os.remove(temp_wav)
                    except: pass

                    logger.info(f"Mixed segment at {seg.start:.1f}s "
                               f"(slot={slot_duration_ms}ms, tts={tts_duration_ms}ms): "
                               f"'{seg.translated_text[:30]}' ({seg.voice_name})")

                except Exception as e:
                    logger.warning(f"Failed to mix segment at {seg.start:.1f}s: {e}")
                    continue

            # Export the mixed audio
            output_path = os.path.join(
                tempfile.gettempdir(), "cinesync_media", "dubbed_track.wav"
            )
            original.export(output_path, format="wav")
            logger.info(f"Dubbed track exported: {output_path} ({len(original)}ms)")

            # Cleanup original audio file
            try:
                os.remove(orig_audio_path)
            except:
                pass

            return output_path

        except Exception as e:
            logger.error(f"Audio mixing error: {e}", exc_info=True)
            return None

    async def _process_chunk(self, start: float, end: float):
        """Process a chunk: STT → per-segment gender detect → emotion → translate → TTS."""
        file_path = self._current_file
        if not file_path:
            return

        # Step 1: Extract audio chunk
        audio_path = await self.media_processor.extract_audio_chunk(
            file_path, start=start, duration=end - start
        )
        if not audio_path:
            return

        # Step 2: STT
        segments = await self.stt.transcribe_chunk(audio_path, chunk_offset=start)
        if not segments:
            return

        # Step 3: Process each segment
        for seg in segments:
            # Emotion classification
            emotion_label, emotion_conf = self.emotion_classifier.classify(seg.text)
            seg_emotion = emotion_label or "neutral"

            # Boost emotion if punctuation suggests it
            if "!" in seg.text and seg_emotion == "neutral":
                seg_emotion = "excitement"
            elif "?" in seg.text and seg_emotion == "neutral":
                seg_emotion = "surprise"

            # ── Speaker identification ──
            # Detect gender from THIS segment's isolated audio
            seg_gender = await self._detect_segment_gender(
                audio_path, seg.start - start, seg.end - start
            )

            # Find or assign a stable speaker ID
            char_id = self._get_stable_speaker(seg.start, seg.end, seg_gender)

            # Translate
            source_lang = seg.language or "en"
            translated = await self.translator.translate(
                seg.text, self._target_lang, source_lang
            )

            # TTS — voice is gender-aware and permanently locked
            voice = self.tts.get_voice_for_character(char_id, self._target_lang)
            tts_result = await self.tts.synthesize(
                translated, voice, seg_emotion, char_id
            )

            if tts_result:
                dubbed = DubbedSegment(
                    start=seg.start,
                    end=seg.end,
                    original_text=seg.text,
                    translated_text=translated,
                    audio_path=tts_result.audio_path,
                    character_id=char_id,
                    emotion=seg_emotion,
                    voice_name=tts_result.voice_name,
                    duration=tts_result.duration,
                )
                self._dubbed_segments.append(dubbed)
                self._total_segments += 1

                # Send live transcript
                await self._send("live_transcript", {
                    "start": round(seg.start, 3),
                    "end": round(seg.end, 3),
                    "originalText": seg.text,
                    "translatedText": translated,
                    "characterId": char_id,
                    "emotion": seg_emotion,
                    "language": self._target_lang,
                })

    def _get_stable_speaker(self, start: float, end: float,
                            gender: Optional[str]) -> str:
        """Get a stable speaker ID using diarization data + gender.
        
        Uses the pipeline's diarization segments to match the current
        speech segment to a known speaker, falling back to gender-based
        identification if diarization is unavailable.
        """
        # ── Try diarization-based speaker matching ──
        diar_segments = []
        if hasattr(self, '_diarizer') and self._diarizer and self._diarizer._segments:
            diar_segments = [s.to_dict() for s in self._diarizer._segments]
        
        if diar_segments:
            # Find the diarization segment that overlaps most with this speech
            best_match = None
            best_overlap = 0.0
            for dseg in diar_segments:
                d_start = dseg.get('start', 0)
                d_end = dseg.get('end', 0)
                overlap = max(0, min(end, d_end) - max(start, d_start))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_match = dseg
            
            if best_match and best_overlap > 0.1:
                # Use the diarization speaker label
                diar_speaker = best_match.get('speaker_id', 'SPEAKER_00')
                char_id = f"speaker_{diar_speaker}"
                
                # Set gender for this diarization speaker ONCE
                if char_id not in self._speaker_genders and gender:
                    self._speaker_genders[char_id] = gender
                    self.tts.set_gender(char_id, gender)
                    logger.info(f"{char_id} → {gender} voice (diarization+pitch)")
                
                self._last_seg_end = end
                return char_id

        # ── Fallback: gap-based + gender identification ──
        gap = start - self._last_seg_end

        # Use gender changes as a stronger speaker-change signal
        current_char_id = f"speaker_{self._current_speaker_idx}"
        current_gender = self._speaker_genders.get(current_char_id)
        
        if gender and current_gender and gender != current_gender and gap > 0.3:
            # Gender changed with a short pause → definitely different speaker
            self._current_speaker_idx = (self._current_speaker_idx + 1) % 6
        elif gap > self._speaker_gap_threshold and self._last_seg_end > 0:
            # Large silence gap → likely a different speaker
            self._current_speaker_idx = (self._current_speaker_idx + 1) % 6

        self._last_seg_end = end
        char_id = f"speaker_{self._current_speaker_idx}"

        # Set gender for this speaker ONCE (first detection wins, locked forever)
        if char_id not in self._speaker_genders and gender:
            self._speaker_genders[char_id] = gender
            self.tts.set_gender(char_id, gender)
            logger.info(f"{char_id} → {gender} voice (pitch-detected)")

        return char_id

    async def _detect_segment_gender(self, chunk_audio_path: str,
                                      local_start: float,
                                      local_end: float) -> Optional[str]:
        """Detect gender by analyzing pitch of JUST this speech segment.
        
        Unlike full-chunk analysis, this isolates the speaker's voice
        from background music/effects using exact STT timestamps.
        """
        try:
            return await asyncio.to_thread(
                self._pitch_from_segment, chunk_audio_path,
                max(0, local_start), local_end
            )
        except Exception as e:
            logger.debug(f"Segment gender detection failed: {e}")
            return None

    def _pitch_from_segment(self, audio_path: str,
                            start_sec: float, end_sec: float) -> Optional[str]:
        """Analyze fundamental frequency on an isolated speech segment."""
        try:
            import numpy as np
            from pydub import AudioSegment

            # Load the chunk audio
            audio = AudioSegment.from_file(audio_path)
            
            # Slice to JUST the speech segment (milliseconds)
            start_ms = int(start_sec * 1000)
            end_ms = int(end_sec * 1000)
            
            if end_ms <= start_ms or end_ms > len(audio):
                return None
                
            speech_slice = audio[start_ms:end_ms]
            
            # Must be at least 200ms of speech
            if len(speech_slice) < 200:
                return None

            # Convert to mono 16kHz
            speech_slice = speech_slice.set_channels(1).set_frame_rate(16000)
            samples = np.array(speech_slice.get_array_of_samples(), dtype=np.float32)

            if len(samples) < 1600:
                return None

            # Normalize
            max_val = np.max(np.abs(samples))
            if max_val < 100:  # near silence
                return None
            samples = samples / max_val

            # Autocorrelation pitch detection on 30ms windows
            min_lag = int(16000 / 300)  # 300 Hz upper bound
            max_lag = int(16000 / 70)   # 70 Hz lower bound
            window_size = int(16000 * 0.03)  # 30ms
            hop_size = int(16000 * 0.01)     # 10ms

            pitches = []
            for i in range(0, len(samples) - window_size, hop_size):
                window = samples[i:i + window_size]

                # Skip quiet frames
                rms = np.sqrt(np.mean(window ** 2))
                if rms < 0.03:
                    continue

                # Autocorrelation
                corr = np.correlate(window, window, mode='full')
                corr = corr[len(corr) // 2:]

                if max_lag >= len(corr):
                    continue

                search = corr[min_lag:max_lag]
                if len(search) == 0:
                    continue

                peak_idx = np.argmax(search) + min_lag

                # Only accept strong pitch peaks
                if corr[peak_idx] > 0.35 * corr[0]:
                    f0 = 16000.0 / peak_idx
                    if 80 < f0 < 280:
                        pitches.append(f0)

            if len(pitches) < 3:
                return None

            median_f0 = float(np.median(pitches))
            gender = "female" if median_f0 > 165 else "male"
            logger.info(f"Pitch: {median_f0:.0f} Hz → {gender} "
                       f"({len(pitches)} frames)")
            return gender

        except ImportError:
            return None
        except Exception as e:
            logger.debug(f"Pitch error: {e}")
            return None

    def update_playback_time(self, time: float):
        self._playback_time = time

    def get_status(self) -> dict:
        return {
            "active": self._active,
            "language": self._target_lang,
            "processedTo": round(self._processed_up_to, 1),
            "bufferedSegments": len(self._dubbed_segments),
            "totalSegments": self._total_segments,
            "outputPath": self._output_path,
            "voiceAssignments": self.tts.get_all_assignments(),
        }
