# Architecture Decision Packet
## System: Boring Business Acquisition Radar
## Date: 2026-06-28
## Verdict: NEEDS_ARCHITECTURE_DECISION
## Confidence: HIGH — full codebase read, all 5 source files, schema, config, and tests examined directly

---

## 1. System Summary

The Boring Business Acquisition Radar is a private-use Python CLI tool built for one operator (Ben Stone) to find, score, and track "boring" cash-flowing small businesses (HVAC, laundromats, pest control, etc.) for acquisition. The system ingests business listing CSV exports, scores each listing against a weighted 8-factor underwriting formula, and writes a daily markdown report sorted by acquisition attractiveness. The system is currently a working MVP for Phase 1 (scoring + report generation) but has not yet implemented Phase 2 (persistence, email delivery, scheduler, or source automation). Several architectural decisions — database client, email delivery method, scoring weight model, and deployment platform — must be made before Phase 2 spec can begin. No payments, no auth, and no multi-user concerns exist.

---

## 2. Current-System Map

| Component | Type | Status | Notes |
|---|---|---|---|
| `src/main.py` | CLI entry point | Live | `python -m src.main --input CSV --output MD` |
| `src/models.py` | Data models | Live | `Listing` + `ScoreBreakdown` + `AgentResult` dataclasses |
| `src/scoring.py` | Core engine | Live | 8-factor weighted score + valuation + deal killers |
| `src/agents.py` | Agent layer | Partial | `SourcingAgent` (CSV ingest) live; `ExtractionAgent` is a stub; `UnderwritingAgent` delegates to scorer |
| `src/reporting.py` | Report builder | Live (buggy) | Payback row renders Python source code (f-string bug at line 39) |
| `config/industry_formulas.yaml` | Industry config | Partial | `base_score`, `target_multiple_low/high` consumed; `weights`, `ideal_sde_margin`, `red_flags` arrays are never read |
| `config/sources.yaml` | Source config | Planned | Defines 8 marketplace/broker sources; never loaded at runtime |
| `sql/schema.sql` | DB schema | Planned | 6 well-designed tables; no Python DB client exists anywhere |
| `tests/test_scoring.py` | Tests | Partial | 2 passing tests covering scoring only; no reporting or agent tests |
| `prompts/agent_prompts.md` | LLM prompts | Planned | Complete prompt templates; no LLM call in any source file |
| `.env.example` | Config template | Defined | SMTP, DATABASE_URL, API keys — none loaded at runtime (no `load_dotenv()`) |
| `examples/sample_listings.csv` | Sample data | Live | 5 listings used for testing and demo |
| `daily_report.md` | Output artifact | Live | Generated correctly except payback row bug |

---

## 3. Target Architecture

The target architecture for Phase 2 adds four missing pillars: persistence, email delivery, scheduled execution, and basic source automation. Nothing about the existing scoring engine or report builder needs to be replaced — only connected.

| Layer | Current State | Target State |
|---|---|---|
| Ingestion | Manual CSV drop | Scheduled: saved-search email alerts → CSV → ingest |
| Scoring | Works correctly | Unchanged |
| Persistence | None (results discarded each run) | Write `Listing` + `ScoreBreakdown` to Postgres after each run |
| Deduplication | None | Check `listing_url UNIQUE` constraint before insert |
| Reporting | Markdown file on disk | Same markdown file + email delivery to `rainking6693@gmail.com` |
| Scheduler | Manual invocation | GitHub Actions cron at 06:00 MT daily |
| Industry config | Partial (weights unused) | **Decision required:** implement per-industry weights OR remove them from YAML |
| Env vars | Never loaded | `load_dotenv()` at startup; all config via `.env` |
| LLM extraction | Stub | Phase 3 item — not in Phase 2 scope |

---

## 4. Domain Entities

### Listing (core entity)

