"""
FastAPI application for lossless DICOM compression/decompression.
"""

import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from backend.compressor.dicom_reader import DicomReader
from backend.compressor.metadata_handler import MetadataHandler
from backend.compressor.wavelet_engine import WaveletEngine
from backend.compressor.predictor_engine import PredictorEngine
from backend.compressor.huffman_engine import HuffmanEngine
from backend.compressor.file_packer import (
    FilePacker,
    PIXEL_ENCODING_WAVELET,
    PIXEL_ENCODING_PREDICTOR,
)
from backend.compressor.stl_compressor import compress as stl_compress, decompress as stl_decompress

# Output folders: compressed and decompressed files saved here (paths returned to user)
COMPRESSED_DIR = Path(__file__).resolve().parent / "compressed_output"
DECOMPRESSED_DIR = Path(__file__).resolve().parent / "decompressed_output"
STL_COMPRESSED_DIR = Path(__file__).resolve().parent / "stl_compressed_output"
STL_DECOMPRESSED_DIR = Path(__file__).resolve().parent / "stl_decompressed_output"
COMPRESSED_DIR.mkdir(parents=True, exist_ok=True)
DECOMPRESSED_DIR.mkdir(parents=True, exist_ok=True)
STL_COMPRESSED_DIR.mkdir(parents=True, exist_ok=True)
STL_DECOMPRESSED_DIR.mkdir(parents=True, exist_ok=True)


