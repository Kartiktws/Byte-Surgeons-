"""
Predictor Engine - JPEG-LS style median predictor for lossless pixel compression.
Residuals are small and highly compressible (80-90% on typical medical images).
"""

import numpy as np
from typing import Tuple, Dict, Any


def median3(a: int, b: int, c: int) -> int:
    """Median of three integers (no float)."""
    if a <= b:
        if b <= c:
            return b
        return c if a <= c else a
    if a <= c:
        return a
    return b if b <= c else c


def residual_to_symbol(r: int) -> int:
    """Map signed residual to non-negative symbol for Huffman. 0->0, -1->1, 1->2, -2->3, 2->4..."""
    if r >= 0:
        return 2 * r
    return -2 * r - 1


def symbol_to_residual(s: int) -> int:
    """Inverse of residual_to_symbol."""
    if s % 2 == 0:
        return s // 2
    return -(s // 2 + 1)


def predict_frame_2d(img: np.ndarray, maxval: int) -> np.ndarray:
    """
    One 2D frame: for each pixel (r,c), predict = median(left, top, left+top-topleft).
    Return 1D array of residual symbols (non-negative) in raster order.
    """
    img = np.asarray(img, dtype=np.int64)
    R, C = img.shape
    out = np.empty((R, C), dtype=np.int64)
    for r in range(R):
        for c in range(C):
            left = img[r, c - 1] if c > 0 else 0
            top = img[r - 1, c] if r > 0 else 0
            topleft = img[r - 1, c - 1] if (r > 0 and c > 0) else 0
            pred = median3(left, top, left + top - topleft)
            pred = max(0, min(maxval, pred))
            residual = int(img[r, c] - pred)
            out[r, c] = residual_to_symbol(residual)
    return out.ravel()


def rle_zero_runs(symbols_flat: np.ndarray, max_residual_symbol: int) -> np.ndarray:
    """
    Replace runs of 2+ zeros with single tokens (max_residual_symbol + run_length).
    Greatly improves compression on smooth/medical images.
    """
    out = []
    i = 0
    n = len(symbols_flat)
    while i < n:
        if symbols_flat[i] != 0:
            out.append(int(symbols_flat[i]))
            i += 1
            continue
        run = 0
        while i < n and symbols_flat[i] == 0 and run < 65535:
            run += 1
            i += 1
        if run == 1:
            out.append(0)
        else:
            out.append(max_residual_symbol + run)
    return np.array(out, dtype=np.int64)


def rle_zero_runs_inverse(tokens: np.ndarray, max_residual_symbol: int) -> np.ndarray:
    """Expand RLE zero runs back to full symbol stream."""
    out = []
    for s in tokens:
        if s <= max_residual_symbol:
            out.append(s)
        else:
            run = s - max_residual_symbol
            out.extend([0] * run)
    return np.array(out, dtype=np.int64)


def inverse_predict_frame_2d(symbols_flat: np.ndarray, shape: tuple, maxval: int) -> np.ndarray:
    """Reconstruct one 2D frame from residual symbols (raster order)."""
    R, C = shape
    symbols = symbols_flat.reshape(R, C)
    out = np.empty((R, C), dtype=np.int64)
    for r in range(R):
        for c in range(C):
            left = out[r, c - 1] if c > 0 else 0
            top = out[r - 1, c] if r > 0 else 0
            topleft = out[r - 1, c - 1] if (r > 0 and c > 0) else 0
            pred = median3(left, top, left + top - topleft)
            pred = max(0, min(maxval, pred))
            residual = symbol_to_residual(int(symbols[r, c]))
            pixel = pred + residual
            # Wrap/clamp to [0, maxval] for lossless
            if pixel < 0:
                pixel += (maxval + 1)
            elif pixel > maxval:
                pixel -= (maxval + 1)
            out[r, c] = pixel
    return out


# For 16-bit, max residual symbol = 2*65535 = 131070. RLE uses 131071+ for run lengths.
def max_residual_symbol(bits: int) -> int:
    maxval = (1 << bits) - 1
    return 2 * maxval


class PredictorEngine:
    """JPEG-LS style median predictor for 2D/3D (multi-frame) images. Lossless. Uses RLE for zero runs."""

    def __init__(self, use_rle_zeros: bool = True):
        self.use_rle_zeros = use_rle_zeros

    def encode(self, pixel_array: np.ndarray, bits: int = 16) -> Tuple[np.ndarray, dict]:
        """
        Encode pixel array to residual symbols (one int per pixel, or RLE for zero runs).
        pixel_array: 2D (rows, cols) or 3D (num_frames, rows, cols), uint8 or uint16.
        Returns (residual_symbols_flat, metadata_dict).
        """
        maxval = (1 << bits) - 1
        if pixel_array.ndim == 2:
            pixel_array = pixel_array[np.newaxis, ...]
        num_frames, R, C = pixel_array.shape
        frames_flat = []
        for i in range(num_frames):
            flat = predict_frame_2d(pixel_array[i], maxval)
            frames_flat.append(flat)
        residuals = np.concatenate(frames_flat)
        max_sym = max_residual_symbol(bits)
        if self.use_rle_zeros:
            residuals = rle_zero_runs(residuals, max_sym)
        metadata = {
            "num_frames": num_frames,
            "rows": R,
            "cols": C,
            "bits": bits,
            "original_dtype": str(pixel_array.dtype),
            "predictor": True,
            "rle_zeros": self.use_rle_zeros,
        }
        return residuals, metadata

    def decode(self, residual_symbols: np.ndarray, metadata: dict) -> np.ndarray:
        """Decode residual symbols back to pixel array (3D: num_frames, rows, cols)."""
        if metadata.get("rle_zeros", False):
            max_sym = max_residual_symbol(metadata["bits"])
            residual_symbols = rle_zero_runs_inverse(residual_symbols, max_sym)
        num_frames = metadata["num_frames"]
        R = metadata["rows"]
        C = metadata["cols"]
        bits = metadata["bits"]
        maxval = (1 << bits) - 1
        n_per_frame = R * C
        frames = []
        for i in range(num_frames):
            start = i * n_per_frame
            end = start + n_per_frame
            frame_flat = residual_symbols[start:end]
            frame_2d = inverse_predict_frame_2d(frame_flat, (R, C), maxval)
            frames.append(frame_2d)
        out = np.stack(frames, axis=0)
        dtype = np.dtype(metadata["original_dtype"])
        out = np.clip(out, 0, maxval).astype(dtype)
        if num_frames == 1:
            out = out[0]
        return out
