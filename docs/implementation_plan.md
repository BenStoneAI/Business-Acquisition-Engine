# Implementation Plan

## Phase 1 — Working Daily Radar

Goal: produce a useful daily email report without building a huge app first.

Tasks:

1. Create a saved-search library for each target industry and source.
2. Ingest listings from CSV, saved-search emails, or broker exports.
3. Normalize listings into the `Listing` schema.
4. Score every listing with `src/scoring.py`.
5. Store listings and scores in Postgres.
6. Generate daily markdown report.
7. Send report to `rainking6693@gmail.com` at 6 AM Mountain.

Minimum report sections:

* Top 5-10 deals
* Watchlist
* Rejected/pass
* Owner-financing alerts
* Retiring-owner alerts
* Utah/Mountain West alerts
* Recommended next action

## Phase 2 — Source Automation

Goal: reduce manual collection.

Use compliant source methods in this order:

1. Marketplace saved-search email alerts.
2. Broker email alerts.
3. Google/Bing Search API queries.
4. Apify/browser actors after terms/robots review.
5. Direct broker relationship feeds.

Do not hard-code brittle scrapers into the scoring engine. Keep all source connectors replaceable.

## Phase 3 — Deal CRM

Add:

* Deal status pipeline
* Broker contact table
* Outreach log
* Follow-up reminders
* NDA/CIM tracking
* Due-diligence checklist generation

Pipeline stages:

1. New
2. Scored
3. Request Info
4. NDA Sent
5. CIM Received
6. Underwriting
7. LOI Draft
8. LOI Sent
9. Due Diligence
10. Closed / Passed

## Phase 4 — Document Intelligence

Add parsing for:

* CIM PDFs
* tax returns
* P\&Ls
* bank statements
* payroll reports
* equipment lists
* leases
* customer reports

Output:

* verified SDE
* add-back quality
* revenue trend
* margin trend
* customer concentration
* owner dependency
* financing risk

## Phase 5 — Post-Acquisition Operating System

Once a deal is acquired, convert the platform into an operating cadence:

* cash dashboard
* weekly KPI dashboard
* call tracking
* CRM/dispatch review
* pricing review
* review/reputation campaign
* maintenance-plan growth
* accounting cleanup
* controls and fraud checks
* employee retention check-ins

## Production Architecture

Recommended stack:

* Backend: FastAPI or NestJS
* Database: Postgres / Supabase
* Queue: Redis + BullMQ or Celery
* Source workers: Playwright/Apify/Search APIs
* AI extraction: OpenAI/Claude structured JSON
* Dashboard: React/Next.js
* Email: Gmail API or Resend
* Orchestration: n8n or scheduled worker

## Non-Negotiable Rules

1. Do not trust listing SDE without verification.
2. Penalize missing data.
3. Reject seller refusal to provide tax returns.
4. Never use asking price as value.
5. Always calculate maximum supportable offer.
6. Always check owner dependency.
7. Always check lease/real estate control.
8. Always identify why the seller is selling.
9. Always separate business value from real estate value.
10. Always generate next action, not just a score.

