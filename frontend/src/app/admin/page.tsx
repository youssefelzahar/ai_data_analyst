"use client";

import Link from "next/link";

import { AppHeader } from "@/components/app-header";
import { AuthGuard } from "@/components/auth-guard";

const ADMIN_SECTIONS = [
  {
    href: "/admin/users",
    title: "User Management",
    description: "Create users, assign roles, and deactivate accounts.",
  },
  {
    href: "/data-sources",
    title: "Data Source Management",
    description: "Upload datasets and register data sources.",
  },
 
  {
    href: "/export",
    title: "Export Report",
    description: "Generate PDF, Excel, and Power BI reports.",
  },
  {
    href: "/",
    title: "AI Chat",
    description: "Open the conversational analyst workspace.",
  },
];

export default function AdminDashboardPage() {
  return (
    <AuthGuard requireAdmin>
      <div className="min-h-screen">
        <AppHeader title="Admin Dashboard" />
        <main className="mx-auto max-w-5xl px-6 py-8">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {ADMIN_SECTIONS.map((section) => (
              <Link
                key={`${section.title}-${section.href}`}
                href={section.href}
                className="rounded-xl border border-slate-800 bg-slate-900 p-5 transition hover:border-sky-600"
              >
                <h2 className="font-semibold text-slate-100">{section.title}</h2>
                <p className="mt-1 text-sm text-slate-400">{section.description}</p>
              </Link>
            ))}
          </div>
        </main>
      </div>
    </AuthGuard>
  );
}
