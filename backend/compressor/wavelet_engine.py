"""
Wavelet Engine - Haar wavelet forward/inverse transform for lossless 2D/multi-frame images.
Supports float Haar (PyWavelets) and integer lifting Haar for higher compression.
No thresholding or quantization; fully reversible.
"""

import numpy as np
import pywt


def haar1d_forward_int(x: np.ndarray) -> tuple:
    """1D integer Haar lifting: (low, high) from 1D array. In-place style."""
    e = x[0::2].astype(np.int64)
    o = x[1::2].astype(np.int64)
    high = o - e
    low = e + (high >> 1)
    return low, high


def haar1d_inverse_int(low: np.ndarray, high: np.ndarray) -> np.ndarray:
    """1D integer Haar inverse: reconstruct 1D from low, high."""
    e = low - (high >> 1)
    o = high + e
    n = len(e) + len(o)
    out = np.empty(n, dtype=np.int64)
    out[0::2] = e
    out[1::2] = o
    return out


def haar2d_one_level_int(arr: np.ndarray) -> tuple:
    """One level 2D integer Haar. Returns (LL, LH, HL, HH)."""
    R, C = arr.shape
    arr = arr.astype(np.int64)
    # Rows: each row -> low | high
    L_rows = np.empty((R, C // 2), dtype=np.int64)
    H_rows = np.empty((R, C // 2), dtype=np.int64)
    for i in range(R):
        low, high = haar1d_forward_int(arr[i, :])
        L_rows[i, :] = low
        H_rows[i, :] = high
    # Columns of L_rows -> LL, HL
    LL = np.empty((R // 2, C // 2), dtype=np.int64)
    HL = np.empty((R // 2, C // 2), dtype=np.int64)
    for j in range(C // 2):
        low, high = haar1d_forward_int(L_rows[:, j])
        LL[:, j] = low
        HL[:, j] = high
    LH = np.empty((R // 2, C // 2), dtype=np.int64)
    HH = np.empty((R // 2, C // 2), dtype=np.int64)
    for j in range(C // 2):
        low, high = haar1d_forward_int(H_rows[:, j])
        LH[:, j] = low
        HH[:, j] = high
    return LL, LH, HL, HH


def haar2d_one_level_inverse_int(LL: np.ndarray, LH: np.ndarray, HL: np.ndarray, HH: np.ndarray) -> np.ndarray:
    """Inverse of one level 2D integer Haar."""
    R2, C2 = LL.shape
    # Reconstruct L_rows and H_rows from columns
    L_rows = np.empty((R2 * 2, C2), dtype=np.int64)
    H_rows = np.empty((R2 * 2, C2), dtype=np.int64)
    for j in range(C2):
        L_rows[:, j] = haar1d_inverse_int(LL[:, j], HL[:, j])
        H_rows[:, j] = haar1d_inverse_int(LH[:, j], HH[:, j])
    # Reconstruct rows
    out = np.empty((R2 * 2, C2 * 2), dtype=np.int64)
    for i in range(R2 * 2):
        out[i, :] = haar1d_inverse_int(L_rows[i, :], H_rows[i, :])
    return out


class WaveletEngine:
    """Haar wavelet transform (3 levels). Lossless only. Supports 2D and 3D (multi-frame).
    Use integer=True for integer lifting Haar (better compression, integer coefficients).
    """

    WAVELET = "haar"
    LEVELS = 3

    def forward_2d_int(self, pixel_2d: np.ndarray) -> dict:
        """Single 2D frame: integer Haar (3 levels). Returns coefficient dict with int64 arrays."""
        arr = np.asarray(pixel_2d, dtype=np.int64)
        if arr.dtype != np.int64 and arr.dtype.kind in "ui":
            arr = arr.astype(np.int64)
        coeffs_list = []
        current = arr
        for _ in range(self.LEVELS):
            LL, LH, HL, HH = haar2d_one_level_int(current)
            coeffs_list.append((LH, HL, HH))
            current = LL
        return {
            "approximation": np.array(current, copy=True),
            "details": [{"H": coeffs_list[i][1], "V": coeffs_list[i][0], "D": coeffs_list[i][2]}
                       for i in range(self.LEVELS)],
            "original_shape": tuple(pixel_2d.shape),
            "original_dtype": str(pixel_2d.dtype),
            "integer": True,
        }

    def inverse_2d_int(self, coefficients_dict: dict) -> np.ndarray:
        """Reconstruct one 2D frame from integer coefficient dict."""
        cA = coefficients_dict["approximation"]
        details = coefficients_dict["details"]
        current = cA.astype(np.int64)
        for level in range(self.LEVELS - 1, -1, -1):
            d = details[level]
            LH, HL, HH = d["V"], d["H"], d["D"]
            current = haar2d_one_level_inverse_int(current, LH, HL, HH)
        original_shape = coefficients_dict["original_shape"]
        original_dtype = np.dtype(coefficients_dict["original_dtype"])
        out = np.clip(current, np.iinfo(original_dtype).min, np.iinfo(original_dtype).max)
        return out.astype(original_dtype)

    def forward_2d(self, pixel_2d: np.ndarray) -> dict:
        """Single 2D frame: Haar decomposition. Returns one coefficient dict. Uses float32 to reduce per-frame allocation."""
        arr = np.asarray(pixel_2d, dtype=np.float32)
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

    def forward_transform_int(self, pixel_array: np.ndarray) -> dict:
        """3-level integer Haar. Use for maximum lossless compression."""
        if pixel_array.ndim == 2:
            one = self.forward_2d_int(pixel_array)
            return {"num_frames": 1, "frames": [one], "integer": True}
        frames = []
        for i in range(pixel_array.shape[0]):
            frames.append(self.forward_2d_int(pixel_array[i]))
        return {"num_frames": pixel_array.shape[0], "frames": frames, "integer": True}

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

    def inverse_transform_int(self, coefficients_dict: dict) -> np.ndarray:
        """Reconstruct pixel array from integer wavelet coefficients."""
        num_frames = coefficients_dict["num_frames"]
        frames = coefficients_dict["frames"]
        if num_frames == 1:
            return self.inverse_2d_int(frames[0])
        out = np.stack([self.inverse_2d_int(f) for f in frames], axis=0)
        return out

    def inverse_transform(self, coefficients_dict: dict) -> np.ndarray:
        """
        Reconstruct pixel array from wavelet coefficients.
        coefficients_dict has "num_frames" and "frames" (list of per-frame coeff dicts).
        Uses integer inverse if "integer" is True, else float Haar inverse.
        Returns 2D (single frame) or 3D (num_frames, rows, cols).
        """
        if coefficients_dict.get("integer"):
            return self.inverse_transform_int(coefficients_dict)
        num_frames = coefficients_dict["num_frames"]
        frames = coefficients_dict["frames"]
        if num_frames == 1:
            return self.inverse_2d(frames[0])
        out = np.stack([self.inverse_2d(f) for f in frames], axis=0)
        return out
