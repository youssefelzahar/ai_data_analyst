import type { UserRole } from "@/types/auth";

/** The page a user lands on after login, based on their role. */
export function landingPathForRole(role: UserRole): string {
  if (role === "superadmin") return "/superadmin";
  if (role === "admin") return "/admin";
  return "/";
}
