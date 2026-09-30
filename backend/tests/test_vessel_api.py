"""Tests for VesselAPI proxy service, validation, error mapping, and GraphQL queries."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from app.services.vessel_api import (
    MAX_VESSEL_API_RESPONSE_BYTES,
    VesselApiAuthError,
    VesselApiNotConfiguredError,
    VesselApiService,
    VesselApiUpstreamError,
    _cache_key,
    _coerce_position,
    _coerce_vessel_summary,
    _validate_id_type,
    _validate_name,
    _validate_vessel_id,
)


def test_validate_name() -> None:
    assert _validate_name("  Northern Explorer  ") == "Northern Explorer"
    with pytest.raises(ValueError, match="must not be empty"):
        _validate_name("   ")
    with pytest.raises(ValueError, match="too long"):
        _validate_name("a" * 101)
    with pytest.raises(ValueError, match="must be a string"):
        _validate_name(123)


def test_validate_id_type() -> None:
    assert _validate_id_type("IMO") == "imo"
    assert _validate_id_type("mmsi") == "mmsi"
    assert _validate_id_type("eni ") == "eni"
    with pytest.raises(ValueError, match="idType must be one of"):
        _validate_id_type("invalid_type")
    with pytest.raises(ValueError, match="idType must be a string"):
        _validate_id_type(None)


def test_validate_vessel_id_rejects_path_and_query_delimiters() -> None:
    assert _validate_vessel_id("  9683934  ") == "9683934"
    with pytest.raises(ValueError, match="invalid characters"):
        _validate_vessel_id("9683934?next=/admin")
    with pytest.raises(ValueError, match="must be a string"):
        _validate_vessel_id(9683934)


@pytest.mark.asyncio
async def test_vessel_adapter_rejects_malformed_numeric_bounds_before_provider_access() -> None:
    service = VesselApiService()

    with pytest.raises(ValueError, match="between 1 and 50"):
        await service.search_vessels("Survey", limit="20")
    with pytest.raises(ValueError, match="latitude out of range"):
        await service.vessels_in_radius(latitude="57", longitude=0, radius_m=100)
    with pytest.raises(ValueError, match="radius must be"):
        await service.vessels_in_radius(latitude=57, longitude=0, radius_m=True)


def test_vessel_cache_key_is_scoped_to_upstream_base_url() -> None:
    assert _cache_key("search", "https://provider-a.example", "survey", "20") != (
        _cache_key("search", "https://provider-b.example", "survey", "20")
    )


def test_coerce_vessel_summary() -> None:
    raw = {
        "id": "123",
        "name": "Ocean Pride",
        "imo": "9876543",
        "mmsi": "235000000",
        "callsign": "MAAA1",
        "vessel_type": "Offshore Supply",
        "flag": "GB",
        "length": "85.5",
        "width": 18,
        "year_built": "2018",
    }
    summary = _coerce_vessel_summary(raw)
    assert summary.id == "9876543"  # IMO resolved as id
    assert summary.name == "Ocean Pride"
    assert summary.imo == "9876543"
    assert summary.mmsi == "235000000"
    assert summary.callsign == "MAAA1"
    assert summary.vessel_type == "Offshore Supply"
    assert summary.flag == "GB"
    assert summary.length == 85.5
    assert summary.width == 18.0
    assert summary.year_built == 2018


def test_coerce_position() -> None:
    raw = {
        "vessel_position": {
            "latitude": "57.1497",
            "longitude": "-2.0943",
            "speed": "12.4",
            "course": "180.0",
            "heading": 182,
            "timestamp": "2026-09-06T10:00:00Z",
            "mmsi": "235000000",
        },
        "destination": "ABERDEEN",
        "eta": "09-07 14:00",
    }
    pos = _coerce_position(raw)
    assert pos.latitude == pytest.approx(57.1497)
    assert pos.longitude == pytest.approx(-2.0943)
    assert pos.sog == pytest.approx(12.4)
    assert pos.cog == pytest.approx(180.0)
    assert pos.heading == 182.0
    assert pos.mmsi == "235000000"
    assert pos.destination == "ABERDEEN"
    assert pos.eta == "09-07 14:00"


def test_coerce_position_preserves_valid_zero_values() -> None:
    pos = _coerce_position(
        {
            "position": {
                "latitude": 0,
                "longitude": 0,
                "speed": 0,
                "course": 0,
                "heading": 0,
            }
        }
    )
    assert pos.latitude == 0.0
    assert pos.longitude == 0.0
    assert pos.sog == 0.0
    assert pos.cog == 0.0
    assert pos.heading == 0.0


def test_coerce_position_discards_non_finite_values() -> None:
    pos = _coerce_position(
        {
            "position": {
                "latitude": "nan",
                "longitude": "inf",
                "speed": "-inf",
                "course": "not-a-number",
            }
        }
    )

    assert pos.latitude is None
    assert pos.longitude is None
    assert pos.sog is None
    assert pos.cog is None


def test_coerce_position_discards_out_of_range_coordinates() -> None:
    pos = _coerce_position(
        {
            "position": {
                "latitude": 91,
                "longitude": -181,
            }
        }
    )

    assert pos.latitude is None
    assert pos.longitude is None


def test_coerce_vessel_summary_discards_non_finite_dimensions() -> None:
    summary = _coerce_vessel_summary(
        {"id": "123", "name": "Example", "length": "nan", "width": "inf"}
    )

    assert summary.length is None
    assert summary.width is None


@pytest.mark.asyncio
async def test_unconfigured_service_fails_closed() -> None:
    svc = VesselApiService()
    with patch(
        "app.services.vessel_api._settings_snapshot",
        return_value=("", "https://api.vesselapi.com", 5.0, 120),
    ):
        assert not svc.is_configured()
        with pytest.raises(VesselApiNotConfiguredError):
            await svc.search_vessels("Surveyor")
        with pytest.raises(VesselApiNotConfiguredError):
            await svc.get_vessel("9876543")
        with pytest.raises(VesselApiNotConfiguredError):
            await svc.get_position("9876543")
        with pytest.raises(VesselApiNotConfiguredError):
            await svc.vessels_in_radius(latitude=57.0, longitude=-2.0, radius_m=50000)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [(403, VesselApiAuthError), (400, VesselApiUpstreamError)],
)
async def test_provider_error_bodies_are_not_embedded_in_adapter_errors(
    status_code: int, error_type: type[Exception]
) -> None:
    """Provider payloads must not cross the adapter error boundary."""
    import httpx

    class FakeClient:
        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        @asynccontextmanager
        async def stream(self, *args: object, **kwargs: object):
            yield httpx.Response(status_code, text="credential-or-request-secret")

    svc = VesselApiService()
    with patch("app.services.vessel_api.httpx.AsyncClient", return_value=FakeClient()):
        with pytest.raises(error_type) as error:
            await svc._request(
                "GET",
                "/search/vessels",
                timeout_s=5.0,
                api_key="key",
                base_url="https://api.vesselapi.com",
            )

    assert "credential-or-request-secret" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("declared_length", [True, False])
async def test_provider_response_size_is_bounded(declared_length: bool) -> None:
    class FakeResponse:
        status_code = 200
        headers = (
            {"Content-Length": str(MAX_VESSEL_API_RESPONSE_BYTES + 1)} if declared_length else {}
        )

        async def aiter_bytes(self):
            if not declared_length:
                yield b"x" * (MAX_VESSEL_API_RESPONSE_BYTES + 1)

    class FakeClient:
        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        @asynccontextmanager
        async def stream(self, *args: object, **kwargs: object):
            yield FakeResponse()

    svc = VesselApiService()
    with patch("app.services.vessel_api.httpx.AsyncClient", return_value=FakeClient()):
        with pytest.raises(VesselApiUpstreamError, match="response too large"):
            await svc._request(
                "GET",
                "/search/vessels",
                timeout_s=5.0,
                api_key="key",
                base_url="https://api.vesselapi.com",
            )


@pytest.mark.asyncio
async def test_search_vessels_success_and_caching() -> None:
    svc = VesselApiService()
    fake_response = {
        "vessels": [
            {
                "name": "Fugro Pioneer",
                "imo": "9683934",
                "mmsi": "244790000",
                "vessel_type": "Research Vessel",
                "flag": "NL",
            }
        ]
    }
    with (
        patch(
            "app.services.vessel_api._settings_snapshot",
            return_value=("mock-key", "https://api.vesselapi.com", 5.0, 120),
        ),
        patch.object(svc, "_get_cached", new_callable=AsyncMock, return_value=None),
        patch.object(svc, "_set_cached", new_callable=AsyncMock) as mock_set_cache,
        patch.object(svc, "_request", new_callable=AsyncMock, return_value=fake_response),
    ):
        result = await svc.search_vessels("Fugro Pioneer", limit=10)
        assert len(result.vessels) == 1
        assert result.vessels[0].name == "Fugro Pioneer"
        assert result.vessels[0].imo == "9683934"
        assert not result.cached
        mock_set_cache.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_vessels_from_cache() -> None:
    svc = VesselApiService()
    cached_payload = {
        "vessels": [
            {
                "id": "9683934",
                "name": "Fugro Pioneer",
                "imo": "9683934",
                "mmsi": "244790000",
                "vessel_type": "Research Vessel",
                "flag": "NL",
            }
        ],
        "upstream_count": 1,
    }
    with (
        patch(
            "app.services.vessel_api._settings_snapshot",
            return_value=("mock-key", "https://api.vesselapi.com", 5.0, 120),
        ),
        patch.object(svc, "_get_cached", new_callable=AsyncMock, return_value=cached_payload),
        patch.object(svc, "_request", new_callable=AsyncMock) as mock_request,
    ):
        result = await svc.search_vessels("Fugro Pioneer", limit=10)
        assert len(result.vessels) == 1
        assert result.cached is True
        mock_request.assert_not_called()


@pytest.mark.asyncio
async def test_search_vessels_validation_bounds() -> None:
    svc = VesselApiService()
    with patch(
        "app.services.vessel_api._settings_snapshot",
        return_value=("mock-key", "https://api.vesselapi.com", 5.0, 120),
    ):
        with pytest.raises(ValueError, match="limit must be between 1 and 50"):
            await svc.search_vessels("Test", limit=0)
        with pytest.raises(ValueError, match="limit must be between 1 and 50"):
            await svc.search_vessels("Test", limit=51)


@pytest.mark.asyncio
async def test_vessels_in_radius_bounds() -> None:
    svc = VesselApiService()
    with patch(
        "app.services.vessel_api._settings_snapshot",
        return_value=("mock-key", "https://api.vesselapi.com", 5.0, 120),
    ):
        with pytest.raises(ValueError, match="latitude out of range"):
            await svc.vessels_in_radius(latitude=95.0, longitude=0.0, radius_m=1000)
        with pytest.raises(ValueError, match="longitude out of range"):
            await svc.vessels_in_radius(latitude=0.0, longitude=200.0, radius_m=1000)
        with pytest.raises(ValueError, match="radius must be"):
            await svc.vessels_in_radius(latitude=0.0, longitude=0.0, radius_m=50)
        with pytest.raises(ValueError, match="radius must be"):
            await svc.vessels_in_radius(latitude=0.0, longitude=0.0, radius_m=600000)
