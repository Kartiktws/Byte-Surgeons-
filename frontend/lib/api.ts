/**
 * API client and helpers for Byte Surgeons backend.
 */

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type FileKind = "dcm" | "dcmz" | "stl" | "twsc" | null;

export const ACCEPT = ".dcm,.dcmz,.stl,.twsc";

export const LOADING_MESSAGES = [
  "Reading your file…",
  "Processing data…",
  "Applying compression…",
  "Almost there…",
  "Finalizing…",
];

export type CompressResult = {
  status: string;
  compression_ratio_percent?: number;
  original_size_kb?: number;
  compressed_size_kb?: number;
  metadata_compression_percent?: number;
  num_frames?: number;
  output_file?: string;
  mode?: string;
  triangle_count?: number;
  original_size_bytes?: number;
  compressed_size_bytes?: number;
  [key: string]: unknown;
};

export type ResultState = {
  type: "compress" | "decompress";
  sizeReducedPercent: number | null;
  message: string;
  details?: CompressResult;
  downloadFilename?: string;
  compressedOutputFile?: string;
  compressedSizeKb?: number;
  decompressedSizeKb?: number;
};

export function getFileKind(file: File): FileKind {
  const name = (file.name || "").toLowerCase();
  if (name.endsWith(".dcm")) return "dcm";
  if (name.endsWith(".dcmz")) return "dcmz";
  if (name.endsWith(".stl")) return "stl";
  if (name.endsWith(".twsc")) return "twsc";
  return null;
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function downloadCompressedFile(
  apiBase: string,
  filename: string,
  kind: "dcmz" | "twsc"
) {
  const path =
    kind === "dcmz"
      ? `${apiBase}/download/compressed/${encodeURIComponent(filename)}`
      : `${apiBase}/download/stl_compressed/${encodeURIComponent(filename)}`;
  const res = await fetch(path);
  if (!res.ok) throw new Error("Download failed");
  const blob = await res.blob();
  downloadBlob(blob, filename);
}

function getErrorMessage(err: unknown, fallback: string): string {
  try {
    const detail = (err as { detail?: string | unknown[] }).detail;
    if (Array.isArray(detail)) return (detail[0] as { msg?: string })?.msg ?? fallback;
    return typeof detail === "string" ? detail : fallback;
  } catch {
    return fallback;
  }
}

export type CompressionMode = "lossless" | "lossy";

export async function compressDicom(
  file: File,
  mode: CompressionMode = "lossless"
): Promise<{ data: CompressResult; result: ResultState }> {
  if (mode === "lossy") return compressDicomLossy(file);
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/compress`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(getErrorMessage(err, "Compression failed"));
  }
  const data: CompressResult = await res.json();
  const sizeReduced = data.compression_ratio_percent ?? 0;
  return {
    data,
    result: {
      type: "compress",
      sizeReducedPercent: sizeReduced,
      message:
        "Lossless compression complete. Download the compressed file below, then upload it here to decompress.",
      details: data,
      compressedOutputFile: data.output_file,
    },
  };
}

export async function compressDicomLossy(
  file: File,
  options?: { Q?: number; threshold_pct?: number }
): Promise<{ data: CompressResult; result: ResultState }> {
  const form = new FormData();
  form.append("file", file);
  if (options?.Q != null) form.append("Q", String(options.Q));
  if (options?.threshold_pct != null) form.append("threshold_pct", String(options.threshold_pct));
  const res = await fetch(`${API_BASE}/compress/lossy`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(getErrorMessage(err, "Lossy compression failed"));
  }
  const data: CompressResult = await res.json();
  const sizeReduced = data.compression_ratio_percent ?? 0;
  return {
    data,
    result: {
      type: "compress",
      sizeReducedPercent: sizeReduced,
      message:
        "Lossy compression complete. Download the compressed file below, then upload it here to decompress.",
      details: data,
      compressedOutputFile: data.output_file,
    },
  };
}

export async function decompressDicom(file: File): Promise<ResultState> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/decompress`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(getErrorMessage(err, "Decompression failed"));
  }
  const blob = await res.blob();
  const disp = res.headers.get("content-disposition");
  const match = disp?.match(/filename="?([^";]+)"?/);
  const filename = match?.[1] ?? "recovered.dcm";
  downloadBlob(blob, filename);
  return {
    type: "decompress",
    sizeReducedPercent: null,
    message: "Lossless recovery complete. File downloaded.",
    downloadFilename: filename,
    compressedSizeKb: Math.round((file.size / 1024) * 100) / 100,
    decompressedSizeKb: Math.round((blob.size / 1024) * 100) / 100,
  };
}

/** Quality for advanced STL lossy: high (70% tris), med (45%), low (25%). */
export type StlLossyQuality = "high" | "med" | "low";

export async function compressStl(
  file: File,
  options: { mode?: CompressionMode; bits?: number; quality_level?: StlLossyQuality } = {}
): Promise<{ data: CompressResult; result: ResultState }> {
  const { mode = "lossless", bits = 12, quality_level = "med" } = options;

  if (mode === "lossy") {
    const form = new FormData();
    form.append("file", file);
    form.append("quality_level", quality_level);
    const res = await fetch(`${API_BASE}/stl/compress/lossy`, { method: "POST", body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(getErrorMessage(err, "Lossy compression failed"));
    }
    const data: CompressResult = await res.json();
    return {
      data,
      result: {
        type: "compress",
        sizeReducedPercent: data.compression_ratio_percent ?? 0,
        message:
          "STL lossy compression complete (advanced). Download the compressed file below, then upload it here to decompress.",
        details: data,
        compressedOutputFile: data.output_file,
      },
    };
  }

  const form = new FormData();
  form.append("file", file);
  form.append("mode", "lossless");
  form.append("bits", String(bits));
  const res = await fetch(`${API_BASE}/stl/compress`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(getErrorMessage(err, "Compression failed"));
  }
  const data: CompressResult = await res.json();
  return {
    data,
    result: {
      type: "compress",
      sizeReducedPercent: data.compression_ratio_percent ?? 0,
      message:
        "STL lossless compression complete. Download the compressed file below, then upload it here to decompress.",
      details: data,
      compressedOutputFile: data.output_file,
    },
  };
}

export async function decompressStl(file: File): Promise<ResultState> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/stl/decompress`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(getErrorMessage(err, "Decompression failed"));
  }
  const blob = await res.blob();
  const disp = res.headers.get("content-disposition");
  const match = disp?.match(/filename="?([^";]+)"?/);
  const filename = match?.[1] ?? "recovered.stl";
  downloadBlob(blob, filename);
  return {
    type: "decompress",
    sizeReducedPercent: null,
    message: "STL recovery complete. File downloaded.",
    downloadFilename: filename,
    compressedSizeKb: Math.round((file.size / 1024) * 100) / 100,
    decompressedSizeKb: Math.round((blob.size / 1024) * 100) / 100,
  };
}
