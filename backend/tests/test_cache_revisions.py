from datetime import date, datetime

from app.services.cache import cache_service


def test_source_versioned_cache_keys_change_when_certification_state_changes():
    first = cache_service._make_key(
        "compliance",
        "crew-1",
        revision=[("cert-1", datetime(2026, 9, 12), date(2027, 1, 1), "valid", "verified")],
    )
    second = cache_service._make_key(
        "compliance",
        "crew-1",
        revision=[
            ("cert-1", datetime(2026, 9, 12), date(2026, 9, 20), "expiring_soon", "verified")
        ],
    )

    assert first != second
