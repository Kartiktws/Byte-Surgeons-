"""
Tests for lossless DICOM compression pipeline.
Uses synthetic DICOM when real files are not available.
"""

import sys
from pathlib import Path

import numpy as np
import pydicom
from pydicom.dataset import Dataset

# Add project root for imports
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.compressor.dicom_reader import DicomReader
from backend.compressor.metadata_handler import MetadataHandler
from backend.compressor.wavelet_engine import WaveletEngine
from backend.compressor.huffman_engine import HuffmanEngine
from backend.compressor.file_packer import FilePacker


def create_test_dicom(tmp_path, number_of_frames=None):
    """
    Create a synthetic 2D DICOM file for testing.
    If number_of_frames is set to an int > 1, the tag is written for 2D enforcement test.
    """
    ds = Dataset()
    ds.file_meta = Dataset()
    ds.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"  # Explicit VR Little Endian
    ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
    ds.file_meta.MediaStorageSOPInstanceUID = "1.2.3.4.5.6.7.8.9.10"
    ds.Rows = 64
    ds.Columns = 64
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    if number_of_frames is not None:
        ds.NumberOfFrames = str(number_of_frames)
        # Valid multi-frame: N frames of 64x64
        single_frame = np.random.randint(0, 2**12, size=(64, 64), dtype=np.uint16)
        pixel_array = np.tile(single_frame, (number_of_frames, 1, 1))
        ds.PixelData = pixel_array.tobytes()
    else:
        pixel_array = np.random.randint(0, 2**12, size=(64, 64), dtype=np.uint16)
        ds.PixelData = pixel_array.tobytes()
    ds.PatientName = "Test Patient"
    ds.PatientID = "TEST001"
    ds.Modality = "CT"
    out_path = tmp_path / "test.dcm"
    ds.save_as(str(out_path), write_like_original=False)
    return str(out_path)


def test_metadata_lossless():
    """Metadata compress → decompress must recover exact dict."""
    handler = MetadataHandler()
    sample = {
        "0010,0010": "Test Patient",
        "0010,0020": "TEST001",
        "0008,0060": "CT",
        "0028,0010": "64",
        "0028,0011": "64",
    }
    compressed = handler.compress(sample)
    recovered = handler.decompress(compressed)
    assert recovered == sample, "Metadata round-trip must be exact"
    for k, v in sample.items():
        assert k in recovered and recovered[k] == v
    print("Metadata lossless: PASSED ✅")


def test_wavelet_lossless():
    """Wavelet forward → inverse must recover exact pixel array."""
    engine = WaveletEngine()
    original = np.random.randint(0, 2**12, size=(64, 64), dtype=np.uint16)
    coeffs = engine.forward_transform(original)
    recovered = engine.inverse_transform(coeffs)
    assert np.array_equal(original, recovered), "Wavelet round-trip must be exact"
    print("Wavelet lossless: PASSED ✅")


def test_huffman_roundtrip():
    """Huffman encode → decode → inverse wavelet must recover exact pixel array (lossless at pixel level)."""
    engine = HuffmanEngine()
    wavelet = WaveletEngine()
    arr = np.random.randint(0, 1024, size=(32, 32), dtype=np.uint16)
    coeffs = wavelet.forward_transform(arr)
    encoded_bytes, codebook, coeff_meta = engine.encode(coeffs)
    recovered_coeffs = engine.decode(encoded_bytes, codebook, coeff_meta)
    recovered_pixels = wavelet.inverse_transform(recovered_coeffs)
    assert np.array_equal(arr, recovered_pixels), "Pixel array must match after full Huffman + wavelet roundtrip"
    assert recovered_coeffs["frames"][0]["original_shape"] == coeffs["frames"][0]["original_shape"]
    assert recovered_coeffs["frames"][0]["original_dtype"] == coeffs["frames"][0]["original_dtype"]
    print("Huffman roundtrip: PASSED ✅")


