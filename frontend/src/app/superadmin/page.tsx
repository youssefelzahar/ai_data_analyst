"use client";

import { AppHeader } from "@/components/app-header";
import { AuthGuard } from "@/components/auth-guard";
import AdminManagement from "@/features/admin/admin-management";

export default function SuperadminPage() {
  return (
    <AuthGuard requireSuperadmin>
      <div className="min-h-screen">
        <AppHeader title="Superadmin — Admin Management" />
        <main className="mx-auto max-w-5xl px-6 py-8">
          <AdminManagement />
        </main>
      </div>
    </AuthGuard>
  );
}
