from __future__ import annotations

"""Deterministic synthetic-listing factory for the simulation harness (t6).

This module ONLY generates data and known-expected outcomes. It never
reimplements pipeline logic — every classification is produced by importing
and calling the real src/ functions from test_simulation.py. Two source
formats are used, matching how real data actually enters the radar:

- BizBuySell alert HTML blocks (fed through `src.bizbuysell_ingest.parse_alert`)
  for financing-language and industry-inference edge cases. The alert regex
  parser requires an "Asking Price" field to keep a block (see
  bizbuysell_ingest.parse_alert docstring), so it cannot express negative or
  zero prices realistically — those go through the CSV path instead.
- CSV rows (fed through `src.agents.SourcingAgent.from_csv`) for thin/missing
  and absurd numeric edge cases, exactly like a real marketplace CSV export
  with a blank or malformed cell.

Every generator returns (payload, expected) where `expected` is a plain dict
describing what the real pipeline MUST produce. Seeded `random.Random`
instances make every run byte-for-byte reproducible.
"""

import random
from typing import Callable, Dict, List, Tuple

from src.financing_filter import FULL, MAJORITY, POSSIBLE, PARTIAL_CAPPED, NONE

SEED = 20260718

LOCATIONS = [
    "Salt Lake City, UT", "Boise, ID", "Phoenix, AZ", "Denver, CO",
    "Reno, NV", "Albuquerque, NM", "Spokane, WA", "Billings, MT",
    "Tucson, AZ", "Colorado Springs, CO",
]

# (industry key as scored, phrase that src.bizbuysell_ingest._infer_industry
# will match — copied verbatim from its _INDUSTRY_KEYWORDS table).
THESIS_INDUSTRIES = [
    ("hvac", "HVAC"),
    ("plumbing", "Plumbing"),
    ("electrical", "Electrical"),
    ("laundromat", "Laundromat"),
    ("pest_control", "Pest Control"),
    ("commercial_cleaning", "Commercial Cleaning"),
    ("pool_service", "Pool Service"),
    ("self_storage", "Self Storage"),
    ("car_wash", "Car Wash"),
    ("roofing", "Roofing"),
]

# Disjoint id ranges per category so listing ids never collide across
# categories, and never collide within a category (idx is globally unique
# per call in generate_population()).
_CATEGORY_OFFSETS = {
    "full_100": 0,
    "possible": 5_000_000,
    "partial_capped": 10_000_000,
    "none_financing": 15_000_000,
    "retiring_strong": 20_000_000,
    "off_thesis_pizzeria": 25_000_000,
    "majority_carry": 30_000_000,
}


def _url(category: str, idx: int) -> str:
    listing_id = 9_000_000 + _CATEGORY_OFFSETS[category] + idx
    return f"https://www.bizbuysell.com/Business-Opportunity/sim-{category}/{listing_id}/"


def _block(url: str, title: str, location: str, price: int,
           cashflow: int | None, revenue: int | None, blurb: str) -> str:
    parts = [f'<a href="{url}">{title}</a><br>', f"{location}<br>",
              f"Asking Price: ${price:,}<br>"]
    if cashflow is not None:
        parts.append(f"Cash Flow: ${cashflow:,}<br>")
    if revenue is not None:
        parts.append(f"Gross Revenue: ${revenue:,}<br>")
    parts.append(blurb)
    return " ".join(parts)


def gen_full_100(rng: random.Random, idx: int) -> Tuple[str, dict]:
    key, phrase = rng.choice(THESIS_INDUSTRIES)
    price = rng.randint(300_000, 1_200_000)
    cashflow = int(price * rng.uniform(0.18, 0.32))
    revenue = int(price * rng.uniform(1.5, 3.0))
    url = _url("full_100", idx)
    block = _block(url, f"{phrase} Business #{idx} - Owner Retiring", rng.choice(LOCATIONS),
                    price, cashflow, revenue,
                    "100% seller financing available to a qualified buyer.")
    return block, {
        "url": url, "category": "full_100", "industry": key,
        "expected_status": FULL, "expected_qualifies": True,
    }


