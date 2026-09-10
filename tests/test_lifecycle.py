"""Set up every entity platform and verify unload and failed-setup cleanup."""

import importlib
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.smart_ev_charging import async_setup_entry, async_unload_entry
from custom_components.smart_ev_charging.const import PLATFORMS
from custom_components.smart_ev_charging.diagnostics import async_get_config_entry_diagnostics


async def test_setup_all_platforms_diagnostics_and_unload(hass, entry):
    hass.states.async_set("sensor.soc", "80")
    hass.states.async_set("sensor.price", "1")
    hass.states.async_set("switch.charger", "off")
    entities = []

    async def forward(config_entry, platforms):
        for platform in platforms:
            module = importlib.import_module(f"custom_components.smart_ev_charging.{platform}")
            await module.async_setup_entry(hass, config_entry, entities.extend)

    with patch.object(hass.config_entries, "async_forward_entry_setups", side_effect=forward):
        assert await async_setup_entry(hass, entry)
    assert len(entities) == 15
    assert len({entity.unique_id for entity in entities}) == len(entities)
    assert all(not entity.should_poll for entity in entities)
    assert entry.runtime_data.coordinator._listeners
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["runtime"]["plan_complete"]
    with patch.object(
        hass.config_entries, "async_unload_platforms", new_callable=AsyncMock, return_value=True
    ) as unload:
        assert await async_unload_entry(hass, entry)
        unload.assert_awaited_once_with(entry, PLATFORMS)
    assert not entry.runtime_data.coordinator._listeners
    assert entry.runtime_data.coordinator._stopped


async def test_failed_platform_setup_cleans_coordinator_listeners(hass, entry):
    with (
        patch.object(hass.config_entries, "async_forward_entry_setups", side_effect=RuntimeError("setup failed")),
        pytest.raises(RuntimeError, match="setup failed"),
    ):
        await async_setup_entry(hass, entry)
    assert not entry.runtime_data.coordinator._listeners
    assert entry.runtime_data.coordinator._stopped


async def test_failed_unload_keeps_coordinator_active(hass, entry):
    with patch.object(hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock):
        await async_setup_entry(hass, entry)
    with patch.object(hass.config_entries, "async_unload_platforms", new_callable=AsyncMock, return_value=False):
        assert not await async_unload_entry(hass, entry)
    assert not entry.runtime_data.coordinator._stopped
    await entry.runtime_data.coordinator.async_stop()
