"""Constants for Smart EV Charging."""

from datetime import time
from typing import Final

DOMAIN: Final = "smart_ev_charging"
PLATFORMS: Final = ["binary_sensor", "button", "calendar", "number", "sensor", "switch", "time"]

CONF_SOC_ENTITY: Final = "soc_entity"
CONF_PLUGGED_ENTITY: Final = "plugged_entity"
CONF_CHARGER_TYPE: Final = "charger_type"
CONF_CHARGER_SWITCH: Final = "charger_switch"
CONF_CHARGER_MODE: Final = "charger_mode"
CONF_AUTHORIZE_BUTTON: Final = "authorize_button"
CONF_RESUME_BUTTON: Final = "resume_button"
CONF_STOP_BUTTON: Final = "stop_button"
CONF_PRICE_ENTITY: Final = "price_entity"
CONF_POWER_ENTITY: Final = "power_entity"
CONF_BATTERY_CAPACITY: Final = "battery_capacity"
CONF_CHARGE_POWER: Final = "charge_power"
CONF_EFFICIENCY: Final = "efficiency"
CONF_TARGET_SOC: Final = "target_soc"
CONF_MINIMUM_SOC: Final = "minimum_soc"
CONF_DEPARTURE: Final = "departure"
CONF_MARKUP: Final = "price_markup"
CONF_DAY_GRID_FEE: Final = "day_grid_fee"
CONF_NIGHT_GRID_FEE: Final = "night_grid_fee"
CONF_NIGHT_START: Final = "night_start"
CONF_NIGHT_END: Final = "night_end"
CONF_FIXED_PRICE: Final = "fixed_energy_price"
CONF_SUPPORT_THRESHOLD: Final = "support_threshold"
CONF_SUPPORT_RATE: Final = "support_rate"

CHARGER_GENERIC: Final = "generic"
CHARGER_ZAPTEC: Final = "zaptec"
DEFAULTS: Final = {
    CONF_BATTERY_CAPACITY: 77.0,
    CONF_CHARGE_POWER: 3.7,
    CONF_EFFICIENCY: 0.90,
    CONF_TARGET_SOC: 80.0,
    CONF_MINIMUM_SOC: 30.0,
    CONF_DEPARTURE: time(7, 45),
    CONF_MARKUP: 0.0,
    CONF_DAY_GRID_FEE: 0.0,
    CONF_NIGHT_GRID_FEE: 0.0,
    CONF_NIGHT_START: time(22, 0),
    CONF_NIGHT_END: time(6, 0),
    CONF_FIXED_PRICE: -1.0,
    CONF_SUPPORT_THRESHOLD: 0.0,
    CONF_SUPPORT_RATE: 0.0,
}

STATE_REQUESTING: Final = "connected_requesting"
STATE_FINISHED: Final = "connected_finished"
STATE_CHARGING: Final = "connected_charging"
DISCONNECTED_STATES: Final = {"disconnected", "unknown", "unavailable", "off", "none"}
