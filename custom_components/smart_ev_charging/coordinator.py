"""State collection, planning, and charger control."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CHARGER_GENERIC,
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
    DISCONNECTED_STATES,
    STATE_CHARGING,
    STATE_FINISHED,
    STATE_REQUESTING,
)
from .models import ChargePlan, PriceSlot
from .planner import build_plan
from .pricing import add_tariffs, parse_price_slots

_LOGGER = logging.getLogger(__name__)


class SmartEVChargingCoordinator:
    """Coordinate inputs and charger actions without polling external APIs."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.plan = ChargePlan()
        self.enabled = True
        self.charge_now = False
        self.trip_mode = False
        self.target_soc = float(self.option(CONF_TARGET_SOC))
        self.minimum_soc = float(self.option(CONF_MINIMUM_SOC))
        self.departure = self.option(CONF_DEPARTURE)
        self.should_charge = False
        self.soc: float | None = None
        self.plugged = False
        self.deadline: datetime | None = None
        self.effective_power_kw = float(self.option(CONF_CHARGE_POWER))
        self.last_error: str | None = None
        self._listeners: list = []
        self._update_callbacks: list = []
        self._control_lock = asyncio.Lock()
        self._last_command: tuple[bool, datetime] | None = None
        self._price_cache: list[PriceSlot] = []
        self._price_cache_at: datetime | None = None
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"smart_ev_charging.{entry.entry_id}")
        self._was_plugged = False

    def option(self, key: str) -> Any:
        return self.entry.options.get(key, self.entry.data.get(key, DEFAULTS.get(key)))

    def time_option(self, key: str) -> time:
        value = self.option(key)
        if isinstance(value, time):
            return value
        return time.fromisoformat(value)

    async def async_start(self) -> None:
        if stored := await self._store.async_load():
            self.enabled = bool(stored.get("enabled", self.enabled))
            self.charge_now = bool(stored.get("charge_now", self.charge_now))
            self.trip_mode = bool(stored.get("trip_mode", self.trip_mode))
            self.target_soc = float(stored.get("target_soc", self.target_soc))
            self.minimum_soc = float(stored.get("minimum_soc", self.minimum_soc))
            self.departure = stored.get("departure", self.departure)
        entities = [
            self.option(CONF_SOC_ENTITY),
            self.option(CONF_PLUGGED_ENTITY),
            self.option(CONF_PRICE_ENTITY),
            self.option(CONF_POWER_ENTITY),
            self.option(CONF_CHARGER_MODE),
            self.option(CONF_CHARGER_SWITCH),
        ]
        entities = [entity for entity in entities if entity]
        self._listeners.append(async_track_state_change_event(self.hass, entities, self._state_changed))
        self._listeners.append(async_track_time_interval(self.hass, self._time_changed, timedelta(minutes=1)))
        await self.async_refresh()

    async def async_stop(self) -> None:
        for remove in self._listeners:
            remove()
        self._listeners.clear()

    @callback
    def async_add_listener(self, update_callback):
        self._update_callbacks.append(update_callback)
        return lambda: self._update_callbacks.remove(update_callback)

    @callback
    def _notify(self) -> None:
        for update_callback in tuple(self._update_callbacks):
            update_callback()

    async def _state_changed(self, event: Event) -> None:
        await self.async_refresh()

    async def _time_changed(self, now: datetime) -> None:
        await self.async_refresh(now)

    def _float_state(self, entity_id: str | None) -> float | None:
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    def _is_plugged(self) -> bool:
        entity_id = self.option(CONF_PLUGGED_ENTITY)
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is not None:
            return state.state.lower() not in DISCONNECTED_STATES
        mode_id = self.option(CONF_CHARGER_MODE)
        mode = self.hass.states.get(mode_id) if mode_id else None
        return mode is not None and mode.state.lower() not in DISCONNECTED_STATES

    def _next_deadline(self, now: datetime) -> datetime:
        departure = self.departure if isinstance(self.departure, time) else time.fromisoformat(self.departure)
        candidate = now.replace(hour=departure.hour, minute=departure.minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    async def async_refresh(self, now: datetime | None = None) -> None:
        now = dt_util.as_local(now or dt_util.now())
        self.soc = self._float_state(self.option(CONF_SOC_ENTITY))
        self.plugged = self._is_plugged()
        if self._was_plugged and not self.plugged and self.charge_now:
            self.charge_now = False
            await self._async_save_state()
        self._was_plugged = self.plugged
        measured_power = self._float_state(self.option(CONF_POWER_ENTITY))
        if measured_power and measured_power > 0.1:
            # HA power sensors normally use W or kW; preserve last useful measurement.
            self.effective_power_kw = measured_power / 1000 if measured_power > 100 else measured_power
        self.deadline = self._next_deadline(now)

        prices = await self._async_get_prices(now)
        prices = add_tariffs(
            prices,
            markup=float(self.option(CONF_MARKUP)),
            day_fee=float(self.option(CONF_DAY_GRID_FEE)),
            night_fee=float(self.option(CONF_NIGHT_GRID_FEE)),
            night_start=self.time_option(CONF_NIGHT_START),
            night_end=self.time_option(CONF_NIGHT_END),
            fixed_price=float(self.option(CONF_FIXED_PRICE)),
            support_threshold=float(self.option(CONF_SUPPORT_THRESHOLD)),
            support_rate=float(self.option(CONF_SUPPORT_RATE)),
        )
        target = 100.0 if self.trip_mode else self.target_soc
        if self.trip_mode and self.soc is not None and self.soc >= 99:
            self.trip_mode = False
            target = self.target_soc
            await self._async_save_state()
        self.plan = (
            build_plan(
                now=now,
                deadline=self.deadline,
                soc=self.soc or 0,
                target_soc=target,
                minimum_soc=self.minimum_soc,
                battery_capacity_kwh=float(self.option(CONF_BATTERY_CAPACITY)),
                charge_power_kw=self.effective_power_kw,
                efficiency=float(self.option(CONF_EFFICIENCY)),
                prices=prices,
            )
            if self.soc is not None
            else ChargePlan(complete=False)
        )
        desired = bool(self.enabled and self.plugged and (self.charge_now or self.plan.active(now)))
        changed = desired != self.should_charge
        self.should_charge = desired
        self._notify()
        if changed or desired or self.last_error:
            await self._async_apply_desired_state(now)

    async def _async_get_prices(self, now: datetime) -> list[PriceSlot]:
        """Read generic attributes or fetch complete days from native Nord Pool."""
        entity_id = self.option(CONF_PRICE_ENTITY)
        price_state = self.hass.states.get(entity_id)
        registry_entry = er.async_get(self.hass).async_get(entity_id) if entity_id else None
        if registry_entry and registry_entry.platform == "nordpool":
            stale = self._price_cache_at is None or now - self._price_cache_at > timedelta(minutes=30)
            if stale:
                area = registry_entry.unique_id.split("-", 1)[0]
                unit = price_state.attributes.get("unit_of_measurement", "NOK/kWh") if price_state else "NOK/kWh"
                currency = str(unit).split("/", 1)[0]
                records = []
                for day in (now.date(), (now + timedelta(days=1)).date()):
                    try:
                        response = await self.hass.services.async_call(
                            "nordpool",
                            "get_prices_for_date",
                            {
                                "config_entry": registry_entry.config_entry_id,
                                "date": day.isoformat(),
                                "areas": [area],
                                "currency": currency,
                            },
                            blocking=True,
                            return_response=True,
                        )
                        records.extend((response or {}).get(area, []))
                    except Exception as err:
                        _LOGGER.warning("Could not fetch Nord Pool prices for %s: %s", day, err)
                parsed = parse_price_slots({"prices": records}, now)
                # Native Nord Pool action returns currency/MWh; sensors use currency/kWh.
                if parsed:
                    self._price_cache = [PriceSlot(slot.start, slot.end, slot.price / 1000) for slot in parsed]
                    self._price_cache_at = now
            if self._price_cache:
                return self._price_cache
        return parse_price_slots(
            dict(price_state.attributes) if price_state else {},
            now,
            price_state.state if price_state else None,
        )

    async def _async_apply_desired_state(self, now: datetime) -> None:
        if not self.enabled:
            return
        if (
            self._last_command
            and self._last_command[0] == self.should_charge
            and now - self._last_command[1] < timedelta(minutes=2)
        ):
            return
        async with self._control_lock:
            try:
                if self.option(CONF_CHARGER_TYPE) == CHARGER_GENERIC:
                    await self._async_control_generic()
                else:
                    await self._async_control_zaptec()
                self.last_error = None
                self._last_command = (self.should_charge, now)
            except Exception as err:  # HA service errors must remain visible in diagnostics.
                self.last_error = str(err)
                _LOGGER.exception("Unable to set charger state")
                self._notify()

    async def _press(self, entity_id: str | None) -> None:
        if entity_id:
            await self.hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)

    async def _async_control_generic(self) -> None:
        switch = self.option(CONF_CHARGER_SWITCH)
        if not switch:
            return
        state = self.hass.states.get(switch)
        is_on = state is not None and state.state == "on"
        if is_on != self.should_charge:
            await self.hass.services.async_call(
                "switch",
                "turn_on" if self.should_charge else "turn_off",
                {"entity_id": switch},
                blocking=True,
            )

    async def _async_control_zaptec(self) -> None:
        mode_id = self.option(CONF_CHARGER_MODE)
        mode_state = self.hass.states.get(mode_id) if mode_id else None
        mode = mode_state.state if mode_state else "unknown"
        if not self.should_charge:
            if mode == STATE_CHARGING:
                await self._press(self.option(CONF_STOP_BUTTON))
            return
        if mode == STATE_FINISHED:
            await self._press(self.option(CONF_RESUME_BUTTON))
            for _ in range(10):
                await asyncio.sleep(1)
                current = self.hass.states.get(mode_id)
                if current and current.state in (STATE_REQUESTING, STATE_CHARGING):
                    mode = current.state
                    break
        if mode == STATE_REQUESTING:
            await self._press(self.option(CONF_AUTHORIZE_BUTTON))

    async def async_set_enabled(self, value: bool) -> None:
        self.enabled = value
        await self._async_save_state()
        await self.async_refresh()

    async def async_set_charge_now(self, value: bool) -> None:
        self.charge_now = value
        await self._async_save_state()
        await self.async_refresh()

    async def async_set_trip_mode(self, value: bool) -> None:
        self.trip_mode = value
        await self._async_save_state()
        await self.async_refresh()

    async def async_set_target(self, value: float) -> None:
        self.target_soc = value
        await self._async_save_state()
        await self.async_refresh()

    async def async_set_minimum(self, value: float) -> None:
        self.minimum_soc = value
        await self._async_save_state()
        await self.async_refresh()

    async def async_set_departure(self, value) -> None:
        self.departure = value
        await self._async_save_state()
        await self.async_refresh()

    async def _async_save_state(self) -> None:
        departure = self.departure.isoformat() if isinstance(self.departure, time) else self.departure
        await self._store.async_save(
            {
                "enabled": self.enabled,
                "charge_now": self.charge_now,
                "trip_mode": self.trip_mode,
                "target_soc": self.target_soc,
                "minimum_soc": self.minimum_soc,
                "departure": departure,
            }
        )
