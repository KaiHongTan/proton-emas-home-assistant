"""Config flow tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.proton_emas.api import EMASAuthError
from custom_components.proton_emas.const import CONF_TOKEN, CONF_VIN, DOMAIN

from .conftest import TOKEN, VIN


async def test_user_flow_creates_entry(hass: HomeAssistant, mock_api: dict[str, AsyncMock]) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_VIN: VIN.lower(), CONF_TOKEN: f" {TOKEN} "}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_VIN] == VIN
    assert result["data"][CONF_TOKEN] == TOKEN


async def test_user_flow_invalid_token(hass: HomeAssistant, mock_api: dict[str, AsyncMock]) -> None:
    mock_api["get_vehicle_status"].side_effect = EMASAuthError("bad")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_VIN: VIN, CONF_TOKEN: "x"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth_shows_form_then_updates_token(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: dict[str, AsyncMock],
    status: dict[str, Any],
) -> None:
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    # The stored (rejected) token must not be re-submitted automatically.
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "new-token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_TOKEN] == "new-token"
