"""Configuration boundary regressions."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_app_env_is_case_insensitive_for_production_security_mode() -> None:
    assert Settings(APP_ENV=" Production ").APP_ENV == "production"


def test_unknown_app_env_is_rejected_instead_of_using_development_controls() -> None:
    with pytest.raises(ValidationError, match="APP_ENV"):
        Settings(APP_ENV="prod")


def test_passwordless_development_login_is_opt_in() -> None:
    assert Settings().ALLOW_PASSWORDLESS_DEV_LOGIN is False
    assert Settings(ALLOW_PASSWORDLESS_DEV_LOGIN=True).ALLOW_PASSWORDLESS_DEV_LOGIN is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"SESSION_MAX_AGE": 0},
        {"VESSELAPI_CACHE_TTL_SECONDS": -1},
        {"VESSELAPI_TIMEOUT_SECONDS": 0},
        {"VESSELAPI_TIMEOUT_SECONDS": float("nan")},
    ],
)
def test_runtime_seconds_settings_reject_non_positive_or_non_finite_values(overrides) -> None:
    with pytest.raises(ValidationError):
        Settings(**overrides)
