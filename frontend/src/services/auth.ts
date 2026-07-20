import { API_URL, request } from "@/services/api";
import {
  clearTokens,
  getRefreshToken,
  setTokens,
} from "@/lib/auth-storage";
import type { AuthUser, TokenResponse } from "@/types/auth";

export async function login(
  username: string,
  password: string,
): Promise<TokenResponse> {
  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) {
    let detail = "Invalid username or password.";
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // keep default
    }
    throw new Error(detail);
  }
  const tokens = (await response.json()) as TokenResponse;
  setTokens(tokens.access_token, tokens.refresh_token);
  return tokens;
}

export function getCurrentUser(): Promise<AuthUser> {
  return request<AuthUser>("/auth/me");
}

export async function logout(): Promise<void> {
  const refreshToken = getRefreshToken();
  try {
    if (refreshToken) {
      await request<void>("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    }
  } catch {
    // Even if the server call fails, clear local tokens below.
  } finally {
    clearTokens();
  }
}
