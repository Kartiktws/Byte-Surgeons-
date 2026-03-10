# 1. Lossless DICOM Compression

## Input

- **Format:** DICOM image file (`.dcm`)
- **Content:** Single-frame (2D) or multi-frame (3D) medical image with:
  - **Metadata:** DICOM tags (patient/study/series info, modality, window center/width, bits stored, etc.)
  - **Pixel data:** Raw pixel array (e.g. 8-, 12-, or 16-bit) at tags `(7FE0,0010)`
- **Typical use:** Archival, transfer, or storage where **exact pixel recovery** is required (e.g. regulatory, diagnosis).



## Approach Summary

| Step | Component | Description |
|------|-----------|-------------|
| 1 | **DICOM Reader** | Parses `.dcm`; extracts metadata (all tags as JSON-serializable dict) and pixel array (2D/3D). |
| 2 | **Metadata Handler** | Compresses metadata: compact JSON (sorted keys, no spaces) → UTF-8 → ZSTD (level 22). Targets ~80–90% metadata compression. |
| 3 | **Predictor Engine** | JPEG-LS style median predictor: predict each pixel from left, top, left+top−topleft; output residuals. RLE on zero runs; map residuals to non-negative symbols for Huffman. |
| 4 | **Huffman Engine** | Build Huffman codec from residual symbols; encode residuals → `pixel_bytes`; store codebook and coeff metadata. |
| 5 | **File Packer** | Pack metadata_bytes, pixel_bytes, codebook, coeff_metadata into `.dcmz` (V4: zstd on all sections, `pixel_encoding = predictor`). |

**Output:** Single `.dcmz` file. Decompression reverses: unpack → decompress metadata → Huffman decode residuals → inverse predictor → reconstruct DICOM with original pixels (lossless).
