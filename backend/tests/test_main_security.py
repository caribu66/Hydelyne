"""Regression tests for production-only application surface hardening."""

import pytest

from app import main


def test_production_disables_public_fastapi_documentation(monkeypatch):
    monkeypatch.setattr(main.settings, "APP_ENV", "production")

    app = main.create_app()

    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None
    route_paths = {getattr(route, "path", None) for route in app.routes}
    assert route_paths.isdisjoint({"/docs", "/redoc", "/openapi.json"})


def test_non_production_keeps_fastapi_documentation(monkeypatch):
    monkeypatch.setattr(main.settings, "APP_ENV", "development")

    app = main.create_app()

    assert app.docs_url == "/docs"
    assert app.redoc_url == "/redoc"
    assert app.openapi_url == "/openapi.json"


@pytest.mark.parametrize(
    ("setting_name", "placeholder"),
    [
        ("SESSION_SECRET_KEY", "change_this_to_a_random_secret_key_at_least_32_chars"),
        ("MEILI_MASTER_KEY", "set_a_long_random_value_for_prod"),
    ],
)
def test_production_rejects_documented_secret_placeholders(monkeypatch, setting_name, placeholder):
    monkeypatch.setattr(main.settings, "APP_ENV", "production")
    monkeypatch.setattr(main.settings, "SESSION_SECRET_KEY", "a" * 40)
    monkeypatch.setattr(main.settings, "MEILI_MASTER_KEY", "b" * 40)
    monkeypatch.setattr(main.settings, "REDIS_PASSWORD", "c" * 24)
    monkeypatch.setattr(main.settings, "FLOWER_PASSWORD", "d" * 24)
    monkeypatch.setattr(main.settings, "ADMIN_PASSWORD", "e" * 24)
    monkeypatch.setattr(
        main.settings,
        "DATABASE_URL",
        "postgresql+asyncpg://hydenlyne:strong-password@db:5432/hydenlyne",
    )
    monkeypatch.setattr(main.settings, setting_name, placeholder)

    with pytest.raises(RuntimeError, match=setting_name):
        main.validate_prod_secrets()
