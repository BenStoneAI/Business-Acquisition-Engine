# Boring Business Acquisition Radar — Seller Kit

Use this kit with `docs/OFFER.md`. Do not invent prices or claims. **Not OMST.**

## One-liner

**Acquisition Radar helps buyers find and underwrite cash-flowing “boring” businesses** — score listings, kill bad deals early, and package the ones worth pursuing.

## SKUs (canonical)

| SKU | Price | When to sell |
|---|---:|---|
| **Radar — Monthly** | **$49/mo** | Default recurring if buyer wants month-to-month |
| **Radar — Annual** | **$499/yr** | Same product, yearly billing |
| **Assisted setup** | **$250** optional | Only if buyer wants Aptria help configuring sources/alerts/workflow |

Sell **monthly or annual**, not both. Setup is additive and optional.

## 30-second explanation

Most acquisition browsers drown in marketplace noise. Radar applies a disciplined 8-factor score, deal-killer checks, and a max-offer frame, then builds a first-contact packet when something clears the bar. It is for cash-flow service and facility businesses — not succession list-building (that is OMST) and not a guarantee you will close a deal.

## Who it is for

- Searchers / operators buying HVAC, pest, laundry, cleaning, and similar cash-flow businesses
- Buyers who want a repeatable underwriting score, not gut feel alone
- People already looking at BizBuySell-style marketplace inventory

## Qualification

- Actively evaluating cash-flow acquisitions (or starting within weeks)
- Understands this is software + optional setup — not a managed deal desk
- Can choose monthly **or** annual billing

## Disqualification

- Wants OMST succession leads / empty-tenant OMST App (sell the correct OMST SKU)
- Expects guaranteed deal volume or closed acquisitions in the price
- Asks you to invent a different price than the catalog

## Demo

Assisted walkthrough by appointment. Point at the public product page: https://aptria.net/radar  
Engineering: https://github.com/BenStoneAI/Business-Acquisition-Engine

## Prohibited promises

- Do not quote OMST prices ($299/mo, $2,990/yr, lead packages) as Radar
- Do not invent prices other than $49/mo, $499/yr, optional $250 setup
- Do not claim Sales Engine charges the card — Aptria Stripe does
- Do not promise ROI, closed deals, or “we find you a business”

## Fulfillment (high level)

1. Qualify + confirm monthly vs annual (+ optional setup)  
2. Seller opens **Checkout Handoff** in Sales Engine (attribution only)  
3. Buyer pays on Aptria Stripe Payment Link when live  
4. Webhook → SE cash_events → accruals (after commission plans exist) → settlement  
5. Provision access / optional assisted setup per written scope  

## Checkout honesty

Live Payment Links are a **human gate** until Ben creates them and sets:

- `RADAR_STRIPE_PAYMENT_LINK_MONTHLY`
- `RADAR_STRIPE_PAYMENT_LINK_ANNUAL`
- `RADAR_STRIPE_PAYMENT_LINK_SETUP`

Empty env → handoff returns `SANDBOX_CODE_PATH` (no fake charge).

## Pricing approval reference

- **Reference:** Plane Sales Catalog / AIOPS-118 (2026-09-11)  
- **Canonical file:** `docs/OFFER.md`  
- **Catalog mirror:** `sales-engine/docs/Product Launch Pricing.md`
