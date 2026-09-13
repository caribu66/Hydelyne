"""Regression tests for privacy-safe error-reporting configuration."""

from unittest.mock import Mock

from app.services import sentry


def test_sentry_excludes_request_bodies_and_exception_locals(monkeypatch):
    init = Mock()
    monkeypatch.setattr(sentry.sentry_sdk, "init", init)
    monkeypatch.setattr(sentry.get_settings(), "SENTRY_DSN", "https://example.invalid/1")
    monkeypatch.setattr(sentry, "_sentry_initialized", False)

    sentry.init_sentry()

    options = init.call_args.kwargs
    assert options["send_default_pii"] is False
    assert options["include_local_variables"] is False
    assert options["max_request_body_size"] == "none"


def test_sentry_redacts_upload_tokens_and_case_insensitive_headers():
    event = {
        "request": {
            "url": "https://example.test/api/documents/request/secret-upload-token/upload",
            "headers": {
                "Authorization": "Bearer secret",
                "Cookie": "hydenlyne_session=secret",
                "X-API-Key": "secret-api-key",
                "Content-Type": "application/json",
            },
        }
    }

    filtered = sentry.filter_sensitive_data(event, {})

    request = filtered["request"]
    assert "secret-upload-token" not in request["url"]
    assert request["url"].endswith("/api/documents/request/[redacted-token]/upload")
    assert request["headers"]["Authorization"] == "[Filtered]"
    assert request["headers"]["Cookie"] == "[Filtered]"
    assert request["headers"]["X-API-Key"] == "[Filtered]"
    assert request["headers"]["Content-Type"] == "application/json"
