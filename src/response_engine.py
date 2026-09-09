from __future__ import annotations

"""Acquisition Response Engine (second layer).

Turns a single "Interested" decision into a complete first-contact package so
the operator only ever decides two things: interested/not, and send/don't send.
Everything in between — outreach email, credibility blurb, deal thesis, seller
questions, tailored document request, 2-3 financing structures, LOI skeleton,
valuation, risk notes, follow-ups, NDA request, deal folder, CRM status,
calendar reminder, and a decision classification — is generated here.

All generation is deterministic templating over the scored `Listing`, so the
output is reproducible and testable. No external calls happen in this module;
delivery (Gmail draft) and live-data enrichment are separate, opt-in layers.
"""

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

from .financing_filter import financing_status, FULL, MAJORITY
from .models import Listing, ScoreBreakdown
from .reporting import money, pct
from .scoring import normalized_industry_key

# --- Buyer profile (set BUYER_NAME / BUYER_EMAIL / BUYER_CREDIBILITY in .env to
# customize every generated document for your own installation) ---------------

BUYER_NAME = os.environ.get("BUYER_NAME", "Your Name Here")
BUYER_EMAIL = os.environ.get("BUYER_EMAIL", "you@example.com")
BUYER_CREDIBILITY = os.environ.get(
    "BUYER_CREDIBILITY",
    "A qualified buyer looking to acquire a durable, service-based local business "
    "with strong cash flow, fair seller financing, and a smooth transition plan "
    "that protects employees, customers, and the seller's legacy.",
)


@dataclass
class FinancingOption:
    name: str
    price: str
    down_payment: str
    seller_note: str
    rate: str
    term: str
    extra: str = ""


@dataclass
class ResponsePackage:
    listing: Listing
    score: ScoreBreakdown
    deal_summary: str
    email_subject: str
    email_body: str
    credibility_blurb: str
    deal_thesis: str
    top_questions: List[str]
    document_requests: List[str]
    financing_options: List[FinancingOption]
    loi_skeleton: str
    preliminary_valuation: str
    risk_notes: List[str]
    followup_1: str
    followup_2: str
    followup_3: str
    followup_4: str
    followup_5: str
    nda_request: str
    crm_status: str
    calendar_reminder: str
    decision: str
    deal_folder_layout: List[str] = field(default_factory=list)


# --- Industry-tailored document requests --------------------------------------

_BASE_DOCS = [
    "3 years of tax returns",
    "3 years of P&Ls",
    "Trailing 12-month P&L",
    "Current balance sheet",
    "Bank statements (12 months)",
    "Payroll reports",
    "Customer concentration report",
    "Employee roster (roles, tenure, licenses)",
    "Lease agreement (or real estate terms)",
    "Equipment / FF&E list",
    "Debt schedule",
    "Licenses and permits",
    "Insurance claims history",
    "Vendor contracts",
    "AR/AP aging",
    "Owner add-back schedule",
]

_INDUSTRY_DOCS = {
    "hvac": [
        "License holder details", "Technician roster", "Service contract list",
        "Maintenance agreements", "Warranty claims", "Fleet list",
        "Dispatch/CRM reports", "Backlog", "Gross margin by job type",
    ],
    "plumbing": [
        "License holder details", "Technician roster", "Service contract list",
        "Maintenance agreements", "Warranty claims", "Fleet list",
        "Dispatch/CRM reports", "Backlog", "Gross margin by job type",
    ],
    "electrical": [
        "License holder details", "Technician roster", "Service contract list",
        "Maintenance agreements", "Warranty claims", "Fleet list",
        "Dispatch/CRM reports", "Backlog", "Gross margin by job type",
    ],
    "laundromat": [
        "Machine list and age", "Lease and renewal options", "Utility bills",
        "Card/cash revenue split", "Repair history", "Wash/dry/fold revenue",
        "Rent-to-revenue ratio", "Equipment debt",
    ],
    "commercial_cleaning": [
        "Route/account list", "Customer churn", "Contract renewal dates",
        "Employee/crew roster", "Vehicle/equipment list",
        "Monthly recurring revenue", "Top 10 customers",
    ],
    "pool_service": [
        "Route list", "Customer churn", "Contract renewal dates",
        "Employee/crew roster", "Vehicle/equipment list",
        "Monthly recurring revenue", "Top 10 customers",
    ],
    "pest_control": [
        "Route list", "Customer churn", "Contract renewal dates",
        "Employee/crew roster", "Vehicle/equipment list",
        "Monthly recurring revenue", "Top 10 customers", "Applicator licenses",
    ],
}


