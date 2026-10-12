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
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import EMASApi, EMASApiError, EMASAuthError, token_expiry
from .const import (
    CHARGER_STATE_CHARGING,
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

# Polling with backoff until telemetry catches up after remote control
# (~65 s over 12 polls; previously 24 polls at a fixed 2.5 s).
_CONTROL_FOLLOW_UP_DELAYS: tuple[float, ...] = (1.5, 2.5, 2.5, 3, 4, 5, 5, 6, 8, 8, 10, 10)
_CONTROL_FOLLOW_UP_BUDGET = sum(_CONTROL_FOLLOW_UP_DELAYS)

TOKEN_EXPIRY_WARNING = timedelta(days=3)

# The official app sends seat-vent levels as integers (t1.java).
SEAT_VENT_LEVEL = 3

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


def is_charging(data: dict[str, Any]) -> bool | None:
    """chargerState in an active charging state; None if not reported."""

    raw = data.get("chargerState")
    try:
        return int(float(raw)) in CHARGER_STATE_CHARGING
    except (TypeError, ValueError):
        return None


def predicate_charging(data: dict[str, Any]) -> bool:
    # RCS-ChargingStart: chargerState goes 25 -> 1 -> 2 within ~7 s.
    return is_charging(data) is True


def predicate_not_charging(data: dict[str, Any]) -> bool:
    # RCS-ChargingStop: chargerState 2 -> 25 (user stopped) within ~2 s.
    return is_charging(data) is False


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


@dataclass
class _PendingCommand:
    """A command whose effect we are waiting to see in telemetry."""

    name: str
    predicate: Callable[[dict[str, Any]], bool]
    deadline: float


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
        self.token_expires_at = token_expiry(api.token)
        self.last_command: dict[str, Any] | None = None
        # The official SDK runs one command at a time; mirror that.
        self._command_lock = asyncio.Lock()
        self._pending: dict[str, _PendingCommand] = {}
        self._control_follow_up_task: asyncio.Task[None] | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.api.get_vehicle_status()
        except EMASAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except EMASApiError as err:
            raise UpdateFailed(str(err)) from err
        self._update_token_expiry_issue()
        return data

    def _update_token_expiry_issue(self) -> None:
        """Raise a repair issue shortly before the captured token expires."""

        issue_id = f"token_expiring_{self.config_entry.entry_id}"
        expires = self.token_expires_at
        if expires is not None and expires - dt_util.utcnow() < TOKEN_EXPIRY_WARNING:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="token_expiring",
                translation_placeholders={
                    "title": self.config_entry.title,
                    "expires": dt_util.as_local(expires).strftime("%Y-%m-%d %H:%M"),
                },
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    def is_pending(self, name: str) -> bool:
        """True while a command named ``name`` is awaiting telemetry confirmation."""

        return name in self._pending

    async def _async_send(
        self,
        body: dict[str, Any],
        *,
        pending: str | None = None,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
    ) -> None:
        """Send one command, then watch telemetry for its effect.

        ``pending`` names the expected state change; a newer command with the
        same name (e.g. unlock after lock) replaces the older expectation, while
        unrelated commands are verified side by side instead of cancelling.
        """

        service_key = body.get("serviceKey")
        async with self._command_lock:
            try:
                response = await self.api.vehicle_control(body)
            except EMASAuthError as err:
                self.config_entry.async_start_reauth(self.hass)
                raise HomeAssistantError(
                    f"Proton e.MAS rejected the token while sending {service_key}: {err}"
                ) from err
            except EMASApiError as err:
                raise HomeAssistantError(f"{service_key} failed: {err}") from err
        self.last_command = {
            "serviceKey": service_key,
            "requestId": response.get("requestId"),
            "sent_at": dt_util.utcnow().isoformat(),
        }
        if pending is None or predicate is None:
            return
        loop = self.hass.loop
        self._pending[pending] = _PendingCommand(
            pending, predicate, loop.time() + _CONTROL_FOLLOW_UP_BUDGET
        )
        self.async_update_listeners()
        if self._control_follow_up_task is None or self._control_follow_up_task.done():
            self._control_follow_up_task = self.config_entry.async_create_background_task(
                self.hass, self._run_control_follow_up(), f"{DOMAIN} control follow-up"
            )

    async def async_cancel_control_follow_up(self) -> None:
        """Stop any in-progress fast polling (e.g. on config unload)."""

        task = self._control_follow_up_task
        self._pending.clear()
        if task is None or task.done():
            self._control_follow_up_task = None
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        self._control_follow_up_task = None

    async def _run_control_follow_up(self) -> None:
        """Poll with backoff until every pending command shows up or times out."""

        loop = self.hass.loop
        attempt = 0
        while self._pending:
            delay = _CONTROL_FOLLOW_UP_DELAYS[min(attempt, len(_CONTROL_FOLLOW_UP_DELAYS) - 1)]
            attempt += 1
            await asyncio.sleep(delay)
            try:
                await self.async_refresh()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Control follow-up refresh failed", exc_info=True)
            now = loop.time()
            for name, cmd in list(self._pending.items()):
                if self.data is not None and cmd.predicate(self.data):
                    del self._pending[name]
                elif now >= cmd.deadline:
                    _LOGGER.debug("Control follow-up: %s not reflected in telemetry", name)
                    del self._pending[name]
        self.async_update_listeners()

    async def async_unlock(self) -> None:
        await self._async_send(
            {"serviceKey": "RDU-ON"}, pending="lock", predicate=predicate_doors_unlocked
        )

    async def async_lock(self) -> None:
        await self._async_send(
            {"serviceKey": "RDL-OFF"}, pending="lock", predicate=predicate_doors_locked
        )

    async def async_climate_on(
        self, temperature: float | None = None, duration_min: int | None = None
    ) -> None:
        temp = self.runtime.climate_target_temp if temperature is None else temperature
        duration = self.runtime.climate_duration_min if duration_min is None else duration_min
        await self._async_send(
            {
                "serviceKey": "RCE-ON",
                "duration": duration,
                "parameters": [{"key": "rce.temp", "stringVal": str(temp)}],
            },
            pending="climate",
            predicate=predicate_pre_climate_active,
        )

    async def async_climate_off(self) -> None:
        await self._async_send(
            {"serviceKey": "RCE-OFF"}, pending="climate", predicate=predicate_pre_climate_inactive
        )

    async def async_driver_vent_on(self) -> None:
        await self._async_send(
            {
                "serviceKey": "RCE-VentilationDriverON",
                "parameters": [{"key": "rce.ventilation.driver", "intVal": SEAT_VENT_LEVEL}],
            },
            pending="driver_vent",
            predicate=predicate_driver_vent_on,
        )

    async def async_driver_vent_off(self) -> None:
        await self._async_send(
            {"serviceKey": "RCE-VentilationDriverOFF"},
            pending="driver_vent",
            predicate=predicate_driver_vent_off,
        )

    async def async_passenger_vent_on(self) -> None:
        await self._async_send(
            {
                "serviceKey": "RCE-VentilationPassengerON",
                "parameters": [{"key": "rce.ventilation.passenger", "intVal": SEAT_VENT_LEVEL}],
            },
            pending="passenger_vent",
            predicate=predicate_passenger_vent_on,
        )

    async def async_passenger_vent_off(self) -> None:
        await self._async_send(
            {"serviceKey": "RCE-VentilationPassengerOFF"},
            pending="passenger_vent",
            predicate=predicate_passenger_vent_off,
        )

    async def async_window_breathable_on(self) -> None:
        await self._async_send(
            {"serviceKey": "RWS-BreathableON"},
            pending="window_vent",
            predicate=predicate_window_vent_any_down,
        )

    async def async_window_breathable_off(self) -> None:
        await self._async_send(
            {"serviceKey": "RWS-OFF"},
            pending="window_vent",
            predicate=predicate_window_vent_none_down,
        )

    async def async_charging_start(self) -> None:
        await self._async_send(
            {"serviceKey": "RCS-ChargingStart"}, pending="charging", predicate=predicate_charging
        )

    async def async_charging_stop(self) -> None:
        await self._async_send(
            {"serviceKey": "RCS-ChargingStop"},
            pending="charging",
            predicate=predicate_not_charging,
        )

    async def async_horn_and_lights(self) -> None:
        await self._async_send({"serviceKey": "RHL-HornAndLight"})

    async def async_flash_lights(self) -> None:
        await self._async_send({"serviceKey": "RHL-LIGHT"})


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
