# AGENTS.md — Validation Commands (CBV)

Run from repo root after every significant edit. ALL must exit 0 with no ERROR/FAIL lines.

```bash
# V1 — full test suite
python -m pytest tests/ -q

# V2 — pipeline runs clean on sample data
python -m src.main --input examples/sample_listings.csv --output daily_report.md

# V3 — report contains no leaked Python source in Payback rows
python -c "import pathlib,sys; t=pathlib.Path('daily_report.md').read_text(encoding='utf-8'); sys.exit(1 if 'if score.payback_years' in t else 0)"

# V4 — package imports cleanly
python -c "import src.main, src.scoring, src.reporting, src.agents, src.models"
```

Notes:
- Python 3.12 on Windows; invoke as `python`.
- No dev server, no HTTP surface — this is a CLI. DB validation (task-006+) adds psql/Supabase row checks per task.
- daily_report.md at repo root is a generated artifact (gitignored) — safe to overwrite in validation.
