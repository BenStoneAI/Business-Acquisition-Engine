import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { setTenantId } from "../tenant";

const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

export function HandoffPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = params.get("token")?.trim();
    if (!token) {
      setError("Missing handoff token. Open Acquisition Radar from the Aptria Customer Portal.");
      return;
    }
    let cancelled = false;
    (async () => {
      const res = await fetch(`${API_BASE.replace(/\/$/, "")}/auth/portal-handoff`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ token }),
      });
      const body = (await res.json().catch(() => ({}))) as { tenant_id?: string; detail?: string };
      if (cancelled) return;
      if (!res.ok || !body.tenant_id) {
        setError(body.detail ?? "Handoff failed. Sign in at portal.aptria.net and try again.");
        return;
      }
      setTenantId(body.tenant_id);
      navigate("/", { replace: true });
    })().catch(() => {
      if (!cancelled) setError("Could not reach Acquisition Radar.");
    });
    return () => {
      cancelled = true;
    };
  }, [params, navigate]);

  return (
    <div>
      <h1>Acquisition Radar</h1>
      {error ? <p role="alert">{error}</p> : <p>Signing you in…</p>}
    </div>
  );
}
