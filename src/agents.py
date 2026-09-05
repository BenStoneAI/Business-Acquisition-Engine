from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import List, Dict, Any

from .models import Listing

logger = logging.getLogger(__name__)


class SourcingAgent:
    """Collects raw listings from compliant sources.

    MVP implementation ingests a CSV export. Production implementation can add:
    - saved-search email parser
    - Google/Bing search API
    - Apify actors after compliance review
    - direct broker feeds
    - manual broker import
    """

    def from_csv(self, path: str | Path) -> List[Listing]:
        listings: List[Listing] = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for line_num, row in enumerate(reader, start=2):
                try:
                    listings.append(self._row_to_listing(row))
                except (ValueError, TypeError) as exc:
                    logger.warning(
                        "Skipping malformed CSV row %d (%s): %s",
                        line_num, row.get("business_name") or "unnamed", exc,
                    )
        return listings

    def _row_to_listing(self, row: Dict[str, str]) -> Listing:
        def num(key: str):
            val = row.get(key, "")
            if val is None or str(val).strip() == "":
                return None
            try:
                return float(str(val).replace("$", "").replace(",", "").strip())
            except ValueError:
                # One bad number ("Call for price") shouldn't cost the whole
                # listing — scoring already handles missing fields.
                logger.warning(
                    "Unparseable %s=%r for %s; treating as blank.",
                    key, val, row.get("business_name") or "unnamed",
                )
                return None

        def boolean(key: str):
            return str(row.get(key, "")).strip().lower() in {"yes", "true", "1", "y"}

        return Listing(
            business_name=row.get("business_name", "Unknown Business"),
            industry=row.get("industry", "other"),
            location=row.get("location", "Unknown"),
            asking_price=num("asking_price"),
            revenue=num("revenue"),
            sde=num("sde"),
            ebitda=num("ebitda"),
            real_estate_included=boolean("real_estate_included"),
            seller_financing=boolean("seller_financing"),
            seller_financing_terms=row.get("seller_financing_terms") or None,
            sba_prequalified=boolean("sba_prequalified"),
            reason_for_sale=row.get("reason_for_sale") or None,
            years_in_business=int(num("years_in_business") or 0) or None,
            employees=int(num("employees") or 0) or None,
            owner_hours_per_week=num("owner_hours_per_week"),
            recurring_revenue_pct=(num("recurring_revenue_pct") / 100 if num("recurring_revenue_pct") and num("recurring_revenue_pct") > 1 else num("recurring_revenue_pct")),
            customer_concentration_pct=(num("customer_concentration_pct") / 100 if num("customer_concentration_pct") and num("customer_concentration_pct") > 1 else num("customer_concentration_pct")),
            equipment_condition=row.get("equipment_condition") or None,
            lease_years_remaining=num("lease_years_remaining"),
            source=row.get("source") or None,
            listing_url=row.get("listing_url") or None,
            notes=row.get("notes") or "",
            raw=row,
        )
