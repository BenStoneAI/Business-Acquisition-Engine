# Boring Business Acquisition Radar

A private, single-operator acquisition radar for finding, scoring, underwriting, and tracking boring cash-flowing small businesses — laundromats, HVAC, plumbing, electrical, pest control, commercial cleaning, pool service, car washes, self-storage, roofing.

## What actually ships

- **Nightly ingest** (Windows Task Scheduler task `BoringBusinessRadar`, 6:00 AM, wake-to-run): reads BizBuySell owner-financed saved-search alert emails from Gmail over IMAP (7-day window), parses them into structured listings, and skips listings already processed on a prior run (`data/ingest_state.json`).
- **100% seller-financing screen**: keeps only deals that are fully seller-financed or leave the door open to it (`--all-financing` to bypass on the CSV path).
- **Weighted 8-factor scoring** (0–100) with deal-killer checks, valuation range, and a disciplined maximum-offer calculation.
- **Postgres persistence** (Supabase, `radar` schema): listings dedup by `listing_url`; every run appends score history.
- **Telegram alerts**: a deal summary when something clears the threshold, a one-line heartbeat when nothing does (so silence always means the pipeline is broken), and a failure alert on any crash.
- **Deal packets**: every qualifying deal gets a "Hit Send" package (outreach email, questions, document request, financing structures, LOI skeleton, valuation, follow-ups) in a `Deals/<Business>/01…08` folder.
- **CSV path** (`python -m src.main`): score any marketplace CSV export, write a markdown daily report, archive it under `Daily Runs/`, and email it via Gmail.
- **Interested trigger** (`python -m src.interested --input CSV --url|--name …`): build the full first-contact package for one deal on demand.

## Daily operation

```bash
# Nightly (automated): BizBuySell alerts -> packets + Telegram
python -m src.ingest_bizbuysell            # --file alert.html to parse a saved alert
                                           # --no-state to reprocess seen listings

# Manual: score a CSV export
python -m src.main --input examples/sample_listings.csv --output daily_report.md

# Mark a deal Interested
python -m src.interested --input listings.csv --name "Wasatch" [--email]
```

Configuration is env-gated via `.env` (see `.env.example`): missing credentials cause a logged skip, never a crash. Live-data enrichment for flagged deals is assistant-driven (Claude `/deep-research` + `/conduit`) — the Google CSE / Bing search APIs originally planned for it were retired by their vendors.

## Score bands

|Score|Meaning|
|-:|-|
|90-100|Pursue immediately|
|80-89|Strong candidate|
|70-79|Watchlist / request info|
|60-69|Only if price drops|
|<60|Pass|

## Core acquisition formula

```text
Acquisition Score =
  0.30 × Financial Score
+ 0.15 × Industry Score
+ 0.15 × Recurring Revenue Score
+ 0.10 × Seller Motivation Score
+ 0.10 × Owner Independence Score
+ 0.10 × Financing Fit Score
+ 0.05 × Growth Upside Score
+ 0.05 × Risk Score
+ Bonus Points
- Deal Killer Penalties
```

## Maximum offer formula

```text
Maximum Offer = min(
  Adjusted SDE × Target Industry Multiple,
  Price Supported by 1.75x DSCR,
  Price Allowing Cash-on-Cash Return > 25%,
  Price Allowing Payback < 4 Years
)
```

## Files

See `CLAUDE.md` for the full file map, hard constraints, and operations runbook — it is the authoritative doc for this repo.

```text
config/industry_formulas.yaml   Per-industry base scores and target multiples
src/scoring.py                  Scoring + valuation engine (do not touch logic)
src/bizbuysell_ingest.py        BizBuySell alert email parser
src/ingest_bizbuysell.py        Nightly ingest orchestrator
src/response_engine.py          "Hit Send" first-contact package generator
src/run_state.py                Cross-run dedup state
src/notifier.py                 Telegram alerts + heartbeat
src/db.py                       Supabase persistence
sql/                            Schema + applied Phase 2 migration
tests/                          55 tests
```