def gen_possible(rng: random.Random, idx: int) -> Tuple[str, dict]:
    key, phrase = rng.choice(THESIS_INDUSTRIES)
    price = rng.randint(300_000, 1_200_000)
    cashflow = int(price * rng.uniform(0.15, 0.30))
    revenue = int(price * rng.uniform(1.5, 3.0))
    url = _url("possible", idx)
    block = _block(url, f"{phrase} Business #{idx}", rng.choice(LOCATIONS),
                    price, cashflow, revenue,
                    "Owner will consider seller financing for the right buyer, terms negotiable.")
    return block, {
        "url": url, "category": "possible", "industry": key,
        "expected_status": POSSIBLE, "expected_qualifies": True,
    }


def gen_partial_capped(rng: random.Random, idx: int) -> Tuple[str, dict]:
    key, phrase = rng.choice(THESIS_INDUSTRIES)
    pct = rng.choice([10, 15, 20, 25, 30, 40, 45])
    price = rng.randint(300_000, 1_200_000)
    cashflow = int(price * rng.uniform(0.15, 0.30))
    revenue = int(price * rng.uniform(1.5, 3.0))
    url = _url("partial_capped", idx)
    block = _block(url, f"{phrase} Business #{idx}", rng.choice(LOCATIONS),
                    price, cashflow, revenue,
                    f"Seller will finance {pct}% for the right buyer; balance due at close.")
    return block, {
        "url": url, "category": "partial_capped", "industry": key,
        "expected_status": PARTIAL_CAPPED, "expected_qualifies": False,
    }


def gen_none_financing(rng: random.Random, idx: int) -> Tuple[str, dict]:
    key, phrase = rng.choice(THESIS_INDUSTRIES)
    price = rng.randint(300_000, 1_200_000)
    cashflow = int(price * rng.uniform(0.15, 0.30))
    revenue = int(price * rng.uniform(1.5, 3.0))
    url = _url("none_financing", idx)
    block = _block(url, f"{phrase} Business #{idx}", rng.choice(LOCATIONS),
                    price, cashflow, revenue,
                    "No seller financing. Cash or SBA financing only.")
    return block, {
        "url": url, "category": "none_financing", "industry": key,
        "expected_status": NONE, "expected_qualifies": False,
    }


def gen_retiring_strong(rng: random.Random, idx: int) -> Tuple[str, dict]:
    key, phrase = rng.choice(THESIS_INDUSTRIES)
    price = rng.randint(500_000, 900_000)
    cashflow = int(price * rng.uniform(0.42, 0.55))  # forces cash_flow_yield >= 0.40
    revenue = int(price * rng.uniform(1.5, 2.5))
    url = _url("retiring_strong", idx)
    block = _block(
        url, f"{phrase} Business #{idx} - Owner Retiring", rng.choice(LOCATIONS),
        price, cashflow, revenue,
        "Owner retiring after 25 years and ready to sell. 100% seller financing "
        "available. Strong recurring revenue with maintenance agreements. "
        "Experienced manager runs day-to-day operations."
    )
    return block, {
        "url": url, "category": "retiring_strong", "industry": key,
        "expected_status": FULL, "expected_qualifies": True,
        "expected_min_total_score": 80,
    }


def gen_off_thesis_pizzeria(rng: random.Random, idx: int) -> Tuple[str, dict]:
    price = rng.randint(150_000, 500_000)
    cashflow = int(price * rng.uniform(0.15, 0.30))
    revenue = int(price * rng.uniform(1.5, 3.0))
    url = _url("off_thesis_pizzeria", idx)
    block = _block(url, f"Profitable Pizzeria #{idx}", rng.choice(LOCATIONS),
                    price, cashflow, revenue,
                    "100% seller financing available. Family-owned pizzeria, prime location.")
    return block, {
        "url": url, "category": "off_thesis_pizzeria", "industry": "restaurant",
        "expected_status": FULL, "expected_qualifies": True,
        "expected_industry_score": 30,
    }


