"""Exercise both setup paths and the options form with Home Assistant entries."""

import pytest
from homeassistant.data_entry_flow import AbortFlow

from custom_components.smart_ev_charging.config_flow import (
    SmartEVChargingConfigFlow,
    SmartEVChargingOptionsFlow,
)


async def test_generic_setup(hass, entry):
    flow = SmartEVChargingConfigFlow()
    flow.hass = hass
    flow.handler = "smart_ev_charging"
    flow.context["source"] = "user"
    result = await flow.async_step_user({
        "soc_entity": "sensor.soc", "price_entity": "sensor.price", "charger_type": "generic",
    })
    assert result["step_id"] == "charger"
    data = result["data_schema"]({
        "charger_switch": "switch.other", "battery_capacity": 77, "charge_power": 3.7,
        "efficiency": 0.9, "target_soc": 80, "minimum_soc": 30, "departure": "07:45:00",
    })
    result = await flow.async_step_charger(data)
    assert result["type"] == "create_entry"
    assert result["data"]["charger_switch"] == "switch.other"
    assert "charger_mode" not in result["data"]
    hass.config_entries.async_update_entry(entry, unique_id="switch.other:sensor.soc")
    with pytest.raises(AbortFlow, match="already_configured"):
        await flow.async_step_charger(data)


async def test_zaptec_form_requires_all_control_buttons(hass):
    flow = SmartEVChargingConfigFlow()
    flow.hass = hass
    flow.handler = "smart_ev_charging"
    flow.context["source"] = "user"
    result = await flow.async_step_user({
        "soc_entity": "sensor.soc", "price_entity": "sensor.price", "charger_type": "zaptec",
    })
    keys = {str(key) for key in result["data_schema"].schema}
    assert {"charger_mode", "authorize_button", "resume_button", "stop_button"} <= keys


async def test_options_form_loads_current_values(hass, entry):
    hass.config_entries.async_update_entry(entry, options={"target_soc": 90})
    flow = SmartEVChargingOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id
    result = await flow.async_step_init()
    defaults = result["data_schema"]({})
    assert defaults["target_soc"] == 90
    result = await flow.async_step_init(defaults)
    assert result["type"] == "create_entry"
    assert result["data"]["target_soc"] == 90
