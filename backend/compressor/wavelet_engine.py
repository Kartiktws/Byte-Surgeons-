"""
Wavelet Engine - Haar wavelet forward/inverse transform for lossless 2D/multi-frame images.
Uses PyWavelets (pywt). No thresholding or quantization; fully reversible.
"""

import numpy as np
import pywt


class WaveletEngine:
    """Haar wavelet transform (3 levels). Lossless only. Supports 2D and 3D (multi-frame)."""

    WAVELET = "haar"
    LEVELS = 3

    def forward_2d(self, pixel_2d: np.ndarray) -> dict:
        """Single 2D frame: Haar decomposition. Returns one coefficient dict."""
        arr = np.asarray(pixel_2d, dtype=np.float64)
        coeffs = pywt.wavedec2(arr, self.WAVELET, level=self.LEVELS)
        cA3 = coeffs[0]
        details = []
        for i in range(1, self.LEVELS + 1):
            cH, cV, cD = coeffs[i]
            details.append({"H": np.array(cH, copy=True), "V": np.array(cV, copy=True), "D": np.array(cD, copy=True)})
        return {
            "approximation": np.array(cA3, copy=True),
            "details": details,
            "original_shape": tuple(pixel_2d.shape),
            "original_dtype": str(pixel_2d.dtype),
        }

    def forward_transform(self, pixel_array: np.ndarray) -> dict:
        """
        Apply 3-level Haar wavelet decomposition.
        Accepts 2D (single frame) or 3D (num_frames, rows, cols).
        Returns dict with num_frames and list of per-frame coefficient dicts.
        """
        if pixel_array.ndim == 2:
            one = self.forward_2d(pixel_array)
            return {"num_frames": 1, "frames": [one]}
        # 3D: (num_frames, rows, cols)
        frames = []
        for i in range(pixel_array.shape[0]):
            frames.append(self.forward_2d(pixel_array[i]))
        return {"num_frames": pixel_array.shape[0], "frames": frames}

    def inverse_2d(self, coefficients_dict: dict) -> np.ndarray:
        """Reconstruct one 2D frame from one coefficient dict."""
        cA3 = coefficients_dict["approximation"]
        details = coefficients_dict["details"]
        coeffs_list = [cA3]
        for d in details:
            coeffs_list.append((d["H"], d["V"], d["D"]))
        reconstructed = pywt.waverec2(coeffs_list, self.WAVELET)
        original_shape = coefficients_dict["original_shape"]
        r_rows, r_cols = reconstructed.shape
        o_rows, o_cols = original_shape
        if r_rows > o_rows or r_cols > o_cols:
            reconstructed = reconstructed[:o_rows, :o_cols].copy()
        elif r_rows < o_rows or r_cols < o_cols:
            padded = np.zeros(original_shape, dtype=reconstructed.dtype)
            padded[:r_rows, :r_cols] = reconstructed
            reconstructed = padded
        original_dtype = np.dtype(coefficients_dict["original_dtype"])
        return np.round(reconstructed).astype(original_dtype)

    def inverse_transform(self, coefficients_dict: dict) -> np.ndarray:
        """
        Reconstruct pixel array from wavelet coefficients.
        coefficients_dict has "num_frames" and "frames" (list of per-frame coeff dicts).
        Returns 2D (single frame) or 3D (num_frames, rows, cols).
        """
        num_frames = coefficients_dict["num_frames"]
        frames = coefficients_dict["frames"]
        if num_frames == 1:
            return self.inverse_2d(frames[0])
        out = np.stack([self.inverse_2d(f) for f in frames], axis=0)
        return out