def gen_majority_carry(rng: random.Random, idx: int) -> Tuple[str, dict]:
    # 2026-07-19 policy: a stated carry at or above MAJORITY_FLOOR (50%)
    # qualifies - screen on quality, negotiate structure up.
    key, phrase = rng.choice(THESIS_INDUSTRIES)
    pct = rng.choice([50, 60, 70, 75, 80, 90])
    price = rng.randint(300_000, 1_200_000)
    cashflow = int(price * rng.uniform(0.15, 0.30))
    revenue = int(price * rng.uniform(1.5, 3.0))
    url = _url("majority_carry", idx)
    block = _block(url, f"{phrase} Business #{idx}", rng.choice(LOCATIONS),
                    price, cashflow, revenue,
                    f"Seller will carry {pct}% for a qualified buyer.")
    return block, {
        "url": url, "category": "majority_carry", "industry": key,
        "expected_status": MAJORITY, "expected_qualifies": True,
    }


CATEGORY_GENERATORS: Dict[str, Callable[[random.Random, int], Tuple[str, dict]]] = {
    "full_100": gen_full_100,
    "possible": gen_possible,
    "partial_capped": gen_partial_capped,
    "majority_carry": gen_majority_carry,
    "none_financing": gen_none_financing,
    "retiring_strong": gen_retiring_strong,
    "off_thesis_pizzeria": gen_off_thesis_pizzeria,
}


def build_alert(blocks: List[str]) -> str:
    rows = "\n".join(f"<tr><td>{b}</td></tr>" for b in blocks)
    return f"<html><body><table>\n{rows}\n</table></body></html>"


def generate_population(n: int, seed: int = SEED) -> Tuple[str, Dict[str, dict]]:
    """Round-robin across the 6 HTML-representable categories.

    Returns (alert_html, {listing_url: expected_dict}).
    """
    rng = random.Random(seed)
    cats = list(CATEGORY_GENERATORS)
    blocks: List[str] = []
    meta: Dict[str, dict] = {}
    for i in range(n):
        cat = cats[i % len(cats)]
        block, info = CATEGORY_GENERATORS[cat](rng, i)
        blocks.append(block)
        meta[info["url"]] = info
    return build_alert(blocks), meta


# ---------------------------------------------------------------------------
# CSV-path generators (src.agents.SourcingAgent.from_csv) for edge cases the
# alert-HTML regex parser cannot express (missing price cell, negative price).
# ---------------------------------------------------------------------------

CSV_FIELDS = [
    "business_name", "industry", "location", "asking_price", "revenue", "sde",
    "seller_financing", "seller_financing_terms", "notes",
]


def gen_thin_bad_rows() -> List[Dict[str, str]]:
    """Missing SDE and/or asking_price — must not crash, must score low."""
    return [
        {
            "business_name": "Opaque HVAC Co", "industry": "hvac", "location": "Utah",
            "asking_price": "", "revenue": "", "sde": "",
            "seller_financing": "true", "seller_financing_terms": "",
            "notes": "Seller declined to share financials.",
        },
        {
            "business_name": "Price Unknown Laundromat", "industry": "laundromat",
            "location": "Idaho", "asking_price": "Call for price", "revenue": "900000",
            "sde": "", "seller_financing": "true", "seller_financing_terms": "",
            "notes": "SDE not disclosed.",
        },
        {
            "business_name": "No Price Pest Route", "industry": "pest_control",
            "location": "Arizona", "asking_price": "", "revenue": "500000",
            "sde": "150000", "seller_financing": "true", "seller_financing_terms": "",
            "notes": "Asking price omitted from listing.",
        },
    ]


def gen_absurd_value_rows() -> List[Dict[str, str]]:
    """Zero / negative / 1e12 prices — must not crash; clamp must hold."""
    return [
        {
            "business_name": "Zero Price Roofing", "industry": "roofing", "location": "Colorado",
            "asking_price": "0", "revenue": "400000", "sde": "150000",
            "seller_financing": "true", "seller_financing_terms": "", "notes": "",
        },
        {
            "business_name": "Negative Price Car Wash", "industry": "car_wash", "location": "Nevada",
            "asking_price": "-500000", "revenue": "300000", "sde": "90000",
            "seller_financing": "true", "seller_financing_terms": "", "notes": "",
        },
        {
            "business_name": "Absurd Trillion Dollar Storage", "industry": "self_storage",
            "location": "New Mexico", "asking_price": "1000000000000", "revenue": "500000",
            "sde": "200000", "seller_financing": "true", "seller_financing_terms": "", "notes": "",
        },
    ]


def write_csv(path, rows: List[Dict[str, str]]) -> None:
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})
