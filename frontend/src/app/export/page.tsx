"use client";

import Link from "next/link";
import ExportPanel from "@/features/export/export-panel";

export default function ExportHubPage() {
  return (
    <main className="mx-auto max-w-6xl p-8">
      <Link href="/" className="text-sm text-slate-500 hover:text-slate-300">
        ← Home
      </Link>
      <h1 className="mt-2 text-3xl font-bold tracking-tight">Report &amp; Export</h1>
      <p className="mt-1 text-slate-400">
        Pick a data source, optionally choose a cleaned version, and export a professional report
        to PDF, Excel, or Power BI.
      </p>

      <div className="mt-6">
        <ExportPanel />
      </div>
    </main>
  );
}
