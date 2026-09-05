from src.models import Listing, ScoreBreakdown
from src.notifier import build_alert, send_telegram, notify_daily


def score(total, bucket="PURSUE NOW"):
    return ScoreBreakdown(
        financial_score=0, industry_score=0, recurring_revenue_score=0,
        seller_motivation_score=0, owner_independence_score=0, financing_fit_score=0,
        growth_upside_score=0, risk_score=0, bonus_points=0, deal_killer_penalty=0,
        total_score=total, bucket=bucket, cash_flow_yield=None, payback_years=None,
        estimated_value_low=None, estimated_value_high=None, estimated_max_offer=None,
        red_flags=[], next_action="",
    )


def listing(name="Wasatch HVAC", url="https://x.test/w"):
    return Listing(business_name=name, industry="hvac", location="Utah County UT",
                   asking_price=850000, seller_financing=True, listing_url=url)


def test_build_alert_lists_top_deals_and_urls():
    scored = [(listing("A", "https://x.test/a"), score(95)),
              (listing("B", "https://x.test/b"), score(60))]  # below threshold
    alert = build_alert(scored, min_score=70)
    assert "A — Utah County UT" in alert
    assert "https://x.test/a" in alert
    assert "B —" not in alert  # filtered out
    assert "financing: possible" in alert


def test_build_alert_empty_when_nothing_reportable():
    scored = [(listing(), score(50))]
    assert build_alert(scored, min_score=70) == ""


def test_send_telegram_skips_without_config(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    calls = []
    assert send_telegram("hi", transport=lambda u, d: calls.append(u) or {"ok": True}) is False
    assert calls == []  # transport never invoked


def test_send_telegram_posts_when_configured(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "555")
    captured = {}

    def fake_transport(url, data):
        captured["url"] = url
        captured["data"] = data.decode("utf-8")
        return {"ok": True, "result": {"message_id": 1}}

    assert send_telegram("hello", transport=fake_transport) is True
    assert "/bot123:ABC/sendMessage" in captured["url"]
    assert "chat_id=555" in captured["data"]
    assert "hello" in captured["data"]


def test_notify_daily_skips_when_no_deals(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
    sent = []
    result = notify_daily([(listing(), score(40))], min_score=70,
                          transport=lambda u, d: sent.append(u) or {"ok": True})
    assert result is False
    assert sent == []  # nothing reportable, so no send


def test_build_heartbeat_mentions_counts():
    from src.notifier import build_heartbeat
    msg = build_heartbeat(parsed=7, fresh=3, built=0, min_score=70.0)
    assert "7 listing(s) parsed" in msg
    assert "3 new" in msg
    assert "0 packet(s)" in msg
    assert "70" in msg
