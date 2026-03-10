# 2. Lossy DICOM Compression

## Input

- **Format:** DICOM image file (`.dcm`)
- **Content:** Same as lossless: metadata + pixel array (2D or multi-frame).
- **Typical use:** Visualization, telemedicine, or storage where **controlled quality loss** is acceptable in exchange for higher compression (e.g. thumbnails, web viewing). Quality is controlled by **Q** (quantization) and **threshold_pct** (wavelet coefficient thresholding).

---

## Block Diagram

## Approach Summary

| Step | Component | Description |
|------|-----------|-------------|
| 1 | **DICOM Reader + Preprocessor** | Read `.dcm`. Normalize pixels: CT → window center/width then scale to [0,255]; MRI/XR/other → min-max to [0,255]. Output: 3D uint8 stack. |
| 2 | **Quantization Engine** | Uniform scalar quantization: `pixel_q = pixel // Q`. Q from modality default (CT→4, MR→6, XR→8) or user. Reduces levels; Q stored in header for dequantization. |
| 3 | **Wavelet Engine** | Forward Haar wavelet (float path), 3 levels → multi-level coefficient structure (approximation + details per level). |
| 4 | **Thresholder** | Zero out coefficients with \|c\| < threshold_pct × max(\|coeffs\|). Sparse coefficients improve RLE + Huffman efficiency. |
| 5 | **Metadata Handler** | Same as lossless: compact JSON + ZSTD → `metadata_bytes`. |
| 6 | **Huffman Engine** | Encode wavelet coefficients (not residuals) → `pixel_bytes`, codebook, coeff_metadata. |
| 7 | **File Packer** | `pack_lossy()`: write MAGIC_V4_LOSSY (V5), store Q, threshold_pct, wavelet_levels; pack metadata + pixel bytes + codebook + coeff_metadata. |

**Output:** Single `.dcmz` file (lossy). Decompression: unpack → Huffman decode → inverse wavelet → dequantize (× Q + midpoint) → optional PSNR vs normalized original. Output DICOM has 8-bit pixel data.
