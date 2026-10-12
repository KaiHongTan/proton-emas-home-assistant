"""Setup, entities, commands, reauth and diagnostics."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
)

from custom_components.proton_emas.api import EMASApiError, EMASAuthError
from custom_components.proton_emas.const import CONF_TOKEN, DOMAIN
from custom_components.proton_emas.diagnostics import async_get_config_entry_diagnostics

from .conftest import VIN, make_jwt


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _entity_id(hass: HomeAssistant, entry: MockConfigEntry, platform: str, suffix: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{suffix}")


async def test_setup_creates_new_entities(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api: dict[str, AsyncMock]
) -> None:
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(_entity_id(hass, config_entry, "sensor", "sensor_charging_state"))
    assert state.state == "ac_charging"
    assert hass.states.get(_entity_id(hass, config_entry, "sensor", "sensor_charging_power")).state == "2210.3"
    assert hass.states.get(_entity_id(hass, config_entry, "binary_sensor", "binary_charging")).state == "on"
    ts = hass.states.get(_entity_id(hass, config_entry, "sensor", "sensor_telemetry_timestamp"))
    assert ts.state.startswith("2025-10-09T")
    assert hass.states.get(_entity_id(hass, config_entry, "sensor", "sensor_token_expires")).state != "unknown"

    # Tyre warnings: present fields create entities, nonzero is a problem.
    lf = _entity_id(hass, config_entry, "binary_sensor", "binary_tyre_pressure_warning_left_front")
    rf = _entity_id(hass, config_entry, "binary_sensor", "binary_tyre_pressure_warning_right_front")
    assert hass.states.get(lf).state == "off"
    assert hass.states.get(rf).state == "on"
    # Fields absent from the payload create no entity.
    assert _entity_id(hass, config_entry, "binary_sensor", "binary_tyre_pressure_warning_left_rear") is None
    assert _entity_id(hass, config_entry, "sensor", "sensor_central_locking_status") is None


async def test_auth_failure_after_setup_starts_reauth(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api: dict[str, AsyncMock]
) -> None:
    await _setup(hass, config_entry)
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    mock_api["get_vehicle_status"].side_effect = EMASAuthError("expired")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(f["context"]["source"] == SOURCE_REAUTH for f in flows)


async def test_auth_failure_on_setup_starts_reauth(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api: dict[str, AsyncMock]
) -> None:
    mock_api["get_vehicle_status"].side_effect = EMASAuthError("expired")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(f["context"]["source"] == SOURCE_REAUTH for f in flows)


async def test_number_set_value_and_restore(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api: dict[str, AsyncMock]
) -> None:
    config_entry.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "number", DOMAIN, f"{config_entry.entry_id}_number_climate_temp", config_entry=config_entry,
        suggested_object_id="climate_temp",
    )
    mock_restore_cache_with_extra_data(
        hass,
        [(State("number.climate_temp", "24.5"), {"native_value": 24.5, "native_min_value": 16.0,
          "native_max_value": 30.0, "native_step": 0.5, "native_unit_of_measurement": "°C"})],
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    assert coordinator.runtime.climate_target_temp == 24.5

    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.climate_temp", "value": 21}, blocking=True
    )
    assert coordinator.runtime.climate_target_temp == 21
    assert hass.states.get("number.climate_temp").state == "21.0"


async def test_lock_command_reports_locking_until_confirmed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: dict[str, AsyncMock],
    status: dict[str, Any],
) -> None:
    status["doorLockStatusLeftFront"] = 1
    await _setup(hass, config_entry)
    lock_id = _entity_id(hass, config_entry, "lock", "lock_vehicle")
    assert hass.states.get(lock_id).state == "unlocked"

    await hass.services.async_call("lock", "lock", {"entity_id": lock_id}, blocking=True)
    mock_api["vehicle_control"].assert_awaited_with({"serviceKey": "RDL-OFF"})
    assert hass.states.get(lock_id).state == "locking"

    status["doorLockStatusLeftFront"] = 2
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(lock_id).state == "locked"
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    assert not coordinator.is_pending("lock")
    assert coordinator.last_command["requestId"] == "task-1"


async def test_charging_switch_stop_and_start(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: dict[str, AsyncMock],
    status: dict[str, Any],
) -> None:
    await _setup(hass, config_entry)
    switch_id = _entity_id(hass, config_entry, "switch", "switch_charging")
    assert hass.states.get(switch_id).state == "on"

    await hass.services.async_call("switch", "turn_off", {"entity_id": switch_id}, blocking=True)
    mock_api["vehicle_control"].assert_awaited_with({"serviceKey": "RCS-ChargingStop"})
    status["chargerState"] = "25"  # ac_user_stopped, as captured
    status["statusOfChargerConnection"] = "2"
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(switch_id).state == "off"

    await hass.services.async_call("switch", "turn_on", {"entity_id": switch_id}, blocking=True)
    mock_api["vehicle_control"].assert_awaited_with({"serviceKey": "RCS-ChargingStart"})

    status["statusOfChargerConnection"] = "0"
    await hass.data[DOMAIN][config_entry.entry_id].async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(switch_id).state == "unavailable"


async def test_pending_command_times_out(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api: dict[str, AsyncMock]
) -> None:
    await _setup(hass, config_entry)
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator.async_climate_on()  # telemetry never shows preClimateActive
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not coordinator.is_pending("climate")


async def test_seat_vent_sends_integer_level(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api: dict[str, AsyncMock]
) -> None:
    await _setup(hass, config_entry)
    switch_id = _entity_id(hass, config_entry, "switch", "switch_driver_vent")
    await hass.services.async_call("switch", "turn_on", {"entity_id": switch_id}, blocking=True)
    body = mock_api["vehicle_control"].await_args.args[0]
    assert body["parameters"] == [{"key": "rce.ventilation.driver", "intVal": 3}]


async def test_command_failure_raises_homeassistant_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api: dict[str, AsyncMock]
) -> None:
    await _setup(hass, config_entry)
    mock_api["vehicle_control"].side_effect = EMASApiError("vehicle offline")
    button_id = _entity_id(hass, config_entry, "button", "button_horn_and_lights")
    with pytest.raises(HomeAssistantError, match="RHL-HornAndLight failed: vehicle offline"):
        await hass.services.async_call("button", "press", {"entity_id": button_id}, blocking=True)


async def test_command_auth_failure_starts_reauth(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api: dict[str, AsyncMock]
) -> None:
    await _setup(hass, config_entry)
    mock_api["vehicle_control"].side_effect = EMASAuthError("kicked")
    button_id = _entity_id(hass, config_entry, "button", "button_flash_lights")
    with pytest.raises(HomeAssistantError, match="rejected the token"):
        await hass.services.async_call("button", "press", {"entity_id": button_id}, blocking=True)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(f["context"]["source"] == SOURCE_REAUTH for f in flows)


async def test_climate_service_does_not_overwrite_numbers(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api: dict[str, AsyncMock]
) -> None:
    await _setup(hass, config_entry)
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await hass.services.async_call(
        DOMAIN, "remote_climate_start", {"vin": VIN, "temperature": 19, "duration": 10}, blocking=True
    )
    body = mock_api["vehicle_control"].await_args.args[0]
    assert body["duration"] == 10
    assert body["parameters"] == [{"key": "rce.temp", "stringVal": "19.0"}]
    assert coordinator.runtime.climate_target_temp == 22.0

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "remote_climate_start", {"vin": "NOPE"}, blocking=True
        )


async def test_token_expiry_repair_issue(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api: dict[str, AsyncMock]
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=VIN,
        title="e.MAS 7",
        data={**config_entry.data, CONF_TOKEN: make_jwt(time.time() + 86400)},
        options=config_entry.options,
    )
    await _setup(hass, entry)
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"token_expiring_{entry.entry_id}")
    assert issue is not None
    assert issue.translation_key == "token_expiring"


async def test_no_repair_issue_for_fresh_token(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api: dict[str, AsyncMock]
) -> None:
    await _setup(hass, config_entry)
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"token_expiring_{config_entry.entry_id}") is None


async def test_diagnostics_redacts_secrets(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api: dict[str, AsyncMock]
) -> None:
    await _setup(hass, config_entry)
    diag = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diag["entry"]["data"]["token"] == "**REDACTED**"
    assert diag["entry"]["data"]["vin"] == "**REDACTED**"
    assert diag["vehicle_status"]["latitude"] == "**REDACTED**"
    assert diag["vehicle_status"]["vin"] == "**REDACTED**"
    assert diag["vehicle_status"]["chargerState"] == "2"
