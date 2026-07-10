"""DataUpdateCoordinator for Proton e.MAS.

Interpretation of opaque API fields is based on observed mobile-app traffic; field
semantics may change without notice. See the project README for background.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EMASApi, EMASApiError, EMASAuthError
from .const import (
    CONF_API_BASE,
    CONF_APP_VERSION,
    CONF_APP_VERSION_CODE,
    CONF_CLIENT_ID,
    CONF_TENANT_ID,
    CONF_TOKEN,
    CONF_VIN,
    DEFAULT_API_BASE,
    DEFAULT_APP_VERSION,
    DEFAULT_APP_VERSION_CODE,
    DEFAULT_CLIENT_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TENANT_ID,
    DOMAIN,
    DOOR_LOCKED_STATUS_VALUE,
    DOOR_UNLOCKED_STATUS_VALUE,
    WINDOW_VENT_WIN_STATUS_VALUES,
)

_LOGGER = logging.getLogger(__name__)

# Short burst polling until telemetry catches up after remote control.
_CONTROL_FOLLOW_UP_INITIAL_DELAY = 1.5
_CONTROL_FOLLOW_UP_INTERVAL = 2.5
_CONTROL_FOLLOW_UP_MAX_ATTEMPTS = 24

_WINDOW_STATUS_FIELDS: tuple[str, ...] = (
    "winStatusLeftFront",
    "winStatusRightFront",
    "winStatusLeftRear",
    "winStatusRightRear",
)

_WINDOW_POSITION_FIELDS: tuple[str, ...] = (
    "winPosLeftFront",
    "winPosRightFront",
    "winPosLeftRear",
    "winPosRightRear",
)


def is_win_status_vent_down(win_status_raw: Any) -> bool:
    """True when window glass is lowered (breathable / vent)."""
    s = "" if win_status_raw is None else str(win_status_raw)
    return s in WINDOW_VENT_WIN_STATUS_VALUES


def is_any_window_vent_down(data: dict[str, Any]) -> bool:
    return any(is_win_status_vent_down(data.get(k)) for k in _WINDOW_STATUS_FIELDS)


def _primary_door_lock_status(data: dict[str, Any]) -> str:
    return str(
        data.get("doorLockStatusLeftFront")
        or data.get("doorLockStatusRightFront")
        or data.get("doorLockStatusLeftRear")
        or data.get("doorLockStatusRightRear")
        or ""
    )


def doors_locked_state(data: dict[str, Any]) -> bool | None:
    """Lock entity semantics — doorLockStatus* '2' locked, '1' unlocked."""

    status = _primary_door_lock_status(data)
    if status == DOOR_LOCKED_STATUS_VALUE:
        return True
    if status == DOOR_UNLOCKED_STATUS_VALUE:
        return False
    return None


def predicate_doors_locked(data: dict[str, Any]) -> bool:
    return doors_locked_state(data) is True


def predicate_doors_unlocked(data: dict[str, Any]) -> bool:
    return doors_locked_state(data) is False


def predicate_pre_climate_active(data: dict[str, Any]) -> bool:
    raw = data.get("preClimateActive")
    return raw is not None and str(raw).lower() == "true"


def predicate_pre_climate_inactive(data: dict[str, Any]) -> bool:
    raw = data.get("preClimateActive")
    return raw is not None and str(raw).lower() != "true"


def predicate_driver_vent_on(data: dict[str, Any]) -> bool:
    raw = data.get("drvVentSts")
    return raw is not None and str(raw) == "1"


def predicate_driver_vent_off(data: dict[str, Any]) -> bool:
    raw = data.get("drvVentSts")
    # drvVentSts "1" fan on, inactive typically "2".
    return raw is not None and str(raw) != "1"


def predicate_passenger_vent_on(data: dict[str, Any]) -> bool:
    raw = data.get("passVentSts")
    return raw is not None and str(raw) == "1"


def predicate_passenger_vent_off(data: dict[str, Any]) -> bool:
    raw = data.get("passVentSts")
    # passVentSts "1" on, inactive typically "2".
    return raw is not None and str(raw) != "1"


def _window_vent_telemetry_complete(data: dict[str, Any]) -> bool:
    """All four winStatus and winPos keys present in getVehicleStatus payload."""

    for k in _WINDOW_STATUS_FIELDS:
        if data.get(k) is None or str(data.get(k)).strip() == "":
            return False
    for k in _WINDOW_POSITION_FIELDS:
        if data.get(k) is None or str(data.get(k)).strip() == "":
            return False
    return True


def _window_breathable_open_signals(data: dict[str, Any]) -> bool:
    """Breathable / crack: winStatus vent (const) OR any winPosition > 0 (e.g. '8' after RWS-BreathableON)."""

    if is_any_window_vent_down(data):
        return True
    for k in _WINDOW_POSITION_FIELDS:
        try:
            if float(str(data[k]).strip()) > 0.0:
                return True
        except ValueError:
            continue
    return False


def is_window_breathable_active(data: dict[str, Any]) -> bool:
    """Switch semantics: breathable when telemetry shows vent crack (winStatus '1', winPos e.g. '8' after RWS-BreathableON)."""

    if not _window_vent_telemetry_complete(data):
        return is_any_window_vent_down(data)
    return _window_breathable_open_signals(data)


def predicate_window_vent_any_down(data: dict[str, Any]) -> bool:
    """Command RWS-BreathableON: wait for ventilation signal (winStatus '1', winPos e.g. '8')."""

    return _window_vent_telemetry_complete(data) and _window_breathable_open_signals(data)


def predicate_window_vent_none_down(data: dict[str, Any]) -> bool:
    """RWS-OFF: cloud can still return prior winStatus '1' / winPos '8' briefly — require all '0'."""

    if not _window_vent_telemetry_complete(data):
        return False
    for k in _WINDOW_STATUS_FIELDS:
        if str(data.get(k)).strip() != "0":
            return False
    for k in _WINDOW_POSITION_FIELDS:
        try:
            if float(str(data.get(k)).strip()) != 0.0:
                return False
        except ValueError:
            return False
    return True


@dataclass
class CoordinatorRuntime:
    """User-adjustable values used when issuing remote commands."""

    climate_target_temp: float = 22.0
    climate_duration_min: int = 15


class EMASDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls vehicle status and exposes last payload to platforms."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: EMASApi,
        entry: ConfigEntry,
    ) -> None:
        self.api = api
        self.config_entry = entry
        self.runtime = CoordinatorRuntime()
        scan = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        interval = timedelta(seconds=max(30, int(scan)))
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=interval,
        )
        self._control_follow_up_task: asyncio.Task[None] | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.get_vehicle_status()
        except EMASAuthError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except EMASApiError as err:
            raise UpdateFailed(str(err)) from err

    def _schedule_control_follow_up(self, predicate: Callable[[dict[str, Any]], bool]) -> None:
        """Poll quickly until telemetry matches commanded state or attempts end."""

        if self._control_follow_up_task is not None and not self._control_follow_up_task.done():
            self._control_follow_up_task.cancel()
        self._control_follow_up_task = self.hass.async_create_task(
            self._run_control_follow_up(predicate)
        )

    async def async_cancel_control_follow_up(self) -> None:
        """Stop any in-progress fast polling (e.g. on config unload)."""

        task = self._control_follow_up_task
        if task is None or task.done():
            self._control_follow_up_task = None
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        self._control_follow_up_task = None

    async def _run_control_follow_up(self, predicate: Callable[[dict[str, Any]], bool]) -> None:
        try:
            await asyncio.sleep(_CONTROL_FOLLOW_UP_INITIAL_DELAY)
            for attempt in range(_CONTROL_FOLLOW_UP_MAX_ATTEMPTS):
                try:
                    await self.async_refresh()
                except Exception:
                    _LOGGER.debug(
                        "Control follow-up refresh failed (attempt %s/%s)",
                        attempt + 1,
                        _CONTROL_FOLLOW_UP_MAX_ATTEMPTS,
                        exc_info=True,
                    )
                else:
                    if predicate(self.data):
                        return

                if attempt < _CONTROL_FOLLOW_UP_MAX_ATTEMPTS - 1:
                    await asyncio.sleep(_CONTROL_FOLLOW_UP_INTERVAL)

            _LOGGER.debug(
                "Control follow-up: state not reflected after %s attempts",
                _CONTROL_FOLLOW_UP_MAX_ATTEMPTS,
            )
        except asyncio.CancelledError:
            raise

    async def async_unlock(self) -> None:
        await self.api.vehicle_control({"serviceKey": "RDU-ON"})
        self._schedule_control_follow_up(predicate_doors_unlocked)

    async def async_lock(self) -> None:
        await self.api.vehicle_control({"serviceKey": "RDL-OFF"})
        self._schedule_control_follow_up(predicate_doors_locked)

    async def async_climate_on(self) -> None:
        await self.api.vehicle_control(
            {
                "serviceKey": "RCE-ON",
                "duration": self.runtime.climate_duration_min,
                "parameters": [
                    {"key": "rce.temp", "stringVal": str(self.runtime.climate_target_temp)}
                ],
            }
        )
        self._schedule_control_follow_up(predicate_pre_climate_active)

    async def async_climate_off(self) -> None:
        await self.api.vehicle_control({"serviceKey": "RCE-OFF"})
        self._schedule_control_follow_up(predicate_pre_climate_inactive)

    async def async_driver_vent_on(self) -> None:
        await self.api.vehicle_control(
            {
                "serviceKey": "RCE-VentilationDriverON",
                "parameters": [{"key": "rce.ventilation.driver", "intVal": "3"}],
            }
        )
        self._schedule_control_follow_up(predicate_driver_vent_on)

    async def async_driver_vent_off(self) -> None:
        await self.api.vehicle_control({"serviceKey": "RCE-VentilationDriverOFF"})
        self._schedule_control_follow_up(predicate_driver_vent_off)

    async def async_passenger_vent_on(self) -> None:
        await self.api.vehicle_control(
            {
                "serviceKey": "RCE-VentilationPassengerON",
                "parameters": [{"key": "rce.ventilation.passenger", "intVal": "3"}],
            }
        )
        self._schedule_control_follow_up(predicate_passenger_vent_on)

    async def async_passenger_vent_off(self) -> None:
        await self.api.vehicle_control({"serviceKey": "RCE-VentilationPassengerOFF"})
        self._schedule_control_follow_up(predicate_passenger_vent_off)

    async def async_window_breathable_on(self) -> None:
        await self.api.vehicle_control({"serviceKey": "RWS-BreathableON"})
        self._schedule_control_follow_up(predicate_window_vent_any_down)

    async def async_window_breathable_off(self) -> None:
        await self.api.vehicle_control({"serviceKey": "RWS-OFF"})
        self._schedule_control_follow_up(predicate_window_vent_none_down)


def build_api_from_entry(
    session: Any,
    entry: ConfigEntry,
) -> EMASApi:
    """Construct API client from config entry data + options."""
    data = entry.data
    opts = entry.options
    return EMASApi(
        session,
        vin=data[CONF_VIN],
        token=data[CONF_TOKEN],
        api_base=opts.get(CONF_API_BASE, DEFAULT_API_BASE),
        tenant_id=opts.get(CONF_TENANT_ID, DEFAULT_TENANT_ID),
        client_id=opts.get(CONF_CLIENT_ID, DEFAULT_CLIENT_ID),
        app_version=opts.get(CONF_APP_VERSION, DEFAULT_APP_VERSION),
        app_version_code=opts.get(CONF_APP_VERSION_CODE, DEFAULT_APP_VERSION_CODE),
    )
