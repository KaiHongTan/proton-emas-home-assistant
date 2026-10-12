"""Diagnostics: a redacted status dump users can attach to issues.

This is the easiest way to collect payloads from untested models (e.MAS 5,
e.MAS 7 PHEV) without an HTTPS proxy.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN, CONF_VIN, DOMAIN
from .coordinator import EMASDataUpdateCoordinator

TO_REDACT = {
    CONF_TOKEN,
    CONF_VIN,
    "vin",
    "title",
    "latitude",
    "longitude",
    "altitude",
    "requestId",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: EMASDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    expires = coordinator.token_expires_at
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "token_expires_at": expires.isoformat() if expires else None,
        "last_update_success": coordinator.last_update_success,
        "last_command": async_redact_data(coordinator.last_command or {}, TO_REDACT),
        "vehicle_status": async_redact_data(coordinator.data or {}, TO_REDACT),
    }
