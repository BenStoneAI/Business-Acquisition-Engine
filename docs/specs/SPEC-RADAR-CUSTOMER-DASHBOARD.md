# SPEC-RADAR-CUSTOMER-DASHBOARD

**Status:** SPEC LOCK — written 2026-09-15; no UI implementation authorised by this document  
**Product:** Acquisition Radar by Aptria *(formerly Boring Business Acquisition Radar)* — see `docs/OFFER.md` and `docs/aptria-master/specs/B-PRODUCT-CATALOG-AND-TERMINOLOGY.md` (B-P07)  
**Parent plan:** `C:\Users\Work\Desktop\GitHub\docs\aptria-master\MASTER-PLAN.md` (AIOPS-162) · Wave 3 item 8 in Spec I  
**Sister spec:** `Off-Market Succession Targets/docs/specs/SPEC-OMST-CUSTOMER-DASHBOARD.md` — this document deliberately mirrors its shape so both radars are built against the same customer-plane rules  
**Storefront page pattern:** P2 "Live surface" (Spec D §D6, copy in Spec E §E5.7)  
**Portal action when built:** "Open Acquisition Radar" from portal.aptria.net My Products (Spec H H-P04 pattern, same signed handoff as H-P08)

---

## 1. Purpose

Define the **customer-facing dashboard product contract** for Acquisition Radar so a later implementation builds the right surfaces on a **customer data plane**, without touching the operator pipeline that runs today.

Goals:

1. A paying customer sees **their** matched opportunities, watchlist, deals, packets, alerts and settings — scored by the same 8-factor engine Ben uses, filtered by **their** criteria.
2. A **fresh tenant** with no criteria sees the setup wizard; a tenant with criteria and no matches yet sees an honest "radar is running, nothing has cleared your threshold" state — never Ben's `Deals/` folders, never his Telegram, never his saved-search mailbox.
3. The dashboard is the thing that turns "a private, single-operator tool" (`README.md`, line 1) into the "SaaS acquisition radar" `docs/OFFER.md` already sells. Until it exists the storefront chip stays **Early access** and the delivery promise is "we run it for you and send the results" (Spec B §B4).
4. This document is the UI/API contract. It is **not** an authorisation to write React screens, provision databases, or change `src/scoring.py`.

Commercial note: the dashboard is part of the Acquisition Radar subscription ($49/month or $499/year, optional $250 setup). It is **not** OMST, not Succession Radar, and never shows OMST inventory or Deal Leads.

---

## 2. Architecture

### 2.1 What exists today (the operator plane)

