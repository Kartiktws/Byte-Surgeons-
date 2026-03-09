"use client";

export default function ExplainerSection() {
  return (
    <section className="mx-auto max-w-4xl px-4 py-12" aria-labelledby="about-formats">
      <h2 id="about-formats" className="mb-8 text-center text-xl font-semibold text-slate-800 dark:text-slate-100">
        About the file formats
      </h2>
      <div className="grid gap-10 md:grid-cols-2">
        {/* DICOM */}
        <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white/90 shadow-sm dark:border-slate-700 dark:bg-slate-800/90">
          <div className="aspect-video w-full bg-gradient-to-br from-teal-100 to-slate-100 dark:from-teal-950/50 dark:to-slate-900 flex items-center justify-center p-4">
            <div className="flex flex-col items-center gap-2 text-teal-700 dark:text-teal-300">
              <svg className="h-16 w-16 opacity-80" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span className="text-xs font-medium uppercase tracking-wider">Medical imaging</span>
            </div>
          </div>
          <div className="p-5">
            <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100">DICOM</h3>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
              <strong>Digital Imaging and Communications in Medicine</strong> — the international standard for medical image storage and transmission. Used in radiology, CT, MRI, ultrasound, and more.
            </p>
            <ul className="mt-3 space-y-1 text-xs text-slate-500 dark:text-slate-400">
              <li>• Single file = image + patient/study metadata</li>
              <li>• Supports 2D and multi-frame (3D) images</li>
              <li>• Enables digital workflows across devices and vendors</li>
            </ul>
          </div>
        </article>

        {/* STL */}
        <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white/90 shadow-sm dark:border-slate-700 dark:bg-slate-800/90">
          <div className="aspect-video w-full bg-gradient-to-br from-indigo-100 to-slate-100 dark:from-indigo-950/50 dark:to-slate-900 flex items-center justify-center p-4">
            <div className="flex flex-col items-center gap-2 text-indigo-700 dark:text-indigo-300">
              <svg className="h-16 w-16 opacity-80" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
              </svg>
              <span className="text-xs font-medium uppercase tracking-wider">3D mesh</span>
            </div>
          </div>
          <div className="p-5">
            <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100">STL</h3>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
              <strong>Stereolithography</strong> — the standard format for 3D printing. Represents surfaces as triangulated meshes (vertices and normals). ASCII or binary encoding.
            </p>
            <ul className="mt-3 space-y-1 text-xs text-slate-500 dark:text-slate-400">
              <li>• Geometry only (no color or texture in classic STL)</li>
              <li>• Universal support in slicers and 3D printers</li>
              <li>• Ideal for single-material additive manufacturing</li>
            </ul>
          </div>
        </article>
      </div>
    </section>
  );
}
