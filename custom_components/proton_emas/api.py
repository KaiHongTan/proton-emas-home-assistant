"""HTTP client for Proton e.MAS cloud API."""

from __future__ import annotations

import base64
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import aiohttp

from .const import (
    DEFAULT_API_BASE,
    DEFAULT_APP_VERSION,
    DEFAULT_APP_VERSION_CODE,
    DEFAULT_CLIENT_ID,
    DEFAULT_TENANT_ID,
)

_LOGGER = logging.getLogger(__name__)


class EMASAuthError(Exception):
    """Authentication failed (e.g. expired or invalid token)."""


class EMASApiError(Exception):
    """API returned an error or unexpected response."""


def token_expiry(token: str) -> datetime | None:
    """Return when the JWT expires as an aware datetime, or None if unknown.

    e.MAS tokens carry no ``exp``; they have ``loginTime`` and ``timeout``,
    both in milliseconds (30 days observed). A standard ``exp`` (seconds) is
    used if present. The signature is not checked; this only reads the expiry
    so we can warn before the token dies.
    """
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload))
        if "exp" in claims:
            return datetime.fromtimestamp(int(claims["exp"]), tz=UTC)
        expires_ms = int(claims["loginTime"]) + int(claims["timeout"])
        return datetime.fromtimestamp(expires_ms / 1000, tz=UTC)
    except (ValueError, KeyError, TypeError, OverflowError, OSError):
        return None


def _unwrap(result: dict[str, Any]) -> Any:
    """Return ``data`` from the {code, msg, data} envelope or raise."""
    code = result.get("code")
    if code == 200:
        return result.get("data")
    msg = result.get("msg") or str(result)
    if code in (401, 403):
        raise EMASAuthError(msg)
    # Unknown codes are logged verbatim so the "session evicted" code can be
    # identified from real traffic and mapped to EMASAuthError.
    _LOGGER.warning("e.MAS API returned code=%s msg=%s", code, msg)
    raise EMASApiError(f"{msg} (code {code})")


class EMASApi:
    """Low-level async client mirroring Proton e.MAS app requests."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        vin: str,
        token: str,
        api_base: str = DEFAULT_API_BASE,
        tenant_id: str = DEFAULT_TENANT_ID,
        client_id: str = DEFAULT_CLIENT_ID,
        app_version: str = DEFAULT_APP_VERSION,
        app_version_code: str = DEFAULT_APP_VERSION_CODE,
    ) -> None:
        self._session = session
        self._vin = vin
        self._token = token
        self._api_base = api_base.rstrip("/")
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._app_version = app_version
        self._app_version_code = app_version_code

    @property
    def token(self) -> str:
        return self._token

    def _headers(self) -> dict[str, str]:
        return {
            "TENANT-ID": self._tenant_id,
            "CLIENT-ID": self._client_id,
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en",
            "Authorization": f"Bearer {self._token}",
            "User-Agent": (
                f"Pronet/{self._app_version} "
                f"(com.malaysia.emas; build:{self._app_version_code}; iOS HomeAssistant)"
                " Alamofire/5.10.0"
            ),
            "X-AGENT-TYPE": "iOS",
            "X-AGENT-VERSION": "17.0",
            "X-EQUIPMENT-BRAND": "iPhone",
            "X-EQUIPMENT-MODEL": "HomeAssistant",
            "X-EQUIPMENT-OS-VERSION": "17.0",
            "X-EQUIPMENT-TYPE": "e_Mas",
            "APP-NAME": "Proton_e.Mas",
            "Software-Version": self._app_version,
            "VERSION-NAME": self._app_version,
            "VERSION-CODE": self._app_version_code,
            "REQUEST-ID": uuid.uuid4().hex,
        }

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._api_base}{path}"
        try:
            async with self._session.post(
                url,
                headers=self._headers(),
                json=body,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 401:
                    raise EMASAuthError("Unauthorized (401) — token may be expired")
                text = await resp.text()
                try:
                    payload: dict[str, Any] = await resp.json()
                except aiohttp.ContentTypeError:
                    raise EMASApiError(f"Non-JSON response HTTP {resp.status}: {text[:200]}") from None
                if resp.status >= 400:
                    raise EMASApiError(f"HTTP {resp.status}: {payload.get('msg', text[:200])}")
                return payload
        except aiohttp.ClientError as err:
            raise EMASApiError(f"Network error: {err}") from err

    async def get_vehicle_status(self) -> dict[str, Any]:
        """Return full API JSON for getVehicleStatus."""
        data = _unwrap(await self._post("/iot/function/getVehicleStatus", {"vin": self._vin}))
        if not isinstance(data, dict):
            raise EMASApiError("Missing data object in response")
        return data

    async def vehicle_control(self, body: dict[str, Any]) -> dict[str, Any]:
        """Send vehicleControl; return the CommandResponse ({requestId, timestamp, vin})."""
        payload = dict(body)
        payload.setdefault("vin", self._vin)
        data = _unwrap(await self._post("/iot/function/vehicleControl", payload))
        response = data if isinstance(data, dict) else {}
        _LOGGER.debug(
            "vehicleControl %s accepted, requestId=%s",
            payload.get("serviceKey"),
            response.get("requestId"),
        )
        return response
