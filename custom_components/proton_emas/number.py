"""Numbers that configure remote climate commands."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .coordinator import EMASDataUpdateCoordinator
from .entity import EMASCoordinatorEntity


class ClimateTargetTemperature(EMASCoordinatorEntity, NumberEntity):
    """Target cabin temperature for remote climate start."""

    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 16.0
    _attr_native_max_value = 30.0
    _attr_native_step = 0.5
    _attr_mode = NumberMode.BOX
    _attr_name = "Remote climate temperature"

    def __init__(self, coordinator: EMASDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "number_climate_temp")

    @property
    def native_value(self) -> float:
        return self.coordinator.runtime.climate_target_temp

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.runtime.climate_target_temp = value
        await self.async_write_ha_state()


class ClimateDurationMinutes(EMASCoordinatorEntity, NumberEntity):
    """Duration for remote climate when turned on."""

    _attr_native_min_value = 5
    _attr_native_max_value = 30
    _attr_native_step = 5
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = "min"
    _attr_name = "Remote climate duration"

    def __init__(self, coordinator: EMASDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "number_climate_duration")

    @property
    def native_value(self) -> float:
        return float(self.coordinator.runtime.climate_duration_min)

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.runtime.climate_duration_min = int(round(value))
        await self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EMASDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ClimateTargetTemperature(coordinator),
            ClimateDurationMinutes(coordinator),
        ]
    )
