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
        """Flatten one frame's coefficient arrays in order into one float64 array."""
        parts = []
        parts.append(coefficients_dict["approximation"].ravel())
        for detail_level in coefficients_dict["details"]:
            for key in ("H", "V", "D"):
                parts.append(detail_level[key].ravel())
        return np.concatenate(parts).astype(np.float64)

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

    def encode(
        self, coefficients_dict: dict
    ) -> Tuple[bytes, Dict[int, str], dict]:
        """
        Encode coefficients to bytes using Huffman.
        coefficients_dict has "num_frames" and "frames" (list of per-frame coeff dicts).
        Returns (encoded_bytes, codebook, coeff_metadata).
        """
        num_frames = coefficients_dict["num_frames"]
        frames = coefficients_dict["frames"]
        # Flatten all frames into one array; build one codebook from all values
        all_flat = np.concatenate([self.coefficients_to_flat(c) for c in frames])
        frame_metadata_list = [self.build_coeff_metadata(c) for c in frames]
        coeff_metadata = {"num_frames": num_frames, "frames": frame_metadata_list}
        values = np.round(all_flat * COEFF_SCALE).astype(np.int64)
        freq = Counter(values.tolist())
        codebook = self.build_codebook(dict(freq))
        code_string = "".join(codebook[int(v)] for v in values.tolist())
        ba = bitarray.bitarray(code_string)
        encoded_bytes = ba.tobytes()
        return encoded_bytes, codebook, coeff_metadata

    def count_frame_coeffs(self, frame_meta: dict) -> int:
        """Total number of coefficients for one frame from its metadata."""
        n = int(np.prod(frame_meta["approximation_shape"]))
        for ds in frame_meta["detail_shapes"]:
            for key in ("H", "V", "D"):
                n += int(np.prod(ds[key]))
        return n

    def decode_one_frame(self, flat: np.ndarray, offset: int, frame_meta: dict) -> tuple:
        """Decode one frame from flat float array; return (coeff_dict, next_offset)."""
        approx_shape = tuple(frame_meta["approximation_shape"])
        n_approx = int(np.prod(approx_shape))
        approximation = flat[offset : offset + n_approx].reshape(approx_shape).astype(np.float64)
        offset += n_approx
        details = []
        for ds in frame_meta["detail_shapes"]:
            level = {}
            for key in ("H", "V", "D"):
                shape = tuple(ds[key])
                n = int(np.prod(shape))
                level[key] = flat[offset : offset + n].reshape(shape).astype(np.float64)
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
        flat = np.array(decoded_values, dtype=np.float64) / COEFF_SCALE
        if num_frames == 1 and "frames" not in coeff_metadata:
            coeff_dict, _ = self.decode_one_frame(flat, 0, coeff_metadata)
            return {"num_frames": 1, "frames": [coeff_dict]}
        frames = []
        offset = 0
        for frame_meta in frames_meta:
            coeff_dict, offset = self.decode_one_frame(flat, offset, frame_meta)
            frames.append(coeff_dict)
        return {"num_frames": num_frames, "frames": frames}