| Field | Type | Source | Notes |
|---|---|---|---|
| `business_name` | str | CSV | Required |
| `industry` | str | CSV | Normalized via `normalized_industry_key()` |
| `location` | str | CSV | Free text |
| `asking_price` | float? | CSV | Optional — scores penalized when None |
| `sde` | float? | CSV | Critical for financial score; None → score = 35 |
| `revenue` | float? | CSV | Informational only |
| `seller_financing` | bool | CSV | Bonus points trigger |
| `sba_prequalified` | bool | CSV | Bonus points trigger |
| `recurring_revenue_pct` | float? | CSV | Drives recurring_revenue_score |
| `customer_concentration_pct` | float? | CSV | Deal killer if >0.30 |
| `owner_hours_per_week` | float? | CSV | Owner independence score driver |
| `years_in_business` | int? | CSV | Bonus if ≥20 years |
| `notes` | str | CSV | Free text; multiple scores keyword-scan this field |
| `listing_url` | str? | CSV | UNIQUE key in Postgres schema |
| `raw` | dict | CSV | Full CSV row preserved |

Relationships: one Listing → many ScoreBreakdowns (one per run) per `sql/schema.sql:27`

### ScoreBreakdown (derived record)

| Field | Type | Source | Notes |
|---|---|---|---|
| `total_score` | float | `score_listing()` | 0–100 after clamping |
| `bucket` | str | `bucket_for_score()` | PURSUE NOW / STRONG CANDIDATE / REQUEST INFO / PRICE TOO HIGH / PASS |
| `financial_score` | float | `financial_score()` | Driven by cash_flow_yield |
| `industry_score` | float | YAML `base_score` | Fixed per-industry value |
| `red_flags` | list[str] | `deal_killers()` | Deal killer strings |
| `next_action` | str | `next_action_for()` | Recommended operator action |
| `estimated_max_offer` | float? | `estimate_values()` | min(SDE×multiple, DSCR, CoC, payback) |

Relationships: many ScoreBreakdowns → one Listing (via `listing_id FK`)

### AgentResult (transient wrapper)

| Field | Type | Notes |
|---|---|---|
| `agent_name` | str | Which agent produced this |
| `status` | str | "ok" or error string |
| `summary` | str | Human-readable run summary |
| `data` | dict | Carries scored pairs or count |

Not persisted. Used for internal handoff between agents in `main.py`.

### DB-Only Entities (schema exists, no Python wiring)

| Entity | Table | Purpose | Status |
|---|---|---|---|
| BrokerContact | `broker_contacts` | Broker directory | Schema only |
| OutreachLog | `outreach_log` | Communication tracking | Schema only |
| DueDiligenceTask | `due_diligence_tasks` | DD checklist | Schema only |
| SourceHistory | `source_history` | Run audit log | Schema only |

---

## 5. Source-of-Truth Matrix

| Entity | SoT Location | Writers | Readers | Conflict Resolution | Risk |
|---|---|---|---|---|---|
| Listing data | CSV input file | Operator (manual) | `SourcingAgent.from_csv()` | Last run wins; no history | MEDIUM — no dedup before Postgres is wired |
| ScoreBreakdown | In-memory only (no persistence) | `score_listing()` | `build_daily_report()` | N/A — discarded after each run | HIGH — scored deals lost between runs |
| Industry config (multiples) | `config/industry_formulas.yaml` | Operator (manual edit) | `score_listing()` via `main.py` | File wins; no versioning | LOW — YAML is read-only at runtime |
| Industry config (weights, margins) | `config/industry_formulas.yaml` | Operator (manual edit) | **Nobody** — never read | N/A | HIGH — creates false expectations |
| Env config | `.env` file | Operator (manual) | **Nobody** — `load_dotenv()` never called | N/A | HIGH — config silently ignored |
| Report output | `daily_report.md` | `build_daily_report()` | Operator (reads manually) | Overwritten each run | LOW — acceptable for now |

---

## 6. State Machines

### Listing — deal_status (DB schema only; not yet implemented in Python)

| State | Transitions To | Triggered By | Irreversible? | Notes |
|---|---|---|---|---|
| `new` | `scored` | `UnderwritingAgent.run()` completes | No | Default on insert |
| `scored` | `request_info`, `watchlist`, `pass` | Operator review of report | No | Not implemented yet |
| `request_info` | `nda_sent`, `pass` | Operator action | No | Phase 3 CRM |
| `nda_sent` | `cim_received`, `pass` | Seller response | No | Phase 3 CRM |
| `cim_received` | `underwriting`, `pass` | Document received | No | Phase 3 CRM |
| `underwriting` | `loi_draft`, `pass` | Operator analysis | No | Phase 3 CRM |
| `loi_draft` | `loi_sent` | Operator action | No | Phase 3 CRM |
| `loi_sent` | `due_diligence`, `pass` | Seller acceptance | No | Phase 3 CRM |
| `due_diligence` | `closed`, `pass` | DD complete | Yes (if closed) | Phase 3 CRM |
| `closed` | *(terminal)* | — | Yes | Phase 3 CRM |
| `pass` | `watchlist` (re-list) | Price drop or new info | No | Phase 3 CRM |

