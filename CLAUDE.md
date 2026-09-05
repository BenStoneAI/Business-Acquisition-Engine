# Boring Business Acquisition Radar — CLAUDE.md

## What This Is

A private-use Python CLI tool for one operator (Ben Stone) to find, score, and track "boring" cash-flowing small businesses (HVAC, laundromats, pest control, etc.) for acquisition. It ingests CSV exports from business listing marketplaces, scores each listing against a weighted 8-factor underwriting formula, writes a daily markdown report, persists listings + score history to Postgres, and emails the report.

**Phase 1 (scoring + report generation): complete.**
**Phase 2 (persistence + email delivery + scheduler): complete 2026-07-04** (CBV session b7r4dk; evidence in `.claude/cbv/`). One manual step remains for live email — see Operations below.

---

## Tech Stack

- Python 3.11+ / CLI only (`python -m src.main --input CSV --output MD`)
- PyYAML — industry config
- python-dotenv — env var loading
- psycopg2-binary — Postgres persistence (Supabase)
- smtplib (stdlib) — email delivery
- truststore — TLS via the OS cert store (endpoint protection intercepts api.telegram.org on this machine; see `src/tls.py`)
- pytest — tests (55 passing)
- GitHub Actions — daily cron scheduler (`daily_radar.yml`)

No web framework. No web UI. No auth. No payments. Single operator only.

---

## File Map

```
src/
  main.py          — CLI entry point; dotenv + logging setup; pipeline orchestration
  scoring.py       — 8-factor weighted scorer + deal killers + valuation [DO NOT TOUCH LOGIC]
  models.py        — Listing + ScoreBreakdown dataclasses [DO NOT RENAME FIELDS]
  reporting.py     — Markdown report builder
  agents.py        — SourcingAgent (CSV ingest; skips bad rows with warning)
  financing_filter.py — 100% seller-financing screen (keep only full/possible) [Layer 1]
  daily_runs.py    — archives each day's report to Daily Runs/M.D.YYYY/ when deals found
  response_engine.py — Layer 2: builds the full first-contact package from a scored Listing
  interested.py    — Layer 2 CLI: `python -m src.interested` marks a deal Interested
  db.py            — Env-gated Postgres persistence; listing_url dedup upsert
  emailer.py       — Env-gated smtplib sender; skips with warning if unconfigured
  run_state.py     — Cross-run ingest state (data/ingest_state.json): canonical listing-id keys, last-seen price per listing, detect_price_drops (≥5% → 📉 Telegram re-alert)
  rescore.py       — `python -m src.rescore --deal X --sde N …`: re-underwrite with verified CIM numbers; writes 02 Financials/rescore_<date>.md + new deal_scores row
  deal.py          — `python -m src.deal --deal X --stage contacted|nda|cim|loi|dd|closing|closed|dead`: status.json history + business_listings.status in DB
  tls.py           — use_system_certs(): trust the OS cert store (guarded truststore inject)
config/
  industry_formulas.yaml — 14 entries (10 target + restaurant/auto_repair/retail off-thesis + other); keys: display_name, base_score, target_multiple_low/high
sql/
  schema.sql       — Full 6-table reference schema (Phase 3 material)
  migrations/phase2_business_listings_deal_scores.sql — the 2-table Phase 2 migration (applied)
.github/workflows/
  daily_radar.yml  — cron 12:00 UTC + workflow_dispatch; uploads daily_report.md artifact
tests/             — 93 tests incl. simulation harness (sim_factory generates 1,000 synthetic listings)
examples/
  sample_listings.csv — 5 listings used for testing and demo
.env.example       — SMTP + DATABASE_URL template
daily_report.md    — Generated output artifact; gitignored, overwritten each run
```

---

## Hard Constraints — Do Not Break These

1. **Do not change `score_listing()` logic in `src/scoring.py`** — correct, tested, matches the acquisition thesis.
2. **Do not rename any field on the `Listing` dataclass** — field names map directly to CSV column headers.
3. **Keep CLI flags unchanged** — `--input`, `--output`, `--min-score` (explicit flag overrides `MIN_SCORE_TO_REPORT` env).
4. **The other 4 schema tables** (broker_contacts, outreach_log, due_diligence_tasks, source_history) belong to a Phase 3 migration — not applied.

---

