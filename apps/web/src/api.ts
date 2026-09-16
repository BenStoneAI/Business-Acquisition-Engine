import { getTenantId } from "./tenant";

const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const tenantId = getTenantId();
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string> | undefined),
  };
  if (tenantId) headers["X-Tenant-Id"] = tenantId;
  if (init.body) headers["Content-Type"] = "application/json";
  const res = await fetch(`${API_BASE.replace(/\/$/, "")}${path}`, { ...init, headers });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError((body as { detail?: string }).detail ?? res.statusText, res.status);
  }
  return body as T;
}
