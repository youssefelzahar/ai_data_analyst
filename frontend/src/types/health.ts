// Mirrors backend/app/schemas/health.py — keep in sync.
export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  environment: string;
}
