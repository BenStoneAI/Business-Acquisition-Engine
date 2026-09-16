const STORAGE_KEY = "radar_tenant_id";

export function getTenantId(): string | null {
  const fromEnv = (import.meta.env.VITE_TENANT_ID as string | undefined)?.trim();
  if (fromEnv) return fromEnv;
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(STORAGE_KEY)?.trim() || null;
}

export function setTenantId(tenantId: string): void {
  window.localStorage.setItem(STORAGE_KEY, tenantId.trim());
}
