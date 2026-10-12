"""Buttons: manual refresh, horn and lights."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EMASDataUpdateCoordinator
from .entity import EMASCoordinatorEntity


class RefreshStatusButton(EMASCoordinatorEntity, ButtonEntity):
    """Pull fresh status from the cloud."""

    _attr_name = "Refresh status"

    def __init__(self, coordinator: EMASDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "button_refresh")

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()


class HornAndLightsButton(EMASCoordinatorEntity, ButtonEntity):
    """Sound the horn and flash the lights (RHL-HornAndLight)."""

    _attr_name = "Horn and lights"
    _attr_icon = "mdi:bullhorn"

    def __init__(self, coordinator: EMASDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "button_horn_and_lights")

    async def async_press(self) -> None:
        await self.coordinator.async_horn_and_lights()


class FlashLightsButton(EMASCoordinatorEntity, ButtonEntity):
    """Flash the lights only (RHL-LIGHT)."""

    _attr_name = "Flash lights"
    _attr_icon = "mdi:car-light-high"

    def __init__(self, coordinator: EMASDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "button_flash_lights")

    async def async_press(self) -> None:
        await self.coordinator.async_flash_lights()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EMASDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            RefreshStatusButton(coordinator),
            HornAndLightsButton(coordinator),
            FlashLightsButton(coordinator),
        ]
    )
