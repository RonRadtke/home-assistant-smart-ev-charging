"""The off state must be visible and recoverable, not silent."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

from custom_components.smart_ev_charging.calendar import ChargeScheduleCalendar
from custom_components.smart_ev_charging.const import DOMAIN
from custom_components.smart_ev_charging.models import RuntimeData
from custom_components.smart_ev_charging.repairs import async_create_fix_flow
from custom_components.smart_ev_charging.sensor import DESCRIPTIONS, SmartEVSensor

from .conftest import NOW


def _issue(hass, coordinator):
    return ir.async_get(hass).async_get_issue(DOMAIN, coordinator.off_issue_id)


async def test_off_while_connected_raises_fixable_warning_until_turned_on(coordinator, hass):
    coordinator.enabled = False
    await coordinator.async_refresh(NOW)
    issue = _issue(hass, coordinator)
    assert issue is not None
    assert issue.is_fixable
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == "smart_charging_off"
    assert issue.translation_placeholders == {"name": "Smart EV Charging"}

    await coordinator.async_set_enabled(True)
    assert _issue(hass, coordinator) is None


async def test_off_while_unplugged_raises_nothing(coordinator, hass):
    hass.config_entries.async_update_entry(
        coordinator.entry, data={**coordinator.entry.data, "plugged_entity": "binary_sensor.connected"}
    )
    hass.states.async_set("binary_sensor.connected", "off")
    coordinator.enabled = False
    await coordinator.async_refresh(NOW)
    assert _issue(hass, coordinator) is None

    hass.states.async_set("binary_sensor.connected", "on")
    await coordinator.async_refresh(NOW + timedelta(minutes=1))
    assert _issue(hass, coordinator) is not None

    hass.states.async_set("binary_sensor.connected", "off")
    await coordinator.async_refresh(NOW + timedelta(minutes=2))
    assert _issue(hass, coordinator) is None


async def test_off_still_leaves_a_manual_session_alone(coordinator, hass):
    hass.states.async_set("sensor.soc", "80")
    hass.states.async_set("switch.charger", "on")
    coordinator.enabled = False
    with patch.object(type(hass.services), "async_call") as call:
        await coordinator.async_refresh(NOW)
    call.assert_not_called()
    assert _issue(hass, coordinator) is not None


async def test_unload_clears_warning(coordinator, hass):
    coordinator.enabled = False
    await coordinator.async_refresh(NOW)
    await coordinator.async_stop()
    assert _issue(hass, coordinator) is None


async def _flow(hass, coordinator):
    issue = _issue(hass, coordinator)
    flow = await async_create_fix_flow(hass, issue.issue_id, issue.data)
    flow.hass, flow.handler, flow.issue_id, flow.flow_id = hass, DOMAIN, issue.issue_id, "flow"
    return flow


async def test_repair_flow_turns_smart_charging_on(coordinator, hass, entry):
    entry.runtime_data = RuntimeData(coordinator)
    coordinator.enabled = False
    await coordinator.async_refresh(NOW)
    flow = await _flow(hass, coordinator)

    form = await flow.async_step_init()
    assert form["type"] is FlowResultType.FORM
    assert form["description_placeholders"] == {"name": "Smart EV Charging"}
    assert not coordinator.enabled

    done = await flow.async_step_confirm({})
    assert done["type"] is FlowResultType.CREATE_ENTRY
    assert coordinator.enabled
    assert _issue(hass, coordinator) is None


async def test_repair_flow_aborts_when_entry_not_loaded(coordinator, hass):
    coordinator.enabled = False
    await coordinator.async_refresh(NOW)
    flow = await _flow(hass, coordinator)
    result = await flow.async_step_confirm({})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_loaded"


async def test_calendar_says_planned_windows_will_not_start_while_off(coordinator, hass):
    hass.states.async_set("sensor.soc", "20")
    await coordinator.async_refresh(NOW)
    calendar = ChargeScheduleCalendar(coordinator)
    assert calendar._events()[0].summary == "Optimized EV charging"
    coordinator.enabled = False
    assert "will not start" in calendar._events()[0].summary


def _cost_sensor(coordinator):
    description = next(item for item in DESCRIPTIONS if item.key == "estimated_cost")
    return SmartEVSensor(coordinator, description)


async def test_cost_uses_price_currency_and_cents(coordinator, hass):
    hass.states.async_set("sensor.price", "1", {"unit_of_measurement": "NOK/kWh"})
    hass.states.async_set("sensor.soc", "20")
    await coordinator.async_refresh(NOW)
    sensor = _cost_sensor(coordinator)
    assert sensor.native_unit_of_measurement == "NOK"
    assert sensor.device_class is SensorDeviceClass.MONETARY
    assert sensor.native_value == round(coordinator.plan.estimated_cost, 2)


async def test_cost_without_iso_currency_has_no_monetary_class(coordinator, hass):
    hass.states.async_set("sensor.price", "100", {"unit_of_measurement": "øre/kWh"})
    sensor = _cost_sensor(coordinator)
    assert sensor.native_unit_of_measurement is None
    assert sensor.device_class is None
    coordinator.plan = coordinator.plan.__class__(estimated_cost=19.1644444449119)
    assert sensor.native_value == 19.16
