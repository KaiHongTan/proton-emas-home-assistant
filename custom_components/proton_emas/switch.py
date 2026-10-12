"""Switches mirroring remote climate, ventilation, window breathable, and charging."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .coordinator import (
    EMASDataUpdateCoordinator,
    is_charging,
    is_window_breathable_active,
)
from .entity import EMASCoordinatorEntity


class RemoteClimateSwitch(EMASCoordinatorEntity, SwitchEntity):
    """Remote cabin preconditioning (pre-climate)."""

    _attr_name = "Remote climate"

    def __init__(self, coordinator: EMASDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "switch_remote_climate")

    @property
    def is_on(self) -> bool | None:
        raw = self.coordinator.data.get("preClimateActive")
        if raw is None:
            return None
        return str(raw).lower() == "true"

    async def async_turn_on(self, **kwargs: object) -> None:
        await self.coordinator.async_climate_on()

    async def async_turn_off(self, **kwargs: object) -> None:
        await self.coordinator.async_climate_off()


class DriverVentSwitch(EMASCoordinatorEntity, SwitchEntity):
    """Driver seat ventilation."""

    _attr_name = "Driver seat ventilation"

    def __init__(self, coordinator: EMASDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "switch_driver_vent")

    @property
    def is_on(self) -> bool | None:
        raw = self.coordinator.data.get("drvVentSts")
        if raw is None:
            return None
        return str(raw) == "1"

    async def async_turn_on(self, **kwargs: object) -> None:
        await self.coordinator.async_driver_vent_on()

    async def async_turn_off(self, **kwargs: object) -> None:
        await self.coordinator.async_driver_vent_off()


class PassengerVentSwitch(EMASCoordinatorEntity, SwitchEntity):
    """Passenger seat ventilation."""

    _attr_name = "Passenger seat ventilation"

    def __init__(self, coordinator: EMASDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "switch_passenger_vent")

    @property
    def is_on(self) -> bool | None:
        raw = self.coordinator.data.get("passVentSts")
        if raw is None:
            return None
        return str(raw) == "1"

    async def async_turn_on(self, **kwargs: object) -> None:
        await self.coordinator.async_passenger_vent_on()

    async def async_turn_off(self, **kwargs: object) -> None:
        await self.coordinator.async_passenger_vent_off()


class WindowBreathableSwitch(EMASCoordinatorEntity, SwitchEntity):
    """Window breathable / vent mode."""

    _attr_name = "Window vent"

    def __init__(self, coordinator: EMASDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "switch_window_vent")

    @property
    def is_on(self) -> bool | None:
        return is_window_breathable_active(self.coordinator.data)

    async def async_turn_on(self, **kwargs: object) -> None:
        await self.coordinator.async_window_breathable_on()

    async def async_turn_off(self, **kwargs: object) -> None:
        await self.coordinator.async_window_breathable_off()


class ChargingSwitch(EMASCoordinatorEntity, SwitchEntity):
    """Start / stop charging while the cable is connected."""

    _attr_name = "Charging"
    _attr_icon = "mdi:ev-station"

    def __init__(self, coordinator: EMASDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "switch_charging")

    @property
    def available(self) -> bool:
        # statusOfChargerConnection: 0 unplugged, 2 plugged in idle, 3 charging.
        connection = self.coordinator.data.get("statusOfChargerConnection")
        return super().available and str(connection) not in ("0", "None", "")

    @property
    def is_on(self) -> bool | None:
        return is_charging(self.coordinator.data)

    async def async_turn_on(self, **kwargs: object) -> None:
        await self.coordinator.async_charging_start()

    async def async_turn_off(self, **kwargs: object) -> None:
        await self.coordinator.async_charging_stop()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EMASDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = [
        RemoteClimateSwitch(coordinator),
        DriverVentSwitch(coordinator),
        PassengerVentSwitch(coordinator),
        WindowBreathableSwitch(coordinator),
    ]
    if (coordinator.data or {}).get("chargerState") is not None:
        entities.append(ChargingSwitch(coordinator))
    async_add_entities(entities)
