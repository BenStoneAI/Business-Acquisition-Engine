import { useEffect, useState } from "react";
import { api } from "../api";

export function DealsPage() {
  const [deals, setDeals] = useState<Array<{ id: string; business_name: string; stage: string }>>([]);
  useEffect(() => {
    api<{ deals: Array<{ id: string; business_name: string; stage: string }> }>("/customer/deals")
      .then((b) => setDeals(b.deals))
      .catch(() => setDeals([]));
  }, []);
  return (
    <section>
      <h1>Deals</h1>
      {deals.length === 0 ? <p>No deals yet. Mark an opportunity as interested.</p> : (
        <ul>{deals.map((d) => <li key={d.id}>{d.business_name} — {d.stage}</li>)}</ul>
      )}
    </section>
  );
}
