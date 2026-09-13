from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Literal

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.config import get_settings

if TYPE_CHECKING:
    # sentry_sdk defines these only inside `if TYPE_CHECKING:` itself (no
    # runtime cost to the SDK) — same pattern here, safe to mirror.
    from sentry_sdk._types import Event, Hint

logger = logging.getLogger(__name__)

_sentry_initialized = False
_UPLOAD_TOKEN_URL = re.compile(r"(/api/documents/request/)[^/?]+")


def init_sentry() -> None:
    """Initialize Sentry error tracking."""
    global _sentry_initialized

    if _sentry_initialized:
        return

    settings = get_settings()

    if not settings.SENTRY_DSN:
        logger.info("Sentry DSN not configured, skipping initialization")
        return

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENV,
        release="1.0.0",
        traces_sample_rate=0.1 if settings.APP_ENV == "production" else 1.0,
        profiles_sample_rate=0.1 if settings.APP_ENV == "production" else 1.0,
        send_default_pii=False,
        # Uploaded CV/document content can exist in exception locals and
        # multipart/request bodies. Keep both out of third-party telemetry;
        # diagnostics retain the exception type and stack only.
        include_local_variables=False,
        max_request_body_size="none",
        max_breadcrumbs=50,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            CeleryIntegration(),
            SqlalchemyIntegration(),
            RedisIntegration(),
        ],
        before_send=filter_sensitive_data,
    )

    _sentry_initialized = True
    logger.info("Sentry initialized successfully")


def filter_sensitive_data(event: "Event", hint: "Hint") -> "Event":
    """Filter out sensitive data before sending to Sentry."""
    if "request" in event:
        request = event["request"]
        headers = request.get("headers")
        if isinstance(headers, dict):
            sensitive_headers = {"authorization", "cookie", "x-api-key"}
            for header in list(headers):
                if str(header).casefold() in sensitive_headers:
                    headers[header] = "[Filtered]"
        url = request.get("url")
        if isinstance(url, str):
            request["url"] = _UPLOAD_TOKEN_URL.sub(r"\1[redacted-token]", url)

    if "exception" in event:
        frames = event["exception"].get("values", [{}])[0].get("stacktrace", {}).get("frames", [])
        for frame in frames:
            frame_vars = frame.get("vars")
            if isinstance(frame_vars, dict):
                sensitive_vars = ["password", "token", "secret", "api_key"]
                for var in sensitive_vars:
                    if var in frame_vars:
                        frame_vars[var] = "[Filtered]"

    return event


def capture_exception(error: Exception, **kwargs: Any) -> None:
    """Capture an exception and send to Sentry."""
    if _sentry_initialized:
        sentry_sdk.capture_exception(error, **kwargs)


SentryLevel = Literal["fatal", "critical", "error", "warning", "info", "debug"]


def capture_message(message: str, level: SentryLevel = "info", **kwargs: Any) -> None:
    """Capture a message and send to Sentry."""
    if _sentry_initialized:
        sentry_sdk.capture_message(message, level=level, **kwargs)
