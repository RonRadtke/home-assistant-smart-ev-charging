"""Smart EV Charging sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfEnergy, UnitOfTime
from homeassistant.generated.currencies import ACTIVE_CURRENCIES
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SmartEVChargingConfigEntry
from .const import CONF_PRICE_ENTITY
from .entity import SmartEVChargingEntity


@dataclass(frozen=True, kw_only=True)
class SmartSensorDescription(SensorEntityDescription):
    value_fn: Callable
    monetary: bool = False


def price_currency(coordinator) -> str | None:
    """Currency of the price entity, e.g. NOK from NOK/kWh.

    Subunits such as øre/kWh are not ISO currencies and yield None.
    """
    entity_id = coordinator.option(CONF_PRICE_ENTITY)
    state = coordinator.hass.states.get(entity_id) if entity_id else None
    unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if state else None
    if not isinstance(unit, str):
        return None
    currency = unit.split("/", 1)[0].strip().upper()
    return currency if currency in ACTIVE_CURRENCIES else None


DESCRIPTIONS = (
    SmartSensorDescription(
        key="required_energy",
        translation_key="required_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=1,
        value_fn=lambda c: c.plan.required_kwh,
    ),
    SmartSensorDescription(
        key="required_time",
        translation_key="required_time",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        suggested_display_precision=1,
        value_fn=lambda c: c.plan.required_kwh / max(0.01, c.effective_power_kw * float(c.option("efficiency"))),
    ),
    SmartSensorDescription(
        key="next_start",
        translation_key="next_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: c.plan.next_start,
    ),
    SmartSensorDescription(
        key="next_end",
        translation_key="next_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: c.plan.next_end,
    ),
    SmartSensorDescription(
        key="estimated_cost",
        translation_key="estimated_cost",
        suggested_display_precision=2,
        monetary=True,
        value_fn=lambda c: c.plan.estimated_cost,
    ),
    SmartSensorDescription(
        key="norgespris_cost",
        translation_key="norgespris_cost",
        suggested_display_precision=2,
        monetary=True,
        value_fn=lambda c: c.norgespris_comparison_cost,
    ),
    SmartSensorDescription(
        key="spot_comparison_cost",
        translation_key="spot_comparison_cost",
        suggested_display_precision=2,
        monetary=True,
        value_fn=lambda c: c.spot_comparison_cost,
    ),
    SmartSensorDescription(
        key="norgespris_savings",
        translation_key="norgespris_savings",
        suggested_display_precision=2,
        monetary=True,
        value_fn=lambda c: c.comparison_savings,
    ),
    SmartSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "error", "disabled", "not_connected", "missing_soc", "starting",
            "charging", "scheduled", "ready", "deadline_unreachable",
        ],
        value_fn=lambda c: c.status,
    ),
)


async def async_setup_entry(
    hass, entry: SmartEVChargingConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([SmartEVSensor(entry.runtime_data.coordinator, description) for description in DESCRIPTIONS])


class SmartEVSensor(SmartEVChargingEntity, SensorEntity):
    entity_description: SmartSensorDescription

    def __init__(self, coordinator, description: SmartSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        value = self.entity_description.value_fn(self.coordinator)
        if self.entity_description.monetary and value is not None:
            # Without a currency unit the frontend shows the raw float.
            return round(value, 2)
        return value

    @property
    def device_class(self) -> SensorDeviceClass | None:
        if self.entity_description.monetary:
            return SensorDeviceClass.MONETARY if price_currency(self.coordinator) else None
        return super().device_class

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.monetary:
            return price_currency(self.coordinator)
        return super().native_unit_of_measurement

    @property
    def extra_state_attributes(self):
        if self.entity_description.key != "status":
            return None
        return {
            "smart_charging": self.coordinator.enabled,
            "charge_now": self.coordinator.charge_now,
            "trip_mode": self.coordinator.trip_mode,
            "soc": self.coordinator.soc,
            "deadline": self.coordinator.deadline,
            "plan_complete": self.coordinator.plan.complete,
            "effective_power_kw": self.coordinator.effective_power_kw,
            "last_error": self.coordinator.last_error,
        }
