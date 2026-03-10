# 4. STL Lossy Compression

## Input

- **Format:** STL mesh file (`.stl`) — same as lossless (binary or ASCII).
- **Content:** Triangle mesh (vertices + triangles).
- **Typical use:** When **smaller file size** is preferred and some **geometry/vertex count reduction** is acceptable. Quality controlled by **quality_level**: `high` (70% triangles, 12-bit), `med` (45%, 10-bit), `low` (25%, 8-bit).


## Approach Summary

| Step | Component | Description |
|------|-----------|-------------|
| **Parse** | `parse_stl` | Same as lossless: vertices_per_triangle, normals dropped. |
| **Weld** | `stage0_weld_deduplicate` | Epsilon welding: grid cells of size ε = bbox_diagonal × factor (quality-based). Vertices in same cell merged to centroid; degenerate triangles removed. Reduces vertex count. |
| **QEM Decimation** | `stage_l1_decimate_qem` | Open3D quadric error metrics decimation. Target triangle count = keep_ratio × current (high 70%, med 45%, low 25%). Reduces triangle count. |
| **Quantize** | `stage2_quantize` | Map vertex coordinates to integer grid: per-axis min/max → `round((v - min)/(max - min) × (2^bits - 1))`. Bits: high=12, med=10, low=8. Bbox stored for dequantization. |
| **Morton Reorder** | `stage_l3_reorder_morton` | Reorder vertices by Morton (Z-order) code; sort triangles by centroid Morton. Improves delta coherence and compression. |
| **Delta + Huffman + ZSTD** | `stage1b_delta_encode` (lossless=False) + `stage1a_huffman_encode` + `stage4_zstd_compress` | Delta-encode quantized integer coords and triangle indices; Huffman encode; ZSTD compress. Same as lossless path but on integer data. |
| **Write** | V2 header | MAGIC, version=2, mode=lossy, quality_level, qbits, tri_count, vert_count, **orig_tri_count**, **orig_vert_count**, bbox (6×float32). Output: `.twsc` (48-byte header). |

**Output:** Single `.twsc` file (version 2). Decompression: read V2 header → ZSTD decompress → Huffman decode → inverse delta → dequantize using bbox + qbits → reconstruct mesh → write STL. Geometry is approximate (lossy); quality level and decimation/quantization control the trade-off.
