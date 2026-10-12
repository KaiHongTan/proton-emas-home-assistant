"""Proton e.MAS cloud integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_VIN,
    DOMAIN,
    SERVICE_REFRESH_VEHICLE,
    SERVICE_REMOTE_CLIMATE_START,
)
from .coordinator import EMASDataUpdateCoordinator, build_api_from_entry

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.BUTTON,
]

# HA 2026+: config_schema_only_config_entries removed — prefer config_entry_only_config_schema.
if hasattr(cv, "config_entry_only_config_schema"):
    CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
elif hasattr(cv, "config_schema_only_config_entries"):
    CONFIG_SCHEMA = cv.config_schema_only_config_entries(DOMAIN)
else:
    CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

SERVICE_REMOTE_CLIMATE_START_SCHEMA = vol.Schema(
    {
        vol.Required("vin"): cv.string,
        vol.Optional("temperature", default=22.0): vol.Coerce(float),
        vol.Optional("duration", default=15): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
    }
)

SERVICE_REFRESH_VEHICLE_SCHEMA = vol.Schema(
    {
        vol.Optional("vin"): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """YAML not used."""

    async def _climate_start(call: Any) -> None:
        vin = call.data["vin"]
        temp = call.data["temperature"]
        duration = call.data["duration"]
        domain_data = hass.data.get(DOMAIN, {})
        for coord in domain_data.values():
            if coord.config_entry.data.get(CONF_VIN) == vin:
                # One-off values: the number entities keep their own settings.
                await coord.async_climate_on(temperature=temp, duration_min=duration)
                return
        raise ServiceValidationError(f"No Proton e.MAS configuration for VIN {vin}")

    async def _refresh_vehicle(call: Any) -> None:
        vin = call.data.get("vin")
        domain_data = hass.data.get(DOMAIN, {})
        if not domain_data:
            raise ServiceValidationError("No Proton e.MAS vehicles configured.")
        matched = 0
        for coord in domain_data.values():
            if vin is not None and coord.config_entry.data.get(CONF_VIN) != vin:
                continue
            await coord.async_request_refresh()
            matched += 1
        if vin is not None and matched == 0:
            raise ServiceValidationError(f"No Proton e.MAS configuration for VIN {vin}")

    if not hass.services.has_service(DOMAIN, SERVICE_REMOTE_CLIMATE_START):
        hass.services.async_register(
            DOMAIN,
            SERVICE_REMOTE_CLIMATE_START,
            _climate_start,
            schema=SERVICE_REMOTE_CLIMATE_START_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH_VEHICLE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_REFRESH_VEHICLE,
            _refresh_vehicle,
            schema=SERVICE_REFRESH_VEHICLE_SCHEMA,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Proton e.MAS from a config entry."""
    session = async_get_clientsession(hass)
    api = build_api_from_entry(session, entry)
    coordinator = EMASDataUpdateCoordinator(hass, api, entry)

    # Auth failures surface as ConfigEntryAuthFailed from the coordinator,
    # here and on every later poll, so HA starts the reauth flow.
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload entry."""
    coordinator: EMASDataUpdateCoordinator | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )
    if coordinator is not None:
        await coordinator.async_cancel_control_follow_up()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload on options update."""
    hass.config_entries.async_schedule_reload(entry.entry_id)