## Decisions (Resolved 2026-07-04)

- **Decision 1 — Email delivery: Option A (smtplib, stdlib).** Works with any SMTP provider; Brevo relay pre-configured in `.env`.
- **Decision 2 — Per-industry weights: Option A (removed dead YAML keys).** Option B ("wire `cfg.get('weights', MASTER_WEIGHTS)`") was infeasible as specced: the YAML weight keys (cash_flow_yield, employee_depth, route_density, …) never matched the 8 MASTER_WEIGHTS factor keys — the one-liner would KeyError on all 9 industries — and a real implementation would redesign `score_listing()`, violating Hard Constraint 1. Scores verified identical pre/post removal.

---

## Layer 1 — seller-financing screen (2026-07-05; floor lowered 2026-07-19)

`src/financing_filter.py` runs between sourcing and scoring. Since 2026-07-19
(strategy change backed by the ETA best-practices research: screen on quality,
negotiate on structure) it keeps listings that are 100% seller financed, leave
the door open to it, **or state a majority carry ≥ `MAJORITY_FLOOR` (50%)** —
statuses `full` / `possible` / `majority_carry`. It drops explicit "no
financing", third-party-only, and caps below 50% (e.g. "finance 25 percent").
Down-payment percentages ("10% down") are never read as caps. Opt out with
`--all-financing`. `score_listing()` is untouched — full carry still outranks
majority carry via the financing-fit factor and bonus. Each run that finds ≥1
reportable deal archives its report to `Daily Runs/M.D.YYYY/daily_report.md`.

**Operator homework (not code — highest-leverage sourcing actions, 2026-07-19):**
tighten the BizBuySell saved-search category/geography filters (the live feed
sends pizzerias and car dealers); introduce yourself to 3–5 Mountain West
business brokers using the existing credibility blurb; add a BizQuest or
DealStream alert once broker flow proves thin (needs a parser before wiring in).

## Layer 2 — Acquisition Response Engine (2026-07-05)

`python -m src.interested --input CSV --url <listing_url>` (or `--name <substr>`)
marks a deal Interested and generates the full "Hit Send" package: deal summary,
decision, thesis, tailored broker outreach email, buyer credibility blurb, top-10
questions, industry-tailored document request, 3 financing structures (anchored ≤
asking), preliminary valuation, risk notes, NDA request, LOI skeleton, two
follow-ups, CRM status, calendar reminder, and the `/01…/08` deal-room folder
under `Deals/<Business>/`. Add `--email` to send the package to `REPORT_TO_EMAIL`
via the SMTP relay. All generation is deterministic templating (tested).

**Deal lifecycle (2026-07-19, Group B build):** every deal folder now also gets
`01 Listing/listing.json` (machine-readable), `07 Due Diligence/checklist.md`,
and `08 Notes/followup_reminders.ics` (+3/+7-day events, importable). Broker
email/phone/name are captured from alert blocks into `listing.raw` when present;
`python -m src.interested --send [--send-to EMAIL]` sends the outreach email to
the broker — never sends without the explicit `--send` flag, never falls back to
Ben's own address, exits 2 if no recipient resolves. After the CIM arrives:
`python -m src.rescore --deal X --sde N …` re-underwrites on verified numbers;
`python -m src.deal --deal X --stage …` tracks pipeline stage (status.json + DB).
Price drops on previously-seen listings re-alert via Telegram (📉, ≥5% lower).
Follow-up cadence is 5 touches over ~10 weeks (days 3/7/21/42/70 — packet emails
+ matching `.ics` events); packet valuations are labeled screening-only until
superseded by `rescore`; financing structures are marked internal-only pre-CIM.

**Live-data enrichment** (Contact Finder / Reputation / Public Records):
**on-demand and assistant-driven** — the old `src/live_data.py` search-API module
was deleted 2026-07-19 (its providers, Google CSE web search and the Bing Search
API, were retired by their vendors). When Ben flags a deal, Claude runs
`/deep-research` + `/conduit` to gather the secondLayer.md fields (broker/owner
contact, website, LinkedIn, GBP, state entity, Google/Yelp/BBB reputation,
SoS/license/UCC records) and writes them to
`Deals/<Business>/03 Legal/enrichment.md`. A cron can't drive a browser, so the
Telegram alert (below) is the trigger to pull Claude in.

