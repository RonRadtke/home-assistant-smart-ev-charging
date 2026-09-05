"""Calendar representation of selected charging windows."""

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import SmartEVChargingConfigEntry
from .entity import SmartEVChargingEntity


async def async_setup_entry(
    hass, entry: SmartEVChargingConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([ChargeScheduleCalendar(entry.runtime_data.coordinator)])


class ChargeScheduleCalendar(SmartEVChargingEntity, CalendarEntity):
    _attr_translation_key = "schedule"
    _attr_initial_color = "#16a765"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "schedule")

    def _events(self) -> list[CalendarEvent]:
        return [
            CalendarEvent(
                start=slot.start,
                end=slot.end,
                summary="Optimized EV charging",
                description=f"Effective price: {slot.price:.4f} per kWh",
                uid=f"{self.coordinator.entry.entry_id}-{slot.start.isoformat()}",
            )
            for slot in self.coordinator.plan.slots
        ]

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        return next((event for event in self._events() if event.end > now), None)

    async def async_get_events(self, hass, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        return [event for event in self._events() if event.end > start_date and event.start < end_date]
