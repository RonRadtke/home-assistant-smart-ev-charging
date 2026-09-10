"""Fixtures using Home Assistant's real state machine and config entries."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from types import MappingProxyType
from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.smart_ev_charging.const import DOMAIN
from custom_components.smart_ev_charging.coordinator import SmartEVChargingCoordinator
from custom_components.smart_ev_charging.models import PriceSlot

NOW = datetime(2026, 9, 10, 16, tzinfo=UTC)


@pytest.fixture
async def hass(tmp_path) -> AsyncGenerator[HomeAssistant]:
    instance = HomeAssistant(str(tmp_path))
    instance.config_entries = ConfigEntries(instance, {})
    await instance.config.async_set_time_zone("Europe/Oslo")
    yield instance
    await instance.async_stop(force=True)
    dt_util.set_default_time_zone(UTC)


@pytest.fixture
def entry(hass):
    entry = ConfigEntry(
        version=1, minor_version=1, domain=DOMAIN, title="Smart EV Charging",
        data={
            "soc_entity": "sensor.soc",
            "price_entity": "sensor.price",
            "power_entity": "sensor.power",
            "charger_type": "generic",
            "charger_switch": "switch.charger",
            "battery_capacity": 100,
            "charge_power": 10,
            "efficiency": 1,
            "departure": "07:45:00",
        },
        options={}, source="user", unique_id="charger",
        discovery_keys=MappingProxyType({}), subentries_data=None,
    )
    hass.config_entries._entries.async_add(entry)
    return entry


@pytest.fixture
def coordinator(hass, entry):
    from datetime import timedelta

    hass.states.async_set("sensor.soc", "70")
    hass.states.async_set("sensor.price", "1")
    hass.states.async_set("switch.charger", "off")
    coordinator = SmartEVChargingCoordinator(hass, entry)
    coordinator._async_get_prices = AsyncMock(return_value=[PriceSlot(NOW, NOW + timedelta(hours=12), 1)])
    return coordinator
