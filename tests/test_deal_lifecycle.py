"""Deal lifecycle: listing.json, DD checklist, .ics reminders, rescore, stages."""

import json
from dataclasses import fields

import pytest

from src.models import Listing
from src.scoring import score_listing
from src.response_engine import build_response_package, create_deal_folder

CONFIGS = {
    "hvac": {"display_name": "HVAC", "base_score": 80,
             "target_multiple_low": 2.0, "target_multiple_high": 3.0},
}


def hvac_listing(**kw) -> Listing:
    base = dict(
        business_name="Wasatch HVAC Services", industry="hvac", location="Utah County UT",
        asking_price=850000, revenue=1800000, sde=310000, seller_financing=True,
        reason_for_sale="Retirement", years_in_business=24, employees=11,
        owner_hours_per_week=25, recurring_revenue_pct=0.32,
        notes="Owner will train for 12 months. Maintenance agreements in place.",
        listing_url="https://example.com/wasatch-hvac",
    )
    base.update(kw)
    return Listing(**base)


def make_deal_folder(tmp_path, listing=None):
    listing = listing or hvac_listing()
    score = score_listing(listing, CONFIGS)
    pkg = build_response_package(listing, score)
    return create_deal_folder(pkg, base_dir=tmp_path), listing, score


# --- Piece 1: listing.json ----------------------------------------------------

def test_listing_json_written_and_roundtrips(tmp_path):
    root, listing, score = make_deal_folder(tmp_path)
    path = root / "01 Listing" / "listing.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["total_score"] == score.total_score
    assert data["bucket"] == score.bucket
    names = {f.name for f in fields(Listing)}
    rebuilt = Listing(**{k: v for k, v in data.items() if k in names})
    assert rebuilt == listing


# --- Piece 4: DD checklist + .ics ---------------------------------------------

def test_checklist_contains_base_industry_and_verification_items(tmp_path):
    root, _, _ = make_deal_folder(tmp_path)
    text = (root / "07 Due Diligence" / "checklist.md").read_text(encoding="utf-8")
    assert "- [ ] 3 years of tax returns" in text        # base doc
    assert "- [ ] Technician roster" in text             # HVAC industry doc
    for task in ["Verify SDE against tax returns", "Verify add-backs",
                 "Customer concentration report", "License transfer plan",
                 "Lease assignment terms", "UCC/lien search",
                 "Insurance loss runs", "Working-capital target"]:
        assert f"- [ ] {task}" in text


def test_ics_is_valid_vcalendar_with_five_allday_events_and_crlf(tmp_path):
    root, listing, _ = make_deal_folder(tmp_path)
    raw = (root / "08 Notes" / "followup_reminders.ics").read_bytes()
    text = raw.decode("utf-8")
    assert text.startswith("BEGIN:VCALENDAR")
    assert "END:VCALENDAR" in text
    assert text.count("BEGIN:VEVENT") == 5
    assert text.count("END:VEVENT") == 5
    assert text.count("DTSTART;VALUE=DATE:") == 5       # all-day events
    assert listing.business_name in text                # SUMMARY names the business
    assert b"\r\n" in raw
    assert "\n" not in text.replace("\r\n", "")         # every newline is CRLF


# --- Piece 2: rescore ---------------------------------------------------------

def test_rescore_sde_override_changes_score_and_writes_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")              # keep DB gated off
    # Score with the real YAML config so the packet's "before" matches what
    # rescore recomputes (rescore always uses config/industry_formulas.yaml).
    import yaml
    from pathlib import Path
    real_configs = yaml.safe_load(
        Path("config/industry_formulas.yaml").read_text(encoding="utf-8")
    )["industries"]
    listing = hvac_listing()
    before_score = score_listing(listing, real_configs)
    pkg = build_response_package(listing, before_score)
    root = create_deal_folder(pkg, base_dir=tmp_path)
    from src.rescore import main
    rc = main(["--deal", "Wasatch", "--deals-dir", str(tmp_path), "--sde", "150000"])
    assert rc == 0
    data = json.loads((root / "01 Listing" / "listing.json").read_text(encoding="utf-8"))
    assert data["sde"] == 150000                        # listing.json updated
    assert data["total_score"] != before_score.total_score
    rescore_files = list((root / "02 Financials").glob("rescore_*.md"))
    assert len(rescore_files) == 1
    report = rescore_files[0].read_text(encoding="utf-8")
    assert "VERIFIED NUMBERS — supersedes listing-ad screening score" in report
    assert f"Total: {before_score.total_score} →" in report


def test_rescore_unknown_deal_returns_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "")
    from src.rescore import main
    assert main(["--deal", "Nope", "--deals-dir", str(tmp_path)]) == 1
    assert "No deal folder" in capsys.readouterr().err


# --- Piece 3: deal stages -----------------------------------------------------

def test_deal_stage_transitions_build_history(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    root, _, _ = make_deal_folder(tmp_path)
    from src.deal import main
    assert main(["--deal", "Wasatch", "--deals-dir", str(tmp_path), "--stage", "contacted"]) == 0
    status = json.loads((root / "status.json").read_text(encoding="utf-8"))
    assert status["stage"] == "contacted"
    assert len(status["history"]) == 1
    assert main(["--deal", "Wasatch", "--deals-dir", str(tmp_path), "--stage", "nda"]) == 0
    status = json.loads((root / "status.json").read_text(encoding="utf-8"))
    assert status["stage"] == "nda"
    assert [h["stage"] for h in status["history"]] == ["contacted", "nda"]
    assert status["updated"] == status["history"][-1]["date"]


def test_deal_without_stage_prints_current_status(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "")
    make_deal_folder(tmp_path)
    from src.deal import main
    main(["--deal", "Wasatch", "--deals-dir", str(tmp_path), "--stage", "loi"])
    capsys.readouterr()
    assert main(["--deal", "Wasatch", "--deals-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert '"stage": "loi"' in out


def test_deal_rejects_unknown_stage(tmp_path):
    from src.deal import main
    with pytest.raises(SystemExit):                     # argparse choices error
        main(["--deal", "Wasatch", "--deals-dir", str(tmp_path), "--stage", "bogus"])