**Note:** The `status TEXT DEFAULT 'new'` column exists in `sql/schema.sql:26` but no Python code reads or writes it. This state machine is entirely planned, not implemented.

### ScoreBreakdown — bucket (implemented, in-memory only)

| State | Transitions To | Triggered By | Irreversible? |
|---|---|---|---|
| PURSUE NOW | — | `score >= 90` | No — re-scored next run |
| STRONG CANDIDATE | — | `80 ≤ score < 90` | No |
| REQUEST INFO / WATCHLIST | — | `70 ≤ score < 80` | No |
| PRICE TOO HIGH / WATCH | — | `60 ≤ score < 70` | No |
| PASS | — | `score < 60` | No |

---

## 7. Critical Workflows

### Workflow 1: Daily Scoring Run (the only currently working flow)

**Trigger:** Operator runs `python -m src.main --input file.csv --output daily_report.md`

**Happy path:**
1. `main.py` loads `config/industry_formulas.yaml` via PyYAML
2. `SourcingAgent.from_csv()` reads CSV → creates `List[Listing]`
3. `ExtractionAgent.run()` returns a stub count (no-op)
4. `UnderwritingAgent.run()` calls `score_listing(listing, industry_configs)` for each listing
5. `score_listing()` computes 8 sub-scores + bonus + deal-killer penalty → `ScoreBreakdown`
6. `build_daily_report()` sorts by score, partitions into Top/Watch/Rejected, renders markdown
7. Markdown written to output path
8. Results discarded — no persistence

**Error path:**
- Malformed CSV row → `ValueError` on `float()` cast → entire run crashes (bug — see Section 11)
- Unknown industry → `DEFAULT_INDUSTRY` used silently (no warning)
- Missing SDE → `financial_score` returns 35 (correct behavior)

**Output:** `daily_report.md` with bug: Payback row displays Python source code instead of value

---

### Workflow 2: Persist Scored Deal (PLANNED — not implemented)

**Trigger:** After scoring run completes
**Path:** Check `listing_url` for uniqueness → INSERT `business_listings` → INSERT `deal_scores`
**Error path:** Duplicate URL → UPDATE `last_seen_at` only; do not re-score
**Status:** Schema exists (`sql/schema.sql`); no Python client, no insert code

---

### Workflow 3: Email Report Delivery (PLANNED — not implemented)

**Trigger:** After report is written
**Path:** Load SMTP config from `.env` → connect → send markdown as email body or attachment
**Target:** `rainking6693@gmail.com`
**Status:** SMTP env vars defined; no `smtplib` or email library import anywhere

---

### Workflow 4: Scheduled Daily Run (PLANNED — not implemented)

**Trigger:** 06:00 MT daily
**Path:** Cron/scheduler → fetch new listings from sources → run scoring → persist → email report
**Status:** No scheduler, no CI/CD, no source connectors

---

### Workflow 5: LLM Extraction (PLANNED — not implemented)

**Trigger:** Listing with unstructured text / scraped HTML
**Path:** Pass raw text to LLM (Claude/GPT) with extraction prompt → parse structured `Listing`
**Status:** `prompts/agent_prompts.md` has complete extraction prompts; `ExtractionAgent` is a stub

---

## 8. Integration Boundaries

| Integration | Direction | Auth Method | What We Send | What We Receive | Failure Mode | Cost/Limit |
|---|---|---|---|---|---|---|
| Postgres | Outbound | DATABASE_URL (not loaded) | `business_listings` + `deal_scores` rows | Confirmation | Run fails; results lost | $0 (self-hosted or Supabase free) |
| SMTP / Gmail | Outbound | SMTP creds (not loaded) | Markdown report email | Delivery confirmation | Report not sent; no retry | $0 (personal Gmail) |
| Bing Search API | Outbound (planned) | `BING_SEARCH_API_KEY` | Search query | JSON listing results | No new listings sourced | ~$7/1000 queries |
| Google CSE | Outbound (planned) | `GOOGLE_CSE_API_KEY` + ID | Search query | JSON listing results | No new listings sourced | ~$5/1000 queries |
| Apify | Outbound (planned) | `APIFY_TOKEN` | Actor run request | Structured listing data | No new listings sourced | Pay-per-use |
| LLM (Claude/GPT) | Outbound (planned) | API key (not in .env.example) | Raw listing text | Structured `Listing` JSON | ExtractionAgent falls back to CSV parsing | ~$0.01/listing |

