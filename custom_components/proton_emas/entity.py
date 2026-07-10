"""Base entity for Proton e.MAS."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_TITLE, CONF_VIN, DOMAIN
from .coordinator import EMASDataUpdateCoordinator


class EMASCoordinatorEntity(CoordinatorEntity[EMASDataUpdateCoordinator]):
    """Shared coordinator binding and device info."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EMASDataUpdateCoordinator, unique_suffix: str) -> None:
        super().__init__(coordinator)
        self._unique_suffix = unique_suffix
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{unique_suffix}"

    @property
    def device_info(self) -> DeviceInfo:
        vin = self.coordinator.config_entry.data[CONF_VIN]
        title = self.coordinator.config_entry.data.get(CONF_TITLE, vin)
        return {
            "identifiers": {(DOMAIN, vin)},
            "name": title,
            "manufacturer": "Proton",
            "model": "e.MAS",
        }