# Thin aliases over reporting.money/pct: packages label missing values "TBD"
# (treating 0 as missing) and render percentages with 0 decimals.
def _money(value: Optional[float]) -> str:
    return money(None if value in (None, 0) else value, none_label="TBD")


def _pct(value: Optional[float]) -> str:
    return pct(value, none_label="unknown", decimals=0)


def _proposed_price(listing: Listing, score: ScoreBreakdown) -> Optional[float]:
    # Anchor on the disciplined max offer, but never propose above the asking price.
    candidates = [p for p in (score.estimated_max_offer, listing.asking_price) if p]
    return min(candidates) if candidates else None


def document_requests(listing: Listing) -> List[str]:
    return _BASE_DOCS + _INDUSTRY_DOCS.get(normalized_industry_key(listing.industry), [])


def financing_options(listing: Listing, score: ScoreBreakdown) -> List[FinancingOption]:
    price = _proposed_price(listing, score)
    if not price:
        pstr = "the agreed purchase price"
        note_a = "the full purchase price"
        down_b = "10% of price"
        note_b = "90% of price"
    else:
        pstr = _money(price)
        note_a = f"{_money(price * 0.95)}–{_money(price)}"
        down_b = _money(price * 0.10)
        note_b = _money(price * 0.90)

    return [
        FinancingOption(
            name="Option A — Full Seller Carry",
            price=pstr,
            down_payment="$0–$10,000",
            seller_note=note_a,
            rate="6%–8%",
            term="5–7 years, monthly payments",
            extra="Transition: 90–180 days of owner training/support.",
        ),
        FinancingOption(
            name="Option B — Small Down + Seller Note",
            price=pstr,
            down_payment=down_b,
            seller_note=note_b,
            rate="6%–8%",
            term="5 years, monthly payments",
        ),
        FinancingOption(
            name="Option C — Performance-Protected Offer",
            price=pstr,
            down_payment="5%–10% of price",
            seller_note="70%–80% of price",
            rate="6%–8%",
            term="5 years",
            extra="Earnout/holdback of 10%–20% tied to retained revenue "
                  "through the transition.",
        ),
    ]


def top_questions(listing: Listing) -> List[str]:
    return [
        "Would the seller consider a full or majority seller-financed structure "
        "for a qualified buyer?",
        "How many hours per week does the owner actually work, and in what role?",
        "Can you share 3 years of tax returns, P&Ls, and a trailing-12 P&L?",
        "What add-backs make up the stated SDE / cash flow?",
        "What percentage of revenue is recurring or under contract?",
        "What is the largest single customer as a % of revenue?",
        "Are the key employees and any license holders expected to stay?",
        "What are the lease terms, or is real estate included?",
        "What equipment or fleet replacement is expected in the next 24 months?",
        "Why is the owner selling now, and what does a good transition look like "
        "to them?",
    ]


def risk_notes(listing: Listing, score: ScoreBreakdown) -> List[str]:
    notes = list(score.red_flags)
    if listing.owner_hours_per_week and listing.owner_hours_per_week > 40:
        notes.append("Owner works long hours — confirm the business is not "
                     "dependent on the owner personally.")
    if listing.recurring_revenue_pct is None:
        notes.append("Recurring revenue % not disclosed — verify before valuing.")
    if listing.customer_concentration_pct is None:
        notes.append("Customer concentration not disclosed — request top-10 report.")
    if normalized_industry_key(listing.industry) in {"hvac", "plumbing", "electrical", "pest_control"}:
        notes.append("License-dependent trade — confirm who holds the license and "
                     "whether it transfers or stays with an employee.")
    return notes or ["No obvious deal-killers from listing data; verify in diligence."]


def decision_for(score: ScoreBreakdown) -> str:
    if score.red_flags and score.total_score < 80:
        return "Ask for more info / need accountant review before pursuing."
    if score.total_score >= 90:
        return "Pursue now — contact broker today."
    if score.total_score >= 80:
        return "Pursue — request financial package and confirm financing."
    if score.total_score >= 70:
        return "Watchlist — request the missing data points."
    return "Pass unless terms or financials improve."


