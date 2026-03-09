"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type FileKind = "dcm" | "dcmz" | "stl" | "twsc" | null;

const ACCEPT = ".dcm,.dcmz,.stl,.twsc";
const LOADING_MESSAGES = [
  "Reading your file…",
  "Processing data…",
  "Applying compression…",
  "Almost there…",
  "Finalizing…",
];

type CompressResult = {
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

function getFileKind(file: File): FileKind {
  const name = (file.name || "").toLowerCase();
  if (name.endsWith(".dcm")) return "dcm";
  if (name.endsWith(".dcmz")) return "dcmz";
  if (name.endsWith(".stl")) return "stl";
  if (name.endsWith(".twsc")) return "twsc";
  return null;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

async function downloadCompressedFile(apiBase: string, filename: string, kind: "dcmz" | "twsc") {
  const path = kind === "dcmz"
    ? `${apiBase}/download/compressed/${encodeURIComponent(filename)}`
    : `${apiBase}/download/stl_compressed/${encodeURIComponent(filename)}`;
  const res = await fetch(path);
  if (!res.ok) throw new Error("Download failed");
  const blob = await res.blob();
  downloadBlob(blob, filename);
}

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [fileKind, setFileKind] = useState<FileKind>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMessageIndex, setLoadingMessageIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    type: "compress" | "decompress";
    /** Size reduced as % of original (compress only). Null for decompress. */
    sizeReducedPercent: number | null;
    message: string;
    details?: CompressResult;
    downloadFilename?: string;
    /** For compress: output filename for download link. For decompress: sizes for ratio. */
    compressedOutputFile?: string;
    compressedSizeKb?: number;
    decompressedSizeKb?: number;
  } | null>(null);

  const resetResult = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  const handleFile = useCallback((f: File | null) => {
    setResult(null);
    setError(null);
    if (!f) {
      setFile(null);
      setFileKind(null);
      return;
    }
    const kind = getFileKind(f);
    if (!kind) {
      setError("Unsupported file. Use .dcm, .dcmz, .stl, or .twsc");
      setFile(null);
      setFileKind(null);
      return;
    }
    setError(null);
    setFile(f);
    setFileKind(kind);
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const f = e.dataTransfer.files?.[0];
      if (f) handleFile(f);
    },
    [handleFile]
  );

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      handleFile(f ?? null);
      e.target.value = "";
    },
    [handleFile]
  );

  const clearFile = useCallback(() => {
    setFile(null);
    setFileKind(null);
    setResult(null);
    setError(null);
  }, []);

  // Cycle loading message while request is in flight
  useEffect(() => {
    if (!loading) return;
    const id = setInterval(() => {
      setLoadingMessageIndex((i) => (i + 1) % LOADING_MESSAGES.length);
    }, 1600);
    return () => clearInterval(id);
  }, [loading]);

  const runCompressDicom = useCallback(async () => {
    if (!file || fileKind !== "dcm") return;
    setLoading(true);
    setError(null);
    setResult(null);
    setLoadingMessageIndex(0);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE}/compress`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        const msg = Array.isArray(err.detail) ? err.detail[0]?.msg ?? res.statusText : (err.detail ?? "Compression failed");
        throw new Error(typeof msg === "string" ? msg : "Compression failed");
      }
      const data: CompressResult = await res.json();
      const sizeReduced = data.compression_ratio_percent ?? 0;
      setResult({
        type: "compress",
        sizeReducedPercent: sizeReduced,
        message: "Lossless compression complete. Download the compressed file below, then upload it here to decompress.",
        details: data,
        compressedOutputFile: data.output_file,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Compression failed");
    } finally {
      setLoading(false);
    }
  }, [file, fileKind]);

  const runDecompressDicom = useCallback(async () => {
    if (!file || fileKind !== "dcmz") return;
    setLoading(true);
    setError(null);
    setResult(null);
    setLoadingMessageIndex(0);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE}/decompress`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        const msg = Array.isArray(err.detail) ? err.detail[0]?.msg ?? res.statusText : (err.detail ?? "Decompression failed");
        throw new Error(typeof msg === "string" ? msg : "Decompression failed");
      }
      const blob = await res.blob();
      const disp = res.headers.get("content-disposition");
      const match = disp?.match(/filename="?([^";]+)"?/);
      const filename = match?.[1] ?? "recovered.dcm";
      downloadBlob(blob, filename);
      const compressedKb = Math.round((file.size / 1024) * 100) / 100;
      const decompressedKb = Math.round((blob.size / 1024) * 100) / 100;
      setResult({
        type: "decompress",
        sizeReducedPercent: null,
        message: "Lossless recovery complete. File downloaded.",
        downloadFilename: filename,
        compressedSizeKb: compressedKb,
        decompressedSizeKb: decompressedKb,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Decompression failed");
    } finally {
      setLoading(false);
    }
  }, [file, fileKind]);

  const runCompressStl = useCallback(async () => {
    if (!file || fileKind !== "stl") return;
    setLoading(true);
    setError(null);
    setResult(null);
    setLoadingMessageIndex(0);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("mode", "lossless");
      form.append("bits", "12");
      const res = await fetch(`${API_BASE}/stl/compress`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        const msg = Array.isArray(err.detail) ? err.detail[0]?.msg ?? res.statusText : (err.detail ?? "Compression failed");
        throw new Error(typeof msg === "string" ? msg : "Compression failed");
      }
      const data: CompressResult = await res.json();
      const sizeReduced = data.compression_ratio_percent ?? 0;
      setResult({
        type: "compress",
        sizeReducedPercent: sizeReduced,
        message: "STL compression complete. Download the compressed file below, then upload it here to decompress.",
        details: data,
        compressedOutputFile: data.output_file,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Compression failed");
    } finally {
      setLoading(false);
    }
  }, [file, fileKind]);

  const runDecompressStl = useCallback(async () => {
    if (!file || fileKind !== "twsc") return;
    setLoading(true);
    setError(null);
    setResult(null);
    setLoadingMessageIndex(0);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE}/stl/decompress`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        const msg = Array.isArray(err.detail) ? err.detail[0]?.msg ?? res.statusText : (err.detail ?? "Decompression failed");
        throw new Error(typeof msg === "string" ? msg : "Decompression failed");
      }
      const blob = await res.blob();
      const disp = res.headers.get("content-disposition");
      const match = disp?.match(/filename="?([^";]+)"?/);
      const filename = match?.[1] ?? "recovered.stl";
      downloadBlob(blob, filename);
      const compressedKb = Math.round((file.size / 1024) * 100) / 100;
      const decompressedKb = Math.round((blob.size / 1024) * 100) / 100;
      setResult({
        type: "decompress",
        sizeReducedPercent: null,
        message: "STL recovery complete. File downloaded.",
        downloadFilename: filename,
        compressedSizeKb: compressedKb,
        decompressedSizeKb: decompressedKb,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Decompression failed");
    } finally {
      setLoading(false);
    }
  }, [file, fileKind]);

  const loadingMessage = LOADING_MESSAGES[loadingMessageIndex % LOADING_MESSAGES.length];
  const canAct = !!file && !!fileKind && !loading;

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 font-sans">
      <div className="mx-auto max-w-2xl px-4 py-12">
        <header className="mb-10 text-center">
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">
            Byte Surgeons
          </h1>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            Compress or decompress DICOM and STL files
          </p>
        </header>

        {/* Drop zone */}
        <section
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          className={`
            relative rounded-2xl border-2 border-dashed p-10 text-center transition-colors
            ${isDragging ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-950/30" : "border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900"}
          `}
        >
          <input
            type="file"
            accept={ACCEPT}
            onChange={onInputChange}
            className={`absolute inset-0 w-full h-full opacity-0 cursor-pointer ${file ? "pointer-events-none" : ""}`}
            aria-label="Upload file"
          />
          {!file ? (
            <>
              <div className="text-zinc-400 dark:text-zinc-500 mb-2">
                <svg className="mx-auto h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
                Drag and drop a file here, or click to browse
              </p>
              <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">
                Supported: .dcm, .dcmz, .stl, .twsc
              </p>
            </>
          ) : (
            <div className="relative z-10 flex flex-col items-center gap-2">
              <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200 truncate max-w-full">
                {file.name}
              </p>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                {fileKind === "dcm" && "DICOM image"}
                {fileKind === "dcmz" && "Compressed DICOM"}
                {fileKind === "stl" && "STL mesh"}
                {fileKind === "twsc" && "Compressed STL"}
              </p>
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  clearFile();
                }}
                className="mt-2 text-xs text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 underline cursor-pointer"
              >
                Remove file
              </button>
            </div>
          )}
        </section>

        {error && (
          <div className="mt-4 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 px-4 py-3 text-sm text-red-800 dark:text-red-200">
            {error}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="mt-6 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 px-4 py-4 text-center">
            <div className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-amber-500 border-t-transparent mb-2" />
            <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
              {loadingMessage}
            </p>
            <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
              Please wait until the process finishes…
            </p>
          </div>
        )}

        {/* Action buttons — shown when file selected, disabled while loading */}
        {file && fileKind && (
          <section className="mt-6 flex flex-wrap gap-3">
            {fileKind === "dcm" && (
              <button
                type="button"
                disabled={!canAct}
                onClick={runCompressDicom}
                className="rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Compress DICOM
              </button>
            )}
            {fileKind === "dcmz" && (
              <button
                type="button"
                disabled={!canAct}
                onClick={runDecompressDicom}
                className="rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Decompress DICOM
              </button>
            )}
            {fileKind === "stl" && (
              <button
                type="button"
                disabled={!canAct}
                onClick={runCompressStl}
                className="rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Compress STL
              </button>
            )}
            {fileKind === "twsc" && (
              <button
                type="button"
                disabled={!canAct}
                onClick={runDecompressStl}
                className="rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Decompress STL
              </button>
            )}
          </section>
        )}

        {/* Result: size reduced % (compress) or size comparison (decompress) */}
        {result && !loading && (
          <section className="mt-6 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 overflow-hidden">
            <div className="bg-emerald-500/10 dark:bg-emerald-500/20 px-4 py-3 border-b border-zinc-200 dark:border-zinc-700">
              {result.sizeReducedPercent !== null && (
                <p className="text-sm font-medium text-emerald-800 dark:text-emerald-200">
                  Size reduced: {result.sizeReducedPercent.toFixed(1)}%
                </p>
              )}
              {result.type === "decompress" && result.compressedSizeKb != null && result.decompressedSizeKb != null && (
                <p className="text-sm font-medium text-emerald-800 dark:text-emerald-200">
                  Compressed: {result.compressedSizeKb} KB → Decompressed: {result.decompressedSizeKb} KB (100% recovery)
                </p>
              )}
              <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-0.5">
                {result.message}
              </p>
            </div>
            {result.compressedOutputFile && (
              <div className="px-4 py-3 border-b border-zinc-200 dark:border-zinc-700">
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      await downloadCompressedFile(
                        API_BASE,
                        result!.compressedOutputFile!,
                        result!.compressedOutputFile!.toLowerCase().endsWith(".twsc") ? "twsc" : "dcmz"
                      );
                    } catch {
                      setError("Failed to download compressed file");
                    }
                  }}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
                >
                  Download compressed file ({result.compressedOutputFile})
                </button>
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-2">
                  Upload this file above and choose &quot;Decompress DICOM&quot; or &quot;Decompress STL&quot; to recover the original.
                </p>
              </div>
            )}
            {result.details && (
              <div className="px-4 py-3 text-sm text-zinc-600 dark:text-zinc-400 space-y-1">
                {typeof result.details.compression_ratio_percent === "number" && (
                  <p>Compression ratio: {result.details.compression_ratio_percent.toFixed(1)}%</p>
                )}
                {typeof result.details.original_size_kb === "number" && (
                  <p>Original size: {result.details.original_size_kb} KB</p>
                )}
                {typeof result.details.compressed_size_kb === "number" && (
                  <p>Compressed size: {result.details.compressed_size_kb} KB</p>
                )}
                {result.details.output_file && !result.compressedOutputFile && (
                  <p>Output file: {result.details.output_file}</p>
                )}
                {result.downloadFilename && (
                  <p>Downloaded: {result.downloadFilename}</p>
                )}
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
