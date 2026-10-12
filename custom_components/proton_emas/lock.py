"""Vehicle lock (aggregate door lock status)."""

from __future__ import annotations

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EMASDataUpdateCoordinator, doors_locked_state
from .entity import EMASCoordinatorEntity


class EMASVehicleLock(EMASCoordinatorEntity, LockEntity):
    """Remote door lock."""

    _attr_name = "Door locks"

    def __init__(self, coordinator: EMASDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "lock_vehicle")
        self._requested_locked: bool | None = None

    @property
    def is_locked(self) -> bool | None:
        return doors_locked_state(self.coordinator.data)

    @property
    def is_locking(self) -> bool:
        return self.coordinator.is_pending("lock") and self._requested_locked is True

    @property
    def is_unlocking(self) -> bool:
        return self.coordinator.is_pending("lock") and self._requested_locked is False

    async def async_unlock(self, **kwargs: object) -> None:
        self._requested_locked = False
        await self.coordinator.async_unlock()

    async def async_lock(self, **kwargs: object) -> None:
        self._requested_locked = True
        await self.coordinator.async_lock()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EMASDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EMASVehicleLock(coordinator)])
