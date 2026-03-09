"""
File Packer - Pack/unpack compressed DICOM components into .dcmz binary format.
V4: zstd for all sections + pixel_encoding (0=wavelet, 1=predictor). Targets 80-90% compression.
V3: zlib for pixel/codebook/coeff_meta (wavelet only).
"""

import json
import struct
import zlib
from pathlib import Path

try:
    import zstandard as zstd
    _ZSTD_AVAILABLE = True
except ImportError:
    _ZSTD_AVAILABLE = False

MAGIC_V1 = b"DCMZ_V1"
MAGIC_V2 = b"DCMZ_V2"
MAGIC_V3 = b"DCMZ_V3"
MAGIC_V4 = b"DCMZ_V4"
MAGIC = MAGIC_V4  # Current format (best compression)
PIXEL_ENCODING_WAVELET = 0
PIXEL_ENCODING_PREDICTOR = 1


def _compress_section(data: bytes, use_zstd: bool) -> bytes:
    if use_zstd and _ZSTD_AVAILABLE:
        cctx = zstd.ZstdCompressor(level=22)
        return cctx.compress(data)
    return zlib.compress(data, level=9)


def _decompress_section(data: bytes, use_zstd: bool) -> bytes:
    if use_zstd and _ZSTD_AVAILABLE:
        dctx = zstd.ZstdDecompressor()
        return dctx.decompress(data)
    return zlib.decompress(data)


