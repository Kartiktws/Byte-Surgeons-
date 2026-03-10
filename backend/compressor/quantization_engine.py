"""
Quantization Engine - Uniform scalar quantization for lossy compression.
Q parameter controls step size; modality-aware defaults (CT→4, MRI→6, XR→8).
"""

import numpy as np
from typing import Tuple

# Modality defaults for Q (quantization step)
DEFAULT_Q_CT = 4
DEFAULT_Q_MRI = 6
DEFAULT_Q_XR = 8
DEFAULT_Q_OTHER = 4


def default_q_for_modality(modality: str) -> int:
    """Return default Q for modality: CT→4, MRI→6, XR→8, else 4."""
    m = (modality or "").upper()
    if m == "CT":
        return DEFAULT_Q_CT
    if m == "MR":
        return DEFAULT_Q_MRI
    if m in ("DX", "CR", "XR"):
        return DEFAULT_Q_XR
    return DEFAULT_Q_OTHER


class QuantizationEngine:
    """
    Uniform scalar quantization: pixel_q = pixel // Q.
    Store Q in header for exact dequantization (pixel_approx = pixel_q * Q + Q//2).
    """

    def quantize_frame(self, pixel_2d: np.ndarray, Q: int) -> np.ndarray:
        """
        Quantize a single 2D frame (uint8 or int) by integer division with Q.
        Returns 2D int64 for that frame only. Use this to avoid full-volume int64 allocation.
        """
        if Q < 1:
            Q = 1
        return np.asarray(pixel_2d, dtype=np.int64) // Q

    def quantize(
        self,
        pixel_array: np.ndarray,
        Q: int,
        modality: str = "OT",
    ) -> Tuple[np.ndarray, dict]:
        """
        Quantize pixel array (uint8 or int) by integer division with Q.
        Returns (quantized array as int64, metadata dict with Q and original_dtype).
        For large volumes prefer building frame-by-frame via quantize_frame() to avoid OOM.
        """
        if Q < 1:
            Q = 1
        arr = np.asarray(pixel_array, dtype=np.int64)
        quantized = arr // Q
        metadata = {
            "Q": Q,
            "modality": (modality or "OT").upper(),
            "original_dtype": str(pixel_array.dtype),
        }
        return quantized, metadata

    def dequantize(self, quantized: np.ndarray, Q: int) -> np.ndarray:
        """
        Dequantize: approximate value = quantized * Q + Q//2 (midpoint).
        Clip to [0, 255] for uint8 output.
        """
        if Q < 1:
            Q = 1
        out = quantized.astype(np.int64) * Q + (Q // 2)
        return np.clip(out, 0, 255).astype(np.uint8)
