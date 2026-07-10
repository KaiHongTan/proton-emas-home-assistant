"""Sensors for Proton e.MAS vehicle telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CHARGE_TIME_SENTINEL, DOMAIN
from .coordinator import EMASDataUpdateCoordinator
from .entity import EMASCoordinatorEntity

@dataclass(frozen=True, kw_only=True)
class EMASSensorEntityDescription(SensorEntityDescription):
    """Maps HA sensor to API field name."""

    api_field: str


def _parse_float(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_int(raw: Any) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


SENSOR_TYPES: tuple[EMASSensorEntityDescription, ...] = (
    EMASSensorEntityDescription(
        key="charge_level",
        api_field="chargeLevel",
        name="12V battery level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EMASSensorEntityDescription(
        key="power_battery_level",
        api_field="powerBatteryLevel",
        name="Battery level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="voltage",
        api_field="voltage",
        name="HV voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="distance_battery_only",
        api_field="distanceToEmptyOnBatteryOnly",
        name="Range (battery only)",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="distance_battery_100_soc",
        api_field="distanceToEmptyOnBattery100Soc",
        name="Range at 100% SoC",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="distance_to_empty",
        api_field="distanceToEmpty",
        name="Distance to empty",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="aver_power_consumption",
        api_field="averPowerConsumption",
        name="Average power consumption",
        native_unit_of_measurement="kWh/100km",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="aver_tra_power_consumption",
        api_field="averTraPowerConsumption",
        name="Trip average power consumption",
        native_unit_of_measurement="kWh/100km",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="ave_tra_fuel_consumption",
        api_field="aveTraFuelConsumption",
        name="Trip average fuel consumption",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="dc_charge_current",
        api_field="dcChargeIAct",
        name="DC charge current",
        native_unit_of_measurement="A",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="dc_charge_voltage",
        api_field="dcChargeUAct",
        name="DC charge voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="charge_current",
        api_field="chargeIAct",
        name="Charge current",
        native_unit_of_measurement="A",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="charge_voltage",
        api_field="chargeUAct",
        name="Charge voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="discharge_current",
        api_field="disChargeIAct",
        name="Discharge current",
        native_unit_of_measurement="A",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="discharge_voltage",
        api_field="disChargeUAct",
        name="Discharge voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="exterior_temperature",
        api_field="exteriorTemp",
        name="Exterior temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="interior_temperature",
        api_field="interiorTemp",
        name="Interior temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="interior_pm25",
        api_field="interiorPM25",
        name="Interior PM2.5",
        native_unit_of_measurement="µg/m³",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="speed",
        api_field="speed",
        name="Speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="average_speed",
        api_field="avgSpeed",
        name="Average speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="odometer",
        api_field="odometer",
        name="Odometer",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EMASSensorEntityDescription(
        key="altitude",
        api_field="altitude",
        name="Altitude",
        native_unit_of_measurement="m",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="direction",
        api_field="direction",
        name="Heading",
        native_unit_of_measurement="°",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="tyre_pressure_left_front",
        api_field="tyreStatusLeftFront",
        name="Tyre pressure left front",
        native_unit_of_measurement=UnitOfPressure.KPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="tyre_pressure_right_front",
        api_field="tyreStatusRightFront",
        name="Tyre pressure right front",
        native_unit_of_measurement=UnitOfPressure.KPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="tyre_pressure_left_rear",
        api_field="tyreStatusLeftRear",
        name="Tyre pressure left rear",
        native_unit_of_measurement=UnitOfPressure.KPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="tyre_pressure_right_rear",
        api_field="tyreStatusRightRear",
        name="Tyre pressure right rear",
        native_unit_of_measurement=UnitOfPressure.KPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="tyre_temp_left_front",
        api_field="tyreTempLeftFront",
        name="Tyre temperature left front",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="tyre_temp_right_front",
        api_field="tyreTempRightFront",
        name="Tyre temperature right front",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="tyre_temp_left_rear",
        api_field="tyreTempLeftRear",
        name="Tyre temperature left rear",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="tyre_temp_right_rear",
        api_field="tyreTempRightRear",
        name="Tyre temperature right rear",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="days_to_service",
        api_field="daysToService",
        name="Days to service",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="distance_to_service",
        api_field="distanceToService",
        name="Distance to service",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EMASSensorEntityDescription(
        key="time_to_fully_charged",
        api_field="timeToFullyCharged",
        name="Time to fully charged",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    EMASSensorEntityDescription(
        key="time_to_target_discharged",
        api_field="timeToTargetDisCharged",
        name="Time to target discharged",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    EMASSensorEntityDescription(
        key="usage_mode",
        api_field="usageMode",
        name="Usage mode",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EMASSensorEntityDescription(
        key="power_source",
        api_field="powerSource",
        name="Power source",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EMASSensorEntityDescription(
        key="power_mode",
        api_field="powerMode",
        name="Power mode",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EMASSensorEntityDescription(
        key="fuel_type",
        api_field="fuelType",
        name="Fuel type",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EMASSensorEntityDescription(
        key="gear_auto_status",
        api_field="gearAutoStatus",
        name="Gear auto status",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EMASSensorEntityDescription(
        key="latitude",
        api_field="latitude",
        name="Latitude",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EMASSensorEntityDescription(
        key="longitude",
        api_field="longitude",
        name="Longitude",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EMASSensorEntityDescription(
        key="driver_vent_detail",
        api_field="drvVentDetail",
        name="Driver vent detail",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EMASSensorEntityDescription(
        key="passenger_vent_detail",
        api_field="passVentDetail",
        name="Passenger vent detail",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EMASSensorEntityDescription(
        key="last_update",
        api_field="lastUpdate",
        name="Vehicle last update",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EMASSensorEntityDescription(
        key="update_time",
        api_field="updateTime",
        name="Telemetry update time",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EMASSensorEntityDescription(
        key="ecu_warnings",
        api_field="ecuWarningMessages",
        name="ECU warnings",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    EMASSensorEntityDescription(
        key="extra_warnings",
        api_field="extrWarning",
        name="Extra warnings",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


class EMASSensor(EMASCoordinatorEntity, SensorEntity):
    """Telemetry sensor."""

    entity_description: EMASSensorEntityDescription

    def __init__(
        self,
        coordinator: EMASDataUpdateCoordinator,
        description: EMASSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, f"sensor_{description.key}")
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data
        raw = data.get(self.entity_description.api_field)
        if raw is None:
            return None

        desc = self.entity_description

        if desc.key in ("time_to_fully_charged", "time_to_target_discharged"):
            s = str(raw).strip()
            if s in CHARGE_TIME_SENTINEL:
                return None
            return _parse_int(raw)

        if desc.device_class in (
            SensorDeviceClass.TEMPERATURE,
            SensorDeviceClass.SPEED,
            SensorDeviceClass.DISTANCE,
            SensorDeviceClass.VOLTAGE,
            SensorDeviceClass.PRESSURE,
            SensorDeviceClass.BATTERY,
        ) or desc.native_unit_of_measurement in (
            PERCENTAGE,
            "A",
            "µg/m³",
            "°",
            "m",
            UnitOfTime.DAYS,
            UnitOfTime.MINUTES,
            "kWh/100km",
        ):
            val = _parse_float(raw)
            if val is None and isinstance(raw, str) and raw.strip() != "":
                return raw.strip()
            return val

        if desc.state_class == SensorStateClass.MEASUREMENT and isinstance(raw, str):
            parsed = _parse_float(raw)
            if parsed is not None:
                return parsed

        if isinstance(raw, str):
            return raw.strip()
        return raw


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EMASDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(EMASSensor(coordinator, desc) for desc in SENSOR_TYPES)
