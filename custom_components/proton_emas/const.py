"""Constants for Proton e.MAS integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "proton_emas"

CONF_API_BASE: Final = "api_base"
CONF_APP_VERSION: Final = "app_version"
CONF_APP_VERSION_CODE: Final = "app_version_code"
CONF_CLIENT_ID: Final = "client_id"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_TENANT_ID: Final = "tenant_id"
CONF_TOKEN: Final = "token"
CONF_VIN: Final = "vin"
CONF_TITLE: Final = "title"

DEFAULT_API_BASE: Final = "https://emas-app.acotech.my:8443"
DEFAULT_APP_VERSION: Final = "2.2.2"
DEFAULT_APP_VERSION_CODE: Final = "2"
DEFAULT_CLIENT_ID: Final = "ios"
DEFAULT_SCAN_INTERVAL: Final = 120
DEFAULT_TENANT_ID: Final = "e_Mas"

# Door/window semantics observed from mobile-app telemetry
DOOR_OPEN_VALUES: Final = frozenset({"1"})
TRUNK_OPEN_VALUES: Final = frozenset({"1"})
HOOD_OPEN_VALUES: Final = frozenset({"1"})
SUNROOF_OPEN_VALUES: Final = frozenset({"1"})
DOOR_LOCKED_STATUS_VALUE: Final = "2"
DOOR_UNLOCKED_STATUS_VALUE: Final = "1"
WINDOW_VENT_WIN_STATUS_VALUES: Final = frozenset({"1"})

CHARGE_TIME_SENTINEL: Final = frozenset({"2047", "-1", ""})

SERVICE_REMOTE_CLIMATE_START: Final = "remote_climate_start"
SERVICE_REFRESH_VEHICLE: Final = "refresh_vehicle"

# ChargeStatus wire values (acosdk ChargeStatus.kt / ChargeStatusAdapter: int on the wire).
CHARGER_STATE_OPTIONS: Final = {
    0: "default",
    1: "not_charging",
    2: "ac_charging",
    3: "ac_charging_stopped",
    25: "ac_charging_user_stopped",
    4: "ac_charging_completed",
    5: "ac_heating",
    6: "ac_scheduled",
    27: "ac_error",
    18: "dc_error",
    15: "dc_charging",
    24: "dc_fast_charging",
    26: "dc_charging_stopped",
    28: "dc_boost_charging",
    30: "wireless_charging",
}
CHARGER_STATE_OTHER: Final = "other"
CHARGER_STATE_CHARGING: Final = frozenset({2, 15, 24, 28, 30})
