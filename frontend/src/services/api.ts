import type { HealthResponse } from "@/types/health";
import type { TokenResponse } from "@/types/auth";
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from "@/lib/auth-storage";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

/**
 * Build request headers, injecting the bearer token and preserving any
 * caller-provided headers. FormData bodies must not carry a JSON content-type.
 */
export function buildHeaders(init?: RequestInit): Headers {
  const headers = new Headers(init?.headers);
  const isFormData =
    typeof FormData !== "undefined" && init?.body instanceof FormData;
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const token = getAccessToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

let refreshInFlight: Promise<boolean> | null = null;

/**
 * Attempt a one-shot token refresh using the stored refresh token.
 * Concurrent callers share a single in-flight refresh. Returns whether a new
 * access token is now available.
 */
export async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      const response = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!response.ok) {
        clearTokens();
        return false;
      }
      const tokens = (await response.json()) as TokenResponse;
      setTokens(tokens.access_token, tokens.refresh_token);
      return true;
    } catch {
      clearTokens();
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

function redirectToLogin(): void {
  clearTokens();
  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    window.location.assign("/login");
  }
}

/**
 * Perform an authenticated fetch. On a 401 it transparently tries a single
 * token refresh and retries once; a persistent 401 clears the session and
 * redirects to the login page.
 */
export async function authorizedFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  let response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: buildHeaders(init),
  });

  if (response.status === 401 && getRefreshToken()) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      response = await fetch(`${API_URL}${path}`, {
        ...init,
        headers: buildHeaders(init),
      });
    }
  }

  if (response.status === 401) {
    redirectToLogin();
  }
  return response;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authorizedFetch(path, init);
  if (!response.ok) {
    const errorMessage = await extractErrorMessage(response);
    throw new Error(errorMessage);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

async function extractErrorMessage(response: Response): Promise<string> {
  try {
    const errorBody = (await response.json()) as { detail?: unknown };
    if (typeof errorBody.detail === "string") return errorBody.detail;
  } catch {
    // fall through to the generic message
  }
  return `API error ${response.status}: ${response.statusText}`;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}
