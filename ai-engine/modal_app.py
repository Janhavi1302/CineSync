"""
CineSync AI — Modal Cloud GPU App
Runs Whisper STT (medium) + YOLOv8 face detection on Modal T4 GPUs.
Deploy: modal deploy ai-engine/modal_app.py
"""

import io
import os
import tempfile
import time
from typing import List, Dict, Optional

import modal

# ── Modal App & Image ────────────────────────────────────────────
app = modal.App("cinesync-ai")

gpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "libsndfile1")
    .pip_install(
        # PyTorch (CUDA 12.x) — install first to get CUDA libs
        "torch>=2.1.0",
        "torchvision>=0.16.0",
        "torchaudio>=2.1.0",
        # NVIDIA CUDA libs explicitly (for ctranslate2)
        "nvidia-cublas-cu12",
        "nvidia-cudnn-cu12",
    )
    .pip_install(
        # Whisper STT (needs cuBLAS from torch)
        "faster-whisper>=1.0.0",
        "ctranslate2>=4.0.0",
        # Face Detection
        "ultralytics>=8.0",
        # Audio/Image processing
        "numpy>=1.24.0",
        "Pillow>=10.0.0",
    )
    .run_commands(
        # Find all CUDA .so files and copy to a single directory
        "python3 -c \""
        "import glob, shutil, os; "
        "os.makedirs('/usr/local/cuda-libs', exist_ok=True); "
        "patterns = ['/usr/local/lib/python3.11/site-packages/nvidia/*/lib/*.so*', "
        "'/usr/local/lib/python3.11/site-packages/torch/lib/*.so*']; "
        "files = [f for p in patterns for f in glob.glob(p)]; "
        "[shutil.copy2(f, '/usr/local/cuda-libs/') for f in files "
        "if not os.path.exists('/usr/local/cuda-libs/' + os.path.basename(f))]; "
        "print('Copied', len(files), 'CUDA libs'); "
        "cublas = glob.glob('/usr/local/cuda-libs/libcublas*'); "
        "print('cublas files:', cublas)"
        "\"",
    )
    .env({"LD_LIBRARY_PATH": "/usr/local/cuda-libs:/usr/local/lib/python3.11/site-packages/torch/lib"})
)

# ── Volumes for model caching ────────────────────────────────────
model_cache = modal.Volume.from_name("cinesync-model-cache", create_if_missing=True)