**Telegram alerts** (`src/notifier.py`): each run that finds reportable deals
pushes a summary (name, location, score, asking, financing, URL) to Telegram via
the Bot API (stdlib `urllib`, env-gated). Needs `TELEGRAM_BOT_TOKEN` +
`TELEGRAM_CHAT_ID` in `.env` (and as CI secrets — already referenced in
`daily_radar.yml`). This is how Ben learns a run found something.

## Listing source — BizBuySell email-alert ingest (2026-07-05)

Real deals enter via a BizBuySell *owner-financed* saved search that emails
rainking6693@gmail.com. The connected Gmail app is a different (workspace)
account, so ingest reads rainking6693 directly over **IMAP** (`src/imap_fetch.py`,
stdlib, env-gated on `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD`). `src/bizbuysell_ingest.py`
parses an alert (HTML→text, split per listing URL, regex fields) into `Listing`s;
because the feed is owner-financed, `seller_financing` defaults True unless the
blurb states a sub-100% cap. `python -m src.ingest_bizbuysell` (or `--file
<saved_alert>`) runs fetch → parse → cross-run dedup (`src/run_state.py`,
`data/ingest_state.json`, `--no-state` to bypass) → 100%-financing filter →
score → **Postgres persist** → Telegram alert → build a packet+deal folder per
qualifying deal ≥ min-score. Sample: `examples/sample_bizbuysell_alert.html`.
Field regexes verified against live alerts 2026-07-12+.

**Hardening (2026-07-18 failure-mode audit):** IMAP fetch window is 7 days (a
missed night no longer loses alerts); the state file keeps overlapping windows
from re-alerting; every run that finds nothing sends a one-line Telegram
**heartbeat** ("✅ Radar ran …") so silence always means failure; any crash
sends a "⚠️ Radar ingest FAILED" Telegram and exits 1; deal-folder names are
sanitized for Windows (`safe_folder_name`); off-thesis feed industries
(restaurant/auto_repair/retail) score against honest low base scores instead of
the 75-point default.

## Operations

**Scheduler:** the PRIMARY nightly run is the Windows Task Scheduler task
**`BoringBusinessRadar`** (daily 6:00 AM local, wake-to-run, StartWhenAvailable)
→ `scripts\run_radar.cmd` → `python -m src.ingest_bizbuysell`, logging to
`logs\radar.log`. Re-registered 2026-07-18 on the `benst` machine — the original
task died when the machine/user changed from `Ben` to `benst` (runs silently
missed 7/15–7/17; alerts recovered same day via the 7-day IMAP window). The
Telegram heartbeat is the liveness signal: **no daily Telegram message = the
task is broken** — check `Get-ScheduledTaskInfo BoringBusinessRadar` and
`logs\radar.log`. The cloud workflow stays a manual backup (its cron is
commented out; it shares no state file, so running both daily would duplicate
alerts).

**Local run:** `python -m src.main --input examples/sample_listings.csv --output daily_report.md`

**Database:** Supabase project `fdnwlcomuddzmluvbylg` ("AI Accounting Hub" — shared because the free tier caps at 2 projects), isolated in the **`radar` schema** with dedicated login role **`radar_app`** (rotate via `ALTER ROLE radar_app PASSWORD '...'`; fully removable via `DROP SCHEMA radar CASCADE; DROP ROLE radar_app;`). Connection: session pooler `aws-1-us-west-2.pooler.supabase.com:5432`, user `radar_app.fdnwlcomuddzmluvbylg`. Re-running the same CSV never duplicates listings (`listing_url` dedup); each run appends `deal_scores` history rows.

**Email:** env-gated in `src/emailer.py`. **Sends via Gmail** (`smtp.gmail.com`) using `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD` — the same App Password used for IMAP ingest, so one credential covers read + send. Brevo/`SMTP_*` remain a fallback only when Gmail creds are absent. Verified live 2026-07-05 (rainking6693 → rainking6693). No Brevo key needed anymore.

**CI:** `gh workflow run daily_radar.yml` (or wait for the 12:00 UTC cron). `DATABASE_URL` secret is set. Missing SMTP secrets cause a logged skip, never a failure.

**Phase 2 Definition of Done:** all 10 checks executed 2026-07-04 — ledger with evidence in `.claude/cbv/dod_ledger.md`.
