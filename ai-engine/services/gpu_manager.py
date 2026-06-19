"""
GPU Manager — Manages GPU resources for CineSync AI.
Supports both local VRAM management and Modal cloud GPU mode.
"""

import gc
import logging
from typing import Optional, Any

logger = logging.getLogger("cinesync.gpu")


class GPUManager:
    """
    Manages GPU memory by loading/unloading models sequentially.
    
    In Modal mode: operates as a no-op pass-through since
    GPU lifecycle is managed by Modal's container system.
    
    In Local mode: original VRAM budget management for GTX 1650.
    """

    def __init__(self, max_vram_gb: float = 3.5, modal_mode: bool = False):
        self.max_vram = max_vram_gb
        self._modal_mode = modal_mode
        self._loaded_model: Optional[str] = None
        self._model_instance: Optional[Any] = None
        self._vram_used: float = 0.0

        if modal_mode:
            logger.info("GPU Manager: Modal cloud mode (no local VRAM management)")

    @property
    def current_model(self) -> Optional[str]:
        return self._loaded_model

    @property
    def vram_used(self) -> float:
        return self._vram_used

    @property
    def vram_available(self) -> float:
        return self.max_vram - self._vram_used

    def unload_current(self):
        """Unload the current GPU model and free VRAM."""
        if self._modal_mode:
            logger.debug("Modal mode: unload is a no-op")
            return

        if self._loaded_model:
            logger.info(f"Unloading model: {self._loaded_model} (freeing ~{self._vram_used:.1f}GB)")
            del self._model_instance
            self._model_instance = None
            self._loaded_model = None
            self._vram_used = 0.0

            # Force garbage collection and CUDA cache clear
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
            except ImportError:
                pass

            logger.info("VRAM freed successfully")

    def load_model(self, name: str, model_instance: Any, vram_estimate: float):
        """
        Load a model onto GPU, unloading any existing model first.
        
        Args:
            name: Human-readable model identifier
            model_instance: The loaded model object
            vram_estimate: Estimated VRAM usage in GB
        """
        if self._modal_mode:
            logger.debug(f"Modal mode: model '{name}' managed by Modal cloud")
            self._loaded_model = name
            return

        if vram_estimate > self.max_vram:
            raise MemoryError(
                f"Model {name} requires ~{vram_estimate:.1f}GB VRAM, "
                f"but max budget is {self.max_vram:.1f}GB"
            )

        # Unload existing model if different
        if self._loaded_model and self._loaded_model != name:
            self.unload_current()

        self._loaded_model = name
        self._model_instance = model_instance
        self._vram_used = vram_estimate
        logger.info(f"Loaded model: {name} (~{vram_estimate:.1f}GB VRAM, {self.vram_available:.1f}GB remaining)")

    def get_model(self) -> Optional[Any]:
        """Get the currently loaded model instance."""
        return self._model_instance

    def get_status(self) -> dict:
        """Get current GPU status."""
        if self._modal_mode:
            return {
                "mode": "modal",
                "gpu": "Modal Cloud T4",
                "loaded_model": self._loaded_model,
                "vram_used_gb": 0,
                "vram_available_gb": 16.0,  # T4 has 16GB
                "max_vram_gb": 16.0,
            }

        return {
            "mode": "local",
            "loaded_model": self._loaded_model,
            "vram_used_gb": round(self._vram_used, 2),
            "vram_available_gb": round(self.vram_available, 2),
            "max_vram_gb": self.max_vram
        }
