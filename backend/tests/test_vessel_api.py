"""Tests for VesselAPI proxy service, validation, error mapping, and GraphQL queries."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.vessel_api import (
    VesselApiNotConfiguredError,
    VesselApiService,
    _coerce_position,
    _coerce_vessel_summary,
    _validate_id_type,
    _validate_name,
)


def test_validate_name() -> None:
    assert _validate_name("  Northern Explorer  ") == "Northern Explorer"
    with pytest.raises(ValueError, match="must not be empty"):
        _validate_name("   ")
    with pytest.raises(ValueError, match="too long"):
        _validate_name("a" * 101)


def test_validate_id_type() -> None:
    assert _validate_id_type("IMO") == "imo"
    assert _validate_id_type("mmsi") == "mmsi"
    assert _validate_id_type("eni ") == "eni"
    with pytest.raises(ValueError, match="idType must be one of"):
        _validate_id_type("invalid_type")


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
