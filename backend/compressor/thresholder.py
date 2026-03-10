"""
Thresholder - Zero out wavelet coefficients below threshold (dead-zone).
Sparse output improves RLE + Huffman efficiency.
"""

import numpy as np
from typing import Dict, Any


class Thresholder:
    """
    Apply threshold to wavelet coefficient dict (approximation + details).
    Coefficients with |c| < threshold are set to 0.
    """

    def apply(
        self,
        coefficients_dict: dict,
        threshold_pct: float = 0.05,
    ) -> dict:
        """
        Zero out coefficients below threshold_pct * max(|coeffs|).
        Works on structure: approximation (2D array) + details (list of {H,V,D}).
        Returns new dict (copy) with same structure; does not mutate original.
        """
        # Collect all coefficient arrays to find global max
        all_coeffs = []
        all_coeffs.append(coefficients_dict["approximation"].ravel())
        for detail_level in coefficients_dict["details"]:
            for key in ("H", "V", "D"):
                all_coeffs.append(detail_level[key].ravel())
        flat = np.concatenate([np.abs(c) for c in all_coeffs])
        max_abs = float(np.max(flat)) if flat.size else 1.0
        threshold = max(max_abs * threshold_pct, 1e-10)

        def zero_below(a: np.ndarray) -> np.ndarray:
            out = np.array(a, copy=True, dtype=a.dtype)
            out[np.abs(out) < threshold] = 0
            return out

        new_approx = zero_below(coefficients_dict["approximation"])
        new_details = []
        for detail_level in coefficients_dict["details"]:
            new_details.append({
                "H": zero_below(detail_level["H"]),
                "V": zero_below(detail_level["V"]),
                "D": zero_below(detail_level["D"]),
            })
        return {
            "approximation": new_approx,
            "details": new_details,
            "original_shape": coefficients_dict["original_shape"],
            "original_dtype": coefficients_dict["original_dtype"],
        }

    def apply_multi(self, coeffs_multi: dict, threshold_pct: float = 0.05) -> dict:
        """
        Apply threshold to multi-frame coefficient dict (num_frames, frames list).
        Returns new dict with same structure.
        """
        frames = []
        for frame in coeffs_multi["frames"]:
            frames.append(self.apply(frame, threshold_pct))
        return {
            "num_frames": coeffs_multi["num_frames"],
            "frames": frames,
        }
