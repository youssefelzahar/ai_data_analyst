import { request } from "@/services/api";
import type {
  CreateAdminRequest,
  CreateUserRequest,
  ManagedUser,
  UpdateUserRequest,
} from "@/types/auth";

export function listUsers(): Promise<ManagedUser[]> {
  return request<ManagedUser[]>("/users");
}

export function createUser(payload: CreateUserRequest): Promise<ManagedUser> {
  return request<ManagedUser>("/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateUser(
  userId: string,
  payload: UpdateUserRequest,
): Promise<ManagedUser> {
  return request<ManagedUser>(`/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deactivateUser(userId: string): Promise<ManagedUser> {
  return request<ManagedUser>(`/users/${userId}`, { method: "DELETE" });
}

// --- Superadmin: manage admins (each with their own company) ---

export function listAdmins(): Promise<ManagedUser[]> {
  return request<ManagedUser[]>("/superadmin/admins");
}

export function createAdmin(payload: CreateAdminRequest): Promise<ManagedUser> {
  return request<ManagedUser>("/superadmin/admins", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deactivateAdmin(adminId: string): Promise<ManagedUser> {
  return request<ManagedUser>(`/superadmin/admins/${adminId}`, {
    method: "DELETE",
  });
}
