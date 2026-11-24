"""Repair flow that turns smart charging back on."""

from __future__ import annotations

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant


class EnableSmartChargingFlow(ConfirmRepairFlow):
    """Confirm, then hand charger control back to the plan."""

    def __init__(self, entry_id: str) -> None:
        super().__init__()
        self._entry_id = entry_id

    async def async_step_confirm(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:
        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(self._entry_id)
            runtime_data = getattr(entry, "runtime_data", None) if entry is not None else None
            if runtime_data is None:
                return self.async_abort(reason="not_loaded")
            await runtime_data.coordinator.async_set_enabled(True)
        return await super().async_step_confirm(user_input)


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None
) -> RepairsFlow:
    return EnableSmartChargingFlow(str((data or {}).get("entry_id", "")))
