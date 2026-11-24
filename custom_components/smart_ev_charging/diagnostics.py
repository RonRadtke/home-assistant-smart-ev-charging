"""Diagnostics with entity IDs but no credentials or raw state attributes."""

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import SmartEVChargingConfigEntry

TO_REDACT = {"access_token", "api_key", "password", "token"}


def _local(value):
    return dt_util.as_local(value).isoformat() if value is not None else None


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: SmartEVChargingConfigEntry):
    coordinator = entry.runtime_data.coordinator
    departure = coordinator.departure
    return async_redact_data(
        {
            "config": dict(entry.data),
            "options": dict(entry.options),
            "runtime": {
                "time_zone": hass.config.time_zone,
                "status": coordinator.status,
                "smart_charging": coordinator.enabled,
                "charge_now": coordinator.charge_now,
                "trip_mode": coordinator.trip_mode,
                "target_soc": coordinator.target_soc,
                "minimum_soc": coordinator.minimum_soc,
                "departure": departure.isoformat() if hasattr(departure, "isoformat") else departure,
                "soc": coordinator.soc,
                "plugged": coordinator.plugged,
                "effective_power_kw": coordinator.effective_power_kw,
                "deadline": _local(coordinator.deadline),
                "should_charge": coordinator.should_charge,
                "plan_complete": coordinator.plan.complete,
                "required_kwh": coordinator.plan.required_kwh,
                "deliverable_kwh": coordinator.plan.deliverable_kwh,
                "slot_count": len(coordinator.plan.slots),
                "slots": [
                    {"start": _local(slot.start), "end": _local(slot.end), "price": slot.price}
                    for slot in coordinator.plan.slots
                ],
                "last_error": coordinator.last_error,
            },
        },
        TO_REDACT,
    )
