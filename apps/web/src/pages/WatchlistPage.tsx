import { useEffect, useState } from "react";
import { api } from "../api";

export function WatchlistPage() {
  const [items, setItems] = useState<Array<{ listing_id: number; business_name: string }>>([]);
  useEffect(() => {
    api<{ watchlist: Array<{ listing_id: number; business_name: string }> }>("/customer/watchlist")
      .then((b) => setItems(b.watchlist))
      .catch(() => setItems([]));
  }, []);
  return (
    <section>
      <h1>Watchlist</h1>
      {items.length === 0 ? <p>Nothing watched yet.</p> : (
        <ul>{items.map((i) => <li key={i.listing_id}>{i.business_name}</li>)}</ul>
      )}
    </section>
  );
}