def unique_filename(prefix: str, suffix: str) -> str:
    """Generate a unique filename to avoid overwriting on multiple requests."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}{suffix}"


app = FastAPI(title="DICOM Lossless Compression API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

reader = DicomReader()
metadata_handler = MetadataHandler()
wavelet_engine = WaveletEngine()
predictor_engine = PredictorEngine()
huffman_engine = HuffmanEngine()
file_packer = FilePacker()


@app.get("/", include_in_schema=False)
def root():
    """Redirect root to Swagger UI."""
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0", "mode": "lossless"}


def _safe_compressed_filename(name: str) -> bool:
    """Allow only compressed_<8 hex>.dcmz (e.g. compressed_73bab97a.dcmz)."""
    if not name or len(name) > 64:
        return False
    name_lower = name.lower()
    if not name_lower.endswith(".dcmz"):
        return False
    base = name_lower[:-5]
    if not base.startswith("compressed_"):
        return False
    hex_part = base[11:]
    return len(hex_part) == 8 and all(c in "0123456789abcdef" for c in hex_part)


def _safe_stl_compressed_filename(name: str) -> bool:
    """Allow only stl_compressed_<8 hex>.twsc."""
    if not name or len(name) > 64:
        return False
    name_lower = name.lower()
    if not name_lower.endswith(".twsc"):
        return False
    base = name_lower[:-5]
    if not base.startswith("stl_compressed_"):
        return False
    hex_part = base[15:]
    return len(hex_part) == 8 and all(c in "0123456789abcdef" for c in hex_part)


@app.get("/download/compressed/{filename:path}", include_in_schema=False)
def download_compressed(filename: str):
    """Download a compressed DICOM file (.dcmz) by name. Filename must be like compressed_xxxxxxxx.dcmz."""
    if not _safe_compressed_filename(filename):
        raise HTTPException(400, "Invalid filename")
    path = COMPRESSED_DIR / filename
    if not path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(
        path=str(path),
        filename=filename,
        media_type="application/octet-stream",
    )


@app.get("/download/stl_compressed/{filename:path}", include_in_schema=False)
def download_stl_compressed(filename: str):
    """Download a compressed STL file (.twsc) by name."""
    if not _safe_stl_compressed_filename(filename):
        raise HTTPException(400, "Invalid filename")
    path = STL_COMPRESSED_DIR / filename
    if not path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(
        path=str(path),
        filename=filename,
        media_type="application/octet-stream",
    )


@app.post("/compress")
async def compress(file: UploadFile = File(...)):
    """
    Upload a .dcm file; compress, save to compressed_output folder, return stats + path.
    """
    if not file.filename or not file.filename.lower().endswith(".dcm"):
        raise HTTPException(400, "Only .dcm files are accepted")
    tmpdir = tempfile.mkdtemp()
    try:
        dcm_path = Path(tmpdir) / "input.dcm"
        content = await file.read()
        dcm_path.write_bytes(content)
        original_size = len(content)
        print("Step 1/5: Reading DICOM file...")
        data = reader.read(str(dcm_path))
        metadata_tags = data["metadata_tags"]
        pixel_array = data["pixel_array"]
        print("Step 2/5: Compressing metadata (compact JSON + zstd for 80-90%)...")
        metadata_bytes = metadata_handler.compress(metadata_tags)
        meta_ratio = metadata_handler.compression_ratio(metadata_tags, metadata_bytes)
        print("Step 3/5: Predictor encoding (JPEG-LS style for 80-90% pixel compression)...")
        residuals, predictor_metadata = predictor_engine.encode(
            pixel_array, bits=data["bits"]
        )
        print("Step 4/5: Huffman encoding residuals...")
        pixel_bytes, codebook, coeff_metadata = huffman_engine.encode_residuals(
            residuals, predictor_metadata
        )
        print("Step 5/5: Packing (V4 + zstd)...")
        out_filename = unique_filename("compressed", ".dcmz")
        out_path = COMPRESSED_DIR / out_filename
        num_frames = data.get("num_frames", 1)
        file_packer.pack(
            str(out_path),
            metadata_bytes=metadata_bytes,
            pixel_bytes=pixel_bytes,
            codebook=codebook,
            coeff_metadata=coeff_metadata,
            rows=data["rows"],
            cols=data["cols"],
            bits=data["bits"],
            num_frames=num_frames,
            use_v4=True,
            pixel_encoding=PIXEL_ENCODING_PREDICTOR,
        )
        compressed_size = out_path.stat().st_size
        ratio_pct = (
            round((1 - compressed_size / original_size) * 100, 2)
            if original_size > 0
            else 0.0
        )
        return {
            "status": "success",
            "num_frames": num_frames,
            "original_size_kb": round(original_size / 1024, 2),
            "compressed_size_kb": round(compressed_size / 1024, 2),
            "compression_ratio_percent": ratio_pct,
            "metadata_compression_percent": meta_ratio["ratio_percent"],
            "output_file": out_filename,
            "output_path": str(out_path),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/decompress")
async def decompress(file: UploadFile = File(...)):
    """
    Upload a .dcmz file; decompress, save to decompressed_output folder, return file + path.
    """
    if not file.filename or not file.filename.lower().endswith(".dcmz"):
        raise HTTPException(400, "Only .dcmz files are accepted")
    tmpdir = tempfile.mkdtemp()
    try:
        dcmz_path = Path(tmpdir) / "input.dcmz"
        content = await file.read()
        dcmz_path.write_bytes(content)
        print("Step 1/4: Reading compressed file...")
        unpacked = file_packer.unpack(str(dcmz_path))
        print("Step 2/4: Decompressing metadata...")
        metadata_tags = metadata_handler.decompress(unpacked["metadata_bytes"])
        pixel_encoding = unpacked.get("pixel_encoding", PIXEL_ENCODING_WAVELET)
        if pixel_encoding == PIXEL_ENCODING_PREDICTOR:
            print("Step 3/4: Huffman decoding residuals (predictor path)...")
            residuals = huffman_engine.decode_residuals(
                unpacked["pixel_bytes"],
                unpacked["codebook"],
                unpacked["coeff_metadata"],
            )
            print("Step 4/4: Inverse predictor...")
            pixel_array = predictor_engine.decode(residuals, unpacked["coeff_metadata"])
        else:
            print("Step 3/4: Huffman decoding (wavelet path)...")
            coefficients = huffman_engine.decode(
                unpacked["pixel_bytes"],
                unpacked["codebook"],
                unpacked["coeff_metadata"],
            )
            print("Step 4/4: Inverse Wavelet Transform...")
            pixel_array = wavelet_engine.inverse_transform(coefficients)
        out_filename = unique_filename("recovered", ".dcm")
        out_dcm = DECOMPRESSED_DIR / out_filename
        reader.reconstruct(metadata_tags, pixel_array, str(out_dcm))
        return FileResponse(
            path=str(out_dcm),
            filename=out_filename,
            media_type="application/dicom",
            headers={"X-Output-Path": str(out_dcm)},
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/stl/compress")
async def stl_compress_api(
    file: UploadFile = File(...),
    mode: str = Form("lossless"),
    bits: int = Form(12),
):
    """
    Upload a .stl file; compress to .twsc (lossless or lossy), save to stl_compressed_output, return stats + path.
    """
    if not file.filename or not file.filename.lower().endswith(".stl"):
        raise HTTPException(400, "Only .stl files are accepted")
    if mode not in ("lossless", "lossy"):
        raise HTTPException(400, "mode must be 'lossless' or 'lossy'")
    tmpdir = tempfile.mkdtemp()
    try:
        stl_path = Path(tmpdir) / "input.stl"
        content = await file.read()
        stl_path.write_bytes(content)
        original_size = len(content)
        out_filename = unique_filename("stl_compressed", ".twsc")
        out_path = STL_COMPRESSED_DIR / out_filename
        result = stl_compress(str(stl_path), str(out_path), mode=mode, bits=bits)
        compressed_size = out_path.stat().st_size
        return {
            "status": "success",
            "original_size_bytes": result["input_size"],
            "original_size_kb": round(original_size / 1024, 2),
            "compressed_size_bytes": result["output_size"],
            "compressed_size_kb": round(compressed_size / 1024, 2),
            "compression_ratio_percent": result["compression_ratio_percent"],
            "mode": result["mode"],
            "triangle_count": result["triangle_count"],
            "unique_vertex_count": result["unique_vertex_count"],
            "output_file": out_filename,
            "output_path": str(out_path),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/stl/decompress")
async def stl_decompress_api(file: UploadFile = File(...)):
    """
    Upload a .twsc file; decompress to .stl, save to stl_decompressed_output, return file + path.
    """
    if not file.filename or not file.filename.lower().endswith(".twsc"):
        raise HTTPException(400, "Only .twsc files are accepted")
    tmpdir = tempfile.mkdtemp()
    try:
        twsc_path = Path(tmpdir) / "input.twsc"
        content = await file.read()
        twsc_path.write_bytes(content)
        out_filename = unique_filename("stl_recovered", ".stl")
        out_path = STL_DECOMPRESSED_DIR / out_filename
        stl_decompress(str(twsc_path), str(out_path))
        return FileResponse(
            path=str(out_path),
            filename=out_filename,
            media_type="application/vnd.ms-pki.stl",
            headers={"X-Output-Path": str(out_path)},
        )
    except Exception as e:
        raise HTTPException(500, str(e))
