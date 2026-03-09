import Link from "next/link";
import Logo from "./Logo";

export default function Navbar() {
  return (
    <nav className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/80 backdrop-blur-md dark:border-slate-700/80 dark:bg-slate-900/80">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link
          href="/"
          className="flex items-center gap-2 rounded-lg transition-opacity hover:opacity-90"
          aria-label="Byte Surgeons home"
        >
          <Logo className="h-9 w-9" />
          <span className="text-lg font-semibold tracking-tight text-slate-800 dark:text-slate-100">
            Byte Surgeons
          </span>
        </Link>
        <div className="flex items-center gap-4 text-sm">
          <a
            href="#upload"
            className="text-slate-600 transition-colors hover:text-teal-600 dark:text-slate-400 dark:hover:text-teal-400"
          >
            Upload
          </a>
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-600 transition-colors hover:text-teal-600 dark:text-slate-400 dark:hover:text-teal-400"
          >
            GitHub
          </a>
        </div>
      </div>
    </nav>
  );
}
