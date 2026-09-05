"""Diagnostics with entity IDs but no credentials or raw state attributes."""

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import SmartEVChargingConfigEntry

TO_REDACT = {"access_token", "api_key", "password", "token"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: SmartEVChargingConfigEntry):
    coordinator = entry.runtime_data.coordinator
    return async_redact_data(
        {
            "config": dict(entry.data),
            "options": dict(entry.options),
            "runtime": {
                "soc": coordinator.soc,
                "plugged": coordinator.plugged,
                "effective_power_kw": coordinator.effective_power_kw,
                "deadline": coordinator.deadline,
                "should_charge": coordinator.should_charge,
                "plan_complete": coordinator.plan.complete,
                "required_kwh": coordinator.plan.required_kwh,
                "deliverable_kwh": coordinator.plan.deliverable_kwh,
                "slot_count": len(coordinator.plan.slots),
                "last_error": coordinator.last_error,
            },
        },
        TO_REDACT,
    )