def deal_thesis(listing: Listing, score: ScoreBreakdown) -> str:
    fin = financing_status(listing)
    if fin == FULL:
        fin_line = "explicitly advertises 100% seller financing"
    elif fin == MAJORITY:
        fin_line = "advertises a majority (≥50%) seller carry with room to negotiate up"
    else:
        fin_line = "leaves the door open to full seller financing"
    return (
        f"{listing.business_name} is an established {listing.industry} business in "
        f"{listing.location} generating {_money(listing.sde)} of owner cash flow on "
        f"{_money(listing.revenue)} of revenue (cash-flow yield {_pct(score.cash_flow_yield)}). "
        f"It scores {score.total_score}/100 ({score.bucket}) on the underwriting "
        f"model and {fin_line}, which fits the strategy of acquiring durable, "
        f"service-based cash flow with little or no bank debt. The thesis: keep the "
        f"team and customers intact through a seller-supported transition, tighten "
        f"financial controls and marketing, and service the seller note out of "
        f"existing cash flow."
    )


def _first_name(broker: Optional[str]) -> str:
    if not broker:
        return "there"
    return broker.strip().split()[0]


def outreach_email(listing: Listing, score: ScoreBreakdown) -> tuple[str, str]:
    broker = listing.raw.get("broker_name") if listing.raw else None
    subject = f"Interest in {listing.business_name} — {listing.location}"
    body = f"""Hi {_first_name(broker)},

I saw the listing for {listing.business_name} in {listing.location} and would
like to learn more. It caught my attention because it appears to be an
established {listing.industry} business with durable, essential-service demand
and the possibility of seller financing.

I'm looking for a durable service business where the owner cares about a smooth
transition for employees, customers, and the legacy of the company.

Could you send the NDA/CIM if available, and clarify whether the seller would
consider a full or majority seller-financed structure for a qualified buyer?

I'd also like to understand:
- The owner's weekly role
- Three-year financial history
- Customer concentration
- Employee and license-holder retention expectations
- Equipment/fleet included
- Transition and training support

A bit about me: {BUYER_CREDIBILITY}

Best,
{BUYER_NAME}
{BUYER_EMAIL}"""
    return subject, body


def followups(listing: Listing) -> tuple[str, str, str, str, str]:
    """Five touches over ~10 weeks (days 3/7/21/42/70) — Main-Street broker
    responsiveness is slow and persistence wins (2026-07-19 cadence change)."""
    f1 = f"""Hi,

Following up on my note about {listing.business_name}. I'm a serious,
financing-ready buyer and happy to sign an NDA to review the CIM and financials.
Is the listing still active, and would the seller entertain a seller-financed
offer? Glad to jump on a quick call.

Best,
{BUYER_NAME}"""
    f2 = f"""Hi,

Circling back on {listing.business_name}. Still interested and financing-ready.
If it's easier, happy to start with a 15-minute call at whatever time suits you.

Thanks,
{BUYER_NAME}"""
    f3 = f"""Hi,

I wanted to ask one specific question about {listing.business_name}: roughly
what share of revenue comes from repeat or contracted customers? That single
number tells me whether this is the kind of durable business I'm looking for —
and if it is, I can move quickly on the NDA and financials.

Best,
{BUYER_NAME}"""
    f4 = f"""Hi,

Following up on {listing.business_name}. Since my first note I've had my
financing approach reviewed — I'm prepared to structure around a seller note
with meaningful protections for the seller (market rate, personal guarantee
discussable, clean transition plan). If the seller is still weighing options,
I'd welcome the chance to make a concrete proposal after seeing the financials.

Best,
{BUYER_NAME}"""
    f5 = f"""Hi,

Last note from me on {listing.business_name} — if the timing isn't right, no
problem at all. I'd appreciate you keeping me in mind if the seller's plans
firm up or if similar seller-financed opportunities come across your desk.
I'm a patient, serious buyer in this space.

Thanks,
{BUYER_NAME}"""
    return f1, f2, f3, f4, f5


def nda_request(listing: Listing) -> str:
    return (
        f"Please send the NDA and CIM for {listing.business_name}. I'm ready to "
        f"sign electronically today so we can move to reviewing financials."
    )


def loi_skeleton(listing: Listing, score: ScoreBreakdown) -> str:
    price = _proposed_price(listing, score)
    low = score.estimated_value_low
    high = score.estimated_value_high
    price_range = (f"{_money(low)}–{_money(high)}" if low and high else _money(price))
    return f"""NON-BINDING INDICATION OF INTEREST (draft — attorney review required)

Buyer: {BUYER_NAME}
Business / Seller: {listing.business_name} ({listing.location})
Proposed purchase price range: {price_range}
Proposed structure: Seller financing (see financing options A–C)
Due diligence period: 45 days from acceptance
Transition period: 90–180 days of seller training/support
Exclusivity: 30 days
Confidentiality: mutual NDA in place
Conditions to close: satisfactory review of financials, verification of SDE
  add-backs, lease/real-estate terms, license transfer, and employee retention.

This is a non-binding indication of interest only and does not create a binding
obligation on either party. A formal LOI will follow attorney review."""


