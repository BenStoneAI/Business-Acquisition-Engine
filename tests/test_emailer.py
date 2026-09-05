import logging

from src.emailer import send_email, send_report_email


_EMAIL_VARS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD",
               "REPORT_TO_EMAIL", "REPORT_FROM_EMAIL", "GMAIL_ADDRESS", "GMAIL_APP_PASSWORD")


def test_send_skips_and_warns_without_smtp_config(monkeypatch, caplog):
    for var in _EMAIL_VARS:
        monkeypatch.delenv(var, raising=False)
    with caplog.at_level(logging.WARNING, logger="src.emailer"):
        assert send_report_email("body", "subject") is False
    assert any("Email not configured" in r.message for r in caplog.records)


def test_send_tolerates_empty_string_env(monkeypatch):
    # GitHub Actions renders unset secrets as empty strings, not missing vars.
    for var in _EMAIL_VARS:
        monkeypatch.setenv(var, "")
    assert send_report_email("body", "subject") is False  # crashed pre-fix


def test_gmail_app_password_selects_gmail_smtp(monkeypatch):
    # With Gmail creds present, the sender targets smtp.gmail.com without any SMTP_* vars.
    for var in _EMAIL_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GMAIL_ADDRESS", "rainking6693@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "abcd efgh ijkl mnop")  # spaces tolerated
    captured = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=30):
            captured["host"] = host
            captured["port"] = port
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def ehlo(self): pass
        def has_extn(self, _): return True
        def starttls(self): captured["tls"] = True
        def login(self, user, pw): captured["login"] = (user, pw)
        def send_message(self, msg): captured["from"] = msg["From"]

    monkeypatch.setattr("src.emailer.smtplib.SMTP", FakeSMTP)
    assert send_report_email("body", "subject") is True
    assert captured["host"] == "smtp.gmail.com"
    assert captured["login"] == ("rainking6693@gmail.com", "abcdefghijklmnop")  # despaced
    assert captured["from"] == "rainking6693@gmail.com"


def test_send_email_routes_to_arbitrary_recipient(monkeypatch):
    # send_email must deliver to whatever recipient it's given (e.g. a broker),
    # not the operator's own REPORT_TO_EMAIL/GMAIL_ADDRESS.
    for var in _EMAIL_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GMAIL_ADDRESS", "rainking6693@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "abcdefghijklmnop")
    captured = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=30):
            captured["host"] = host
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def ehlo(self): pass
        def has_extn(self, _): return True
        def starttls(self): pass
        def login(self, user, pw): pass
        def send_message(self, msg):
            captured["to"] = msg["To"]
            captured["subject"] = msg["Subject"]

    monkeypatch.setattr("src.emailer.smtplib.SMTP", FakeSMTP)
    assert send_email("broker@examplebrokerage.com", "Interest in Wasatch HVAC", "body") is True
    assert captured["to"] == "broker@examplebrokerage.com"
    assert captured["subject"] == "Interest in Wasatch HVAC"


def test_send_email_skips_and_warns_without_smtp_config(monkeypatch, caplog):
    for var in _EMAIL_VARS:
        monkeypatch.delenv(var, raising=False)
    with caplog.at_level(logging.WARNING, logger="src.emailer"):
        assert send_email("broker@examplebrokerage.com", "subject", "body") is False
    assert any("Email not configured" in r.message for r in caplog.records)
