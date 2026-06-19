"""
CineSync AI — Configuration
Supports both local GPU and Modal cloud GPU modes.
"""

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    """Application configuration."""

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8765
    DEBUG: bool = True

    # ── GPU Mode ──
    # Set to True to use Modal cloud GPUs instead of local GPU
    USE_MODAL: bool = True
    MODAL_GPU: str = "T4"  # T4, A10G, or A100

    # Local GPU Configuration (only used when USE_MODAL=False)
    GPU_NAME: str = "GTX 1650"
    GPU_VRAM: int = 4  # GB
    DEVICE: str = "cuda"  # cuda or cpu
    MAX_VRAM_USAGE: float = 3.5  # GB — leave 0.5GB headroom

    # Model paths
    MODELS_DIR: str = os.path.join(os.path.dirname(__file__), "models")

    # Speech Recognition (faster-whisper)
    # When USE_MODAL=True: uses "medium" with float16 on cloud GPU
    # When USE_MODAL=False: uses local settings below
    WHISPER_MODEL: str = "medium"  # tiny, small, medium (medium for Modal)
    WHISPER_COMPUTE_TYPE: str = "float16"  # float16 for Modal, int8 for local
    WHISPER_VRAM: float = 1.5  # GB estimated for medium

    # Translation (deep-translator, CPU/network — no GPU needed)
    NLLB_MODEL: str = "facebook/nllb-200-distilled-600M"
    NLLB_COMPUTE_TYPE: str = "int8"
    NLLB_VRAM: float = 0.8  # GB estimated

    # TTS (Edge TTS, cloud service — no GPU needed)
    TTS_MODEL: str = "edge-tts"
    TTS_VRAM: float = 0.0

    # Face Detection (YOLOv8-nano)
    FACE_MODEL: str = "yolov8n"
    FACE_VRAM: float = 0.2  # GB estimated

    # Processing
    CHUNK_DURATION: float = 5.0  # seconds per processing chunk
    BUFFER_AHEAD: float = 15.0  # seconds to pre-process ahead
    MAX_CHARACTERS: int = 15

    # Supported languages
    SUPPORTED_LANGUAGES: list = field(default_factory=lambda: [
        "en", "hi", "es", "fr", "de", "ja", "ko", "zh", "ar", "pt", "ru"
    ])

    def get_gpu_display_name(self) -> str:
        """Get human-readable GPU name for display."""
        if self.USE_MODAL:
            return f"Modal Cloud {self.MODAL_GPU}"
        return self.GPU_NAME

    def get_mode_display(self) -> str:
        """Get display string for the current mode."""
        if self.USE_MODAL:
            return f"Modal Cloud GPU ({self.MODAL_GPU})"
        return f"Local GPU ({self.GPU_NAME})"