**Currently active integrations: NONE.** All integrations are defined in config but unwired.

---

## 9. Money/Auth/Proof Boundaries

### MONEY

No payments, charges, refunds, or billing logic exist or are planned. This system does not handle money — it analyzes deals that involve money.

| Location | Action | Trigger | Guard | Idempotent? | Audit Log? |
|---|---|---|---|---|---|
| *(none)* | — | — | — | — | — |

### AUTH

No authentication exists. The system is a single-user local CLI. No web interface, no API, no multi-user access.

| Check Point | Token Type | Validates | Failure Behavior | Rate Limited? |
|---|---|---|---|---|
| *(none)* | — | — | — | — |

### PROOF

No formal proof system. The daily report markdown is the only output artifact.

| Proof Type | Generated At | Storage Location | User-Visible? | Tamper-Proof? |
|---|---|---|---|---|
| Daily report | End of scoring run | `daily_report.md` (local disk) | Yes (manual read) | No — plain file, overwritten each run |
| Score record | *(planned)* | `deal_scores` table | No | No — DB row, mutable |

---

## 10. Data Flow

### Current working flow (Phase 1):

```
1. Operator drops CSV → src/main.py
2. main.py → loads config/industry_formulas.yaml (PyYAML)
3. main.py → SourcingAgent.from_csv(csv_path)
   - Reads each row with csv.DictReader
   - Coerces types (float, bool, int)
   - Creates Listing dataclass
   - [RISK: ValueError on bad row crashes entire run]
4. main.py → ExtractionAgent.run(listings) → [NO-OP stub]
5. main.py → UnderwritingAgent.run(listings)
   - For each listing: calls score_listing(listing, industry_configs)
   - score_listing():
     a. Normalizes industry key
     b. Looks up industry cfg (falls back to DEFAULT_INDUSTRY silently)
     c. Computes 8 sub-scores (financial, industry, recurring, motivation, independence, financing, growth, risk)
     d. Computes bonus (seller_financing, real_estate, sba_prequalified, years_in_business)
     e. Runs deal_killers() text scan → penalty
     f. Computes total = weighted sum + bonus - penalty, clamped 0-100
     g. Computes estimate_values() → low/high/max_offer
     h. Returns ScoreBreakdown
6. main.py → build_daily_report(scored, min_score)
   - Sorts by total_score desc
   - Partitions: top (≥min_score), watch (60–min_score), rejected (<60)
   - Renders markdown (BUG: payback row at line 39)
7. Writes daily_report.md
8. [RESULTS DISCARDED — no DB write]
```

### Failure points in current flow:
- Step 3: Bad CSV row → crash
- Step 5b: Unknown industry → silent wrong score
- Step 6: Payback f-string renders Python code
- Step 8: All scored results lost each run

---

## 11. Failure Modes

