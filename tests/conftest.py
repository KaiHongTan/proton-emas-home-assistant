"""Shared fixtures for Proton e.MAS tests."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.proton_emas.const import (
    CONF_SCAN_INTERVAL,
    CONF_TITLE,
    CONF_TOKEN,
    CONF_VIN,
    DOMAIN,
)

VIN = "L6TE21SB0XX000001"


def make_jwt(exp: float) -> str:
    """e.MAS-shaped token: loginTime + timeout (ms) instead of exp."""

    def enc(obj: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    timeout_ms = 2592000000
    claims = {"loginTime": int(exp * 1000) - timeout_ms, "timeout": timeout_ms}
    return f"{enc({'alg': 'HS256'})}.{enc(claims)}.sig"


TOKEN = make_jwt(time.time() + 30 * 86400)


def base_status() -> dict[str, Any]:
    return {
        "vin": VIN,
        "powerBatteryLevel": 80.0,
        "chargerState": "2",
        "statusOfChargerConnection": "3",
        "chargeUAct": "240.25",
        "chargeIAct": "9.2",
        "updateTime": 1760000000000,
        "doorLockStatusLeftFront": 2,
        "preClimateActive": "false",
        "drvVentSts": "2",
        "passVentSts": "2",
        "latitude": "3.1390",
        "longitude": "101.6869",
        "posCanBeTrusted": "true",
        "tyrePreWarningLeftFront": 0,
        "tyrePreWarningRightFront": 1,
    }


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/ in every test."""


@pytest.fixture(autouse=True)
def fast_follow_up() -> Generator[None]:
    with (
        patch("custom_components.proton_emas.coordinator._CONTROL_FOLLOW_UP_DELAYS", (0, 0, 0)),
        patch("custom_components.proton_emas.coordinator._CONTROL_FOLLOW_UP_BUDGET", 0.5),
    ):
        yield


@pytest.fixture
def status() -> dict[str, Any]:
    return base_status()


@pytest.fixture
def mock_api(status: dict[str, Any]) -> Generator[dict[str, AsyncMock]]:
    with (
        patch(
            "custom_components.proton_emas.api.EMASApi.get_vehicle_status",
            new=AsyncMock(side_effect=lambda: dict(status)),
        ) as get_status,
        patch(
            "custom_components.proton_emas.api.EMASApi.vehicle_control",
            new=AsyncMock(return_value={"requestId": "task-1", "vin": VIN}),
        ) as control,
    ):
        yield {"get_vehicle_status": get_status, "vehicle_control": control}


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=VIN,
        title="e.MAS 7",
        data={CONF_VIN: VIN, CONF_TOKEN: TOKEN, CONF_TITLE: "e.MAS 7"},
        options={CONF_SCAN_INTERVAL: 120},
    )
