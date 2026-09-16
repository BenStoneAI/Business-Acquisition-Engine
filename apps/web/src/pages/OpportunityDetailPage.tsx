import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";

export function OpportunityDetailPage() {
  const { id } = useParams();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api<Record<string, unknown>>(`/customer/opportunities/${id}`)
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, [id]);

  if (error) return <p role="alert">{error}</p>;
  if (!data) return <p>Loading…</p>;
  const listing = data.listing as Record<string, string>;
  const maxOffer = data.max_offer as Record<string, string | number | null>;
  return (
    <section>
      <h1>{listing.business_name}</h1>
      <p>{listing.industry} · {listing.location}</p>
      <h2>Max offer constraints</h2>
      <ul>
        <li>SDE × multiple: {String(maxOffer.sde_multiple)}</li>
        <li>DSCR 1.75×: {String(maxOffer.dscr_1_75)}</li>
        <li>Cash-on-cash 25%: {String(maxOffer.cash_on_cash_25)}</li>
        <li>Payback &lt; 4 yrs: {String(maxOffer.payback_4yr)}</li>
        <li>Binding: {String(maxOffer.binding)}</li>
        <li>Max offer: {String(maxOffer.estimated_max_offer)}</li>
      </ul>
      <button type="button" onClick={() => api(`/customer/opportunities/${id}/watch`, { method: "POST" })}>
        Watch
      </button>{" "}
      <button type="button" onClick={() => api(`/customer/opportunities/${id}/interested`, { method: "POST" })}>
        Mark interested
      </button>
    </section>
  );
}
