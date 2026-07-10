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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import (
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


@dataclass(frozen=True, kw_only=True)
class EMASBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Binary sensor tied to API field."""

    api_field: str
    value_fn: Callable[[Any], bool]


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
    async_add_entities(EMASBinarySensor(coordinator, d) for d in BINARY_TYPES)
