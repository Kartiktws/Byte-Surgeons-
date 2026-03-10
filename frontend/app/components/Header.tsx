"use client";

import { useRef, useEffect, useState } from "react";
import Image from "next/image";
import Logo from "./Logo";

const COLLABORATORS = [
  { name: "Avani Choudhary", image: "/collaborators/avani.jpg" },
  { name: "Kartik Sarda", image: "/collaborators/kartik.jpg" },
  { name: "Sanket Swaroop", image: "/collaborators/sanket.jpg" },
];

export default function Header() {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  return (
    <header className="sticky top-0 z-50 flex items-center justify-between border-b border-slate-200/40 bg-white/20 px-4 py-3 backdrop-blur-md dark:border-slate-600/30 dark:bg-slate-900/25">
      <div className="flex items-center gap-2">
        <Logo className="h-10 w-10" />
        <h1 className="text-xl font-bold tracking-tight text-slate-800 dark:text-slate-100 sm:text-2xl">
          Byte Surgeons
        </h1>
      </div>

      <div className="relative" ref={menuRef}>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
          aria-expanded={open}
          aria-haspopup="true"
        >
          Collaborators
        </button>

        {open && (
          <div className="absolute right-0 top-full mt-1 w-72 rounded-xl border border-slate-200 bg-white py-3 shadow-lg dark:border-slate-700 dark:bg-slate-800">
            <p className="mb-3 px-4 text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
              Team
            </p>
            <ul className="space-y-1">
              {COLLABORATORS.map((person) => (
                <li key={person.name}>
                  <div className="flex items-center gap-3 px-4 py-2 hover:bg-slate-50 dark:hover:bg-slate-700/50">
                    <div className="relative h-10 w-10 shrink-0 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-600">
                      <Image
                        src={person.image}
                        alt={person.name}
                        fill
                        className="object-cover"
                        sizes="40px"
                      />
                    </div>
                    <span className="text-sm font-medium text-slate-800 dark:text-slate-200">
                      {person.name}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </header>
  );
}
