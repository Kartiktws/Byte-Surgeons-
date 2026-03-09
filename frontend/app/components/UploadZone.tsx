"use client";

import { ACCEPT, type FileKind } from "@/lib/api";

type Props = {
  file: File | null;
  fileKind: FileKind;
  isDragging: boolean;
  disabled?: boolean;
  onDrop: (e: React.DragEvent) => void;
  onDragOver: (e: React.DragEvent) => void;
  onDragLeave: (e: React.DragEvent) => void;
  onInputChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onClearFile: () => void;
};

export default function UploadZone({
  file,
  fileKind,
  isDragging,
  disabled = false,
  onDrop,
  onDragOver,
  onDragLeave,
  onInputChange,
  onClearFile,
}: Props) {
  return (
    <section
      id="upload"
      onDrop={disabled ? undefined : onDrop}
      onDragOver={disabled ? undefined : onDragOver}
      onDragLeave={disabled ? undefined : onDragLeave}
      aria-disabled={disabled}
      className={`
        relative rounded-2xl border-2 border-dashed p-10 text-center transition-all duration-300
        ${disabled ? "cursor-not-allowed opacity-60 pointer-events-none" : "cursor-pointer hover:shadow-[0_0_28px_rgba(13,148,136,0.35)] dark:hover:shadow-[0_0_28px_rgba(13,148,136,0.25)]"}
        ${isDragging && !disabled ? "scale-[1.01] border-teal-500 bg-teal-50/80 shadow-[0_0_28px_rgba(13,148,136,0.4)] dark:bg-teal-950/40 dark:shadow-[0_0_28px_rgba(13,148,136,0.3)]" : "border-slate-300 dark:border-slate-600 bg-white/90 shadow-sm dark:bg-slate-800/90"}
      `}
    >
      <input
        type="file"
        accept={ACCEPT}
        onChange={onInputChange}
        disabled={disabled}
        className="absolute inset-0 h-full w-full cursor-pointer opacity-0 disabled:pointer-events-none"
        aria-label="Upload file"
      />
      {!file ? (
        <div className="pointer-events-none animate-fade-in">
          <div className="mb-2 text-slate-400 dark:text-slate-500">
            <svg
              className="mx-auto h-12 w-12"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
            </svg>
          </div>
          <p className="text-sm font-medium text-slate-600 dark:text-slate-400">
            Drag and drop a file here, or click anywhere to browse
          </p>
          <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
            Supported: .dcm, .dcmz, .stl, .twsc
          </p>
        </div>
      ) : (
        <div className="relative z-10 flex flex-col items-center gap-2 animate-fade-in pointer-events-none">
          <p className="max-w-full truncate text-sm font-medium text-slate-800 dark:text-slate-200">
            {file.name}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {fileKind === "dcm" && "DICOM image"}
            {fileKind === "dcmz" && "Compressed DICOM"}
            {fileKind === "stl" && "STL mesh"}
            {fileKind === "twsc" && "Compressed STL"}
          </p>
          <span className="mt-2 pointer-events-auto">
            <button
              type="button"
              disabled={disabled}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                if (!disabled) onClearFile();
              }}
              className="cursor-pointer text-xs text-slate-500 underline transition-colors hover:text-teal-600 disabled:cursor-not-allowed disabled:opacity-70 dark:text-slate-400 dark:hover:text-teal-400"
            >
              Remove file
            </button>
          </span>
        </div>
      )}
    </section>
  );
}