| Component | File | Customer-plane consequence |
|---|---|---|
| Nightly ingest of BizBuySell owner-financed alert emails via IMAP, 7-day window, dedup by `listing_url` | `src/ingest_bizbuysell.py`, `src/imap_fetch.py`, `src/run_state.py` | Listings are **public marketplace data**. They can be pooled and shared across tenants. What is private is each tenant's criteria, matches, watchlist, deal state, notes and packets. |
| Seller-financing screen: keep `full` / `possible` / `majority_carry` (≥ 50%) | `src/financing_filter.py` | Becomes a **per-tenant setting** (financing floor) applied at match time, not at ingest. |
| 8-factor weighted score, deal killers, valuation range, max offer, bucket, next action | `src/scoring.py`, `src/models.py` (**DO NOT CHANGE LOGIC OR FIELD NAMES**) | Score is deterministic from listing data + `config/industry_formulas.yaml`, so one `deal_scores` row per listing per run serves every tenant. No per-tenant scoring. |
| Persistence: `business_listings` (dedup on `listing_url`), `deal_scores` (append per run) in Supabase `radar` schema | `src/db.py`, `sql/migrations/phase2_*.sql` | These two tables become the **shared listing pool** (read-only from customer APIs). Four Phase 3 tables (`broker_contacts`, `outreach_log`, `due_diligence_tasks`, `source_history`) are still unapplied. |
| Telegram alert (deals cleared threshold), heartbeat (nothing cleared), failure alert | `src/notifier.py` | Operator-only. Customers get their own alert channel (§2.4). |
| "Hit Send" packet: deal summary, decision, thesis, outreach email, credibility blurb, top-10 questions, document request, 3 financing structures, preliminary valuation (screening-only), risk notes, NDA request, LOI skeleton, follow-ups (days 3/7/21/42/70), `Deals/<Business>/01…08` folder with `listing.json`, DD checklist, `.ics` | `src/response_engine.py`, `src/interested.py` | Packet generation is deterministic templating and can run per tenant. Output moves from a folder on Ben's machine to **rows + rendered markdown per tenant**. The `--send` broker email path is **operator-only**; customers copy the email, they do not send through Aptria. |
| Deal lifecycle stages `contacted → nda → cim → loi → dd → closing → closed / dead` | `src/deal.py` | Per-tenant deal state. |
| Re-underwrite with verified CIM numbers | `src/rescore.py` | Per-tenant rescore inputs; new score row scoped to the tenant's deal, not to the shared listing. |
| Price-drop re-alert (≥ 5%) | `src/run_state.py` | Shared detection; per-tenant alert delivery. |
| Live-data enrichment (contact finder, reputation, public records) | assistant-driven, not code | **Not a customer feature.** Not promised on any page. |
| No web framework, no auth, no payments, GitHub Actions cron 12:00 UTC + Windows Task Scheduler | `CLAUDE.md` Tech Stack | Everything in §2.3–2.4 is **new**. |

### 2.2 Data binding rule

Every customer dashboard read/write goes through the **customer plane**:

| Layer | Requirement |
|---|---|
| Env | `CUSTOMER_DATABASE_URL` for tenant tables. The shared listing pool is reached through a **read-only role** (`RADAR_POOL_READONLY_URL`). The operator CLI keeps `DATABASE_URL` untouched. |
| Tenant scope | Phase 1: `X-Tenant-Id` header (parity with OMST `apps/api/tenant.py`). Before public launch: signed handoff token from portal.aptria.net (Spec H H-P08 pattern) exchanged for a session; `X-Tenant-Id` alone is never accepted from the public internet. |
| Forbidden | Any customer path that reads `data/ingest_state.json`, `Deals/`, `Daily Runs/`, Ben's IMAP/SMTP/Telegram env vars, or writes to `business_listings` / `deal_scores`. |
| Isolation | Every tenant table carries `tenant_id`; every query is scoped; cross-tenant IDs return 404, never 403 with a hint. |

If `CUSTOMER_DATABASE_URL` is unset or points at the operator database fingerprint, the API refuses to start (`DataPlaneError`) and the dashboard shows a configuration error — never Ben's data.

### 2.3 Required surfaces

Names follow `MasterDesignAptriaProducts.md` §35 (Radar · Opportunities · Watchlist · Deal Packets · Alerts · Settings) plus Deals, which the repo's lifecycle already supports. Each surface is tenant-scoped.

