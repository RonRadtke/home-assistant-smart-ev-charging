"""Departure time control."""

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SmartEVChargingConfigEntry
from .entity import SmartEVChargingEntity


async def async_setup_entry(
    hass, entry: SmartEVChargingConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([DepartureTime(entry.runtime_data.coordinator)])


class DepartureTime(SmartEVChargingEntity, TimeEntity):
    _attr_translation_key = "departure"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "departure")

    @property
    def native_value(self) -> time:
        value = self.coordinator.departure
        return value if isinstance(value, time) else time.fromisoformat(value)

    async def async_set_value(self, value: time) -> None:
        await self.coordinator.async_set_departure(value)