def test_full_pipeline_lossless(tmp_path):
    """Full compress → decompress must yield bit-identical pixels and metadata."""
    dcm_path = create_test_dicom(tmp_path)
    reader = DicomReader()
    meta_handler = MetadataHandler()
    wavelet_engine = WaveletEngine()
    huffman_engine = HuffmanEngine()
    file_packer = FilePacker()

    # Read original (pixel_array is 3D (1, rows, cols) for single-frame)
    data = reader.read(dcm_path)
    original_pixels = np.array(data["pixel_array"], copy=True)
    original_patient_name = data["metadata_tags"].get("0010,0010", "")
    original_rows = data["rows"]

    # Compress
    metadata_bytes = meta_handler.compress(data["metadata_tags"])
    coeffs = wavelet_engine.forward_transform(data["pixel_array"])
    pixel_bytes, codebook, coeff_meta = huffman_engine.encode(coeffs)
    dcmz_path = tmp_path / "compressed.dcmz"
    file_packer.pack(
        str(dcmz_path),
        metadata_bytes=metadata_bytes,
        pixel_bytes=pixel_bytes,
        codebook=codebook,
        coeff_metadata=coeff_meta,
        rows=data["rows"],
        cols=data["cols"],
        bits=data["bits"],
        num_frames=data.get("num_frames", 1),
    )
    original_size = Path(dcm_path).stat().st_size
    compressed_size = dcmz_path.stat().st_size
    ratio = (1 - compressed_size / original_size) * 100 if original_size else 0
    print(f"Compression ratio: {ratio:.2f}%")

    # Decompress
    unpacked = file_packer.unpack(str(dcmz_path))
    metadata_tags = meta_handler.decompress(unpacked["metadata_bytes"])
    coeffs_rec = huffman_engine.decode(
        unpacked["pixel_bytes"],
        unpacked["codebook"],
        unpacked["coeff_metadata"],
    )
    recovered_pixels = wavelet_engine.inverse_transform(coeffs_rec)
    recovered_dcm_path = tmp_path / "recovered.dcm"
    reader.reconstruct(metadata_tags, recovered_pixels, str(recovered_dcm_path))

    # Verify (single-frame: original_pixels (1,R,C), recovered_pixels (R,C) -> compare squeezed)
    orig = original_pixels.squeeze()
    rec = recovered_pixels.squeeze() if recovered_pixels.ndim == 3 else recovered_pixels
    assert np.array_equal(orig, rec), "Pixel array must match exactly after full pipeline"
    ds_recovered = pydicom.dcmread(str(recovered_dcm_path))
    assert str(ds_recovered.PatientName) == original_patient_name
    assert int(ds_recovered.Rows) == original_rows
    print("FULL PIPELINE LOSSLESS: PASSED ✅")


def test_multi_frame_pipeline_lossless(tmp_path):
    """Full compress → decompress for multi-frame DICOM must yield bit-identical pixels."""
    dcm_path = create_test_dicom(tmp_path, number_of_frames=3)
    reader = DicomReader()
    meta_handler = MetadataHandler()
    wavelet_engine = WaveletEngine()
    huffman_engine = HuffmanEngine()
    file_packer = FilePacker()

    data = reader.read(dcm_path)
    original_pixels = np.array(data["pixel_array"], copy=True)
    assert original_pixels.ndim == 3 and original_pixels.shape[0] == 3

    metadata_bytes = meta_handler.compress(data["metadata_tags"])
    coeffs = wavelet_engine.forward_transform(data["pixel_array"])
    assert coeffs["num_frames"] == 3 and len(coeffs["frames"]) == 3
    pixel_bytes, codebook, coeff_meta = huffman_engine.encode(coeffs)
    dcmz_path = tmp_path / "compressed_mf.dcmz"
    file_packer.pack(
        str(dcmz_path),
        metadata_bytes=metadata_bytes,
        pixel_bytes=pixel_bytes,
        codebook=codebook,
        coeff_metadata=coeff_meta,
        rows=data["rows"],
        cols=data["cols"],
        bits=data["bits"],
        num_frames=3,
    )

    unpacked = file_packer.unpack(str(dcmz_path))
    assert unpacked["num_frames"] == 3
    metadata_tags = meta_handler.decompress(unpacked["metadata_bytes"])
    coeffs_rec = huffman_engine.decode(
        unpacked["pixel_bytes"],
        unpacked["codebook"],
        unpacked["coeff_metadata"],
    )
    recovered_pixels = wavelet_engine.inverse_transform(coeffs_rec)
    assert recovered_pixels.ndim == 3 and recovered_pixels.shape[0] == 3
    recovered_dcm_path = tmp_path / "recovered_mf.dcm"
    reader.reconstruct(metadata_tags, recovered_pixels, str(recovered_dcm_path))

    assert np.array_equal(original_pixels, recovered_pixels), "Multi-frame pixels must match exactly"
    print("MULTI-FRAME PIPELINE LOSSLESS: PASSED ✅")
