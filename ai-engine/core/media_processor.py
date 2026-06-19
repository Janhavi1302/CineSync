"""
Media Processor — FFmpeg-based audio/video extraction.
Extracts audio tracks and video frames for AI pipeline processing.
"""

import asyncio
import logging
import subprocess
import json
import os
import tempfile
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger("cinesync.media")


class MediaProcessor:
    """Extracts audio and video data from media files using FFmpeg."""

    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        # Auto-detect FFmpeg from imageio-ffmpeg if system one isn't available
        self.ffmpeg = self._resolve_ffmpeg(ffmpeg_path)
        self.ffprobe = self._resolve_ffprobe(ffprobe_path)
        self._temp_dir = os.path.join(tempfile.gettempdir(), "cinesync_media")
        os.makedirs(self._temp_dir, exist_ok=True)

    @staticmethod
    def _resolve_ffmpeg(default: str) -> str:
        """Find FFmpeg binary: system PATH → imageio-ffmpeg bundled."""
        import shutil
        if shutil.which(default):
            return default
        try:
            import imageio_ffmpeg
            path = imageio_ffmpeg.get_ffmpeg_exe()
            logger.info(f"Using imageio-ffmpeg: {path}")
            return path
        except (ImportError, Exception):
            return default

    @staticmethod
    def _resolve_ffprobe(default: str) -> str:
        """Find FFprobe binary: system PATH → derive from imageio-ffmpeg."""
        import shutil
        if shutil.which(default):
            return default
        try:
            import imageio_ffmpeg
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            # ffprobe is typically alongside ffmpeg
            probe_path = ffmpeg_path.replace("ffmpeg", "ffprobe")
            if os.path.exists(probe_path):
                return probe_path
        except (ImportError, Exception):
            pass
        return default

    async def get_media_info(self, file_path: str) -> Dict:
        """Get media file metadata using FFprobe, with ffmpeg -i fallback."""
        # Try FFprobe first
        info = await self._get_info_ffprobe(file_path)
        if info:
            return info

        # Fallback: use ffmpeg -i (always available via imageio-ffmpeg)
        info = await self._get_info_ffmpeg(file_path)
        if info:
            return info

        logger.warning("Could not extract media info (no ffprobe or ffmpeg)")
        return {}

    async def _get_info_ffprobe(self, file_path: str) -> Dict:
        """Try FFprobe for full metadata."""
        cmd = [
            self.ffprobe, "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            file_path
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                info = json.loads(stdout.decode())
                return self._parse_media_info(info)
            else:
                logger.debug(f"FFprobe error: {stderr.decode()[:200]}")
                return {}
        except FileNotFoundError:
            logger.debug("FFprobe not found, will use ffmpeg fallback")
            return {}
        except Exception as e:
            logger.debug(f"FFprobe failed: {e}")
            return {}

    async def _get_info_ffmpeg(self, file_path: str) -> Dict:
        """Fallback: extract duration/codec info from ffmpeg -i stderr output."""
        return await asyncio.to_thread(self._get_info_ffmpeg_sync, file_path)

    def _get_info_ffmpeg_sync(self, file_path: str) -> Dict:
        """Synchronous ffmpeg -i probe (runs in thread)."""
        import re
        cmd = [self.ffmpeg, "-i", file_path]
        try:
            # ffmpeg -i always returns exit code 1 (no output specified), that's fine
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=15, errors="replace"
            )
            output = result.stderr or ""

            if not output:
                logger.warning("FFmpeg returned no output")
                return {}

            # Parse duration from "Duration: HH:MM:SS.ms"
            duration = 0.0
            dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", output)
            if dur_match:
                h, m, s, ms = dur_match.groups()
                duration = int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 100

            # Parse video stream info
            video_streams = []
            vid_match = re.search(r"Video:\s*(\w+).*?(\d{2,5})x(\d{2,5})", output)
            if vid_match:
                video_streams.append({
                    "codec": vid_match.group(1),
                    "width": int(vid_match.group(2)),
                    "height": int(vid_match.group(3)),
                    "fps": 24.0,
                    "index": 0
                })

            # Parse audio stream info
            audio_streams = []
            aud_match = re.search(r"Audio:\s*(\w+).*?(\d+)\s*Hz", output)
            if aud_match:
                audio_streams.append({
                    "codec": aud_match.group(1),
                    "channels": 2,
                    "sample_rate": int(aud_match.group(2)),
                    "language": "und",
                    "index": 1
                })

            if duration > 0:
                logger.info(f"Media info (ffmpeg fallback): {duration:.1f}s, "
                           f"video: {len(video_streams)}, audio: {len(audio_streams)}")
                return {
                    "filename": file_path,
                    "duration": duration,
                    "size": 0,
                    "bitrate": 0,
                    "video": video_streams,
                    "audio": audio_streams,
                    "subtitles": []
                }

            logger.warning(f"Could not parse duration from ffmpeg output")
            return {}
        except Exception as e:
            logger.warning(f"FFmpeg fallback failed: {e}")
            return {}

    def _parse_media_info(self, raw: Dict) -> Dict:
        """Parse FFprobe JSON output into structured info."""
        fmt = raw.get("format", {})
        streams = raw.get("streams", [])

        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]

        result = {
            "filename": fmt.get("filename", ""),
            "duration": float(fmt.get("duration", 0)),
            "size": int(fmt.get("size", 0)),
            "bitrate": int(fmt.get("bit_rate", 0)),
            "video": [],
            "audio": [],
            "subtitles": []
        }

        for vs in video_streams:
            result["video"].append({
                "codec": vs.get("codec_name", ""),
                "width": vs.get("width", 0),
                "height": vs.get("height", 0),
                "fps": self._parse_fps(vs.get("r_frame_rate", "0/1")),
                "index": vs.get("index", 0)
            })

        for aus in audio_streams:
            result["audio"].append({
                "codec": aus.get("codec_name", ""),
                "channels": aus.get("channels", 0),
                "sample_rate": int(aus.get("sample_rate", 0)),
                "language": aus.get("tags", {}).get("language", "und"),
                "index": aus.get("index", 0)
            })

        for ss in subtitle_streams:
            result["subtitles"].append({
                "codec": ss.get("codec_name", ""),
                "language": ss.get("tags", {}).get("language", "und"),
                "index": ss.get("index", 0)
            })

        return result

    def _parse_fps(self, rate_str: str) -> float:
        """Parse fractional FPS string like '24000/1001'."""
        try:
            num, den = rate_str.split("/")
            return round(int(num) / int(den), 2)
        except (ValueError, ZeroDivisionError):
            return 0.0

    async def extract_audio_chunk(
        self, file_path: str, start: float, duration: float,
        sample_rate: int = 16000, mono: bool = True
    ) -> Optional[str]:
        """
        Extract an audio chunk as WAV for speech recognition.
        Returns path to temporary WAV file.
        """
        output_path = os.path.join(
            self._temp_dir, f"audio_{start:.1f}_{duration:.1f}.wav"
        )

        channels = "1" if mono else "2"
        cmd = [
            self.ffmpeg, "-y",
            "-ss", str(start),
            "-t", str(duration),
            "-i", file_path,
            "-vn",  # no video
            "-acodec", "pcm_s16le",
            "-ar", str(sample_rate),
            "-ac", channels,
            output_path
        ]

        try:
            result = await asyncio.to_thread(
                subprocess.run, cmd,
                capture_output=True, timeout=30
            )
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
            logger.warning(f"Audio extraction failed (rc={result.returncode})")
            return None
        except Exception as e:
            logger.error(f"Audio extraction error: {e}")
            return None

    async def extract_frame(
        self, file_path: str, timestamp: float, width: int = 640
    ) -> Optional[bytes]:
        """Extract a single video frame as JPEG bytes."""
        cmd = [
            self.ffmpeg, "-y",
            "-ss", str(timestamp),
            "-i", file_path,
            "-vframes", "1",
            "-vf", f"scale={width}:-1",
            "-f", "image2pipe",
            "-vcodec", "mjpeg",
            "pipe:1"
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0 and stdout:
                return stdout
            return None
        except Exception as e:
            logger.error(f"Frame extraction error: {e}")
            return None

    async def extract_frames_batch(
        self, file_path: str, start: float, duration: float,
        fps: float = 2.0, width: int = 640
    ) -> List[Tuple[float, str]]:
        """
        Extract multiple frames at a given FPS rate.
        Returns list of (timestamp, frame_path) tuples.
        """
        frames = []
        output_pattern = os.path.join(self._temp_dir, f"frame_{start:.1f}_%04d.jpg")

        cmd = [
            self.ffmpeg, "-y",
            "-ss", str(start),
            "-t", str(duration),
            "-i", file_path,
            "-vf", f"fps={fps},scale={width}:-1",
            "-q:v", "2",
            output_pattern
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()

            if proc.returncode == 0:
                frame_idx = 1
                while True:
                    fpath = output_pattern.replace("%04d", f"{frame_idx:04d}")
                    if os.path.exists(fpath):
                        timestamp = start + (frame_idx - 1) / fps
                        frames.append((timestamp, fpath))
                        frame_idx += 1
                    else:
                        break
        except Exception as e:
            logger.error(f"Batch frame extraction error: {e}")

        return frames

    def cleanup(self):
        """Remove temporary files."""
        import shutil
        if os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            os.makedirs(self._temp_dir, exist_ok=True)
        logger.info("Temporary media files cleaned up")
