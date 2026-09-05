"""Smart EV Charging integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import SmartEVChargingCoordinator
from .models import RuntimeData

type SmartEVChargingConfigEntry = ConfigEntry[RuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: SmartEVChargingConfigEntry) -> bool:
    coordinator = SmartEVChargingCoordinator(hass, entry)
    entry.runtime_data = RuntimeData(coordinator)
    await coordinator.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SmartEVChargingConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.coordinator.async_stop()
        return True
    return False


async def _async_reload_entry(hass: HomeAssistant, entry: SmartEVChargingConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
