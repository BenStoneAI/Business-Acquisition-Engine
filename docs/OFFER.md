# Boring Business Acquisition Radar — Commercial Offer

> **Canonical commercial pricing (2026-09-11).**  
> Source: Plane Sales Catalog + `sales-engine/docs/Product Launch Pricing.md`.  
> Do not invent prices. This product is **distinct from OMST** (Off-Market Succession Targets).

## 1. What is being sold

**Boring Business Acquisition Radar** is a SaaS acquisition radar for finding, scoring, underwriting, and tracking cash-flowing “boring” small businesses — laundromats, HVAC, plumbing, electrical, pest control, commercial cleaning, pool service, car washes, self-storage, roofing.

Per this repo’s `README.md`, the product includes:

- Listing ingest (e.g. marketplace / alert paths)
- Weighted 8-factor scoring with deal-killer checks
- Valuation range and maximum-offer calculation
- Deal packets (“Hit Send” first-contact packages)
- Persistence / score history for tracking

## 2. Pricing — current (canonical)

| Plan | Price | Notes |
|---|---:|---|
| **Monthly** | **$49/mo** | Choose monthly **or** annual |
| **Annual** | **$499/yr** | Choose monthly **or** annual |
| **Assisted setup** | **$250** one-time | **Optional** — not required to run the Radar |

### Distinct from OMST — do not conflate

| Product | What it is | Price (catalog) |
|---|---|---:|
| **Acquisition Radar** (this offer) | Marketplace cash-flow deal scoring / underwriting radar | $49/mo or $499/yr (+ opt $250 setup) |
| **OMST App** | Empty-tenant succession-research app | $299/mo or $2,990/yr |
| **OMST Deal Leads** | Packaged lead inventory | $1,250 / 25 · $4,000 / 100 |

## 3. What is explicitly NOT included

- Guaranteed deal flow, closed acquisitions, or return targets
- OMST succession inventory or OMST App tenancy
- Custom underwriting formula changes outside published product scope (quote separately if needed)
- Live Stripe Payment Links until Ben creates them in Aptria Stripe Dashboard (human gate)

## 4. Checkout path (honesty)

1. Buyer lands on https://aptria.net/radar  
2. Books a call / starts checkout path  
3. Pays on **Aptria Stripe** via Payment Link (monthly, annual, and optional setup) once links exist  
4. Sales Engine sellers use **checkout handoff** (attribution metadata only) — SE **does not** create Stripe Checkout Sessions / Prices / Subscriptions  

Until Payment Links are set in env (`RADAR_STRIPE_PAYMENT_LINK_MONTHLY` / `_ANNUAL` / `_SETUP`), handoff mode is `SANDBOX_CODE_PATH` — no fake live money movement.

## 5. Claims guardrail

Allowed: scoring, deal packets, boring cash-flow verticals, catalog prices above, “not OMST.”

Not allowed: invented ROI, “you will buy a business,” OMST price/lead claims on this SKU, or claiming SE charges the card.

---

*Parent: Plane System: Acquisition Radar. Execution card: AIOPS-118.*
