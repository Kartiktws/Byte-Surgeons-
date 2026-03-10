"use client";

import type { FileKind, CompressionMode } from "@/lib/api";

type Props = {
  fileKind: FileKind;
  disabled: boolean;
  compressionMode: CompressionMode;
  onCompressionModeChange: (mode: CompressionMode) => void;
  onCompressDicom: () => void;
  onDecompressDicom: () => void;
  onCompressStl: () => void;
  onDecompressStl: () => void;
};

const btnClass =
  "rounded-xl px-5 py-2.5 text-sm font-medium text-white shadow-md transition-all hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-50 bg-gradient-to-r from-teal-600 to-indigo-600 hover:from-teal-500 hover:to-indigo-500";

const radioClass =
  "cursor-pointer accent-teal-600 text-slate-700 dark:text-slate-300";

export default function ActionButtons({
  fileKind,
  disabled,
  compressionMode,
  onCompressionModeChange,
  onCompressDicom,
  onDecompressDicom,
  onCompressStl,
  onDecompressStl,
}: Props) {
  if (!fileKind) return null;

  const showCompressionMode = fileKind === "dcm" || fileKind === "stl";

  return (
    <section className="mt-6 space-y-4">
      {showCompressionMode && (
        <div className="flex flex-wrap items-center gap-4 rounded-lg border border-slate-200 bg-slate-50/80 px-4 py-3 dark:border-slate-700 dark:bg-slate-800/50">
          <span className="text-sm font-medium text-slate-600 dark:text-slate-400">
            Compression:
          </span>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="compression-mode"
              checked={compressionMode === "lossless"}
              onChange={() => onCompressionModeChange("lossless")}
              className={radioClass}
            />
            <span className="text-sm">Lossless</span>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="compression-mode"
              checked={compressionMode === "lossy"}
              onChange={() => onCompressionModeChange("lossy")}
              className={radioClass}
            />
            <span className="text-sm">Lossy</span>
          </label>
        </div>
      )}
      <div className="flex flex-wrap gap-3">
        {fileKind === "dcm" && (
          <button type="button" disabled={disabled} onClick={onCompressDicom} className={btnClass}>
            Compress DICOM ({compressionMode})
          </button>
        )}
        {fileKind === "dcmz" && (
          <button type="button" disabled={disabled} onClick={onDecompressDicom} className={btnClass}>
            Decompress DICOM
          </button>
        )}
        {fileKind === "stl" && (
          <button type="button" disabled={disabled} onClick={onCompressStl} className={btnClass}>
            Compress STL ({compressionMode})
          </button>
        )}
        {fileKind === "twsc" && (
          <button type="button" disabled={disabled} onClick={onDecompressStl} className={btnClass}>
            Decompress STL
          </button>
        )}
      </div>
    </section>
  );
}
