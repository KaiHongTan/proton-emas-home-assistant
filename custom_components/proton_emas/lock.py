"""Vehicle lock (aggregate door lock status)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, DOOR_LOCKED_STATUS_VALUE, DOOR_UNLOCKED_STATUS_VALUE
from .coordinator import EMASDataUpdateCoordinator
from .entity import EMASCoordinatorEntity


def _primary_door_lock_status(data: dict[str, Any]) -> str:
    return str(
        data.get("doorLockStatusLeftFront")
        or data.get("doorLockStatusRightFront")
        or data.get("doorLockStatusLeftRear")
        or data.get("doorLockStatusRightRear")
        or ""
    )


class EMASVehicleLock(EMASCoordinatorEntity, LockEntity):
    """Remote door lock."""

    _attr_name = "Door locks"

    def __init__(self, coordinator: EMASDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "lock_vehicle")

    @property
    def is_locked(self) -> bool | None:
        status = _primary_door_lock_status(self.coordinator.data)
        if status == DOOR_LOCKED_STATUS_VALUE:
            return True
        if status == DOOR_UNLOCKED_STATUS_VALUE:
            return False
        return None

    async def async_unlock(self, **kwargs: object) -> None:
        await self.coordinator.async_unlock()

    async def async_lock(self, **kwargs: object) -> None:
        await self.coordinator.async_lock()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EMASDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EMASVehicleLock(coordinator)])