@app.cls(
    gpu="T4",
    image=gpu_image,
    scaledown_window=300,        # 5 min idle before shutdown
    timeout=600,                 # 10 min max per request
    volumes={"/cache": model_cache},
)
class CineSyncGPU:
    """
    GPU-accelerated inference for CineSync AI.
    Models are loaded once when the container starts and reused across requests.
    """

    @modal.enter()
    def load_models(self):
        """Load all models on container startup (runs once)."""
        import torch

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
        print(f"🎬 CineSync GPU Worker starting on {gpu_name}")
        print(f"   CUDA: {torch.cuda.is_available()}, Device: {self._device}")

        # ── Load Whisper STT ──
        self._load_whisper()

        # ── Load YOLOv8 Face Detection ──
        self._load_yolo()

        print("✅ All models loaded successfully")

    def _load_whisper(self):
        """Load faster-whisper medium model with float16."""
        from faster_whisper import WhisperModel

        cache_dir = "/cache/whisper"
        os.makedirs(cache_dir, exist_ok=True)

        print("Loading Whisper 'medium' model (float16)...")
        t0 = time.time()
        self._whisper = WhisperModel(
            "medium",
            device=self._device,
            compute_type="float16",
            download_root=cache_dir,
        )
        elapsed = time.time() - t0
        print(f"   Whisper loaded in {elapsed:.1f}s")

    def _load_yolo(self):
        """Load YOLOv8-nano face detection model."""
        try:
            from ultralytics import YOLO

            cache_dir = "/cache/yolo"
            os.makedirs(cache_dir, exist_ok=True)

            print("Loading YOLOv8-nano face model...")
            t0 = time.time()
            # Use standard YOLOv8n (will auto-download)
            model_path = os.path.join(cache_dir, "yolov8n.pt")
            self._yolo = YOLO("yolov8n.pt")
            # Warm up with a dummy inference
            import numpy as np
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            self._yolo(dummy, verbose=False)
            elapsed = time.time() - t0
            print(f"   YOLOv8 loaded in {elapsed:.1f}s")
            self._yolo_loaded = True
        except Exception as e:
            print(f"   ⚠️ YOLOv8 failed to load: {e}")
            self._yolo = None
            self._yolo_loaded = False

    @modal.method()
    def transcribe(
        self,
        audio_bytes: bytes,
        chunk_offset: float = 0.0,
        beam_size: int = 5,
    ) -> Dict:
        """
        Transcribe audio bytes using Whisper medium (GPU).

        Args:
            audio_bytes: Raw WAV file bytes
            chunk_offset: Time offset to add to all timestamps
            beam_size: Beam size for decoding

        Returns:
            Dict with 'segments' list and 'language' info
        """
        t0 = time.time()

        # Write bytes to temp file (faster-whisper needs a file path)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            segments_iter, info = self._whisper.transcribe(
                temp_path,
                beam_size=beam_size,
                word_timestamps=True,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=300,
                    speech_pad_ms=200,
                ),
            )

            detected_lang = info.language
            lang_prob = info.language_probability

            results = []
            for seg in segments_iter:
                words = []
                if seg.words:
                    for w in seg.words:
                        words.append({
                            "word": w.word.strip(),
                            "start": round(w.start + chunk_offset, 3),
                            "end": round(w.end + chunk_offset, 3),
                            "probability": round(w.probability, 2),
                        })

                confidence = 0.0
                if seg.words:
                    confidence = round(
                        sum(w.probability for w in seg.words) / max(len(seg.words), 1), 2
                    )

                results.append({
                    "text": seg.text.strip(),
                    "start": round(seg.start + chunk_offset, 3),
                    "end": round(seg.end + chunk_offset, 3),
                    "duration": round(seg.end - seg.start, 3),
                    "language": detected_lang,
                    "confidence": confidence,
                    "words": words,
                })

            elapsed = time.time() - t0
            print(f"STT: {len(results)} segments in {elapsed:.2f}s "
                  f"(lang={detected_lang}, prob={lang_prob:.0%})")

            return {
                "segments": results,
                "language": detected_lang,
                "language_probability": round(lang_prob, 2),
                "processing_time": round(elapsed, 3),
            }

        finally:
            os.unlink(temp_path)

    @modal.method()
    def detect_faces(
        self,
        frame_bytes: bytes,
        timestamp: float = 0.0,
        confidence_threshold: float = 0.4,
    ) -> Dict:
        """
        Detect faces in a JPEG frame using YOLOv8.

        Args:
            frame_bytes: Raw JPEG image bytes
            timestamp: Frame timestamp for tracking
            confidence_threshold: Minimum detection confidence

        Returns:
            Dict with 'detections' list
        """
        if not self._yolo_loaded:
            return {"detections": [], "error": "YOLOv8 not loaded"}

        t0 = time.time()

        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(frame_bytes)
            temp_path = f.name

        try:
            results = self._yolo(temp_path, verbose=False, conf=confidence_threshold)
            detections = []

            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue

                img_h, img_w = result.orig_shape
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    cls = int(box.cls[0]) if box.cls is not None else 0

                    # Only keep person class (class 0) as proxy for faces
                    detections.append({
                        "bbox": [
                            round(x1 / img_w, 4),
                            round(y1 / img_h, 4),
                            round(x2 / img_w, 4),
                            round(y2 / img_h, 4),
                        ],
                        "confidence": round(conf, 3),
                        "class": cls,
                        "timestamp": timestamp,
                    })

            elapsed = time.time() - t0
            print(f"Face: {len(detections)} detections in {elapsed:.3f}s")

            return {
                "detections": detections,
                "processing_time": round(elapsed, 3),
            }

        finally:
            os.unlink(temp_path)

    @modal.method()
    def health_check(self) -> Dict:
        """Check GPU worker health and return system info."""
        import torch

        return {
            "status": "online",
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
            "cuda_available": torch.cuda.is_available(),
            "vram_total_gb": round(
                torch.cuda.get_device_properties(0).total_memory / 1e9, 2
            ) if torch.cuda.is_available() else 0,
            "vram_used_gb": round(
                torch.cuda.memory_allocated(0) / 1e9, 2
            ) if torch.cuda.is_available() else 0,
            "whisper_model": "medium",
            "whisper_compute": "float16",
            "yolo_loaded": self._yolo_loaded,
        }


# ── Test / CLI entry points ──────────────────────────────────────

@app.function(image=gpu_image)
def test_health():
    """Quick health check: modal run modal_app.py::test_health"""
    gpu = CineSyncGPU()
    result = gpu.health_check.remote()
    print(f"Health: {result}")
    return result


@app.local_entrypoint()
def main():
    """CLI test: modal run modal_app.py"""
    print("🎬 CineSync AI — Modal GPU Test")
    print("=" * 50)

    gpu = CineSyncGPU()

    # Health check
    health = gpu.health_check.remote()
    print(f"\n✅ GPU Worker Online:")
    for k, v in health.items():
        print(f"   {k}: {v}")

    print("\n🎉 Modal GPU backend is ready!")
    print("   Deploy with: modal deploy modal_app.py")
