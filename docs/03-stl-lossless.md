# 3. STL Lossless Compression

## Input

- **Format:** STL mesh file (`.stl`)
- **Content:** Triangle mesh — either:
  - **Binary STL:** 80-byte header + triangle count + 50 bytes per triangle (normal + 3 vertices × xyz + attribute).
  - **ASCII STL:** Text with `facet normal` / `vertex` / `endfacet` blocks.
- **Data:** For each triangle: 3 vertices (x, y, z) and optional normal. No quantization or mesh simplification; **exact geometry** is preserved.


## Approach Summary

| Step | Component | Description |
|------|-----------|-------------|
| **Parse** | `parse_stl` | Detect binary vs ASCII; parse to `vertices_per_triangle` (N×3×3 float32) and normals. Normals discarded and recomputed on decompression. |
| **Stage 0** | `stage0_deduplicate` | Build unique vertex list and index map; output `unique_vertices` (V×3 float32) and `triangles` (N×3 int32 indices). No welding; exact positions kept. |
| **Stage 1B** | `stage1b_delta_encode` | Sort vertices by X,Y,Z; sort triangles by first index. Delta-encode vertex coordinates (float32 bit-pattern as int32) and flattened triangle indices. |
| **Stage 1A** | `stage1a_huffman_encode` | Build Huffman codecs (dahuffman) from each delta stream; encode → 4 byte streams + 4 codec objects. |
| **Stage 4** | `build_payload` + `stage4_zstd_compress` | Serialize codecs + encoded blobs (length-prefixed); compress with ZSTD level 19. |
| **Write** | Header + payload | V1 header: MAGIC, version, mode=lossless, qbits=0, tri_count, vert_count, bbox (6×float32). Output: `.twsc`. |

**Output:** Single `.twsc` file (version 1). Decompression: read header → ZSTD decompress → decode Huffman → inverse delta → expand indices to vertex list → write STL (binary). Geometry is bit-exact (lossless).
