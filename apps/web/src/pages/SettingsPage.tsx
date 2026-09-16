import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";

type Industry = { id: string; display_name: string; on_thesis: boolean };

export function SettingsPage() {
  const [industries, setIndustries] = useState<Industry[]>([]);
  const [selected, setSelected] = useState<string[]>(["hvac", "plumbing", "electrical"]);
  const [states, setStates] = useState("UT");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api<{ industries: Industry[] }>("/customer/settings").then((body) => {
      setIndustries(body.industries);
      setSelected(body.industries.filter((i) => i.on_thesis).map((i) => i.id));
    }).catch(() => undefined);
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    await api("/customer/settings", {
      method: "PUT",
      body: JSON.stringify({
        states: states.split(",").map((s) => s.trim()).filter(Boolean),
        industries: selected,
        financing_floor: "full",
        score_threshold: 80,
      }),
    });
    setSaved(true);
  }

  return (
    <section>
      <h1>Setup / Settings</h1>
      <form onSubmit={onSubmit}>
        <label>States (comma-separated)
          <input value={states} onChange={(e) => setStates(e.target.value)} />
        </label>
        <fieldset>
          <legend>Industries</legend>
          {industries.map((i) => (
            <label key={i.id}>
              <input
                type="checkbox"
                checked={selected.includes(i.id)}
                onChange={(e) => {
                  setSelected((cur) =>
                    e.target.checked ? [...cur, i.id] : cur.filter((x) => x !== i.id),
                  );
                }}
              />{" "}
              {i.display_name}
            </label>
          ))}
        </fieldset>
        <button type="submit">Save criteria</button>
      </form>
      {saved ? <p>Radar is running against your criteria.</p> : null}
    </section>
  );
}
