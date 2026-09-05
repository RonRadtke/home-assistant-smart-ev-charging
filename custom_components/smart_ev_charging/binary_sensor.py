"""Charging recommendation binary sensor."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SmartEVChargingConfigEntry
from .entity import SmartEVChargingEntity


async def async_setup_entry(
    hass, entry: SmartEVChargingConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([ShouldChargeEntity(entry.runtime_data.coordinator)])


class ShouldChargeEntity(SmartEVChargingEntity, BinarySensorEntity):
    _attr_translation_key = "should_charge"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "should_charge")

    @property
    def is_on(self) -> bool:
        return self.coordinator.should_charge
