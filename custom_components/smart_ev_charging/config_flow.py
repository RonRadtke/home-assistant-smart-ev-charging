"""UI configuration for Smart EV Charging."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CHARGER_GENERIC,
    CHARGER_ZAPTEC,
    CONF_AUTHORIZE_BUTTON,
    CONF_BATTERY_CAPACITY,
    CONF_CHARGE_POWER,
    CONF_CHARGER_MODE,
    CONF_CHARGER_SWITCH,
    CONF_CHARGER_TYPE,
    CONF_DAY_GRID_FEE,
    CONF_DEPARTURE,
    CONF_EFFICIENCY,
    CONF_FIXED_PRICE,
    CONF_MARKUP,
    CONF_MINIMUM_SOC,
    CONF_NIGHT_END,
    CONF_NIGHT_GRID_FEE,
    CONF_NIGHT_START,
    CONF_PLUGGED_ENTITY,
    CONF_POWER_ENTITY,
    CONF_PRICE_ENTITY,
    CONF_RESUME_BUTTON,
    CONF_SOC_ENTITY,
    CONF_STOP_BUTTON,
    CONF_SUPPORT_RATE,
    CONF_SUPPORT_THRESHOLD,
    CONF_TARGET_SOC,
    DEFAULTS,
    DOMAIN,
)


def _entity(domain: str | list[str] | None = None) -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig(domain=domain))


def _number(minimum: float, maximum: float, step: float = 1) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(min=minimum, max=maximum, step=step, mode=selector.NumberSelectorMode.BOX)
    )


class SmartEVChargingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the setup flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_charger()
        schema = vol.Schema(
            {
                vol.Required(CONF_SOC_ENTITY): _entity("sensor"),
                vol.Optional(CONF_PLUGGED_ENTITY): _entity(["binary_sensor", "sensor"]),
                vol.Required(CONF_PRICE_ENTITY): _entity("sensor"),
                vol.Optional(CONF_POWER_ENTITY): _entity("sensor"),
                vol.Required(CONF_CHARGER_TYPE, default=CHARGER_ZAPTEC): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[CHARGER_ZAPTEC, CHARGER_GENERIC],
                        translation_key="charger_type",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_charger(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data.update(user_input)
            unique = self._data.get(CONF_CHARGER_MODE) or self._data.get(CONF_CHARGER_SWITCH)
            await self.async_set_unique_id(f"{unique}:{self._data[CONF_SOC_ENTITY]}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Smart EV Charging", data=self._data)
        if self._data[CONF_CHARGER_TYPE] == CHARGER_ZAPTEC:
            fields = {
                vol.Required(CONF_CHARGER_MODE): _entity("sensor"),
                vol.Required(CONF_AUTHORIZE_BUTTON): _entity("button"),
                vol.Required(CONF_RESUME_BUTTON): _entity("button"),
                vol.Required(CONF_STOP_BUTTON): _entity("button"),
            }
        else:
            fields = {vol.Required(CONF_CHARGER_SWITCH): _entity("switch")}
        fields.update(
            {
                vol.Required(CONF_BATTERY_CAPACITY, default=DEFAULTS[CONF_BATTERY_CAPACITY]): _number(5, 250, 0.1),
                vol.Required(CONF_CHARGE_POWER, default=DEFAULTS[CONF_CHARGE_POWER]): _number(0.5, 50, 0.1),
                vol.Required(CONF_EFFICIENCY, default=DEFAULTS[CONF_EFFICIENCY]): _number(0.5, 1, 0.01),
                vol.Required(CONF_TARGET_SOC, default=DEFAULTS[CONF_TARGET_SOC]): _number(10, 100),
                vol.Required(CONF_MINIMUM_SOC, default=DEFAULTS[CONF_MINIMUM_SOC]): _number(0, 100),
                vol.Required(CONF_DEPARTURE, default="07:45:00"): selector.TimeSelector(),
            }
        )
        return self.async_show_form(step_id="charger", data_schema=vol.Schema(fields))

    @staticmethod
    def async_get_options_flow(config_entry):
        return SmartEVChargingOptionsFlow()


class SmartEVChargingOptionsFlow(config_entries.OptionsFlow):
    """Configure optimization and tariff options."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(CONF_BATTERY_CAPACITY, default=current.get(CONF_BATTERY_CAPACITY, 77)): _number(
                    5, 250, 0.1
                ),
                vol.Required(CONF_CHARGE_POWER, default=current.get(CONF_CHARGE_POWER, 3.7)): _number(0.5, 50, 0.1),
                vol.Required(CONF_EFFICIENCY, default=current.get(CONF_EFFICIENCY, 0.9)): _number(0.5, 1, 0.01),
                vol.Required(CONF_TARGET_SOC, default=current.get(CONF_TARGET_SOC, 80)): _number(10, 100),
                vol.Required(CONF_MINIMUM_SOC, default=current.get(CONF_MINIMUM_SOC, 30)): _number(0, 100),
                vol.Required(CONF_DEPARTURE, default=current.get(CONF_DEPARTURE, "07:45:00")): selector.TimeSelector(),
                vol.Required(CONF_MARKUP, default=current.get(CONF_MARKUP, 0)): _number(-10, 10, 0.001),
                vol.Required(CONF_DAY_GRID_FEE, default=current.get(CONF_DAY_GRID_FEE, 0)): _number(0, 10, 0.001),
                vol.Required(CONF_NIGHT_GRID_FEE, default=current.get(CONF_NIGHT_GRID_FEE, 0)): _number(0, 10, 0.001),
                vol.Required(
                    CONF_NIGHT_START, default=current.get(CONF_NIGHT_START, "22:00:00")
                ): selector.TimeSelector(),
                vol.Required(CONF_NIGHT_END, default=current.get(CONF_NIGHT_END, "06:00:00")): selector.TimeSelector(),
                vol.Required(CONF_FIXED_PRICE, default=current.get(CONF_FIXED_PRICE, -1)): _number(-1, 20, 0.001),
                vol.Required(CONF_SUPPORT_THRESHOLD, default=current.get(CONF_SUPPORT_THRESHOLD, 0)): _number(
                    0, 20, 0.001
                ),
                vol.Required(CONF_SUPPORT_RATE, default=current.get(CONF_SUPPORT_RATE, 0)): _number(0, 1, 0.01),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
