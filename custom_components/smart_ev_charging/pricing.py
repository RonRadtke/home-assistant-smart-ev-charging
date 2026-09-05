"""Normalize common Home Assistant electricity price entity formats."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .models import PriceSlot


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        parsed = dt_util.parse_datetime(value)
        if parsed is not None:
            return dt_util.as_local(parsed)
    return None


def _records(values: Any) -> list[tuple[datetime, float]]:
    result: list[tuple[datetime, float]] = []
    if not isinstance(values, list):
        return result
    for item in values:
        if not isinstance(item, dict):
            continue
        start = _as_datetime(item.get("start") or item.get("datetime") or item.get("time"))
        price = item.get("price", item.get("value"))
        try:
            if start is not None:
                result.append((start, float(price)))
        except (TypeError, ValueError):
            continue
    return result


def _numeric_day(values: Any, day: datetime) -> list[tuple[datetime, float]]:
    if not isinstance(values, list) or not values or isinstance(values[0], dict):
        return []
    interval = timedelta(hours=24 / len(values))
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    result = []
    for index, value in enumerate(values):
        try:
            result.append((start + index * interval, float(value)))
        except (TypeError, ValueError):
            continue
    return result


def parse_price_slots(attributes: dict[str, Any], now: datetime, state_price: Any = None) -> list[PriceSlot]:
    """Parse Nord Pool and generic price attributes into intervals."""
    points: list[tuple[datetime, float]] = []
    for key in ("prices", "raw_today", "raw_tomorrow"):
        points.extend(_records(attributes.get(key)))
    points.extend(_numeric_day(attributes.get("today"), now))
    points.extend(_numeric_day(attributes.get("tomorrow"), now + timedelta(days=1)))
    points = sorted(set(points), key=lambda item: item[0])
    if not points:
        try:
            current = float(state_price)
        except (TypeError, ValueError):
            return []
        start = now.replace(second=0, microsecond=0)
        return [
            PriceSlot(start + index * timedelta(minutes=15), start + (index + 1) * timedelta(minutes=15), current)
            for index in range(192)
        ]

    default_interval = points[1][0] - points[0][0] if len(points) > 1 else timedelta(hours=1)
    result: list[PriceSlot] = []
    for index, (start, price) in enumerate(points):
        end = points[index + 1][0] if index + 1 < len(points) else start + default_interval
        if end > start:
            result.append(PriceSlot(start, end, price))
    return result


def add_tariffs(
    slots: list[PriceSlot],
    *,
    markup: float,
    day_fee: float,
    night_fee: float,
    night_start: time,
    night_end: time,
    fixed_price: float = -1,
    support_threshold: float = 0,
    support_rate: float = 0,
) -> list[PriceSlot]:
    """Add supplier markup and time-of-use grid fees."""

    def is_night(value: time) -> bool:
        if night_start < night_end:
            return night_start <= value < night_end
        return value >= night_start or value < night_end

    result = []
    for slot in slots:
        energy_price = fixed_price if fixed_price >= 0 else slot.price
        support = max(0.0, energy_price - support_threshold) * support_rate
        grid_fee = night_fee if is_night(slot.start.timetz().replace(tzinfo=None)) else day_fee
        result.append(PriceSlot(slot.start, slot.end, energy_price - support + markup + grid_fee))
    return result
