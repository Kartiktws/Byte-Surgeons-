"""
File Packer - Pack/unpack compressed DICOM components into .dcmz binary format.
"""

import json
import struct
from pathlib import Path


MAGIC_V1 = b"DCMZ_V1"
MAGIC_V2 = b"DCMZ_V2"
MAGIC = MAGIC_V2  # Current format (multi-frame support)


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
    ) -> str:
        """
        Write full .dcmz file with header and sections.
        Header includes num_frames for multi-frame support.
        """
        codebook_json = json.dumps(codebook)
        codebook_bytes = codebook_json.encode("utf-8")
        coeff_meta_json = json.dumps(coeff_metadata)
        coeff_meta_bytes = coeff_meta_json.encode("utf-8")
        metadata_size = len(metadata_bytes)
        codebook_size = len(codebook_bytes)
        coeff_meta_size = len(coeff_meta_bytes)
        pixel_size = len(pixel_bytes)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
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
        Raises ValueError if magic bytes do not match.
        """
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {input_path}")
        with open(path, "rb") as f:
            magic = f.read(7)
            if magic not in (MAGIC_V1, MAGIC_V2):
                raise ValueError("Not a valid DCMZ file")
            is_v2 = magic == MAGIC_V2
            rows = struct.unpack("<I", f.read(4))[0]
            cols = struct.unpack("<I", f.read(4))[0]
            bits = struct.unpack("<H", f.read(2))[0]
            wavelet_levels = struct.unpack("<B", f.read(1))[0]
            if is_v2:
                num_frames = struct.unpack("<I", f.read(4))[0]
                if num_frames == 0:
                    num_frames = 1
            else:
                num_frames = 1
            metadata_size = struct.unpack("<I", f.read(4))[0]
            codebook_size = struct.unpack("<I", f.read(4))[0]
            coeff_meta_size = struct.unpack("<I", f.read(4))[0]
            pixel_size = struct.unpack("<I", f.read(4))[0]
            metadata_bytes = f.read(metadata_size)
            codebook_bytes = f.read(codebook_size)
            coeff_meta_bytes = f.read(coeff_meta_size)
            pixel_bytes = f.read(pixel_size)
        codebook = json.loads(codebook_bytes.decode("utf-8"))
        coeff_metadata = json.loads(coeff_meta_bytes.decode("utf-8"))
        if "num_frames" not in coeff_metadata:
            coeff_metadata["num_frames"] = num_frames
        if "frames" not in coeff_metadata and num_frames == 1:
            pass  # Legacy single-frame: coeff_metadata is the one frame's metadata
        return {
            "rows": rows,
            "cols": cols,
            "bits": bits,
            "num_frames": num_frames,
            "wavelet_levels": wavelet_levels,
            "metadata_bytes": metadata_bytes,
            "codebook": codebook,
            "coeff_metadata": coeff_metadata,
            "pixel_bytes": pixel_bytes,
        }
