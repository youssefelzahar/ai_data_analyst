"use client";

import { AppHeader } from "@/components/app-header";
import { AuthGuard } from "@/components/auth-guard";
import UserManagement from "@/features/admin/user-management";

export default function AdminUsersPage() {
  return (
    <AuthGuard requireAdmin>
      <div className="min-h-screen">
        <AppHeader
          title="User Management"
          links={[{ href: "/admin", label: "← Admin" }]}
        />
        <main className="mx-auto max-w-5xl px-6 py-8">
          <UserManagement />
        </main>
      </div>
    </AuthGuard>
  );
}
