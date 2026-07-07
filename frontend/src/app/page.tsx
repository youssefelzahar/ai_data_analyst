"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getHealth } from "@/services/api";
import type { HealthResponse } from "@/types/health";

type ConnectionState =
  | { kind: "loading" }
  | { kind: "connected"; health: HealthResponse }
  | { kind: "error"; message: string };

export default function HomePage() {
  const [state, setState] = useState<ConnectionState>({ kind: "loading" });

  useEffect(() => {
    getHealth()
      .then((health) => setState({ kind: "connected", health }))
      .catch((error: Error) =>
        setState({ kind: "error", message: error.message }),
      );
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 p-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight">AI Data Analyst</h1>
        <p className="mt-2 text-slate-400">
          Upload datasets and analyze them with natural language.
        </p>
      </div>

      <section className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900 p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Backend status
        </h2>

        {state.kind === "loading" && (
          <p className="mt-3 text-slate-300">Checking…</p>
        )}

        {state.kind === "connected" && (
          <dl className="mt-3 space-y-1 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-400">Status</dt>
              <dd className="font-medium text-emerald-400">
                {state.health.status}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">App</dt>
              <dd>{state.health.app}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Version</dt>
              <dd>{state.health.version}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Environment</dt>
              <dd>{state.health.environment}</dd>
            </div>
          </dl>
        )}

        {state.kind === "error" && (
          <p className="mt-3 text-sm text-red-400">
            Cannot reach the backend: {state.message}
          </p>
        )}
      </section>

      <Link
        href="/data-sources"
        className="rounded-lg bg-sky-600 px-5 py-2.5 text-sm font-medium hover:bg-sky-500"
      >
        Manage Data Sources →
      </Link>
    </main>
  );
}
