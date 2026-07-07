import type { HealthResponse } from "@/types/health";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
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