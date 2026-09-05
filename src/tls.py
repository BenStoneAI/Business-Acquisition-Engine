from __future__ import annotations

"""Trust the OS certificate store for all TLS (Telegram, SMTP, IMAP).

Some endpoint-protection tools intercept HTTPS to specific hosts (observed
2026-07-18: api.telegram.org re-signed with a local root that lives in the
Windows cert store but not in Python's bundled CA set, so every Telegram send
failed CERTIFICATE_VERIFY_FAILED). `truststore` makes Python's ssl module use
the operating system's trust store, which fixes that without disabling
verification. Guarded: a missing package degrades to Python's default CAs.
"""


def use_system_certs() -> None:
    try:
        import truststore
    except ImportError:
        return
    truststore.inject_into_ssl()
