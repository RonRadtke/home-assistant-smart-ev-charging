"""Plan refresh button."""

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SmartEVChargingConfigEntry
from .entity import SmartEVChargingEntity


async def async_setup_entry(
    hass, entry: SmartEVChargingConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([RefreshPlanButton(entry.runtime_data.coordinator)])


class RefreshPlanButton(SmartEVChargingEntity, ButtonEntity):
    _attr_translation_key = "refresh_plan"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "refresh_plan")

    async def async_press(self) -> None:
        await self.coordinator.async_refresh()
