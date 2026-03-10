"""
Preprocessor - Normalize DICOM pixel data for lossy compression.
Apply window center/width (CT), rescale to uint8 [0-255], stack multi-frame as 3D.
"""

import numpy as np
from typing import Optional


def get_window_params(metadata_tags: Optional[dict]) -> tuple:
    """Extract window center and width from metadata. Returns (center, width) or (None, None)."""
    if not metadata_tags:
        return None, None
    center, width = None, None
    for key in ("0028,1050", "0028,1051"):
        entry = metadata_tags.get(key)
        if isinstance(entry, dict):
            try:
                v = entry.get("v", "")
                if key == "0028,1050":
                    center = float(v.split("\\")[0] if "\\" in str(v) else v)
                else:
                    width = float(v.split("\\")[0] if "\\" in str(v) else v)
            except (ValueError, TypeError):
                pass
        if center is not None and width is not None:
            break
    return center, width


class Preprocessor:
    """
    Normalize pixel array for lossy path: windowing (CT), rescale to uint8, 3D stack.
    """

    def normalize(
        self,
        pixel_array: np.ndarray,
        modality: str,
        metadata_tags: Optional[dict] = None,
    ) -> np.ndarray:
        """
        Apply modality-appropriate normalization and rescale to uint8 [0-255].
        - CT: use DICOM window center/width to clip relevant HU range then scale to 0-255.
        - MRI/XR/other: min-max scale over the full range.
        Multi-frame: input (Z, H, W) is preserved as 3D uint8.
        """
        arr = np.asarray(pixel_array, dtype=np.float64)
        if arr.ndim == 2:
            arr = arr[np.newaxis, ...]

        modality = (modality or "OT").upper()

        if modality == "CT":
            center, width = get_window_params(metadata_tags)
            if center is not None and width is not None and width > 0:
                low = center - width / 2
                high = center + width / 2
                arr = np.clip(arr, low, high)
                arr = (arr - low) / width * 255.0
            else:
                # Default CT window: e.g. 40/400 or use percentiles
                low = np.percentile(arr, 0.5)
                high = np.percentile(arr, 99.5)
                span = max(high - low, 1.0)
                arr = np.clip((arr - low) / span * 255.0, 0, 255)
        else:
            # MRI, XR, other: full range to 0-255
            min_val = np.min(arr)
            max_val = np.max(arr)
            span = max(max_val - min_val, 1.0)
            arr = (arr - min_val) / span * 255.0

        arr = np.clip(arr, 0, 255).astype(np.uint8)
        return arr
