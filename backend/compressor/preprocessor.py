"""
Preprocessor - Normalize DICOM pixel data for lossy compression.
Apply window center/width (CT), rescale to uint8 [0-255], stack multi-frame as 3D.
Supports chunked processing: get global stats once, then normalize_frame() per frame
so the full normalized volume is never allocated.
"""

import numpy as np
from typing import Optional, Dict, Any


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
    Chunked flow: get_global_stats() once (no full float copy), then normalize_frame() per frame.
    """

    def get_global_stats(
        self,
        pixel_array: np.ndarray,
        modality: str,
        metadata_tags: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Compute normalization stats without allocating the full volume in float.
        Returns dict with keys needed by normalize_frame: e.g. "low", "high" (CT)
        or "min_val", "max_val" (other). Use with normalize_frame() for chunked processing.
        """
        arr = np.asarray(pixel_array)
        if arr.ndim == 2:
            arr = arr[np.newaxis, ...]
        n_frames, rows, cols = arr.shape
        modality = (modality or "OT").upper()

        if modality == "CT":
            center, width = get_window_params(metadata_tags)
            if center is not None and width is not None and width > 0:
                return {"low": center - width / 2, "high": center + width / 2, "width": width}
            # Sampled percentiles (no full-array float)
            step = max(1, int(round((n_frames * rows * cols / 2e6) ** (1 / 3))))
            sample = arr[::step, ::step, ::step]
            low = float(np.percentile(sample, 0.5))
            high = float(np.percentile(sample, 99.5))
            return {"low": low, "high": high, "span": max(high - low, 1.0)}
        # MRI/XR/other: min/max by iterating frames (no full float copy)
        min_val = float(np.min(arr[0]))
        max_val = float(np.max(arr[0]))
        for i in range(1, n_frames):
            min_val = min(min_val, float(np.min(arr[i])))
            max_val = max(max_val, float(np.max(arr[i])))
        return {"min_val": min_val, "max_val": max_val, "span": max(max_val - min_val, 1.0)}

    def normalize_frame(
        self,
        frame_2d: np.ndarray,
        global_stats: Dict[str, Any],
        modality: str,
    ) -> np.ndarray:
        """
        Normalize a single 2D frame to uint8 using precomputed global_stats.
        Use after get_global_stats() for chunked processing (only one frame in float at a time).
        """
        modality = (modality or "OT").upper()
        frame = np.asarray(frame_2d, dtype=np.float32)
        if modality == "CT":
            if "width" in global_stats:
                low, high = global_stats["low"], global_stats["high"]
                width = global_stats["width"]
                frame = np.clip(frame, low, high)
                frame = (frame - low) / width * 255.0
            else:
                low, span = global_stats["low"], global_stats["span"]
                frame = np.clip((frame - low) / span * 255.0, 0, 255)
        else:
            min_val = global_stats["min_val"]
            span = global_stats["span"]
            frame = (frame - min_val) / span * 255.0
        return np.clip(frame, 0, 255).astype(np.uint8)

    def normalize(
        self,
        pixel_array: np.ndarray,
        modality: str,
        metadata_tags: Optional[dict] = None,
    ) -> np.ndarray:
        """
        Apply modality-appropriate normalization and rescale to uint8 [0-255].
        Processes frame-by-frame to avoid allocating the full volume in float
        (prevents OOM on large stacks, e.g. 851x1001x1001).
        - CT: use DICOM window center/width to clip relevant HU range then scale to 0-255.
        - MRI/XR/other: min-max scale over the full range.
        Multi-frame: input (Z, H, W) is preserved as 3D uint8.
        """
        arr = np.asarray(pixel_array)
        if arr.ndim == 2:
            arr = arr[np.newaxis, ...]
        n_frames, rows, cols = arr.shape
        out = np.empty((n_frames, rows, cols), dtype=np.uint8)
        modality = (modality or "OT").upper()

        if modality == "CT":
            center, width = get_window_params(metadata_tags)
            if center is not None and width is not None and width > 0:
                low = center - width / 2
                high = center + width / 2
                for i in range(n_frames):
                    frame = np.asarray(arr[i], dtype=np.float32)
                    frame = np.clip(frame, low, high)
                    frame = (frame - low) / width * 255.0
                    out[i] = np.clip(frame, 0, 255).astype(np.uint8)
            else:
                # Default CT window: percentiles on a downsampled view to avoid large internal allocations
                step = max(1, int(round((n_frames * rows * cols / 2e6) ** (1 / 3))))
                sample = arr[::step, ::step, ::step]
                low = float(np.percentile(sample, 0.5))
                high = float(np.percentile(sample, 99.5))
                span = max(high - low, 1.0)
                for i in range(n_frames):
                    frame = np.asarray(arr[i], dtype=np.float32)
                    frame = np.clip((frame - low) / span * 255.0, 0, 255)
                    out[i] = frame.astype(np.uint8)
        else:
            # MRI, XR, other: full range to 0-255 (min/max on original dtype)
            min_val = float(np.min(arr))
            max_val = float(np.max(arr))
            span = max(max_val - min_val, 1.0)
            for i in range(n_frames):
                frame = np.asarray(arr[i], dtype=np.float32)
                frame = (frame - min_val) / span * 255.0
                out[i] = np.clip(frame, 0, 255).astype(np.uint8)
        return out
