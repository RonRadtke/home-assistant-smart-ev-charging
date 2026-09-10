"""Regression tests for charger state, retries, persistence, and native prices."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError

from custom_components.smart_ev_charging.coordinator import SmartEVChargingCoordinator
from custom_components.smart_ev_charging.models import PriceSlot

from .conftest import NOW


async def test_generic_without_connection_sensor_charges(coordinator, hass):
    with patch.object(hass.services, "async_call", new_callable=AsyncMock) as call:
        await coordinator.async_refresh(NOW)
    assert coordinator.plugged
    call.assert_awaited_once_with("switch", "turn_on", {"entity_id": "switch.charger"}, blocking=True)


async def test_startup_stops_a_charger_when_target_is_reached(coordinator, hass):
    hass.states.async_set("sensor.soc", "80")
    hass.states.async_set("switch.charger", "on")
    with patch.object(hass.services, "async_call", new_callable=AsyncMock) as call:
        await coordinator.async_refresh(NOW)
    call.assert_awaited_once_with("switch", "turn_off", {"entity_id": "switch.charger"}, blocking=True)


async def test_external_start_is_reconciled_even_when_desired_stays_off(coordinator, hass):
    hass.states.async_set("sensor.soc", "80")
    await coordinator.async_refresh(NOW)
    hass.states.async_set("switch.charger", "on")
    with patch.object(hass.services, "async_call", new_callable=AsyncMock) as call:
        await coordinator.async_refresh(NOW + timedelta(seconds=10))
    assert call.await_args.args[:2] == ("switch", "turn_off")


@pytest.mark.parametrize("state", ["unknown", "unavailable", "nan", "-1", "101"])
async def test_missing_or_invalid_soc_stops_optimized_charging(coordinator, hass, state):
    hass.states.async_set("sensor.soc", state)
    hass.states.async_set("switch.charger", "on")
    with patch.object(hass.services, "async_call", new_callable=AsyncMock) as call:
        await coordinator.async_refresh(NOW)
    assert coordinator.soc is None
    assert not coordinator.plan.complete
    assert call.await_args.args[:2] == ("switch", "turn_off")


async def test_disabled_does_not_control_charger(coordinator, hass):
    coordinator.enabled = False
    hass.states.async_set("switch.charger", "on")
    with patch.object(hass.services, "async_call", new_callable=AsyncMock) as call:
        await coordinator.async_refresh(NOW)
    call.assert_not_awaited()


async def test_failure_cooldown_and_recovery_update_status(coordinator, hass):
    listener = Mock()
    coordinator.async_add_listener(listener)
    with patch.object(hass.services, "async_call", new_callable=AsyncMock) as call:
        call.side_effect = HomeAssistantError("offline")
        await coordinator.async_refresh(NOW)
        await coordinator.async_refresh(NOW + timedelta(seconds=10))
        assert call.await_count == 1
        assert coordinator.last_error == "offline"
        call.side_effect = None
        await coordinator.async_refresh(NOW + timedelta(minutes=2))
        assert call.await_count == 2
        assert coordinator.last_error is None
    assert listener.call_count == 3


async def test_concurrent_refreshes_send_one_command(coordinator, hass):
    entered, release = asyncio.Event(), asyncio.Event()

    async def slow_call(*args, **kwargs):
        entered.set()
        await release.wait()

    with patch.object(hass.services, "async_call", side_effect=slow_call) as call:
        first = asyncio.create_task(coordinator.async_refresh(NOW))
        await entered.wait()
        second = asyncio.create_task(coordinator.async_refresh(NOW))
        release.set()
        await asyncio.gather(first, second)
    assert call.await_count == 1


@pytest.mark.parametrize(("value", "unit", "expected"), [
    ("3700", "W", 3.7), ("3.7", "kW", 3.7), ("50", "W", 10),
    ("50", "kW", 50), ("nan", "W", 10), ("5000", None, 10),
    ("5000", "invalid", 10), ("0", "W", 10),
])
async def test_power_uses_units_and_ignores_standby(coordinator, hass, value, unit, expected):
    coordinator.enabled = False
    hass.states.async_set("sensor.power", value, {"unit_of_measurement": unit})
    await coordinator.async_refresh(NOW)
    assert coordinator.effective_power_kw == expected


@pytest.fixture
def zaptec(coordinator, hass):
    hass.config_entries.async_update_entry(coordinator.entry, data={
        **coordinator.entry.data, "charger_type": "zaptec", "charger_mode": "sensor.mode",
        "authorize_button": "button.authorize", "resume_button": "button.resume",
        "stop_button": "button.stop",
    })
    hass.states.async_set("sensor.mode", "connected_finished")
    return coordinator


async def test_zaptec_resume_then_authorize_on_state_change(zaptec, hass):
    with patch.object(hass.services, "async_call", new_callable=AsyncMock) as call:
        await zaptec.async_refresh(NOW)
        assert call.await_args.args[2] == {"entity_id": "button.resume"}
        hass.states.async_set("sensor.mode", "connected_requesting")
        await zaptec.async_refresh(NOW + timedelta(seconds=1))
        assert call.await_count == 2
        assert call.await_args.args[2] == {"entity_id": "button.authorize"}


@pytest.mark.parametrize("cancel", ["disabled", "unplugged", "target_reached"])
async def test_zaptec_cancels_authorization_after_resume(zaptec, hass, cancel):
    with patch.object(hass.services, "async_call", new_callable=AsyncMock) as call:
        await zaptec.async_refresh(NOW)
        hass.states.async_set("sensor.mode", "connected_requesting")
        if cancel == "disabled":
            zaptec.enabled = False
        elif cancel == "unplugged":
            hass.states.async_set("sensor.mode", "disconnected")
        else:
            hass.states.async_set("sensor.soc", "80")
        await zaptec.async_refresh(NOW + timedelta(seconds=1))
        assert call.await_count == 1


async def test_zaptec_stops_existing_session(zaptec, hass):
    hass.states.async_set("sensor.soc", "80")
    hass.states.async_set("sensor.mode", "connected_charging")
    with patch.object(hass.services, "async_call", new_callable=AsyncMock) as call:
        await zaptec.async_refresh(NOW)
        assert call.await_args.args[2] == {"entity_id": "button.stop"}


async def test_explicit_unavailable_connection_does_not_assume_plugged(coordinator, hass):
    hass.config_entries.async_update_entry(coordinator.entry, data={
        **coordinator.entry.data, "plugged_entity": "binary_sensor.connected",
    })
    await coordinator.async_refresh(NOW)
    assert not coordinator.plugged


async def test_runtime_values_survive_restart_and_options_override_changes(coordinator, hass):
    coordinator.enabled = False
    coordinator.target_soc = 85
    coordinator.minimum_soc = 35
    coordinator.departure = "08:15:00"
    await coordinator._async_save_state()
    restored = SmartEVChargingCoordinator(hass, coordinator.entry)
    await restored.async_start()
    assert (restored.target_soc, restored.minimum_soc, restored.departure) == (85, 35, "08:15:00")
    await restored.async_stop()
    hass.config_entries.async_update_entry(coordinator.entry, options={"target_soc": 90, "departure": "09:00:00"})
    changed = SmartEVChargingCoordinator(hass, coordinator.entry)
    await changed.async_start()
    assert (changed.target_soc, changed.minimum_soc, changed.departure) == (90, 35, "09:00:00")
    await changed.async_stop()


async def test_legacy_storage_respects_explicit_options(coordinator, hass):
    await coordinator._store.async_save({"enabled": False, "target_soc": 85})
    hass.config_entries.async_update_entry(coordinator.entry, options={"target_soc": 90})
    restored = SmartEVChargingCoordinator(hass, coordinator.entry)
    await restored.async_start()
    assert restored.target_soc == 90
    await restored.async_stop()


async def test_charge_now_resets_if_restarted_unplugged(coordinator, hass):
    coordinator.charge_now = True
    await coordinator._async_save_state()
    hass.states.async_set("switch.charger", "unavailable")
    restored = SmartEVChargingCoordinator(hass, coordinator.entry)
    await restored.async_start()
    assert not restored.charge_now
    await restored.async_stop()


async def test_stopped_coordinator_ignores_queued_refresh(coordinator, hass):
    await coordinator.async_stop()
    with patch.object(hass.services, "async_call", new_callable=AsyncMock) as call:
        await coordinator.async_refresh(NOW)
    call.assert_not_awaited()


async def test_native_nordpool_converts_prices_and_keeps_explicit_ends(coordinator, hass):
    registry = Mock()
    registry.async_get.return_value = Mock(platform="nordpool", unique_id="NO2-current_price", config_entry_id="np")
    del coordinator._async_get_prices
    hass.states.async_set("sensor.price", "1", {"unit_of_measurement": "NOK/kWh"})
    response = {"NO2": [{"start": NOW.isoformat(), "end": (NOW + timedelta(minutes=15)).isoformat(), "price": 1000}]}
    with patch("custom_components.smart_ev_charging.coordinator.er.async_get", return_value=registry):
        with patch.object(hass.services, "async_call", new_callable=AsyncMock, return_value=response) as call:
            prices = await coordinator._async_get_prices(NOW)
            assert prices == [PriceSlot(NOW, NOW + timedelta(minutes=15), 1)]
            assert call.await_count == 2
            assert call.await_args.args[2]["areas"] == ["NO2"]
            await coordinator._async_get_prices(NOW + timedelta(minutes=1))
            assert call.await_count == 2


async def test_native_price_failures_are_throttled_without_numeric_fallback(coordinator, hass):
    registry = Mock()
    registry.async_get.return_value = Mock(platform="nordpool", unique_id="NO2-current_price", config_entry_id="np")
    del coordinator._async_get_prices
    with patch("custom_components.smart_ev_charging.coordinator.er.async_get", return_value=registry):
        with patch.object(hass.services, "async_call", side_effect=HomeAssistantError("offline")) as call:
            assert await coordinator._async_get_prices(NOW) == []
            assert await coordinator._async_get_prices(NOW + timedelta(minutes=1)) == []
            assert call.await_count == 2


async def test_service_registry_receives_real_switch_command(coordinator, hass):
    calls = []

    async def turn_on(call):
        calls.append(call.data)
        hass.states.async_set("switch.charger", "on")

    hass.services.async_register("switch", "turn_on", turn_on, supports_response=SupportsResponse.NONE)
    await coordinator.async_refresh(NOW)
    assert calls == [{"entity_id": "switch.charger"}]
    assert hass.states.get("switch.charger").state == "on"
