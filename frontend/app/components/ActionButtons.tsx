"use client";

import type { FileKind } from "@/lib/api";

type Props = {
  fileKind: FileKind;
  disabled: boolean;
  onCompressDicom: () => void;
  onDecompressDicom: () => void;
  onCompressStl: () => void;
  onDecompressStl: () => void;
};

const btnClass =
  "rounded-xl px-5 py-2.5 text-sm font-medium text-white shadow-md transition-all hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-50 bg-gradient-to-r from-teal-600 to-indigo-600 hover:from-teal-500 hover:to-indigo-500";

export default function ActionButtons({
  fileKind,
  disabled,
  onCompressDicom,
  onDecompressDicom,
  onCompressStl,
  onDecompressStl,
}: Props) {
  if (!fileKind) return null;

  return (
    <section className="mt-6 flex flex-wrap gap-3">
      {fileKind === "dcm" && (
        <button type="button" disabled={disabled} onClick={onCompressDicom} className={btnClass}>
          Compress DICOM
        </button>
      )}
      {fileKind === "dcmz" && (
        <button type="button" disabled={disabled} onClick={onDecompressDicom} className={btnClass}>
          Decompress DICOM
        </button>
      )}
      {fileKind === "stl" && (
        <button type="button" disabled={disabled} onClick={onCompressStl} className={btnClass}>
          Compress STL
        </button>
      )}
      {fileKind === "twsc" && (
        <button type="button" disabled={disabled} onClick={onDecompressStl} className={btnClass}>
          Decompress STL
        </button>
      )}
    </section>
  );
}
