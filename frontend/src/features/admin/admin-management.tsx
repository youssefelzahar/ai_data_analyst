"use client";

import { useCallback, useEffect, useState } from "react";

import { createAdmin, deactivateAdmin, listAdmins } from "@/services/users";
import type { ManagedUser } from "@/types/auth";

const inputClassName =
  "w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 " +
  "placeholder:text-slate-500 focus:border-sky-500 focus:outline-none";

interface FormState {
  username: string;
  password: string;
  companyName: string;
  fullName: string;
}

const EMPTY_FORM: FormState = {
  username: "",
  password: "",
  companyName: "",
  fullName: "",
};

export default function AdminManagement() {
  const [admins, setAdmins] = useState<ManagedUser[]>([]);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [feedback, setFeedback] = useState<{ kind: "ok" | "error"; message: string } | null>(
    null,
  );
  const [isSubmitting, setIsSubmitting] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setAdmins(await listAdmins());
    } catch (error) {
      setFeedback({
        kind: "error",
        message: error instanceof Error ? error.message : "Failed to load admins.",
      });
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    setFeedback(null);
    setIsSubmitting(true);
    try {
      await createAdmin({
        username: form.username.trim(),
        password: form.password,
        company_name: form.companyName.trim(),
        full_name: form.fullName.trim() || null,
      });
      setForm(EMPTY_FORM);
      setFeedback({ kind: "ok", message: "Admin created." });
      await refresh();
    } catch (error) {
      setFeedback({
        kind: "error",
        message: error instanceof Error ? error.message : "Failed to create admin.",
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeactivate(admin: ManagedUser) {
    setFeedback(null);
    try {
      await deactivateAdmin(admin.id);
      await refresh();
    } catch (error) {
      setFeedback({
        kind: "error",
        message: error instanceof Error ? error.message : "Failed to update admin.",
      });
    }
  }

  return (
    <div className="space-y-8">
      <section className="rounded-xl border border-slate-800 bg-slate-900 p-6">
        <h2 className="text-lg font-semibold text-slate-100">Add admin</h2>
        <p className="mt-1 text-sm text-slate-400">
          Each admin gets their own company. Users that admin later creates
          belong to that company.
        </p>
        <form onSubmit={handleCreate} className="mt-4 grid gap-4 sm:grid-cols-2">
          <input
            className={inputClassName}
            placeholder="Admin username"
            value={form.username}
            onChange={(event) => setForm({ ...form, username: event.target.value })}
            required
          />
          <input
            className={inputClassName}
            type="password"
            placeholder="Password (min 6 chars)"
            value={form.password}
            onChange={(event) => setForm({ ...form, password: event.target.value })}
            required
          />
          <input
            className={inputClassName}
            placeholder="Company name"
            value={form.companyName}
            onChange={(event) => setForm({ ...form, companyName: event.target.value })}
            required
          />
          <input
            className={inputClassName}
            placeholder="Full name (optional)"
            value={form.fullName}
            onChange={(event) => setForm({ ...form, fullName: event.target.value })}
          />
          <div className="sm:col-span-2">
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-500 disabled:opacity-60"
            >
              {isSubmitting ? "Creating…" : "Create admin"}
            </button>
          </div>
        </form>
        {feedback && (
          <p
            className={`mt-4 rounded-lg border px-3 py-2 text-sm ${
              feedback.kind === "ok"
                ? "border-emerald-800 bg-emerald-950/40 text-emerald-300"
                : "border-red-800 bg-red-950/40 text-red-300"
            }`}
          >
            {feedback.message}
          </p>
        )}
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900 p-6">
        <h2 className="text-lg font-semibold text-slate-100">Admins</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-slate-400">
              <tr className="border-b border-slate-800">
                <th className="py-2 pr-4">Username</th>
                <th className="py-2 pr-4">Company</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Actions</th>
              </tr>
            </thead>
            <tbody>
              {admins.map((admin) => (
                <tr key={admin.id} className="border-b border-slate-800/60">
                  <td className="py-2 pr-4 text-slate-200">{admin.username}</td>
                  <td className="py-2 pr-4 text-slate-300">{admin.company_name}</td>
                  <td className="py-2 pr-4">
                    <span className={admin.is_active ? "text-emerald-400" : "text-slate-500"}>
                      {admin.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="py-2 pr-4">
                    {admin.is_active && (
                      <button
                        onClick={() => handleDeactivate(admin)}
                        className="rounded-md border border-slate-700 px-2 py-1 text-xs text-slate-300 transition hover:border-slate-500"
                      >
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {admins.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-4 text-center text-slate-500">
                    No admins yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
