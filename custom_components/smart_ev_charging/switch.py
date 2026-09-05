"""Optimizer control switches."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SmartEVChargingConfigEntry
from .entity import SmartEVChargingEntity


@dataclass(frozen=True, kw_only=True)
class SmartSwitchDescription(SwitchEntityDescription):
    value_fn: Callable
    set_fn: Callable[..., Awaitable[None]]


DESCRIPTIONS = (
    SmartSwitchDescription(
        key="optimization",
        translation_key="optimization",
        value_fn=lambda c: c.enabled,
        set_fn=lambda c, value: c.async_set_enabled(value),
    ),
    SmartSwitchDescription(
        key="charge_now",
        translation_key="charge_now",
        value_fn=lambda c: c.charge_now,
        set_fn=lambda c, value: c.async_set_charge_now(value),
    ),
    SmartSwitchDescription(
        key="trip_mode",
        translation_key="trip_mode",
        value_fn=lambda c: c.trip_mode,
        set_fn=lambda c, value: c.async_set_trip_mode(value),
    ),
)


async def async_setup_entry(
    hass, entry: SmartEVChargingConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([SmartSwitch(entry.runtime_data.coordinator, item) for item in DESCRIPTIONS])


class SmartSwitch(SmartEVChargingEntity, SwitchEntity):
    entity_description: SmartSwitchDescription

    def __init__(self, coordinator, description: SmartSwitchDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.coordinator)

    async def async_turn_on(self, **kwargs) -> None:
        await self.entity_description.set_fn(self.coordinator, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.entity_description.set_fn(self.coordinator, False)
