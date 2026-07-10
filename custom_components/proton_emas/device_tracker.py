"""Device tracker when GPS is trusted."""

from __future__ import annotations

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import EMASDataUpdateCoordinator
from .entity import EMASCoordinatorEntity


def _parse_coord(raw: StateType) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


class EMASDeviceTracker(EMASCoordinatorEntity, TrackerEntity):
    """Vehicle GPS position."""

    _attr_name = "Location"

    def __init__(self, coordinator: EMASDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "device_tracker")

    @property
    def latitude(self) -> float | None:
        data = self.coordinator.data
        if str(data.get("posCanBeTrusted", "")).lower() != "true":
            return None
        return _parse_coord(data.get("latitude"))

    @property
    def longitude(self) -> float | None:
        data = self.coordinator.data
        if str(data.get("posCanBeTrusted", "")).lower() != "true":
            return None
        return _parse_coord(data.get("longitude"))

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def location_accuracy(self) -> int:
        return 10


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EMASDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EMASDeviceTracker(coordinator)])
