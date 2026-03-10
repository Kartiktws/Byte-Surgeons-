"""
Metadata Handler - Compress and decompress DICOM metadata for 80-90% ratio.
Uses compact JSON + zstd (fallback zlib). Auto-detects zstd vs zlib on decompress.
"""

import json
import zlib

# zstd magic (first 4 bytes) for auto-detect on decompress
ZSTD_MAGIC = bytes((0x28, 0xB5, 0x2F, 0xFD))

try:
    import zstandard as zstd
    _ZSTD_AVAILABLE = True
except ImportError:
    _ZSTD_AVAILABLE = False


def compress_zstd(data: bytes, level: int = 22) -> bytes:
    if not _ZSTD_AVAILABLE:
        return zlib.compress(data, level=9)
    cctx = zstd.ZstdCompressor(level=min(level, 22))
    return cctx.compress(data)


def decompress_zstd(data: bytes) -> bytes:
    if not _ZSTD_AVAILABLE:
        raise ValueError("zstandard not installed")
    dctx = zstd.ZstdDecompressor()
    return dctx.decompress(data)


def is_zstd(data: bytes) -> bool:
    return len(data) >= 4 and data[:4] == ZSTD_MAGIC


class MetadataHandler:
    """Compress metadata to bytes (compact JSON + zstd) for 80-90% compression."""

    def compress(self, metadata_tags: dict) -> bytes:
        """
        Compress metadata dict to bytes.
        STEP 1: dict → compact JSON (sorted keys, no spaces) for better ratio
        STEP 2: UTF-8 bytes
        STEP 3: zstd level 22 (or zlib if zstandard not available)
        """
        json_str = json.dumps(
            metadata_tags,
            ensure_ascii=True,
            sort_keys=True,
            separators=(',', ':'),
        )
        utf8_bytes = json_str.encode("utf-8")
        if _ZSTD_AVAILABLE:
            compressed = compress_zstd(utf8_bytes, level=22)
        else:
            compressed = zlib.compress(utf8_bytes, level=9)
        return compressed

    def decompress(self, compressed_bytes: bytes) -> dict:
        """
        Decompress bytes back to metadata_tags dict.
        Auto-detects zstd (magic 28 B5 2F FD) vs zlib.
        """
        if is_zstd(compressed_bytes):
            decompressed = decompress_zstd(compressed_bytes)
        else:
            decompressed = zlib.decompress(compressed_bytes)
        json_str = decompressed.decode("utf-8")
        metadata_tags = json.loads(json_str)
        return metadata_tags

    def compression_ratio(
        self, original_tags: dict, compressed_bytes: bytes
    ) -> dict:
        """
        Calculate compression ratio for metadata.
        Returns original_bytes, compressed_bytes, and ratio_percent.
        """
        json_str = json.dumps(original_tags, ensure_ascii=True)
        original_bytes = len(json_str.encode("utf-8"))
        compressed_len = len(compressed_bytes)
        if original_bytes == 0:
            ratio_percent = 0.0
        else:
            ratio_percent = round(
                (1 - compressed_len / original_bytes) * 100, 2
            )
        return {
            "original_bytes": original_bytes,
            "compressed_bytes": compressed_len,
            "ratio_percent": ratio_percent,
        }