def preliminary_valuation(listing: Listing, score: ScoreBreakdown) -> str:
    return (
        f"Asking: {_money(listing.asking_price)} | SDE: {_money(listing.sde)} | "
        f"Cash-flow yield: {_pct(score.cash_flow_yield)}\n"
        f"Screening value range: {_money(score.estimated_value_low)}–"
        f"{_money(score.estimated_value_high)}\n"
        f"Disciplined max offer: {_money(score.estimated_max_offer)}\n"
        f"Estimated equity payback: "
        f"{f'{score.payback_years:.1f} years' if score.payback_years else 'unknown'}\n"
        f"NOTE: screening estimate from unverified listing-ad numbers — never "
        f"anchor a real offer on it. Superseded by `python -m src.rescore` "
        f"once CIM/tax-return figures are in hand."
    )


DEAL_FOLDER_LAYOUT = [
    "01 Listing", "02 Financials", "03 Legal", "04 Operations",
    "05 Financing", "06 LOI", "07 Due Diligence", "08 Notes",
]


def build_response_package(listing: Listing, score: ScoreBreakdown) -> ResponsePackage:
    subject, body = outreach_email(listing, score)
    f1, f2, f3, f4, f5 = followups(listing)
    reminder_date = (date.today() + timedelta(days=3)).isoformat()
    return ResponsePackage(
        listing=listing,
        score=score,
        deal_summary=(
            f"{listing.business_name} — {listing.industry}, {listing.location} — "
            f"{score.total_score}/100 ({score.bucket}). Asking {_money(listing.asking_price)}, "
            f"SDE {_money(listing.sde)}, financing: {financing_status(listing)}."
        ),
        email_subject=subject,
        email_body=body,
        credibility_blurb=BUYER_CREDIBILITY,
        deal_thesis=deal_thesis(listing, score),
        top_questions=top_questions(listing),
        document_requests=document_requests(listing),
        financing_options=financing_options(listing, score),
        loi_skeleton=loi_skeleton(listing, score),
        preliminary_valuation=preliminary_valuation(listing, score),
        risk_notes=risk_notes(listing, score),
        followup_1=f1,
        followup_2=f2,
        followup_3=f3,
        followup_4=f4,
        followup_5=f5,
        nda_request=nda_request(listing),
        crm_status=f"NEW → INTERESTED ({date.today().isoformat()})",
        calendar_reminder=f"Follow up on {listing.business_name} on {reminder_date} "
                          f"if no broker reply.",
        decision=decision_for(score),
        deal_folder_layout=DEAL_FOLDER_LAYOUT,
    )


def render_package_markdown(pkg: ResponsePackage) -> str:
    fin = "\n".join(
        f"### {o.name}\n"
        f"- Purchase price: {o.price}\n"
        f"- Down payment: {o.down_payment}\n"
        f"- Seller note: {o.seller_note}\n"
        f"- Rate: {o.rate}\n"
        f"- Term: {o.term}"
        + (f"\n- {o.extra}" if o.extra else "")
        for o in pkg.financing_options
    )
    questions = "\n".join(f"{i}. {q}" for i, q in enumerate(pkg.top_questions, 1))
    docs = "\n".join(f"- {d}" for d in pkg.document_requests)
    risks = "\n".join(f"- {r}" for r in pkg.risk_notes)
    folders = "\n".join(f"- /{f}" for f in pkg.deal_folder_layout)
    raw = pkg.listing.raw or {}
    broker_line = (
        f"Name: {raw.get('broker_name') or 'not captured'} | "
        f"Email: {raw.get('broker_email') or 'not captured'} | "
        f"Phone: {raw.get('broker_phone') or 'not captured'}"
    )
    return f"""# Hit Send Package — {pkg.listing.business_name}

## Deal Summary
{pkg.deal_summary}

## Broker
{broker_line}

## Decision
**{pkg.decision}**

## Deal Thesis
{pkg.deal_thesis}

## Seller / Broker Outreach Email
**Subject:** {pkg.email_subject}

{pkg.email_body}

## Buyer Credibility Blurb
{pkg.credibility_blurb}

## Top 10 Questions for the Seller
{questions}

## Document Request List
{docs}

## Proposed Financing Structures
_Internal only — broker etiquette: do not share structures before the CIM is
reviewed. The first email only asks whether seller financing is on the table._

{fin}

## Preliminary Valuation
{pkg.preliminary_valuation}

## Risk Notes
{risks}

## NDA Request
{pkg.nda_request}

## LOI Skeleton (draft — attorney review required)
```
{pkg.loi_skeleton}
```

## Follow-up Email 1 (send ~day 3)
{pkg.followup_1}

## Follow-up Email 2 (send ~day 7)
{pkg.followup_2}

## Follow-up Email 3 (send ~day 21 — specific question)
{pkg.followup_3}

## Follow-up Email 4 (send ~day 42 — financing readiness)
{pkg.followup_4}

## Follow-up Email 5 (send ~day 70 — soft close)
{pkg.followup_5}

## Deal Folder
{folders}

## CRM Status
{pkg.crm_status}

## Calendar Reminder
{pkg.calendar_reminder}
"""