class FilePacker:
    """Pack metadata, codebook, coeff_metadata, and pixel bytes into .dcmz file."""

    def pack(
        self,
        output_path: str,
        metadata_bytes: bytes,
        pixel_bytes: bytes,
        codebook: dict,
        coeff_metadata: dict,
        rows: int,
        cols: int,
        bits: int,
        num_frames: int = 1,
        wavelet_levels: int = 3,
        use_v3: bool = False,
        use_v4: bool = True,
        pixel_encoding: int = PIXEL_ENCODING_PREDICTOR,
    ) -> str:
        """
        Write full .dcmz file. V4 (default): zstd for all sections + pixel_encoding byte.
        pixel_encoding: PIXEL_ENCODING_WAVELET (0) or PIXEL_ENCODING_PREDICTOR (1).
        """
        codebook_json = json.dumps(codebook, separators=(',', ':'))
        codebook_bytes = codebook_json.encode("utf-8")
        coeff_meta_json = json.dumps(coeff_metadata, separators=(',', ':'))
        coeff_meta_bytes = coeff_meta_json.encode("utf-8")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        use_zstd = use_v4 and _ZSTD_AVAILABLE
        if use_v4 or use_v3:
            pixel_bytes = _compress_section(pixel_bytes, use_zstd)
            codebook_bytes = _compress_section(codebook_bytes, use_zstd)
            coeff_meta_bytes = _compress_section(coeff_meta_bytes, use_zstd)
        if use_v4:
            # Metadata is already compressed by handler (zstd or zlib)
            pass
        elif use_v3:
            pass

        metadata_size = len(metadata_bytes)
        codebook_size = len(codebook_bytes)
        coeff_meta_size = len(coeff_meta_bytes)
        pixel_size = len(pixel_bytes)

        with open(path, "wb") as f:
            if use_v4:
                f.write(MAGIC_V4)
                f.write(struct.pack("<I", rows))
                f.write(struct.pack("<I", cols))
                f.write(struct.pack("<H", bits))
                f.write(struct.pack("<B", wavelet_levels))
                f.write(struct.pack("<I", num_frames))
                f.write(struct.pack("<B", pixel_encoding))
                f.write(struct.pack("<I", metadata_size))
                f.write(struct.pack("<I", codebook_size))
                f.write(struct.pack("<I", coeff_meta_size))
                f.write(struct.pack("<I", pixel_size))
            elif use_v3:
                f.write(MAGIC_V3)
                f.write(struct.pack("<I", rows))
                f.write(struct.pack("<I", cols))
                f.write(struct.pack("<H", bits))
                f.write(struct.pack("<B", wavelet_levels))
                f.write(struct.pack("<I", num_frames))
                f.write(struct.pack("<I", metadata_size))
                f.write(struct.pack("<I", codebook_size))
                f.write(struct.pack("<I", coeff_meta_size))
                f.write(struct.pack("<I", pixel_size))
            else:
                f.write(MAGIC_V2)
                f.write(struct.pack("<I", rows))
                f.write(struct.pack("<I", cols))
                f.write(struct.pack("<H", bits))
                f.write(struct.pack("<B", wavelet_levels))
                f.write(struct.pack("<I", num_frames))
                f.write(struct.pack("<I", metadata_size))
                f.write(struct.pack("<I", codebook_size))
                f.write(struct.pack("<I", coeff_meta_size))
                f.write(struct.pack("<I", pixel_size))
            f.write(metadata_bytes)
            f.write(codebook_bytes)
            f.write(coeff_meta_bytes)
            f.write(pixel_bytes)
        return str(path)

    def unpack(self, input_path: str) -> dict:
        """
        Read .dcmz file and return dict with all components.
        V4: zstd decompress sections, pixel_encoding byte (0=wavelet, 1=predictor).
        V3: zlib decompress pixel/codebook/coeff_meta.
        """
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {input_path}")
        with open(path, "rb") as f:
            magic = f.read(7)
            if magic not in (MAGIC_V1, MAGIC_V2, MAGIC_V3, MAGIC_V4):
                raise ValueError("Not a valid DCMZ file")
            is_v4 = magic == MAGIC_V4
            is_v3 = magic == MAGIC_V3
            is_v2 = magic == MAGIC_V2
            rows = struct.unpack("<I", f.read(4))[0]
            cols = struct.unpack("<I", f.read(4))[0]
            bits = struct.unpack("<H", f.read(2))[0]
            wavelet_levels = struct.unpack("<B", f.read(1))[0]
            if is_v2 or is_v3 or is_v4:
                num_frames = struct.unpack("<I", f.read(4))[0]
                if num_frames == 0:
                    num_frames = 1
            else:
                num_frames = 1
            pixel_encoding = PIXEL_ENCODING_WAVELET
            if is_v4:
                pixel_encoding = struct.unpack("<B", f.read(1))[0]
            metadata_size = struct.unpack("<I", f.read(4))[0]
            codebook_size = struct.unpack("<I", f.read(4))[0]
            coeff_meta_size = struct.unpack("<I", f.read(4))[0]
            pixel_size = struct.unpack("<I", f.read(4))[0]
            metadata_bytes = f.read(metadata_size)
            codebook_bytes = f.read(codebook_size)
            coeff_meta_bytes = f.read(coeff_meta_size)
            pixel_bytes = f.read(pixel_size)
        use_zstd = is_v4 and _ZSTD_AVAILABLE
        if is_v4 or is_v3:
            codebook_bytes = _decompress_section(codebook_bytes, use_zstd)
            coeff_meta_bytes = _decompress_section(coeff_meta_bytes, use_zstd)
            pixel_bytes = _decompress_section(pixel_bytes, use_zstd)
        codebook = json.loads(codebook_bytes.decode("utf-8"))
        coeff_metadata = json.loads(coeff_meta_bytes.decode("utf-8"))
        if "num_frames" not in coeff_metadata:
            coeff_metadata["num_frames"] = num_frames
        if "frames" not in coeff_metadata and num_frames == 1 and not coeff_metadata.get("predictor"):
            pass
        return {
            "rows": rows,
            "cols": cols,
            "bits": bits,
            "num_frames": num_frames,
            "wavelet_levels": wavelet_levels,
            "pixel_encoding": pixel_encoding,
            "metadata_bytes": metadata_bytes,
            "codebook": codebook,
            "coeff_metadata": coeff_metadata,
            "pixel_bytes": pixel_bytes,
        }
