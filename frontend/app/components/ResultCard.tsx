"use client";

import { API_BASE, downloadCompressedFile, type ResultState } from "@/lib/api";

type Props = {
  result: ResultState;
  onDownloadError: (message: string) => void;
};

export default function ResultCard({ result, onDownloadError }: Props) {
  const handleDownload = async () => {
    if (!result.compressedOutputFile) return;
    try {
      await downloadCompressedFile(
        API_BASE,
        result.compressedOutputFile,
        result.compressedOutputFile.toLowerCase().endsWith(".twsc") ? "twsc" : "dcmz"
      );
    } catch {
      onDownloadError("Failed to download compressed file");
    }
  };

  return (
    <section className="mt-6 animate-fade-in overflow-hidden rounded-xl border border-slate-200 bg-white/95 shadow-md dark:border-slate-700 dark:bg-slate-800/95">
      <div className="border-b border-slate-200 bg-gradient-to-r from-teal-500/15 to-indigo-500/15 px-4 py-3 dark:border-slate-700">
        {result.sizeReducedPercent !== null && (
          <p className="text-sm font-semibold text-teal-800 dark:text-teal-200">
            Size reduced: {result.sizeReducedPercent.toFixed(1)}%
          </p>
        )}
        {result.type === "decompress" &&
          result.compressedSizeKb != null &&
          result.decompressedSizeKb != null && (
            <p className="text-sm font-semibold text-teal-800 dark:text-teal-200">
              Compressed: {result.compressedSizeKb} KB → Decompressed: {result.decompressedSizeKb}{" "}
              KB (100% recovery)
            </p>
          )}
        <p className="mt-0.5 text-xs text-teal-600 dark:text-teal-400">{result.message}</p>
      </div>
      {result.compressedOutputFile && (
        <div className="border-b border-slate-200 px-4 py-3 dark:border-slate-700">
          <button
            type="button"
            onClick={handleDownload}
            className="rounded-lg bg-gradient-to-r from-teal-600 to-indigo-600 px-4 py-2 text-sm font-medium text-white shadow transition hover:from-teal-500 hover:to-indigo-500"
          >
            Download compressed file ({result.compressedOutputFile})
          </button>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            Upload this file above and choose &quot;Decompress DICOM&quot; or &quot;Decompress
            STL&quot; to recover the original.
          </p>
        </div>
      )}
      {result.details && (
        <div className="space-y-1 px-4 py-3 text-sm text-slate-600 dark:text-slate-400">
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
          {result.downloadFilename && <p>Downloaded: {result.downloadFilename}</p>}
        </div>
      )}
    </section>
  );
}
