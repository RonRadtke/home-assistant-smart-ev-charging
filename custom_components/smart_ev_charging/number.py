"""SOC target controls."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SmartEVChargingConfigEntry
from .entity import SmartEVChargingEntity


@dataclass(frozen=True, kw_only=True)
class SmartNumberDescription(NumberEntityDescription):
    value_fn: Callable
    set_fn: Callable[..., Awaitable[None]]


DESCRIPTIONS = (
    SmartNumberDescription(
        key="target_soc",
        translation_key="target_soc",
        native_min_value=10,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda c: c.target_soc,
        set_fn=lambda c, value: c.async_set_target(value),
    ),
    SmartNumberDescription(
        key="minimum_soc",
        translation_key="minimum_soc",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda c: c.minimum_soc,
        set_fn=lambda c, value: c.async_set_minimum(value),
    ),
)


async def async_setup_entry(
    hass, entry: SmartEVChargingConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([SmartNumber(entry.runtime_data.coordinator, item) for item in DESCRIPTIONS])


class SmartNumber(SmartEVChargingEntity, NumberEntity):
    entity_description: SmartNumberDescription

    def __init__(self, coordinator, description: SmartNumberDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float:
        return self.entity_description.value_fn(self.coordinator)

    async def async_set_native_value(self, value: float) -> None:
        await self.entity_description.set_fn(self.coordinator, value)
