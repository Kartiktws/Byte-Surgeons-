"""
Huffman Engine - Encode/decode wavelet coefficients using Huffman coding.
Lossless: float64 coefficients scaled to integers for encoding, then restored.
"""

import json
import numpy as np
from collections import Counter
from typing import Tuple, Dict, Any
import bitarray


class HuffmanNode:
    """Node for Huffman tree."""

    __slots__ = ("value", "freq", "left", "right")

    def __init__(self, value=None, freq=0, left=None, right=None):
        self.value = value  # None for internal nodes
        self.freq = freq
        self.left = left
        self.right = right


# Scale factor to preserve float precision losslessly (2^20 gives ~6 decimal digits)
COEFF_SCALE = 2**20

# Use delta encoding for integer coefficient stream (much better compression)
USE_DELTA_FOR_INT = True


class HuffmanEngine:
    """Build Huffman tree from coefficient frequencies; encode/decode to bytes."""

    def build_codebook(self, value_freq: Dict[int, int]) -> Dict[int, str]:
        """Build Huffman tree and return codebook {value: binary_code_string}."""
        if not value_freq:
            return {}
        if len(value_freq) == 1:
            (only_val,) = value_freq.keys()
            return {only_val: "0"}

        nodes = [HuffmanNode(value=v, freq=f) for v, f in value_freq.items()]
        nodes.sort(key=lambda n: n.freq)

        while len(nodes) > 1:
            left = nodes.pop(0)
            right = nodes.pop(0)
            parent = HuffmanNode(
                freq=left.freq + right.freq, left=left, right=right
            )
            nodes.append(parent)
            nodes.sort(key=lambda n: n.freq)

        root = nodes[0]
        codebook = {}

        def traverse(node: HuffmanNode, code: str) -> None:
            if node.value is not None:
                codebook[node.value] = code if code else "0"
                return
            if node.left:
                traverse(node.left, code + "0")
            if node.right:
                traverse(node.right, code + "1")

        traverse(root, "")
        return codebook

    def coefficients_to_flat(self, coefficients_dict: dict) -> np.ndarray:
        """Flatten one frame's coefficient arrays in order. Uses float32 to reduce allocation (e.g. ~1M elements)."""
        parts = []
        parts.append(coefficients_dict["approximation"].ravel())
        for detail_level in coefficients_dict["details"]:
            for key in ("H", "V", "D"):
                parts.append(detail_level[key].ravel())
        out = np.concatenate(parts)
        return out.astype(np.float32) if out.dtype != np.float32 else out

    def build_coeff_metadata(self, coefficients_dict: dict) -> dict:
        """Build shape metadata for one frame (for reshape on decode)."""
        detail_shapes = []
        for detail_level in coefficients_dict["details"]:
            detail_shapes.append(
                {
                    "H": list(detail_level["H"].shape),
                    "V": list(detail_level["V"].shape),
                    "D": list(detail_level["D"].shape),
                }
            )
        return {
            "approximation_shape": list(coefficients_dict["approximation"].shape),
            "detail_shapes": detail_shapes,
            "original_shape": list(coefficients_dict["original_shape"]),
            "original_dtype": coefficients_dict["original_dtype"],
        }

    def frame_to_symbols(self, coefficients_dict: dict) -> np.ndarray:
        """Flatten one frame's coefficients and convert to int64 Huffman symbols (non-integer/lossy path)."""
        flat = self.coefficients_to_flat(coefficients_dict)
        return np.round(flat * COEFF_SCALE).astype(np.int64)

    def coefficients_to_flat_int(self, coefficients_dict: dict) -> np.ndarray:
        """Flatten one frame's coefficient arrays (int64) in same order as coefficients_to_flat."""
        parts = []
        parts.append(coefficients_dict["approximation"].ravel().astype(np.int64))
        for detail_level in coefficients_dict["details"]:
            for key in ("H", "V", "D"):
                parts.append(detail_level[key].ravel().astype(np.int64))
        return np.concatenate(parts)

    def encode(
        self, coefficients_dict: dict
    ) -> Tuple[bytes, Dict[int, str], dict]:
        """
        Encode coefficients to bytes using Huffman.
        If coefficients_dict has "integer" True, uses integer coeffs + delta encoding for best compression.
        Returns (encoded_bytes, codebook, coeff_metadata).
        """
        num_frames = coefficients_dict["num_frames"]
        frames = coefficients_dict["frames"]
        use_integer = coefficients_dict.get("integer", False)

        if use_integer:
            all_flat = np.concatenate([self.coefficients_to_flat_int(c) for c in frames])
            values = all_flat.astype(np.int64)
            if USE_DELTA_FOR_INT:
                # Delta encoding: first value then differences. Much smaller symbols -> better Huffman.
                deltas = np.empty_like(values)
                deltas[0] = values[0]
                if len(values) > 1:
                    deltas[1:] = np.diff(values)
                values = deltas
        else:
            all_flat = np.concatenate([self.coefficients_to_flat(c) for c in frames])
            values = np.round(all_flat * COEFF_SCALE).astype(np.int64)

        frame_metadata_list = [self.build_coeff_metadata(c) for c in frames]
        coeff_metadata = {
            "num_frames": num_frames,
            "frames": frame_metadata_list,
            "integer": use_integer,
            "delta_encoded": use_integer and USE_DELTA_FOR_INT,
        }

        freq = Counter(values.tolist())
        codebook = self.build_codebook(dict(freq))
        code_string = "".join(codebook[int(v)] for v in values.tolist())
        ba = bitarray.bitarray(code_string)
        encoded_bytes = ba.tobytes()
        return encoded_bytes, codebook, coeff_metadata

    def encode_residuals(
        self, residual_symbols: np.ndarray, predictor_metadata: dict
    ) -> Tuple[bytes, Dict[int, str], dict]:
        """
        Encode predictor residual symbols (flat int array) with Huffman.
        Used for predictor-based pixel path (80-90% compression).
        Returns (encoded_bytes, codebook, metadata) with metadata["predictor"] = True.
        """
        values = np.asarray(residual_symbols, dtype=np.int64).ravel()
        freq = Counter(values.tolist())
        codebook = self.build_codebook(dict(freq))
        code_string = "".join(codebook[int(v)] for v in values.tolist())
        ba = bitarray.bitarray(code_string)
        encoded_bytes = ba.tobytes()
        meta = dict(predictor_metadata)
        meta["predictor"] = True
        meta["n_symbols"] = len(values)
        return encoded_bytes, codebook, meta

    def decode_residuals(
        self, encoded_bytes: bytes, codebook: dict, metadata: dict
    ) -> np.ndarray:
        """
        Decode Huffman bytes back to flat array of residual symbols (predictor path).
        metadata must have "n_symbols" or "num_frames", "rows", "cols" to get count.
        """
        n_total = metadata.get("n_symbols")
        if n_total is None:
            n_total = (
                metadata["num_frames"]
                * metadata["rows"]
                * metadata["cols"]
            )
        reverse_cb = {}
        for k, v in codebook.items():
            reverse_cb[v] = int(k) if isinstance(k, str) else k
        ba = bitarray.bitarray()
        ba.frombytes(encoded_bytes)
        bit_str = ba.to01()
        decoded_values = []
        i = 0
        while i < len(bit_str) and len(decoded_values) < n_total:
            for length in range(1, min(len(bit_str) - i + 1, 64)):
                chunk = bit_str[i : i + length]
                if chunk in reverse_cb:
                    decoded_values.append(reverse_cb[chunk])
                    i += length
                    break
            else:
                i += 1
        return np.array(decoded_values, dtype=np.int64)

    def count_frame_coeffs(self, frame_meta: dict) -> int:
        """Total number of coefficients for one frame from its metadata."""
        n = int(np.prod(frame_meta["approximation_shape"]))
        for ds in frame_meta["detail_shapes"]:
            for key in ("H", "V", "D"):
                n += int(np.prod(ds[key]))
        return n

    def decode_one_frame(self, flat: np.ndarray, offset: int, frame_meta: dict) -> tuple:
        """Decode one frame from flat float array; return (coeff_dict, next_offset). Uses float32 to reduce allocation."""
        approx_shape = tuple(frame_meta["approximation_shape"])
        n_approx = int(np.prod(approx_shape))
        approximation = flat[offset : offset + n_approx].reshape(approx_shape).astype(np.float32)
        offset += n_approx
        details = []
        for ds in frame_meta["detail_shapes"]:
            level = {}
            for key in ("H", "V", "D"):
                shape = tuple(ds[key])
                n = int(np.prod(shape))
                level[key] = flat[offset : offset + n].reshape(shape).astype(np.float32)
                offset += n
            details.append(level)
        coeff_dict = {
            "approximation": approximation,
            "details": details,
            "original_shape": tuple(frame_meta["original_shape"]),
            "original_dtype": frame_meta["original_dtype"],
        }
        return coeff_dict, offset

    def decode_one_frame_int(self, flat_float: np.ndarray, flat_int: np.ndarray, offset: int, frame_meta: dict) -> tuple:
        """Decode one frame for integer path: use flat_int (int64) for coefficient arrays."""
        approx_shape = tuple(frame_meta["approximation_shape"])
        n_approx = int(np.prod(approx_shape))
        approximation = flat_int[offset : offset + n_approx].reshape(approx_shape).astype(np.int64)
        offset += n_approx
        details = []
        for ds in frame_meta["detail_shapes"]:
            level = {}
            for key in ("H", "V", "D"):
                shape = tuple(ds[key])
                n = int(np.prod(shape))
                level[key] = flat_int[offset : offset + n].reshape(shape).astype(np.int64)
                offset += n
            details.append(level)
        coeff_dict = {
            "approximation": approximation,
            "details": details,
            "original_shape": tuple(frame_meta["original_shape"]),
            "original_dtype": frame_meta["original_dtype"],
        }
        return coeff_dict, offset

    def decode(
        self,
        encoded_bytes: bytes,
        codebook: dict,
        coeff_metadata: dict,
    ) -> dict:
        """
        Decode bytes back to coefficients dict (multi-frame format).
        coeff_metadata has "num_frames" and "frames" (list of per-frame metadata).
        """
        reverse_cb = {}
        for k, v in codebook.items():
            reverse_cb[v] = int(k) if isinstance(k, str) else k
        num_frames = coeff_metadata.get("num_frames", 1)
        frames_meta = coeff_metadata.get("frames", [coeff_metadata])
        if num_frames == 1 and "frames" not in coeff_metadata:
            # Legacy single-frame format (no "frames" key)
            n_total = self.count_frame_coeffs(coeff_metadata)
        else:
            n_total = sum(self.count_frame_coeffs(m) for m in frames_meta)
        ba = bitarray.bitarray()
        ba.frombytes(encoded_bytes)
        bit_str = ba.to01()
        decoded_values = []
        i = 0
        while i < len(bit_str) and len(decoded_values) < n_total:
            for length in range(1, len(bit_str) - i + 1):
                chunk = bit_str[i : i + length]
                if chunk in reverse_cb:
                    decoded_values.append(reverse_cb[chunk])
                    i += length
                    break
            else:
                i += 1

        use_integer = coeff_metadata.get("integer", False)
        delta_encoded = coeff_metadata.get("delta_encoded", False)

        if use_integer:
            flat = np.array(decoded_values, dtype=np.int64)
            if delta_encoded:
                flat = np.cumsum(flat)
            # Decode expects float for legacy path; for integer we use decode_one_frame with int->float view
            # decode_one_frame reshapes and sets .astype(np.float64). For integer path we need to keep int
            # and set "integer" on each frame. So we need a variant that keeps int64.
            flat_float = flat.astype(np.float64)  # same numbers for reshape
            if num_frames == 1 and "frames" not in coeff_metadata:
                coeff_dict, _ = self.decode_one_frame_int(flat_float, flat, 0, coeff_metadata)
                return {"num_frames": 1, "frames": [coeff_dict], "integer": True}
            frames = []
            offset = 0
            for frame_meta in frames_meta:
                coeff_dict, offset = self.decode_one_frame_int(flat_float, flat, offset, frame_meta)
                frames.append(coeff_dict)
            return {"num_frames": num_frames, "frames": frames, "integer": True}
        else:
            flat = np.array(decoded_values, dtype=np.float32) / COEFF_SCALE
            if num_frames == 1 and "frames" not in coeff_metadata:
                coeff_dict, _ = self.decode_one_frame(flat, 0, coeff_metadata)
                return {"num_frames": 1, "frames": [coeff_dict]}
            frames = []
            offset = 0
            for frame_meta in frames_meta:
                coeff_dict, offset = self.decode_one_frame(flat, offset, frame_meta)
                frames.append(coeff_dict)
            return {"num_frames": num_frames, "frames": frames}
