import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

type Summary = {
  wizard_required: boolean;
  new_matches: number;
  strong_scores: number;
  last_run_at: string | null;
  empty_message: string | null;
};

export function RadarPage() {
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Summary>("/customer/radar/summary")
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  if (error) return <p role="alert">{error}</p>;
  if (!data) return <p>Loading radar…</p>;
  if (data.wizard_required) {
    return (
      <section>
        <h1>Set your radar</h1>
        <p>Tell us geography, industries, and score floor before matches appear.</p>
        <Link className="btn" to="/settings">Open setup</Link>
      </section>
    );
  }
  return (
    <section>
      <h1>Radar</h1>
      {data.empty_message ? <p data-testid="empty-matches">{data.empty_message}</p> : null}
      <div className="cards">
        <div className="card"><strong>{data.new_matches}</strong>Matches</div>
        <div className="card"><strong>{data.strong_scores}</strong>Strong scores</div>
        <div className="card"><strong>{data.last_run_at ?? "—"}</strong>Last pool run</div>
      </div>
    </section>
  );
}
