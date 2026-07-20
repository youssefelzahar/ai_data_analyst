"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/context/auth-context";

import { landingPathForRole } from "@/lib/roles";

interface AuthGuardProps {
  children: React.ReactNode;
  /** When true, only admins may view; others are sent to their landing page. */
  requireAdmin?: boolean;
  /** When true, only the superadmin may view. */
  requireSuperadmin?: boolean;
}

/**
 * Client-side route protection. App Router middleware can't read the
 * localStorage-held token, so pages gate on the auth context instead.
 */
export function AuthGuard({
  children,
  requireAdmin = false,
  requireSuperadmin = false,
}: AuthGuardProps) {
  const { user, isLoading, isAuthenticated } = useAuth();
  const router = useRouter();

  const denied =
    (requireAdmin && user?.role !== "admin") ||
    (requireSuperadmin && user?.role !== "superadmin");

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (denied && user) {
      router.replace(landingPathForRole(user.role));
    }
  }, [isLoading, isAuthenticated, denied, user, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        Loading…
      </div>
    );
  }

  if (!isAuthenticated || denied) {
    return null;
  }

  return <>{children}</>;
}
