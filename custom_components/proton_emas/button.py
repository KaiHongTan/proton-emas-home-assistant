"""Manual refresh button."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EMASDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RefreshStatusButton(coordinator)])
