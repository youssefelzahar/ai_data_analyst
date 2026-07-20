export type UserRole = "superadmin" | "admin" | "user";

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AuthUser {
  id: string;
  username: string;
  role: UserRole;
  company_id: string;
  company_name: string;
}

export interface ManagedUser {
  id: string;
  username: string;
  role: UserRole;
  full_name: string | null;
  is_active: boolean;
  company_id: string;
  company_name: string;
  created_at: string;
}

export interface CreateUserRequest {
  username: string;
  password: string;
  role: UserRole;
  full_name?: string | null;
}

export interface CreateAdminRequest {
  username: string;
  password: string;
  company_name: string;
  full_name?: string | null;
}

export interface UpdateUserRequest {
  password?: string;
  role?: UserRole;
  full_name?: string | null;
  is_active?: boolean;
}