# Business names come from parsed email text and can contain characters that are
# invalid in Windows paths (or, like "w/", would silently create nested dirs).
_INVALID_FOLDER_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_folder_name(name: str, max_len: int = 80) -> str:
    cleaned = _INVALID_FOLDER_CHARS.sub(" ", name or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return (cleaned or "Unnamed Deal")[:max_len].rstrip(" .")


# Fixed verification work that applies to every deal regardless of industry —
# these are tasks the operator performs, on top of the documents requested.
DD_VERIFICATION_TASKS = [
    "Verify SDE against tax returns",
    "Verify add-backs",
    "Customer concentration report",
    "License transfer plan",
    "Lease assignment terms",
    "UCC/lien search",
    "Insurance loss runs",
    "Working-capital target",
]


def listing_json_payload(listing: Listing, score: ScoreBreakdown) -> dict:
    """Machine-readable snapshot: full Listing plus the headline score, so later
    commands (rescore, stage tracking) never need the original CSV/email."""
    data = asdict(listing)
    data["total_score"] = score.total_score
    data["bucket"] = score.bucket
    return data


def dd_checklist_markdown(listing: Listing) -> str:
    docs = "\n".join(f"- [ ] {d}" for d in document_requests(listing))
    tasks = "\n".join(f"- [ ] {t}" for t in DD_VERIFICATION_TASKS)
    return (
        f"# Due Diligence Checklist — {listing.business_name}\n\n"
        f"## Documents to collect\n{docs}\n\n"
        f"## Verification tasks\n{tasks}\n"
    )


def followup_ics(business_name: str, start: Optional[date] = None) -> str:
    """All-day follow-up VEVENTs matching the 5-touch cadence (days 3/7/21/42/70).
    CRLF per RFC 5545; UID is stable per business+date so re-imports update
    instead of duplicate."""
    start = start or date.today()
    slug = re.sub(r"[^a-z0-9]+", "-", safe_folder_name(business_name).lower()).strip("-")
    stamp = start.strftime("%Y%m%d")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Boring Business Acquisition Radar//EN",
        "CALSCALE:GREGORIAN",
    ]
    for n, offset in ((1, 3), (2, 7), (3, 21), (4, 42), (5, 70)):
        day = start + timedelta(days=offset)
        lines += [
            "BEGIN:VEVENT",
            f"UID:{slug}-{stamp}-followup{n}@acquisition-radar",
            f"DTSTAMP:{stamp}T000000Z",
            f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}",
            f"SUMMARY:Follow-up {n}: {business_name} (acquisition outreach)",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def create_deal_folder(pkg: ResponsePackage, base_dir: str | Path = "Deals") -> Path:
    """Create the /01…/08 deal-room folder tree and drop the package inside."""
    root = Path(base_dir) / safe_folder_name(pkg.listing.business_name)
    for sub in pkg.deal_folder_layout:
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "01 Listing" / "hit_send_package.md").write_text(
        render_package_markdown(pkg), encoding="utf-8"
    )
    (root / "01 Listing" / "listing.json").write_text(
        json.dumps(listing_json_payload(pkg.listing, pkg.score), indent=2),
        encoding="utf-8",
    )
    (root / "07 Due Diligence" / "checklist.md").write_text(
        dd_checklist_markdown(pkg.listing), encoding="utf-8"
    )
    # write_bytes: Path.write_text would translate \n and corrupt the CRLFs.
    (root / "08 Notes" / "followup_reminders.ics").write_bytes(
        followup_ics(pkg.listing.business_name).encode("utf-8")
    )
    return root
