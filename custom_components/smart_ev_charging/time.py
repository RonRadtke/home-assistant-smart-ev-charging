"""Departure and charging-window time controls."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import time

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SmartEVChargingConfigEntry
from .entity import SmartEVChargingEntity


@dataclass(frozen=True, kw_only=True)
class SmartTimeDescription(TimeEntityDescription):
    value_fn: Callable
    set_fn: Callable[..., Awaitable[None]]


DESCRIPTIONS = (
    SmartTimeDescription(
        key="departure",
        translation_key="departure",
        value_fn=lambda c: c.departure,
        set_fn=lambda c, value: c.async_set_departure(value),
    ),
    SmartTimeDescription(
        key="window_start",
        translation_key="window_start",
        value_fn=lambda c: c.window_start,
        set_fn=lambda c, value: c.async_set_window_start(value),
    ),
    SmartTimeDescription(
        key="window_end",
        translation_key="window_end",
        value_fn=lambda c: c.window_end,
        set_fn=lambda c, value: c.async_set_window_end(value),
    ),
)


async def async_setup_entry(
    hass, entry: SmartEVChargingConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([SmartTime(entry.runtime_data.coordinator, item) for item in DESCRIPTIONS])


class SmartTime(SmartEVChargingEntity, TimeEntity):
    entity_description: SmartTimeDescription

    def __init__(self, coordinator, description: SmartTimeDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> time:
        value = self.entity_description.value_fn(self.coordinator)
        return value if isinstance(value, time) else time.fromisoformat(value)

    async def async_set_value(self, value: time) -> None:
        await self.entity_description.set_fn(self.coordinator, value)
