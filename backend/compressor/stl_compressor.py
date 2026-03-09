"""
Proprietary STL mesh compression engine.

Compresses binary or ASCII STL files using vertex deduplication, optional
quantization (lossy), delta coding, Huffman coding, and ZSTD.
Output format: .twsc (single binary file).
"""

from __future__ import annotations

import argparse
import pickle
import struct
from pathlib import Path
from typing import Literal, Tuple, List, Dict, Any

import numpy as np
import zstandard
from dahuffman import HuffmanCodec

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
MAGIC = b"TWSC"
VERSION = 1
MODE_LOSSLESS = 0
MODE_LOSSY = 1
DEFAULT_QUANTIZATION_BITS = 12
ZSTD_LEVEL = 19
HEADER_SIZE = 4 + 1 + 1 + 1 + 4 + 4 + 24  # 39 bytes: magic + version + mode + qbits + tri + vert + 6*float

# Binary STL: 80-byte header + 4-byte triangle count + 50 bytes per triangle
STL_BINARY_TRIANGLE_SIZE = 50  # 12 (normal) + 36 (9 floats) + 2 (attr)


def parse_stl_binary(data: bytes) -> Tuple[np.ndarray, np.ndarray]:
    """
    Parse binary STL. Returns (vertices_per_triangle, normals).
    vertices_per_triangle: (N, 3, 3) float32 — N triangles, 3 vertices, xyz each.
    normals: (N, 3) float32 — not used after stage0 but needed for validation.
    """
    if len(data) < 84:
        raise ValueError("Binary STL too short")
    num_tri = struct.unpack_from("<I", data, 80)[0]
    expected = 84 + num_tri * STL_BINARY_TRIANGLE_SIZE
    if len(data) < expected:
        raise ValueError("Binary STL truncated")
    vertices = np.zeros((num_tri, 3, 3), dtype=np.float32)
    normals = np.zeros((num_tri, 3), dtype=np.float32)
    off = 84
    for i in range(num_tri):
        # normal
        normals[i] = struct.unpack_from("<3f", data, off)
        off += 12
        # 3 vertices
        for j in range(3):
            vertices[i, j] = struct.unpack_from("<3f", data, off)
            off += 12
        off += 2  # attribute
    return vertices, normals


