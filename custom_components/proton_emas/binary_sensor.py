"""Binary sensors derived from Proton e.MAS vehicle status."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CHARGER_STATE_CHARGING,
    DOMAIN,
    DOOR_OPEN_VALUES,
    HOOD_OPEN_VALUES,
    SUNROOF_OPEN_VALUES,
    TRUNK_OPEN_VALUES,
)
from .coordinator import EMASDataUpdateCoordinator
from .entity import EMASCoordinatorEntity


def _truthy_string(raw: Any) -> bool:
    return str(raw).lower() == "true"


def _nonzero(raw: Any) -> bool:
    s = str(raw).strip()
    return s not in ("", "0", "false", "False")


def _charging(raw: Any) -> bool:
    try:
        return int(float(raw)) in CHARGER_STATE_CHARGING
    except (TypeError, ValueError):
        return False


def _tyre_warning(key: str, field: str, name: str) -> EMASBinarySensorEntityDescription:
    return EMASBinarySensorEntityDescription(
        key=key,
        api_field=field,
        name=name,
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_nonzero,
        create_if_present=True,
    )


@dataclass(frozen=True, kw_only=True)
class EMASBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Binary sensor tied to API field."""

    api_field: str
    value_fn: Callable[[Any], bool]
    # See EMASSensorEntityDescription.create_if_present.
    create_if_present: bool = False


BINARY_TYPES: tuple[EMASBinarySensorEntityDescription, ...] = (
    EMASBinarySensorEntityDescription(
        key="pre_climate_active",
        api_field="preClimateActive",
        name="Pre-climate active",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_truthy_string,
    ),
    EMASBinarySensorEntityDescription(
        key="defrost_active",
        api_field="defrostActive",
        name="Defrost active",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_truthy_string,
    ),
    EMASBinarySensorEntityDescription(
        key="air_blower_active",
        api_field="airBlowerActive",
        name="Air blower active",
        value_fn=_truthy_string,
    ),
    EMASBinarySensorEntityDescription(
        key="engine_running",
        api_field="engineStatus",
        name="Engine running",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_nonzero,
    ),
    EMASBinarySensorEntityDescription(
        key="charger_connected",
        api_field="statusOfChargerConnection",
        name="Charger connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=_nonzero,
    ),
    EMASBinarySensorEntityDescription(
        key="position_trusted",
        api_field="posCanBeTrusted",
        name="GPS trusted",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_truthy_string,
    ),
    EMASBinarySensorEntityDescription(
        key="door_open_left_front",
        api_field="doorOpenStatusLeftFront",
        name="Door open left front",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda r: str(r) in DOOR_OPEN_VALUES,
    ),
    EMASBinarySensorEntityDescription(
        key="door_open_right_front",
        api_field="doorOpenStatusRightFront",
        name="Door open right front",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda r: str(r) in DOOR_OPEN_VALUES,
    ),
    EMASBinarySensorEntityDescription(
        key="door_open_left_rear",
        api_field="doorOpenStatusLeftRear",
        name="Door open left rear",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda r: str(r) in DOOR_OPEN_VALUES,
    ),
    EMASBinarySensorEntityDescription(
        key="door_open_right_rear",
        api_field="doorOpenStatusRightRear",
        name="Door open right rear",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda r: str(r) in DOOR_OPEN_VALUES,
    ),
    EMASBinarySensorEntityDescription(
        key="trunk_open",
        api_field="trunkOpenStatus",
        name="Trunk open",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda r: str(r) in TRUNK_OPEN_VALUES,
    ),
    EMASBinarySensorEntityDescription(
        key="hood_open",
        api_field="engineHoodOpenStatus",
        name="Hood open",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda r: str(r) in HOOD_OPEN_VALUES,
    ),
    EMASBinarySensorEntityDescription(
        key="sunroof_open",
        api_field="sunroofOpenStatus",
        name="Sunroof open",
        value_fn=lambda r: str(r) in SUNROOF_OPEN_VALUES,
    ),
    EMASBinarySensorEntityDescription(
        key="seatbelt_driver",
        api_field="seatBeltStatusDriver",
        name="Seatbelt driver",
        device_class=BinarySensorDeviceClass.SAFETY,
        value_fn=_truthy_string,
    ),
    EMASBinarySensorEntityDescription(
        key="seatbelt_passenger",
        api_field="seatBeltStatusPassenger",
        name="Seatbelt passenger",
        device_class=BinarySensorDeviceClass.SAFETY,
        value_fn=_truthy_string,
    ),
    EMASBinarySensorEntityDescription(
        key="seatbelt_driver_rear",
        api_field="seatBeltStatusDriverRear",
        name="Seatbelt driver rear",
        device_class=BinarySensorDeviceClass.SAFETY,
        value_fn=_truthy_string,
    ),
    EMASBinarySensorEntityDescription(
        key="seatbelt_passenger_rear",
        api_field="seatBeltStatusPassengerRear",
        name="Seatbelt passenger rear",
        device_class=BinarySensorDeviceClass.SAFETY,
        value_fn=_truthy_string,
    ),
    EMASBinarySensorEntityDescription(
        key="charging",
        api_field="chargerState",
        name="Charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=_charging,
        create_if_present=True,
    ),
)

TYRE_WARNING_TYPES: tuple[EMASBinarySensorEntityDescription, ...] = tuple(
    _tyre_warning(f"tyre_{kind}_warning_{pos_key}", f"{field}{pos}", f"Tyre {label} warning {pos_label}")
    for kind, field, label in (
        ("pressure", "tyrePreWarning", "pressure"),
        ("temperature", "tyreTempWarning", "temperature"),
    )
    for pos, pos_key, pos_label in (
        ("LeftFront", "left_front", "left front"),
        ("RightFront", "right_front", "right front"),
        ("LeftRear", "left_rear", "left rear"),
        ("RightRear", "right_rear", "right rear"),
    )
)


class EMASBinarySensor(EMASCoordinatorEntity, BinarySensorEntity):
    """Binary telemetry sensor."""

    entity_description: EMASBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: EMASDataUpdateCoordinator,
        description: EMASBinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, f"binary_{description.key}")
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        raw = self.coordinator.data.get(self.entity_description.api_field)
        if raw is None:
            return None
        return self.entity_description.value_fn(raw)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EMASDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    async_add_entities(
        EMASBinarySensor(coordinator, d)
        for d in (*BINARY_TYPES, *TYRE_WARNING_TYPES)
        if not d.create_if_present or data.get(d.api_field) is not None
    )