| Surface | Job | Reads | Fresh-tenant behaviour |
|---|---|---|---|
| **Setup wizard** (first run) | Collect geography (states / metros / radius), industries (from `config/industry_formulas.yaml` display names; the 10 target verticals pre-checked, 4 off-thesis unchecked), asking-price range, SDE range, financing floor (`full` only / `full + possible` / `majority carry ≥ 50%`), score threshold (default 80 = "Strong candidate"), alert channel (email always; Telegram optional), then run a **test match** against the pool and show the count. | pool (read-only), tenant settings | Wizard is the only screen until criteria are saved. |
| **Radar** (home) | Since-last-visit summary: new matches, strong scores (≥ 90), price drops, seller-financing signals (full carry), last run time and next scheduled run, "nothing cleared your threshold since {date}" when true. | `tenant_matches`, `deal_scores`, run metadata | All zeros; shows last pool run time so the customer knows the radar is alive. |
| **Opportunities** | Table of matched listings: business, industry, location, asking, SDE, score, bucket, financing status, max offer, listing age, source. Filters mirror the wizard. Sort by score, asking, age. | `tenant_matches` ⋈ pool | "No matches yet. Your criteria: … Widen them?" |
| **Opportunity detail** | Listing facts (all `business_listings` fields the customer is allowed to see), full score breakdown (8 factors, bonus, deal-killer penalty), valuation range, max-offer logic shown as the four constraints (SDE × multiple, DSCR 1.75×, cash-on-cash > 25%, payback < 4 yrs) with which one bound, red flags, next action, price history, financing status. Actions: Watch · Mark interested (creates a Deal + packet) · Hide. | pool, `deal_scores` history for that listing | 404 for any listing not matched to this tenant, even if it exists in the pool. |
| **Watchlist** | Watched opportunities with notes, priority, next action, price-drop badge. | `tenant_watchlist` | Empty state. |
| **Deals** | Pipeline: stage (`contacted … dead`), value, last activity, next follow-up date (from the 3/7/21/42/70 cadence), rescore status. Stage changes write `tenant_deal_stage_history`. | `tenant_deals` | Empty state. |
| **Deal packet** | Rendered "Hit Send" package for one deal: summary, decision, thesis, outreach email (copy button; **no send**), credibility blurb (tenant's own, from Settings), top questions, document request, financing structures (labelled internal-only pre-CIM), preliminary valuation (labelled screening-only until rescored), risk notes, NDA request, LOI skeleton, follow-up dates, DD checklist. Download as markdown and `.ics`. | `tenant_packets` | — |
| **Rescore** (inside a deal) | Enter verified SDE / revenue / asking from the CIM; see the new score, valuation and max offer beside the screening numbers; packet re-renders. | `tenant_rescores` | — |
| **Alerts** | Channel settings (email to the account email; Telegram chat ID optional), digest vs immediate, threshold, price-drop alerts on/off; alert history. | `tenant_alert_prefs`, `tenant_alert_log` | Email on, immediate, threshold from wizard. |
| **Settings** | Everything from the wizard, plus buyer profile used in packets (name, entity, credibility blurb, target close timeline), and account/plan (read-only, link to portal Billing). | tenant settings | Pre-filled from wizard. **No connection strings, no mailbox credentials, no operator fields.** |

### 2.4 API contracts (customer plane; all require tenant context)

| Contract | Dashboard use |
|---|---|
| `POST /customer/tenants` (portal-initiated at purchase) | Create tenant; returns tenant id |
| `GET/PUT /customer/settings` | Wizard + Settings |
| `POST /customer/settings/test-match` | Wizard test feed: count + top 5 |
| `GET /customer/radar/summary?since=` | Radar home |
| `GET /customer/opportunities?filters…` | Opportunities table |
| `GET /customer/opportunities/{listing_id}` | Detail (404 if not matched to tenant) |
| `POST /customer/opportunities/{listing_id}/watch` · `DELETE …/watch` | Watchlist |
| `POST /customer/opportunities/{listing_id}/hide` | Hide |
| `POST /customer/opportunities/{listing_id}/interested` | Creates deal + packet (calls `build_response_package` with the tenant's buyer profile) |
| `GET /customer/deals` · `GET /customer/deals/{id}` · `POST /customer/deals/{id}/stage` | Pipeline |
| `POST /customer/deals/{id}/rescore` | Rescore |
| `GET /customer/deals/{id}/packet.md` · `…/followups.ics` | Downloads |
| `GET/PUT /customer/alerts` · `GET /customer/alerts/log` | Alerts |
| `GET /customer/runs/latest` | "Radar last ran at …" |

Operator-only, never exposed to customers: ingest triggers, pool writes, `--send` outreach, Telegram operator alerts, enrichment.

### 2.5 Matching model (the one new piece of logic)

A nightly **match job** runs after ingest: for every tenant with saved criteria, select pool listings where industry ∈ tenant industries, location within geography, asking within range, SDE within range, financing status ≥ tenant floor, latest `deal_scores.total_score` ≥ tenant threshold → upsert `tenant_matches(tenant_id, listing_id, matched_at, first_seen_score, last_score)`. Price drops and score changes on already-matched listings raise alerts per tenant prefs. Matching **does not rescore**; it filters.

### 2.6 Explicit non-surfaces (different products or operator-only)

| Not in this dashboard | Why |
|---|---|
| OMST companies, succession scores, Deal Leads packs | Different products (Succession Radar / Deal Leads) |
| Sending outreach email from Aptria | `--send` is operator-only; liability and deliverability. Customers copy the draft. |
| Live-data enrichment (contact finder, reputation, SoS/UCC) | Assistant-driven, not automatable; not promised on any page |
| Ben's `Deals/`, `Daily Runs/`, `data/ingest_state.json`, operator Telegram | Operator plane |
| Adding new listing sources (BizQuest, DealStream) | Needs parsers; separate card |
| Custom scoring weights per customer | Hard constraint 1 (`score_listing()` untouchable) |

### 2.7 Prerequisites before UI implementation

| Prerequisite | Status |
|---|---|
| This spec locked; Spec B B4 chip stays Early access until §3 passes | This document |
| Multi-tenant schema migration (`tenants`, `tenant_criteria`, `tenant_matches`, `tenant_watchlist`, `tenant_deals`, `tenant_deal_stage_history`, `tenant_packets`, `tenant_rescores`, `tenant_alert_prefs`, `tenant_alert_log`) + read-only pool role | **Not written** |
| Customer database provisioned (separate from operator DB) | **Not provisioned** |
| Web API + web app scaffolding — repo has no web framework. Decision: reuse the OMST pattern (Python API + React/Vite in `apps/api`, `apps/web`) so both radars share tenant middleware, auth handoff and UI kit (Spec D tokens, P2 conventions) | **Not started** |
| Match job (§2.5) with tests | **Not written** |
| Portal signed handoff (Spec H H-P08 pattern) | **Depends on portal work** |
| Alert delivery per tenant (email via existing SMTP relay; Telegram via customer-supplied chat ID) | **Not written** |
| Payment Links live (AIOPS-130 says yes; `docs/OFFER.md` §3 still says pending — update OFFER.md) | **Doc drift to fix** |
| Storefront `/acquisition-radar` on P2 with Spec E §E5.7 copy | Wave 2 |
| README/OFFER retitled to match reality (Spec H H-A10) | **Open** |

Do not build dashboard UI until the schema migration and customer database are locked. After lock, implementation is a separate Plane card under the Acquisition Radar system — not this spec card.

---

## 3. Acceptance criteria

| ID | Criterion | Proof |
|---|---|---|
| **RD-01** | Fresh tenant with no criteria sees only the setup wizard; with criteria and no matches sees "no matches yet" with last pool run time | Playwright screenshot of both states on a new tenant |
| **RD-02** | Customer APIs use the customer plane and the read-only pool role only | Route audit: no customer path imports `db.persist_scored_listings`, `imap_fetch`, `notifier.send_telegram`, or reads `Deals/` |
| **RD-03** | Tenant A cannot list, watch, or open Tenant B's matches, deals, packets or settings | Isolation test: cross-tenant IDs → 404; parity with OMST `test_fresh_customer_tenant_is_empty_and_isolated` |
| **RD-04** | Scores shown to customers equal `score_listing()` output for the same listing; no per-tenant scoring path exists | Unit test compares API payload to `ScoreBreakdown` for 20 sample listings |
| **RD-05** | Opportunity detail shows the four max-offer constraints and which one bound the offer | Screenshot + assertion on payload fields `estimated_max_offer`, constraint values |
| **RD-06** | Packet content for a tenant deal equals `render_package_markdown()` output with the tenant's buyer profile substituted; no operator identity leaks | Golden-file test with a fake tenant profile; grep for Ben's name/email/phone = 0 |
| **RD-07** | Rescore writes a tenant-scoped score row and never mutates the shared `deal_scores` row | DB assertion after rescore |
| **RD-08** | Alerts go only to the tenant's configured channels; operator Telegram receives nothing tenant-specific | Alert log rows + operator chat unchanged during test |
| **RD-09** | Settings never expose mailbox, IMAP, SMTP, Telegram bot token, or database fields | UI + API contract review |
| **RD-10** | Match job is idempotent and a re-run creates no duplicate `tenant_matches` | Run twice, count unchanged |
| **RD-11** | Operator pipeline (`python -m src.ingest_bizbuysell`, `src.main`, `src.interested`, `src.rescore`, `src.deal`) and all 93 tests are unaffected | `pytest` green; CLI smoke unchanged |
| **RD-12** | This SPEC exists, forbids UI build under its own card, and lists blockers honestly | Spec present; §2.7 |
| **RD-13** | Storefront chip flips to "Available now" only after RD-01…RD-11 pass and portal "Open Acquisition Radar" lands an entitled test user in their tenant | Evidence folder `docs/aptria-master/evidence/journeys/J-BUY-acquisition-radar/` |

---

## 4. Do not break

| Protected asset | Rule |
|---|---|
| `src/scoring.py` `score_listing()` | Untouched. Customers get the same score Ben gets. |
| `src/models.py` `Listing` field names | Untouched; CSV headers and `business_listings` columns depend on them. |
| CLI flags `--input`, `--output`, `--min-score`, `--all-financing` | Unchanged. |
| Operator ingest, Telegram heartbeat semantics ("silence means broken") | Customer alerts are additive; operator heartbeat still fires. |
| `business_listings` / `deal_scores` | Customer plane is read-only against them. |
| Phase 3 tables | Stay unapplied unless a migration card applies them; the tenant schema is a **new** migration, not a repurposing. |
| `docs/OFFER.md` claims guardrail | No invented ROI, no "you will buy a business", no OMST claims on this SKU. Dashboard copy follows Spec E §E5.7. |

---

## 5. Out of scope (for the spec card)

- Any dashboard UI or API implementation.
- Schema migration authoring (separate card; this spec names the tables).
- Provisioning the customer database.
- New listing sources or parsers.
- Automating enrichment.
- Sending broker email on a customer's behalf.
- Changing prices ($49/mo · $499/yr · $250 setup are canonical, Spec B).

---

## 6. Related work

| Item | Relation |
|---|---|
| `docs/aptria-master/MASTER-PLAN.md` (AIOPS-162) | Parent plan; Spec I Wave 3 item 8 schedules the build |
| Spec H H-A10 | Retitle README/OFFER; define the interim "we run it for you" delivery |
| Spec E §E5.7 | Storefront copy and the honest interim framing |
| AIOPS-118 | Radar offer + seller kit (commercial) |
| AIOPS-130 | Payment Links live for Radar monthly/annual/setup |
| `SPEC-OMST-CUSTOMER-DASHBOARD.md` | Sister contract; shared tenant middleware and UI kit |
| `docs/SALES_KIT.md` | Seller-facing description; must not outrun §2.3 |

---

## 7. Definition of done for this SPEC

- [x] Spec written at `docs/specs/SPEC-RADAR-CUSTOMER-DASHBOARD.md` (uncommitted; commit when Ben asks).
- [ ] Linked from the Acquisition Radar Plane card and from `docs/aptria-master/specs/H-PROPERTY-IMPLEMENTATION-REQUIREMENTS.md` H-A10.
- [ ] **Zero** dashboard code shipped under the spec card.
- [ ] Remaining blockers listed in §2.7 carried into the implementation card, not papered over.
