"""Bug A5: a failed deal alert must leave the ingest state unsaved so the
next run re-alerts instead of burying the deals."""

import argparse
import json

import src.ingest_bizbuysell as ing


def _args(tmp_path, state):
    return argparse.Namespace(
        file="examples/sample_bizbuysell_alert.html",
        industry_config="config/industry_formulas.yaml",
        deals_dir=str(tmp_path / "Deals"),
        state_file=str(state),
        no_state=False,
    )


def test_state_not_saved_when_alert_fails(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    monkeypatch.setattr(ing, "telegram_configured", lambda: True)
    monkeypatch.setattr(ing, "send_telegram", lambda text: False)
    monkeypatch.setattr(ing, "persist_scored_listings", lambda scored: 0)
    assert ing._run(_args(tmp_path, state), min_score=0.0) == 0
    assert not state.exists()


def test_state_saved_when_alert_succeeds(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    monkeypatch.setattr(ing, "telegram_configured", lambda: True)
    monkeypatch.setattr(ing, "send_telegram", lambda text: True)
    monkeypatch.setattr(ing, "persist_scored_listings", lambda scored: 0)
    assert ing._run(_args(tmp_path, state), min_score=0.0) == 0
    assert state.exists()


def test_price_drop_reprocessed_alerted_and_state_updated(tmp_path, monkeypatch):
    """b4: a listing already marked processed at a higher price must still be
    re-surfaced (with its own '📉 PRICE DROP' Telegram message), scored, and
    have its new price recorded in state — instead of being buried forever by
    filter_unprocessed."""
    state = tmp_path / "state.json"
    state.write_text(
        json.dumps({"2101010": {"last_seen": "2026-07-01", "asking_price": 900000}}),
        encoding="utf-8",
    )

    sent = []
    monkeypatch.setattr(ing, "telegram_configured", lambda: True)
    monkeypatch.setattr(ing, "send_telegram", lambda text: sent.append(text) or True)
    monkeypatch.setattr(ing, "persist_scored_listings", lambda scored: 0)

    assert ing._run(_args(tmp_path, state), min_score=0.0) == 0

    drop_msgs = [t for t in sent if "PRICE DROP" in t]
    assert len(drop_msgs) == 1
    assert "Established HVAC" in drop_msgs[0]
    assert "$900,000" in drop_msgs[0]
    assert "$850,000" in drop_msgs[0]

    reloaded = json.loads(state.read_text(encoding="utf-8"))
    assert reloaded["2101010"]["asking_price"] == 850000
    # Other listings in the same alert are freshly seen and get their price recorded too.
    assert reloaded["2102020"]["asking_price"] == 600000
