"use client";

import { useCallback, useEffect, useState } from "react";
import {
  LOADING_MESSAGES,
  getFileKind,
  compressDicom,
  decompressDicom,
  compressStl,
  decompressStl,
  type FileKind,
  type ResultState,
  type CompressionMode,
} from "@/lib/api";
import {
  ActionButtons,
  ErrorAlert,
  ExplainerSection,
  LoadingState,
  ResultCard,
  UploadZone,
} from "@/app/components";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [fileKind, setFileKind] = useState<FileKind>(null);
  const [compressionMode, setCompressionMode] = useState<CompressionMode>("lossless");
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMessageIndex, setLoadingMessageIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ResultState | null>(null);

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

  useEffect(() => {
    if (!loading) return;
    const id = setInterval(() => {
      setLoadingMessageIndex((i) => (i + 1) % LOADING_MESSAGES.length);
    }, 1600);
    return () => clearInterval(id);
  }, [loading]);

  const run = useCallback(
    async (fn: () => Promise<ResultState | { result: ResultState }>) => {
      setLoading(true);
      setError(null);
      setResult(null);
      setLoadingMessageIndex(0);
      try {
        const res = await fn();
        setResult("result" in res ? res.result : res);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Something went wrong");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const runCompressDicom = useCallback(() => {
    if (!file || fileKind !== "dcm") return;
    run(() => compressDicom(file, compressionMode));
  }, [file, fileKind, compressionMode, run]);

  const runDecompressDicom = useCallback(() => {
    if (!file || fileKind !== "dcmz") return;
    run(() => decompressDicom(file));
  }, [file, fileKind, run]);

  const runCompressStl = useCallback(() => {
    if (!file || fileKind !== "stl") return;
    run(() => compressStl(file, { mode: compressionMode }));
  }, [file, fileKind, compressionMode, run]);

  const runDecompressStl = useCallback(() => {
    if (!file || fileKind !== "twsc") return;
    run(() => decompressStl(file));
  }, [file, fileKind, run]);

  const loadingMessage = LOADING_MESSAGES[loadingMessageIndex % LOADING_MESSAGES.length];
  const canAct = !!file && !!fileKind && !loading;

  return (
    <div className="relative min-h-screen">
      <div className="mx-auto max-w-2xl px-4 py-10">
        <header className="mb-8 text-center">
          <h1 className="text-2xl font-bold tracking-tight text-slate-800 dark:text-slate-100">
            Compress or Decompress
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            DICOM and STL — lossless or lossy compression
          </p>
        </header>

        <UploadZone
          file={file}
          fileKind={fileKind}
          isDragging={isDragging}
          disabled={loading}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onInputChange={onInputChange}
          onClearFile={clearFile}
        />

        {error && <ErrorAlert message={error} />}

        {loading && <LoadingState message={loadingMessage} />}

        {file && fileKind && (
          <ActionButtons
            fileKind={fileKind}
            disabled={!canAct}
            compressionMode={compressionMode}
            onCompressionModeChange={setCompressionMode}
            onCompressDicom={runCompressDicom}
            onDecompressDicom={runDecompressDicom}
            onCompressStl={runCompressStl}
            onDecompressStl={runDecompressStl}
          />
        )}

        {result && !loading && (
          <ResultCard result={result} onDownloadError={setError} />
        )}
      </div>

      <ExplainerSection />
    </div>
  );
}