| Scenario | Trigger | System State After | Detectable? | Recoverable? | Mitigation |
|---|---|---|---|---|---|
| Malformed CSV row (bad `asking_price`) | `float("$not_a_number")` | Run crashes; no report written | Yes — traceback | Yes — fix CSV manually | Wrap `_row_to_listing` in try/except; skip bad rows |
| Unknown industry (not in YAML) | Industry string not in `industry_configs` keys | Silent fallback to `base_score: 75`; operator sees wrong score | No — no warning | N/A — wrong score used | Add `logging.warning()` before fallback |
| `.env` not present or not loaded | `load_dotenv()` never called | All env-driven config silently uses None | No | Yes — add `load_dotenv()` | Fix now (P1) |
| Duplicate listing in next run | Same `listing_url` re-scored | Duplicate entries in report; no history | Partially (same name appears again) | Yes — deduplicate before insert | Postgres `UNIQUE` constraint on `listing_url`; check before insert |
| Report file already exists | Every daily run | Silently overwritten | No | No (previous day's report lost) | Timestamp report filename or archive before overwrite |
| `config/industry_formulas.yaml` missing | `load_industry_configs()` raises FileNotFoundError | Run crashes before any scoring | Yes — FileNotFoundError | Yes — restore file | Validate config path at startup |
| All listings score below `min_score` | Weak listing batch | Report body shows "No deals cleared threshold today" | Yes — report says so | N/A | Correct behavior; acceptable |
| SMTP connection fails (planned) | Bad creds or host unreachable | Report written to disk but not sent | Yes — SMTP exception | Yes — re-send manually | Retry once; log failure; do not crash main run |
| Postgres write fails (planned) | DB unreachable or schema not applied | Scoring succeeds but results not persisted | Yes — psycopg2 exception | Yes — re-run after DB restored | Wrap insert in try/except; log; continue |

---

## 12. Duplicate / Sprawl Analysis

| Redundancy Found | Type | Risk Level | Recommendation |
|---|---|---|---|
| Industry `weights` defined in YAML but `MASTER_WEIGHTS` used in Python | Data/Config | HIGH — YAML implies per-industry weighting; runtime ignores it; misleads any future developer | DECIDE: implement per-industry weights OR remove from YAML |
| Industry `red_flags` in YAML + hardcoded `deal_killers()` text scan | Config/Code | MEDIUM — two sources of red-flag logic that diverge silently | MERGE: read YAML red_flags into deal_killers(); remove hardcoded strings OR remove from YAML |
| Industry `ideal_sde_margin` in YAML but never consumed | Config | MEDIUM — false documentation | REMOVE from YAML or ADD to scoring logic |
| `sources.yaml` defines 8 sources but is never loaded | Config | LOW — dead config | LOAD in Phase 2 source automation OR mark as documentation only |
| 4 packages in `requirements.txt` with zero imports | Dependency | LOW — install waste + false surface area | REMOVE: pydantic, pandas, Jinja2, requests |
| `import math` in scoring.py with no math calls | Code | LOW — noise | REMOVE import |

---

## 13. Build / Reuse / Delete Decisions

| Component | Decision | Rationale | Priority | Dependencies |
|---|---|---|---|---|
| `src/scoring.py` | REUSE AS-IS | Correct logic, 2 passing tests, matches spec | — | None |
| `src/models.py` | REUSE AS-IS | Clean dataclass design | — | None |
| `src/reporting.py` | REUSE WITH CHANGES | Fix payback f-string bug (line 39) | P0 | None |
| `src/main.py` | REUSE WITH CHANGES | Add `load_dotenv()`, CSV error handling, min-score from env | P1 | python-dotenv |
| `src/agents.py:SourcingAgent` | REUSE WITH CHANGES | Add try/except for malformed rows | P2 | None |
| `src/agents.py:ExtractionAgent` | DELETE | No-op stub; delete — do not keep as a Phase 3 placeholder | P2 | None |
| `src/agents.py:UnderwritingAgent` | DELETE (inline into main.py) | Wraps a single call to `score_listing()`; no abstraction value for a single-user CLI | P2 | None |
| `src/models.py:AgentResult` | DELETE | Transient wrapper that carries a status string to main.py for printing; replace with a direct log line | P2 | None |
| `sql/schema.sql` (business_listings + deal_scores) | REUSE PARTIAL — Phase 2 migration only | Apply only these 2 tables in a dedicated Phase 2 migration file; do not apply the full 6-table schema | P2 | DB client decision |
| `sql/schema.sql` (broker_contacts, outreach_log, due_diligence_tasks, source_history) | DEFER TO PHASE 3 MIGRATION | Zero Python consumers in Phase 2; provisioning now creates dead tables | P3 | Phase 3 CRM build |
| `prompts/agent_prompts.md` | DELETE | LLM extraction prompts for a Phase 3 integration with no live code; remove from repo | P2 | None |
| Industry YAML `weights/ideal_sde_margin/red_flags` | DECIDE (see Section 15) | Cannot keep as-is — misleads developers | P2 | Architecture decision |
| `config/sources.yaml` | DELETE | 8 marketplace sources, none loaded at runtime; archive as planning notes outside the repo | P2 | None |
| `pydantic, pandas, Jinja2, requests` | DELETE | Zero imports confirmed | P2 | None |
| `import math` in scoring.py | DELETE | Zero usage confirmed | P3 | None |
| `.github/workflows/daily_radar.yml` | BUILD NEW | No scheduler exists; GitHub Actions is the lowest-friction option | P1 | GitHub repo with Actions enabled |
| Email send module | BUILD NEW | No code exists; decision needed on delivery method | P2 | Email method decision |
| DB write path (business_listings + deal_scores only) | BUILD NEW | Phase 2-only migration; no client, no insert code; add after DB client decision | P2 | DB client decision |

---

## 14. Non-Scope

1. We are not building a web UI because this is a personal operator tool; markdown report is sufficient for Phase 2.
2. We are not building multi-user auth because the system is single-operator by design.
3. We are not building LLM extraction (ExtractionAgent) in Phase 2 because the CSV ingest path is functional and LLM extraction is a Phase 3 item.
4. We are not building source scraping (Apify/playwright) in Phase 2 because marketplace terms compliance review is required first.
5. We are not refactoring the scoring formula because it is correct, tested, and matches the documented acquisition thesis.
6. We are not implementing the full CRM pipeline (outreach_log, due_diligence_tasks) in Phase 2; those are Phase 3.
7. We are not building a mobile or notification interface; email delivery to Gmail satisfies the daily report requirement.
8. We are not applying the full `sql/schema.sql` in the Phase 2 database migration. Only `business_listings` and `deal_scores` will be created. The remaining four tables (`broker_contacts`, `outreach_log`, `due_diligence_tasks`, `source_history`) belong in a Phase 3 migration when the CRM pipeline is built.
8. We are not changing the database schema; `sql/schema.sql` is already well-designed for the full roadmap.

---

## 15. Risk Register

| Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|
| **G9 — No persistence means deal history is lost forever until DB is wired** — A promising deal scored today is invisible tomorrow unless the operator kept the report. Trend analysis, dedup, and CRM require history. | HIGH | HIGH | Wire Postgres insert path immediately after deciding on DB client; this is the most important Phase 2 task | Operator/developer |
| **Per-industry weights in YAML create a false architecture contract** — Any future developer reading `industry_formulas.yaml` will believe HVAC and pest control use different weights. They do not. This causes wrong debugging, wrong feature work, and wrong scoring assumptions. | HIGH | MEDIUM | Decide in Phase 2: implement per-industry weights from YAML (richer scoring) OR strip all unused keys from YAML (simpler) | Operator |
| **No scheduler means "daily" report is never daily** — The system requires manual invocation. If operator forgets or travels, pipeline stops. | MEDIUM | HIGH | Add GitHub Actions cron as P1; cheapest path to reliable daily execution | Developer |
| **`.env` never loaded means email/DB/API config is silently dead** — Even after email and DB code is written, if `load_dotenv()` is not added first, all integrations will fail with cryptic `None`-type errors | HIGH | MEDIUM | Fix now (P1); one line change; no architecture decision required | Developer |
| **Payback bug produces incorrect reports today** — The f-string render error means every report the operator reads shows Python source code in the Payback Estimate row | HIGH | LOW | Fix now (P0); one line change | Developer |
| **No input validation means one bad CSV row kills the entire run** — With real marketplace data, malformed rows (non-numeric prices, encoding issues) are certain | MEDIUM | MEDIUM | Add try/except in `SourcingAgent._row_to_listing()` (P2) | Developer |
| **Industry config drift will worsen** — As more fields are added to YAML without being wired into scoring, the gap between "what config implies" and "what scoring does" grows, eroding trust in the system | MEDIUM | MEDIUM | Before adding any new YAML field, either wire it in scoring.py or document it as aspirational | Operator |

---

## 16. Definition of Done

Phase 2 is complete when ALL of the following are verifiable:

1. `python -m src.main --input examples/sample_listings.csv --output daily_report.md` runs without errors and the Payback row contains a numeric value (e.g., "1.5 years"), not Python source code.
2. Running with a `.env` containing `MIN_SCORE_TO_REPORT=80` changes the report threshold without using `--min-score` flag.
3. After a scoring run, all 5 sample listings appear as rows in the `business_listings` Postgres table with correct `total_score` values in `deal_scores`.
4. Re-running against the same CSV does not create duplicate rows in `business_listings` (verified by `SELECT COUNT(*) FROM business_listings WHERE listing_url = 'https://example.com/bee-safe'` returning 1).
5. A daily report email arrives at `rainking6693@gmail.com` from the configured sender address after a manual trigger.
6. GitHub Actions workflow `daily_radar.yml` runs successfully on manual dispatch and produces `daily_report.md` as an artifact.
7. `python -m pytest tests/ -v` shows ≥6 passing tests including at least 2 for the reporting module (payback value + payback unknown).
8. `pip install -r requirements.txt` installs exactly these packages: `PyYAML`, `python-dotenv`, `pytest` — and nothing else (pydantic, pandas, Jinja2, requests removed).
9. A CSV row with a non-numeric `asking_price` logs a warning and is skipped; remaining rows are still scored.
10. The GitHub Actions workflow log shows no unhandled exceptions and exits 0.

---

## 17. Handoff to Spec-Superstar

When ready to spec Phase 2, provide spec-superstar with:

**Confirmed scope:**
- Fix payback f-string bug (`src/reporting.py:39`)
- Add `load_dotenv()` to `src/main.py`
- Delete `ExtractionAgent`, `UnderwritingAgent`, `AgentResult` from `agents.py`; replace agent delegation in `main.py` with direct function calls
- Delete `prompts/agent_prompts.md` and `config/sources.yaml`
- Create Phase 2-only migration file containing only `business_listings` and `deal_scores` from `sql/schema.sql`; add `psycopg2-binary` and wire Postgres insert path
- Add email send module (decision needed: smtplib vs Resend API — see Blocking Decisions)
- Add GitHub Actions cron workflow
- Remove 4 dead dependencies from `requirements.txt`
- Add CSV error handling in `SourcingAgent`
- Add `logging.warning()` for unknown industry fallback
- Add 4+ new tests (reporting, edge cases)

**Entities to spec:**
- `Listing` insert to `business_listings` table — map all dataclass fields to SQL columns
- `ScoreBreakdown` insert to `deal_scores` table — map all fields
- Deduplication logic on `listing_url`

**Constraints to preserve:**
- Do not change `score_listing()` logic — it is correct and tested
- Do not change the `Listing` dataclass field names — they map to CSV column headers
- Keep CLI interface unchanged (`--input`, `--output`, `--min-score` flags)
- Keep markdown report format unchanged (operators may be parsing it)

**Explicitly out of scope for Phase 2 spec:**
- LLM extraction (ExtractionAgent real implementation)
- Source automation (Apify, Bing, Google CSE)
- CRM pipeline (outreach_log, due_diligence_tasks, deal status management)
- Per-industry weights implementation (blocked on architecture decision)

---

## 18. Handoff to O2O

**Build order (must be sequential for dependent items):**

1. **Fix payback bug** (`src/reporting.py:39`) — no dependencies; do this first so all subsequent testing produces correct output.
2. **Add `load_dotenv()`** (`src/main.py`) — required before any env-var-dependent feature can be tested.
3. **Remove dead dependencies** (`requirements.txt`) — no dependencies; clean the surface before adding new packages.
4. **Delete `ExtractionAgent`, `UnderwritingAgent`, `AgentResult`; delete `prompts/agent_prompts.md` and `config/sources.yaml`** — no dependencies; collapse agent delegation in `main.py` to direct function calls before building anything new on top of it.
5. **Add CSV error handling** (`src/agents.py:SourcingAgent`) — required before testing with real marketplace data.
6. **Create Phase 2-only migration file** (business_listings + deal_scores tables only from `sql/schema.sql`); add `psycopg2-binary`; wire Postgres insert path — requires: DB client decision made, `load_dotenv()` done, migration applied to target DB. Do not apply the full 6-table schema.
7. **Add email send module** — requires: email method decision made, `load_dotenv()` done.
8. **Add GitHub Actions cron** — requires: email send and DB insert working in CI environment.
9. **Add tests** (`tests/test_reporting.py`, `tests/test_scoring.py` additions) — can run in parallel with steps 5–7.

**Parallel work (safe to do simultaneously):**
- Steps 3 + 4 can run in parallel
- Step 9 (new tests) can be written in parallel with steps 6–7

**Risky steps requiring human review:**
- Step 5 (DB insert): Verify `DATABASE_URL` points to correct environment before first run. Do not run against a shared DB without testing on a local Postgres instance first.
- Step 7 (GitHub Actions): Add secrets (`DATABASE_URL`, SMTP creds) to GitHub repository settings before the cron fires.

**No circular dependencies found.**

---

## 19. Handoff to QA / Audit

**Critical paths to test:**

1. **Payback row rendering** — run against `examples/sample_listings.csv`; verify "1.5 years" appears, not "if score.payback_years".
2. **Env var loading** — set `MIN_SCORE_TO_REPORT=80` in `.env`; run without `--min-score` flag; verify report uses 80 threshold.
3. **Bad CSV row handling** — add a row with `asking_price=not_a_number`; verify warning logged and other rows scored.
4. **Unknown industry** — add a listing with `industry=dog_grooming`; verify warning logged and `industry_score=75`.
5. **Postgres dedup** — run twice with same CSV; verify `business_listings` row count unchanged on second run.
6. **Email delivery** — trigger manual run in GitHub Actions; verify email received at `rainking6693@gmail.com`.
7. **Full regression** — 6 existing listings → `daily_report.md` → verify Top/Watch/Rejected counts match expected scores.

**Irreversible actions to gate with a test before first production run:**
- Postgres inserts (run against a test DB, not production, for first validation)
- Email send (send to a test address first, not `rainking6693@gmail.com`, until formatting is confirmed)

**There are no payment flows, auth flows, or proof systems to audit in Phase 2.**

---

## 20. Final Architecture Verdict

```
╔══════════════════════════════════════════════════════╗
║  VERDICT: NEEDS_ARCHITECTURE_DECISION                ║
╚══════════════════════════════════════════════════════╝
```

[G7 CHECK: 2 unresolved CRITICAL risks found (no persistence + misleading industry config) — verdict confirmed as NEEDS_ARCHITECTURE_DECISION. Would have been READY_FOR_SPEC for Phase 1 fixes only, but Phase 2 spec cannot begin without the decisions below.]

The Phase 1 scoring engine is production-ready with one bug fix. Phase 2 (persistence + email + scheduler) cannot be specced until two architectural decisions are resolved. One has a strong default; one requires operator input.

### BLOCKING DECISIONS

**Decision 1: Email delivery method** *(no strong default — operator must choose)*

The email must reach `rainking6693@gmail.com` daily. Two viable options:

- **Option A — smtplib (stdlib):** No new dependency. Use `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, App Password in `.env`. Requires enabling "App Passwords" in Google Account. Works offline/locally.
- **Option B — Resend or Brevo API:** Requires `requests` back in requirements.txt + API key. Better deliverability tracking. Requires internet and API key management.

**Recommended:** Option A (smtplib). Zero new dependencies. One operator is not a deliverability concern.

Operator must choose before Phase 2 spec begins.

---

**Decision 2: Per-industry weights — implement or remove** *(strong default exists)*

`config/industry_formulas.yaml` defines 8 sub-weights per industry (e.g., pest_control weights `recurring_revenue: 0.25` vs the global `0.15`). `src/scoring.py` uses a global `MASTER_WEIGHTS` dict and never reads these YAML weights.

- **Option A — Remove from YAML:** Delete `weights`, `ideal_sde_margin` keys from all 10 industries. Global weights stay. Simpler. Current scoring behavior unchanged.
- **Option B — Implement per-industry weights:** Replace `MASTER_WEIGHTS` references in `score_listing()` with `cfg.get("weights", MASTER_WEIGHTS)`. More accurate (a laundromat IS equipment-driven; pest control IS recurring-revenue-driven). Requires testing that existing test assertions still hold.

**Recommended:** Option B (implement). The YAML was clearly designed with intent. A laundromat's SDE margin matters far more than HVAC's. Industry-specific weights improve scoring accuracy and make the system more defensible.

Operator must approve before Phase 2 spec begins.

---

**Non-blocking but must happen before Phase 2 starts (no decision required):**
- Fix payback f-string (`src/reporting.py:39`) — one line
- Add `load_dotenv()` (`src/main.py`) — one line
- Remove 4 dead dependencies from `requirements.txt`
- Choose Postgres host: local Docker or Supabase free tier (either works; Supabase recommended for zero-config access from GitHub Actions)