def parse_stl_ascii(text: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    Parse ASCII STL. Returns (vertices_per_triangle, normals).
    Same shapes as binary.
    """
    lines = [s.strip() for s in text.splitlines()]
    tri_list: List[Tuple[np.ndarray, np.ndarray]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("facet normal"):
            parts = line.split()
            if len(parts) != 5:
                i += 1
                continue
            try:
                nx, ny, nz = float(parts[2]), float(parts[3]), float(parts[4])
            except ValueError:
                i += 1
                continue
            normal = np.array([nx, ny, nz], dtype=np.float32)
            verts = []
            i += 1
            if i < len(lines) and lines[i].strip() == "outer loop":
                i += 1
            for _ in range(3):
                if i < len(lines) and lines[i].strip().startswith("vertex"):
                    p = lines[i].split()
                    if len(p) >= 4:
                        verts.append([float(p[1]), float(p[2]), float(p[3])])
                    i += 1
            if len(verts) == 3:
                tri_list.append((normal, np.array(verts, dtype=np.float32)))
            while i < len(lines) and not lines[i].strip().startswith("endfacet"):
                i += 1
            if i < len(lines):
                i += 1
        else:
            i += 1
    if not tri_list:
        raise ValueError("No triangles found in ASCII STL")
    normals = np.array([t[0] for t in tri_list], dtype=np.float32)
    vertices = np.array([t[1] for t in tri_list], dtype=np.float32)
    return vertices, normals


def is_ascii_stl(data: bytes) -> bool:
    """Heuristic: if starts with 'solid ' and has newlines, treat as ASCII."""
    if len(data) < 6:
        return False
    return data[:6].lower() == b"solid " and b"\n" in data[:200]


def parse_stl(path: str | Path) -> Tuple[np.ndarray, np.ndarray]:
    """
    Parse STL file (binary or ASCII). Returns (vertices_per_triangle, normals).
    vertices_per_triangle: (N, 3, 3) float32.
    """
    path = Path(path)
    data = path.read_bytes()
    if is_ascii_stl(data):
        text = data.decode("utf-8", errors="replace")
        return parse_stl_ascii(text)
    return parse_stl_binary(data)


def stage0_deduplicate(
    vertices_per_triangle: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Stage 0: Vertex deduplication + indexing.

    Input: vertices_per_triangle (N, 3, 3) float32 — each triangle has 3 vertices (x,y,z).
    Output:
      - unique_vertices: (V, 3) float32, unique (x,y,z) rows.
      - triangles: (N, 3) int32, each row is (index0, index1, index2) into unique_vertices.
    Normals are dropped; they will be recomputed on decompression.
    """
    N = vertices_per_triangle.shape[0]
    vertex_to_index: Dict[Tuple[float, float, float], int] = {}
    unique_list: List[np.ndarray] = []
    for i in range(N):
        for j in range(3):
            v = vertices_per_triangle[i, j]
            key = (float(v[0]), float(v[1]), float(v[2]))
            if key not in vertex_to_index:
                vertex_to_index[key] = len(unique_list)
                unique_list.append(v.copy())
    unique_vertices = np.array(unique_list, dtype=np.float32)
    triangles = np.zeros((N, 3), dtype=np.int32)
    for i in range(N):
        for j in range(3):
            v = vertices_per_triangle[i, j]
            key = (float(v[0]), float(v[1]), float(v[2]))
            triangles[i, j] = vertex_to_index[key]
    return unique_vertices, triangles


def stage2_quantize(
    unique_vertices: np.ndarray,
    bits: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Stage 2: Quantization (lossy only).

    Input: unique_vertices (V, 3) float32.
    Output:
      - quantized_vertices: (V, 3) integer array (uint or int depending on range).
      - bbox: (6,) float32 = xmin, xmax, ymin, ymax, zmin, zmax.
    Formula: quantized = round((v - axis_min) / (axis_max - axis_min) * (2^N - 1))
    """
    bbox = np.array(
        [
            unique_vertices[:, 0].min(),
            unique_vertices[:, 0].max(),
            unique_vertices[:, 1].min(),
            unique_vertices[:, 1].max(),
            unique_vertices[:, 2].min(),
            unique_vertices[:, 2].max(),
        ],
        dtype=np.float32,
    )
    xmin, xmax = bbox[0], bbox[1]
    ymin, ymax = bbox[2], bbox[3]
    zmin, zmax = bbox[4], bbox[5]
    max_val = (1 << bits) - 1
    qx = (unique_vertices[:, 0] - xmin) / (xmax - xmin + 1e-12) * max_val
    qy = (unique_vertices[:, 1] - ymin) / (ymax - ymin + 1e-12) * max_val
    qz = (unique_vertices[:, 2] - zmin) / (zmax - zmin + 1e-12) * max_val
    quantized = np.column_stack(
        [np.round(qx).astype(np.int64), np.round(qy).astype(np.int64), np.round(qz).astype(np.int64)]
    )
    return quantized, bbox


def stage1b_delta_encode(
    unique_vertices: np.ndarray,
    triangles: np.ndarray,
    lossless: bool,
) -> Tuple[Any, Any, Any, Any]:
    """
    Stage 1B: Delta / prediction coding.

    Vertices are sorted by X, then Y, then Z. For each coordinate array (X, Y, Z),
    first value stored as-is, then deltas. For triangle indices, sort by first index,
    then delta-code the index list (flattened).

    Input:
      - unique_vertices: (V, 3) — float32 for lossless, integer for lossy.
      - triangles: (N, 3) int32.
      - lossless: if True, treat vertex coords as float32 and delta on bit pattern (int32 view).
    Output: (x_deltas, y_deltas, z_deltas, index_deltas) as lists of integers (for Huffman).
    """
    # Sort vertices by X, then Y, then Z
    order = np.lexsort((unique_vertices[:, 2], unique_vertices[:, 1], unique_vertices[:, 0]))
    sorted_verts = unique_vertices[order]
    # Inverse permutation: new_index[old_index] = position in sorted list
    inv_order = np.empty_like(order)
    inv_order[order] = np.arange(len(order))
    # Remap triangle indices to sorted order
    tri_remap = inv_order[triangles]
    # Sort triangles by first index
    tri_sort = np.lexsort((tri_remap[:, 2], tri_remap[:, 1], tri_remap[:, 0]))
    tri_sorted = tri_remap[tri_sort]

    if lossless:
        # Reinterpret float32 as int32 for exact delta
        view = sorted_verts.view(np.int32)
        x_vals = view[:, 0].tolist()
        y_vals = view[:, 1].tolist()
        z_vals = view[:, 2].tolist()
    else:
        x_vals = sorted_verts[:, 0].astype(np.int64).tolist()
        y_vals = sorted_verts[:, 1].astype(np.int64).tolist()
        z_vals = sorted_verts[:, 2].astype(np.int64).tolist()

    def delta_list(arr: List[int]) -> List[int]:
        out = [arr[0]]
        for i in range(1, len(arr)):
            out.append(arr[i] - arr[i - 1])
        return out

    x_deltas = delta_list(x_vals)
    y_deltas = delta_list(y_vals)
    z_deltas = delta_list(z_vals)

    # Flatten triangle indices and delta-code
    flat = tri_sorted.ravel().astype(np.int64).tolist()
    index_deltas = delta_list(flat)

    return x_deltas, y_deltas, z_deltas, index_deltas


def stage1a_huffman_encode(
    x_deltas: List[int],
    y_deltas: List[int],
    z_deltas: List[int],
    index_deltas: List[int],
) -> Tuple[bytes, bytes, bytes, bytes, Any, Any, Any, Any]:
    """
    Stage 1A: Entropy coding with Huffman.

    Input: four lists of integers (deltas).
    Output: (x_bytes, y_bytes, z_bytes, idx_bytes, codec_x, codec_y, codec_z, codec_idx).
    Codecs are dahuffman HuffmanCodec instances (to be pickled).
    """
    codec_x = HuffmanCodec.from_data(x_deltas)
    codec_y = HuffmanCodec.from_data(y_deltas)
    codec_z = HuffmanCodec.from_data(z_deltas)
    codec_idx = HuffmanCodec.from_data(index_deltas)
    x_bytes = codec_x.encode(x_deltas)
    y_bytes = codec_y.encode(y_deltas)
    z_bytes = codec_z.encode(z_deltas)
    idx_bytes = codec_idx.encode(index_deltas)
    return x_bytes, y_bytes, z_bytes, idx_bytes, codec_x, codec_y, codec_z, codec_idx


def stage4_zstd_compress(payload: bytes) -> bytes:
    """
    Stage 4: Compress payload with ZSTD at level 19.

    Input: serialized payload (header + huffman tables + encoded data).
    Output: compressed bytes.
    """
    cctx = zstandard.ZstdCompressor(level=ZSTD_LEVEL)
    return cctx.compress(payload)


def build_payload(
    codec_x: Any,
    codec_y: Any,
    codec_z: Any,
    codec_idx: Any,
    x_bytes: bytes,
    y_bytes: bytes,
    z_bytes: bytes,
    idx_bytes: bytes,
) -> bytes:
    """Build payload with length-prefixed blobs (uint32 length each)."""
    parts = []
    for blob in [codec_x, codec_y, codec_z, codec_idx]:
        b = pickle.dumps(blob)
        parts.append(struct.pack("<I", len(b)))
        parts.append(b)
    for blob in [x_bytes, y_bytes, z_bytes, idx_bytes]:
        parts.append(struct.pack("<I", len(blob)))
        parts.append(blob)
    return b"".join(parts)


def compress(
    input_path: str | Path,
    output_path: str | Path,
    mode: Literal["lossless", "lossy"] = "lossless",
    bits: int = DEFAULT_QUANTIZATION_BITS,
) -> Dict[str, Any]:
    """
    Master compress: parse STL, run pipeline in order Stage0 -> (Stage2 if lossy) -> Stage1B -> Stage1A -> Stage4,
    write .twsc file. Returns dict with sizes, ratio, counts.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    lossless = mode == "lossless"

    vertices_pt, _ = parse_stl(input_path)
    unique_vertices, triangles = stage0_deduplicate(vertices_pt)

    if lossless:
        bbox = np.zeros(6, dtype=np.float32)
        verts_for_delta = unique_vertices.astype(np.float32)
    else:
        verts_quant, bbox = stage2_quantize(unique_vertices, bits)
        verts_for_delta = verts_quant

    x_d, y_d, z_d, idx_d = stage1b_delta_encode(verts_for_delta, triangles, lossless)

    x_b, y_b, z_b, i_b, cx, cy, cz, ci = stage1a_huffman_encode(x_d, y_d, z_d, idx_d)
    payload = build_payload(cx, cy, cz, ci, x_b, y_b, z_b, i_b)
    compressed_payload = stage4_zstd_compress(payload)

    # Header: magic, version, mode, qbits, tri_count, vert_count, bbox (6 float32)
    header = struct.pack(
        "<4sBBBII",
        MAGIC,
        VERSION,
        MODE_LOSSLESS if lossless else MODE_LOSSY,
        0 if lossless else bits,
        triangles.shape[0],
        unique_vertices.shape[0],
    )
    header += struct.pack("<6f", *bbox.tolist())
    full = header + compressed_payload
    output_path.write_bytes(full)

    input_size = input_path.stat().st_size
    output_size = len(full)
    ratio_pct = (1 - output_size / input_size) * 100 if input_size > 0 else 0.0
    return {
        "input_size": input_size,
        "output_size": output_size,
        "compression_ratio_percent": round(ratio_pct, 2),
        "mode": mode,
        "triangle_count": int(triangles.shape[0]),
        "unique_vertex_count": int(unique_vertices.shape[0]),
    }


# -----------------------------------------------------------------------------
# Decompression
# -----------------------------------------------------------------------------


def read_header(data: bytes) -> Dict[str, Any]:
    """Parse .twsc header. Returns dict with mode, bits, tri_count, vert_count, bbox."""
    if len(data) < HEADER_SIZE or data[:4] != MAGIC:
        raise ValueError("Invalid TWSC file or header too short")
    version, mode, qbits, tri_count, vert_count = struct.unpack_from("<BBBII", data, 4)
    if version != VERSION:
        raise ValueError(f"Unsupported TWSC version {version}")
    bbox = struct.unpack_from("<6f", data, 4 + 1 + 1 + 1 + 4 + 4)  # offset 15
    return {
        "version": version,
        "mode": mode,
        "quantization_bits": qbits,
        "triangle_count": tri_count,
        "vertex_count": vert_count,
        "bbox": np.array(bbox, dtype=np.float32),
    }


def decompress_zstd(compressed: bytes) -> bytes:
    dctx = zstandard.ZstdDecompressor()
    return dctx.decompress(compressed)


def read_length_prefixed(data: bytes, offset: int) -> Tuple[Any, int]:
    """Read uint32 length then that many bytes. Return (payload, new_offset)."""
    if offset + 4 > len(data):
        raise ValueError("Payload truncated at length prefix")
    ln = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    if offset + ln > len(data):
        raise ValueError("Payload truncated at blob")
    blob = data[offset : offset + ln]
    return blob, offset + ln


def decompress(input_path: str | Path, output_path: str | Path) -> None:
    """
    Decompress .twsc to binary STL. Reverses: read header, zstd decompress,
    unpickle codecs, huffman decode, delta decode, (dequantize if lossy),
    rebuild vertices and triangles, compute normals, write STL.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    data = input_path.read_bytes()
    info = read_header(data)
    payload_compressed = data[HEADER_SIZE:]
    payload = decompress_zstd(payload_compressed)
    offset = 0
    codecs = []
    for _ in range(4):
        blob, offset = read_length_prefixed(payload, offset)
        codecs.append(pickle.loads(blob))
    streams = []
    for _ in range(4):
        blob, offset = read_length_prefixed(payload, offset)
        streams.append(blob)
    codec_x, codec_y, codec_z, codec_idx = codecs
    x_deltas = codec_x.decode(streams[0])
    y_deltas = codec_y.decode(streams[1])
    z_deltas = codec_z.decode(streams[2])
    index_deltas = codec_idx.decode(streams[3])

    def undelta(arr: List[int]) -> List[int]:
        out = [arr[0]]
        for i in range(1, len(arr)):
            out.append(out[-1] + arr[i])
        return out

    x_vals = undelta(x_deltas)
    y_vals = undelta(y_deltas)
    z_vals = undelta(z_deltas)
    index_vals = undelta(index_deltas)

    n_verts = len(x_vals)
    if info["mode"] == MODE_LOSSY:
        bbox = info["bbox"]
        xmin, xmax = bbox[0], bbox[1]
        ymin, ymax = bbox[2], bbox[3]
        zmin, zmax = bbox[4], bbox[5]
        max_val = (1 << info["quantization_bits"]) - 1
        scale_x = (xmax - xmin) / max_val if max_val else 0
        scale_y = (ymax - ymin) / max_val if max_val else 0
        scale_z = (zmax - zmin) / max_val if max_val else 0
        xs = np.array(x_vals, dtype=np.float64) * scale_x + xmin
        ys = np.array(y_vals, dtype=np.float64) * scale_y + ymin
        zs = np.array(z_vals, dtype=np.float64) * scale_z + zmin
        unique_vertices = np.column_stack([xs, ys, zs]).astype(np.float32)
    else:
        # Reinterpret int32 as float32
        arr = np.array([x_vals, y_vals, z_vals], dtype=np.int32).T
        unique_vertices = arr.view(np.float32).reshape(-1, 3)

    # Rebuild triangles: index_vals is flattened (tri_count * 3)
    tri_count = info["triangle_count"]
    if len(index_vals) != tri_count * 3:
        raise ValueError("Index count mismatch")
    triangles = np.array(index_vals, dtype=np.int32).reshape(tri_count, 3)

    # Compute normals from vertices (right-hand rule)
    verts_geom = unique_vertices[triangles]
    v0 = verts_geom[:, 0]
    v1 = verts_geom[:, 1]
    v2 = verts_geom[:, 2]
    e1 = v1 - v0
    e2 = v2 - v0
    normals = np.cross(e1, e2)
    nl = np.linalg.norm(normals, axis=1, keepdims=True)
    nl[nl == 0] = 1
    normals = (normals / nl).astype(np.float32)

    # Write binary STL
    with open(output_path, "wb") as f:
        f.write(b"\x00" * 80)
        f.write(struct.pack("<I", tri_count))
        for i in range(tri_count):
            f.write(struct.pack("<3f", *normals[i]))
            for j in range(3):
                idx = triangles[i, j]
                f.write(struct.pack("<3f", *unique_vertices[idx]))
            f.write(struct.pack("<H", 0))
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="STL compressor (TWSC)")
    parser.add_argument("--input", "-i", required=True, help="Input .stl file")
    parser.add_argument("--output", "-o", required=True, help="Output .twsc file")
    parser.add_argument("--mode", "-m", choices=["lossless", "lossy"], default="lossless")
    parser.add_argument("--bits", "-b", type=int, default=DEFAULT_QUANTIZATION_BITS, help="Quantization bits (lossy)")
    args = parser.parse_args()
    result = compress(args.input, args.output, mode=args.mode, bits=args.bits)
    print(f"Input file size (bytes): {result['input_size']}")
    print(f"Output file size (bytes): {result['output_size']}")
    print(f"Compression ratio (%): {result['compression_ratio_percent']}")
    print(f"Mode used: {result['mode']}")
    print(f"Triangle count: {result['triangle_count']}")
    print(f"Unique vertex count: {result['unique_vertex_count']}")


if __name__ == "__main__":
    main()
