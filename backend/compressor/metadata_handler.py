"""
Metadata Handler - Compress and decompress DICOM metadata using JSON + DEFLATE.
"""

import json
import zlib


class MetadataHandler:
    """Compress metadata to bytes (JSON + zlib) and decompress back to dict."""

    def compress(self, metadata_tags: dict) -> bytes:
        """
        Compress metadata dict to bytes.
        STEP 1: dict → JSON string
        STEP 2: Encode to UTF-8 bytes
        STEP 3: zlib.compress(level=9)
        """
        json_str = json.dumps(metadata_tags, ensure_ascii=True)
        utf8_bytes = json_str.encode("utf-8")
        compressed = zlib.compress(utf8_bytes, level=9)
        return compressed

    def decompress(self, compressed_bytes: bytes) -> dict:
        """
        Decompress bytes back to metadata_tags dict.
        STEP 1: zlib.decompress
        STEP 2: Decode UTF-8
        STEP 3: json.loads
        """
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
