"""Smart EV Charging sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.const import UnitOfEnergy, UnitOfTime
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SmartEVChargingConfigEntry
from .entity import SmartEVChargingEntity


@dataclass(frozen=True, kw_only=True)
class SmartSensorDescription(SensorEntityDescription):
    value_fn: Callable


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
        value_fn=lambda c: c.plan.estimated_cost,
    ),
    SmartSensorDescription(
        key="status",
        translation_key="status",
        value_fn=lambda c: (
            "error"
            if c.last_error
            else (
                "disabled"
                if not c.enabled
                else (
                    "not_connected"
                    if not c.plugged
                    else ("charging" if c.should_charge else ("ready" if c.plan.complete else "deadline_unreachable"))
                )
            )
        ),
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
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self):
        if self.entity_description.key != "status":
            return None
        return {
            "soc": self.coordinator.soc,
            "deadline": self.coordinator.deadline,
            "plan_complete": self.coordinator.plan.complete,
            "effective_power_kw": self.coordinator.effective_power_kw,
            "last_error": self.coordinator.last_error,
        }
