from __future__ import annotations

from datetime import date
from typing import List, Tuple

from .models import Listing, ScoreBreakdown


def money(value, none_label="Unknown"):
    if value is None:
        return none_label
    return f"${value:,.0f}"


def pct(value, none_label="Unknown", decimals=1):
    if value is None:
        return none_label
    return f"{value * 100:.{decimals}f}%"


def render_deal(listing: Listing, score: ScoreBreakdown, rank: int) -> str:
    red_flags = "\n".join(f"- {flag}" for flag in score.red_flags) or "- None obvious from listing data"
    return f"""
## {rank}. {listing.business_name} — {listing.industry} — {listing.location}

**Score:** {score.total_score}/100  
**Bucket:** {score.bucket}  
**Source:** {listing.source or 'Unknown'}  
**Listing:** {listing.listing_url or 'No URL provided'}

| Metric | Value |
|---|---:|
| Asking Price | {money(listing.asking_price)} |
| Revenue | {money(listing.revenue)} |
| SDE / Cash Flow | {money(listing.sde)} |
| Cash Flow Yield | {pct(score.cash_flow_yield)} |
| Estimated Value Range | {money(score.estimated_value_low)} – {money(score.estimated_value_high)} |
| Estimated Max Offer | {money(score.estimated_max_offer)} |
| Payback Estimate | {f"{score.payback_years:.1f} years" if score.payback_years is not None else 'Unknown'} |
| Seller Financing | {'Yes' if listing.seller_financing else 'No/Unknown'} |
| SBA Prequalified | {'Yes' if listing.sba_prequalified else 'No/Unknown'} |
| Reason for Sale | {listing.reason_for_sale or 'Unknown'} |

**Why it is interesting**

- Industry score: {score.industry_score}/100
- Financial score: {score.financial_score}/100
- Recurring revenue score: {score.recurring_revenue_score}/100
- Seller motivation score: {score.seller_motivation_score}/100
- Financing fit score: {score.financing_fit_score}/100

**Red flags / diligence questions**

{red_flags}

**Recommended next action**

{score.next_action}
""".strip()


def build_daily_report(scored: List[Tuple[Listing, ScoreBreakdown]], min_score: float = 70) -> str:
    today = date.today().isoformat()
    sorted_deals = sorted(scored, key=lambda x: x[1].total_score, reverse=True)
    top = [x for x in sorted_deals if x[1].total_score >= min_score][:10]
    watch = [x for x in sorted_deals if 60 <= x[1].total_score < min_score]
    rejected = [x for x in sorted_deals if x[1].total_score < 60]

    lines = [
        f"# Daily Boring Business Acquisition Radar — {today}",
        "",
        "## Executive Summary",
        "",
        f"- Total deals reviewed: {len(scored)}",
        f"- Reportable deals: {len(top)}",
        f"- Watchlist deals: {len(watch)}",
        f"- Rejected/pass deals: {len(rejected)}",
        "",
        "## Top Deals",
        "",
    ]

    if not top:
        lines.append("No deals cleared the reporting threshold today.")
    else:
        for idx, item in enumerate(top, 1):
            lines.append(render_deal(item[0], item[1], idx))
            lines.append("\n---\n")

    if watch:
        lines.extend(["", "## Watchlist", ""])
        for listing, score in watch[:10]:
            lines.append(f"- **{listing.business_name}** — {listing.industry}, {listing.location} — {score.total_score}/100 — {score.bucket}")

    if rejected:
        lines.extend(["", "## Rejected / Pass", ""])
        for listing, score in rejected[:10]:
            lines.append(f"- **{listing.business_name}** — {listing.industry}, {listing.location} — {score.total_score}/100 — {score.bucket}")

    lines.extend([
        "",
        "## Default broker/seller questions for promising deals",
        "",
        "1. Can you provide the last 3 years of tax returns and P&Ls?",
        "2. What add-backs are included in SDE?",
        "3. How many hours does the owner work each week?",
        "4. Is seller financing available for a qualified buyer?",
        "5. What percentage of revenue is recurring or contracted?",
        "6. What customer concentration exists?",
        "7. Are employees expected to stay after closing?",
        "8. What is the lease term or is real estate included?",
        "9. What equipment or fleet replacement is needed in the next 24 months?",
        "10. Why is the owner selling now?",
    ])
    return "\n".join(lines)
