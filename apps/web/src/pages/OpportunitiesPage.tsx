import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

type Row = {
  id: number;
  business_name: string;
  industry: string;
  location: string;
  last_score: number;
  bucket: string;
  asking_price: number | null;
};

export function OpportunitiesPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [empty, setEmpty] = useState<string | null>(null);
  const [wizard, setWizard] = useState(false);

  useEffect(() => {
    api<{ opportunities: Row[]; empty_message?: string; wizard_required?: boolean }>("/customer/opportunities")
      .then((body) => {
        setWizard(Boolean(body.wizard_required));
        setRows(body.opportunities);
        setEmpty(body.empty_message ?? null);
      })
      .catch(() => setEmpty("Could not load opportunities."));
  }, []);

  if (wizard) return <p>Finish setup first. <Link to="/settings">Open setup</Link></p>;
  return (
    <section>
      <h1>Opportunities</h1>
      {empty ? <p data-testid="empty-matches">{empty}</p> : null}
      <table>
        <thead>
          <tr>
            <th>Business</th>
            <th>Industry</th>
            <th>Location</th>
            <th>Score</th>
            <th>Asking</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td><Link to={`/opportunities/${r.id}`}>{r.business_name}</Link></td>
              <td>{r.industry}</td>
              <td>{r.location}</td>
              <td>{r.last_score} · {r.bucket}</td>
              <td>{r.asking_price ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
