export default function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="mt-auto border-t border-slate-200/80 bg-white/60 backdrop-blur-sm dark:border-slate-700/80 dark:bg-slate-900/60">
      <div className="mx-auto max-w-6xl px-4 py-6">
        <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            © {year} Byte Surgeons. Lossless DICOM & STL compression.
          </p>
          <div className="flex gap-6 text-sm">
            <a
              href="#upload"
              className="text-slate-500 transition-colors hover:text-teal-600 dark:text-slate-400 dark:hover:text-teal-400"
            >
              Upload
            </a>
            <a
              href="#"
              className="text-slate-500 transition-colors hover:text-teal-600 dark:text-slate-400 dark:hover:text-teal-400"
            >
              API
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
