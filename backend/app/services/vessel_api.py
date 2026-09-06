"""VesselAPI proxy — backend-owned adapter for https://github.com/vessel-api/VesselApi.

The frontend never talks to api.vesselapi.com directly: that would leak the
API key and bypass Hydenlyne's auth boundary (docs/ARCHITECTURE.md). Every
call goes through this service which validates input, applies finite timeouts,
caches in Redis, and surfaces typed errors that GraphQL/REST can map.

Uses httpx directly rather than requiring vessel-api-python at import time so
tests and local dev remain runnable without the vendor SDK. The same endpoints
and semantics are exposed — `pip install vessel-api-python` remains the
documented upgrade path if callers want the SDK's iterators.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Literal, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

VESSEL_ID_TYPES: set[str] = {"imo", "mmsi", "eni"}


class VesselApiNotConfiguredError(RuntimeError):
    """Raised when VESSELAPI_API_KEY is blank - fail-closed, not fail-open."""

    def __init__(self) -> None:
        super().__init__("Vessel tracking is not configured")


class VesselApiAuthError(RuntimeError):
    """401 - key missing/invalid/revoked."""

    def __init__(self, message: str = "Vessel API authentication failed") -> None:
        super().__init__(message)


class VesselApiRateLimitedError(RuntimeError):
    """429 - caller should back off; SDK automatically retries."""

    def __init__(self, message: str = "Vessel API rate limit exceeded") -> None:
        super().__init__(message)


class VesselApiNotFoundError(RuntimeError):
    """404 - no such vessel/port/event."""

    def __init__(self, message: str = "Vessel not found") -> None:
        super().__init__(message)


class VesselApiUpstreamError(RuntimeError):
    """5xx or transport failure - observable, retryable."""


@dataclass(frozen=True)
class VesselSummary:
    """Minimal, typed projection of a VesselAPI vessel record.

    Only C1-safe preview fields are surfaced. Full payload stays behind the
    adapter - callers receive a scrubbed copy, not the raw upstream JSON.
    """

    id: str
    name: Optional[str] = None
    imo: Optional[str] = None
    mmsi: Optional[str] = None
    callsign: Optional[str] = None
    vessel_type: Optional[str] = None
    flag: Optional[str] = None
    # Optional enrichment when present upstream
    length: Optional[float] = None
    width: Optional[float] = None
    year_built: Optional[int] = None


@dataclass(frozen=True)
class VesselPosition:
    mmsi: Optional[str] = None
    imo: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    sog: Optional[float] = None  # speed over ground
    cog: Optional[float] = None  # course over ground
    heading: Optional[float] = None
    timestamp: Optional[str] = None
    destination: Optional[str] = None
    eta: Optional[str] = None


@dataclass(frozen=True)
class VesselSearchResult:
    vessels: list[VesselSummary] = field(default_factory=list)
    cached: bool = False
    provider: str = "vesselapi"
    # Raw count from upstream before local limit
    upstream_count: Optional[int] = None


def _settings_snapshot() -> tuple[str, str, float, int]:
    s = get_settings()
    return (
        s.VESSELAPI_API_KEY.strip(),
        s.VESSELAPI_BASE_URL.rstrip("/"),
        float(s.VESSELAPI_TIMEOUT_SECONDS),
        int(s.VESSELAPI_CACHE_TTL_SECONDS),
    )


def _validate_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Vessel name must not be empty")
    if len(cleaned) > 100:
        raise ValueError("Vessel name too long (max 100)")
    return cleaned


def _validate_id_type(id_type: str) -> Literal["imo", "mmsi", "eni"]:
    lowered = id_type.strip().lower()
    if lowered not in VESSEL_ID_TYPES:
        raise ValueError(f"idType must be one of {sorted(VESSEL_ID_TYPES)}")
    # mypy literal narrowing
    assert lowered in ("imo", "mmsi", "eni")
    return lowered  # type: ignore[return-value]


def _cache_key(prefix: str, *parts: str) -> str:
    raw = ":".join(parts)
    digest = hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()[:16]
    return f"hydenlyne:vesselapi:{prefix}:{digest}"


def _coerce_vessel_summary(raw: dict[str, Any]) -> VesselSummary:
    """Map upstream shape to our typed summary - tolerant to schema drift.

    Upstream examples use `name/mmsi/imo/vessel_type/flag`. Keep mapping
    permissive and never propagate raw secrets.
    """

    # Upstream has shown both `vessel_type` and `vesselType`
    vtype = raw.get("vessel_type") or raw.get("vesselType") or raw.get("type")
    flag = raw.get("flag")
    # Length/width occasionally present; coerce defensively
    try:
        length = float(raw["length"]) if raw.get("length") is not None else None
    except Exception:
        length = None
    try:
        width = float(raw["width"]) if raw.get("width") is not None else None
    except Exception:
        width = None
    try:
        year_built = int(raw["year_built"]) if raw.get("year_built") is not None else None
    except Exception:
        year_built = None
    # Id fallback: imo > mmsi > eni > id
    resolved_id = (
        str(raw.get("imo") or raw.get("mmsi") or raw.get("eni") or raw.get("id") or "")
    ).strip()
    return VesselSummary(
        id=resolved_id or str(raw.get("id", "")),
        name=(str(raw["name"]).strip() if raw.get("name") else None),
        imo=str(raw["imo"]).strip() if raw.get("imo") is not None else None,
        mmsi=str(raw["mmsi"]).strip() if raw.get("mmsi") is not None else None,
        callsign=str(raw["callsign"]).strip() if raw.get("callsign") else None,
        vessel_type=str(vtype).strip() if vtype else None,
        flag=str(flag).strip() if flag else None,
        length=length,
        width=width,
        year_built=year_built,
    )


def _coerce_position(raw: dict[str, Any]) -> VesselPosition:
    # Upstream positions appear under several wrappers:
    #   { vessel_position: { latitude, longitude, ... } }
    #   { position: { ... } }
    #   { latitude, longitude, ... }
    inner: dict[str, Any]
    if isinstance(raw.get("vessel_position"), dict):
        inner = raw["vessel_position"]
    elif isinstance(raw.get("position"), dict):
        inner = raw["position"]
    elif isinstance(raw.get("vesselPosition"), dict):
        inner = raw["vesselPosition"]
    else:
        inner = raw
    # ETA/destination may be siblings
    eta = raw.get("eta") or inner.get("eta")
    dest = raw.get("destination") or inner.get("destination") or raw.get("reportedDestination")

    def _f(key: str) -> Optional[float]:
        v = inner.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except Exception:
            return None

    ts_raw = inner.get("timestamp") or inner.get("updatedAt") or raw.get("timestamp")
    return VesselPosition(
        mmsi=str(inner.get("mmsi") or raw.get("mmsi") or "") or None,
        imo=str(inner.get("imo") or raw.get("imo") or "") or None,
        latitude=_f("latitude") or _f("lat"),
        longitude=_f("longitude") or _f("lon") or _f("lng"),
        sog=_f("sog") or _f("speed"),
        cog=_f("cog") or _f("course"),
        heading=_f("heading") or _f("hdg"),
        timestamp=str(ts_raw).strip() or None if ts_raw else None,
        destination=str(dest).strip() if dest else None,
        eta=str(eta).strip() if eta else None,
    )


class VesselApiService:
    """Backend-owned VesselAPI adapter. Thin transport delegates here."""

    def _require_key(self) -> tuple[str, str, float, int]:
        api_key, base_url, timeout_s, ttl_s = _settings_snapshot()
        if not api_key:
            raise VesselApiNotConfiguredError()
        return api_key, base_url, timeout_s, ttl_s

    def is_configured(self) -> bool:
        api_key, _, _, _ = _settings_snapshot()
        return bool(api_key.strip())

    async def _get_cached(self, key: str) -> Optional[Any]:
        try:
            from app.services.cache import cache_service

            if not await cache_service.is_redis_available():
                return None
            return await cache_service.get(key)
        except Exception:
            return None

    async def _set_cached(self, key: str, value: Any, ttl_s: int) -> None:
        try:
            from app.services.cache import cache_service

            if not await cache_service.is_redis_available():
                return
            await cache_service.set(key, value, ttl=timedelta(seconds=ttl_s))
        except Exception as e:
            logger.debug("VesselAPI cache set failed: %s", e)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        timeout_s: float,
        api_key: str,
        base_url: str,
    ) -> dict[str, Any]:
        url = f"{base_url}{path}"
        timeout = httpx.Timeout(timeout_s, connect=min(5.0, timeout_s))
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
                resp = await client.request(method, url, params=params)
        except httpx.TimeoutException as exc:
            logger.warning("VesselAPI timeout %s %s: %s", method, path, exc)
            raise VesselApiUpstreamError("Vessel service timed out") from exc
        except httpx.TransportError as exc:
            logger.warning("VesselAPI transport %s %s: %s", method, path, exc)
            raise VesselApiUpstreamError("Vessel service unavailable") from exc

        if resp.status_code == 401:
            raise VesselApiAuthError()
        if resp.status_code == 403:
            # Upstream uses 403 for suspended keys / plan limits
            body = resp.text[:500]
            raise VesselApiAuthError(body or "Vessel API key forbidden or plan limit")
        if resp.status_code == 404:
            raise VesselApiNotFoundError()
        if resp.status_code == 429:
            # Respect Retry-After but surface as typed error for transport
            retry_after = resp.headers.get("Retry-After", "")
            msg = f"Rate limited{f' retry after {retry_after}' if retry_after else ''}"
            raise VesselApiRateLimitedError(msg)
        if resp.status_code == 402:
            raise VesselApiAuthError("Vessel API satellite credits exhausted")
        if resp.status_code >= 500:
            raise VesselApiUpstreamError(f"Vessel service error {resp.status_code}")
        if resp.status_code >= 400:
            # Safe excerpt, no secret echo
            body = resp.text[:500]
            raise VesselApiUpstreamError(f"Vessel request failed {resp.status_code}: {body}")

        try:
            data: dict[str, Any] = resp.json() if resp.content else {}
        except Exception as exc:
            raise VesselApiUpstreamError("Invalid vessel response") from exc
        if not isinstance(data, dict):
            # Some endpoints return list at top level; normalize
            return {"_list": data}
        return data

    # --- public ops ---

    async def search_vessels(
        self,
        name: str,
        *,
        limit: int = 20,
    ) -> VesselSearchResult:
        """Search by vessel name/callsign. Provider-cached for 2 min."""
        q = _validate_name(name)
        if limit < 1 or limit > 50:
            raise ValueError("limit must be between 1 and 50")
        api_key, base_url, timeout_s, ttl_s = self._require_key()
        ckey = _cache_key("search", q.lower(), str(limit))
        cached = await self._get_cached(ckey)
        if isinstance(cached, dict) and isinstance(cached.get("vessels"), list):
            try:
                vessels = [
                    _coerce_vessel_summary(v) for v in cached["vessels"] if isinstance(v, dict)
                ]
                # Rehydrate as plain dicts for GraphQL mapping below
                return VesselSearchResult(
                    vessels=[
                        _coerce_vessel_summary(v) for v in cached["vessels"] if isinstance(v, dict)
                    ],
                    cached=True,
                    upstream_count=cached.get("upstream_count"),
                )
                _ = vessels  # keep mypy quiet if branch unreachable
            except Exception:
                pass

        data = await self._request(
            "GET",
            "/search/vessels",
            params={"filter.name": q, "pagination.limit": str(limit)},
            timeout_s=timeout_s,
            api_key=api_key,
            base_url=base_url,
        )
        # Upstream shape: { vessels: [...] } or { data: [...] } or { hits: [...] }
        raw_list: list[Any]
        if isinstance(data.get("vessels"), list):
            raw_list = data["vessels"]
        elif isinstance(data.get("data"), list):
            raw_list = data["data"]
        elif isinstance(data.get("hits"), list):
            raw_list = data["hits"]
        elif isinstance(data.get("_list"), list):
            raw_list = data["_list"]
        else:
            raw_list = []

        summaries = [
            _coerce_vessel_summary(item)
            for item in raw_list
            if isinstance(item, dict) and (item.get("name") or item.get("imo") or item.get("mmsi"))
        ][:limit]

        # Cache the raw dict projection, not the dataclass, for JSON round-trip
        try:
            to_cache = {
                "vessels": [s.__dict__ for s in summaries],
                "upstream_count": len(raw_list),
            }
            await self._set_cached(ckey, to_cache, ttl_s)
        except Exception:
            pass

        return VesselSearchResult(vessels=summaries, cached=False, upstream_count=len(raw_list))

    async def get_vessel(self, vessel_id: str, *, id_type: str = "imo") -> VesselSummary:
        vid = vessel_id.strip()
        if not vid:
            raise ValueError("vessel id must not be empty")
        itype = _validate_id_type(id_type)
        api_key, base_url, timeout_s, ttl_s = self._require_key()
        ckey = _cache_key("get", vid, itype)
        cached = await self._get_cached(ckey)
        if isinstance(cached, dict) and (cached.get("name") or cached.get("imo")):
            try:
                return _coerce_vessel_summary(cached)
            except Exception:
                pass
        data = await self._request(
            "GET",
            f"/vessel/{vid}",
            params={"filter.idType": itype},
            timeout_s=timeout_s,
            api_key=api_key,
            base_url=base_url,
        )
        # Response may be { vessel: {...} } or bare {...}
        inner = data.get("vessel") if isinstance(data.get("vessel"), dict) else data
        if not isinstance(inner, dict) or not inner:
            raise VesselApiNotFoundError()
        # Inject id fallback if upstream omits
        if not inner.get("imo") and itype == "imo":
            inner = {**inner, "imo": vid}
        summary = _coerce_vessel_summary(inner)
        try:
            await self._set_cached(ckey, inner, ttl_s)
        except Exception:
            pass
        return summary

    async def get_position(
        self,
        vessel_id: str,
        *,
        id_type: str = "imo",
        use_satellite_fallback: bool = False,
    ) -> VesselPosition:
        """Current AIS position. Satellite fallback is off by default (costs credits)."""
        vid = vessel_id.strip()
        if not vid:
            raise ValueError("vessel id must not be empty")
        itype = _validate_id_type(id_type)
        api_key, base_url, timeout_s, _ = self._require_key()
        params: dict[str, Any] = {"filter.idType": itype}
        if use_satellite_fallback:
            params["filter.sat"] = "true"
        data = await self._request(
            "GET",
            f"/vessel/{vid}/position",
            params=params,
            timeout_s=timeout_s,
            api_key=api_key,
            base_url=base_url,
        )
        # Normalize; raise not-found if empty but vessel exists
        if not data or (
            isinstance(data, dict)
            and not any(
                k in data
                for k in ("vessel_position", "position", "latitude", "longitude", "vesselPosition")
            )
        ):
            # Provider raises 404 for missing position; we only get here if 200 with no pos
            raise VesselApiNotFoundError("No stored position for vessel")
        return _coerce_position(data)

    async def vessels_in_radius(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_m: int,
        limit: int = 20,
    ) -> VesselSearchResult:
        if not (-90 <= latitude <= 90):
            raise ValueError("latitude out of range")
        if not (-180 <= longitude <= 180):
            raise ValueError("longitude out of range")
        if not (100 <= radius_m <= 500000):
            raise ValueError("radius must be 100..500000 meters")
        if not (1 <= limit <= 50):
            raise ValueError("limit must be 1..50")
        api_key, base_url, timeout_s, ttl_s = self._require_key()
        ckey = _cache_key(
            "radius", f"{latitude:.4f}", f"{longitude:.4f}", str(radius_m), str(limit)
        )
        cached = await self._get_cached(ckey)
        if isinstance(cached, dict) and isinstance(cached.get("vessels"), list):
            try:
                return VesselSearchResult(
                    vessels=[
                        _coerce_vessel_summary(v) for v in cached["vessels"] if isinstance(v, dict)
                    ],
                    cached=True,
                    upstream_count=cached.get("upstream_count"),
                )
            except Exception:
                pass
        data = await self._request(
            "GET",
            "/location/vessels/radius",
            params={
                "filter.latitude": str(latitude),
                "filter.longitude": str(longitude),
                "filter.radius": str(radius_m),
                "pagination.limit": str(limit),
            },
            timeout_s=timeout_s,
            api_key=api_key,
            base_url=base_url,
        )
        raw_list: list[Any]
        if isinstance(data.get("vessels"), list):
            raw_list = data["vessels"]
        elif isinstance(data.get("hits"), list):
            raw_list = data["hits"]
        elif isinstance(data.get("_list"), list):
            raw_list = data["_list"]
        else:
            raw_list = []
        # Radius endpoint returns position-flavored rows (vessel_name/lat/lon) - map
        summaries: list[VesselSummary] = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            # Normalize position rows to summary where name lives in vessel_name
            if item.get("vessel_name") and not item.get("name"):
                item = {**item, "name": item.get("vessel_name")}
            if item.get("name") or item.get("imo") or item.get("mmsi"):
                summaries.append(_coerce_vessel_summary(item))
            if len(summaries) >= limit:
                break
        try:
            await self._set_cached(
                ckey,
                {"vessels": [s.__dict__ for s in summaries], "upstream_count": len(raw_list)},
                ttl_s,
            )
        except Exception:
            pass
        return VesselSearchResult(vessels=summaries, cached=False, upstream_count=len(raw_list))

    async def health_check(self) -> dict[str, Any]:
        """Lightweight health probe - does not require a valid vessel id.

        Returns a scrubbed status dict (no key). Used by `GET /health/` to
        surface readiness without hitting a billable vessel lookup.
        """
        api_key, base_url, timeout_s, _ = _settings_snapshot()
        if not api_key:
            return {"configured": False, "reachable": False}
        # Introspect search with a cheap one-row page; 401/403 surface misconfig
        try:
            await self._request(
                "GET",
                "/search/vessels",
                params={"filter.name": "a", "pagination.limit": "1"},
                timeout_s=min(5.0, timeout_s),
                api_key=api_key,
                base_url=base_url,
            )
            return {"configured": True, "reachable": True}
        except VesselApiAuthError as exc:
            return {"configured": True, "reachable": False, "error": str(exc)[:120]}
        except Exception as exc:
            return {"configured": True, "reachable": False, "error": str(exc)[:120]}


vessel_api_service = VesselApiService()
