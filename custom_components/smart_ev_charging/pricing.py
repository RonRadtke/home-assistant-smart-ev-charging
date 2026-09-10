"""Normalize electricity prices without inventing prices across missing intervals."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta, tzinfo
from math import isfinite
from typing import Any

from .models import PriceSlot


def _as_datetime(value: Any, zone: tzinfo) -> datetime | None:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=zone)
        return parsed.astimezone(UTC)
    except (TypeError, ValueError):
        return None


def _records(values: Any, zone: tzinfo) -> list[PriceSlot]:
    if not isinstance(values, list):
        return []
    points = []
    for item in values:
        if not isinstance(item, dict):
            continue
        start = _as_datetime(item.get("start") or item.get("datetime") or item.get("time"), zone)
        end = _as_datetime(item.get("end"), zone)
        if start is None or ("end" in item and (end is None or end <= start)):
            continue
        try:
            price = float(item.get("price", item.get("value")))
        except (TypeError, ValueError):
            continue
        if isfinite(price):
            points.append((start, end, price))
    points.sort(key=lambda point: point[0])
    # Infer only supported market intervals. Explicit ends always take precedence.
    gaps = [b[0] - a[0] for a, b in zip(points, points[1:], strict=False) if b[0] > a[0]]
    interval = min(gaps, default=timedelta(minutes=15))
    if interval not in (timedelta(minutes=15), timedelta(minutes=30), timedelta(hours=1)):
        interval = timedelta(minutes=15)
    result = []
    for index, (start, end, price) in enumerate(points):
        if end is None:
            end = start + interval
            if index + 1 < len(points):
                end = min(end, points[index + 1][0])
        if end > start:
            result.append(PriceSlot(start, end, price))
    return result


def _numeric_day(values: Any, day: datetime) -> list[PriceSlot]:
    if not isinstance(values, list) or not values or isinstance(values[0], dict):
        return []
    midnight = day.replace(hour=0, minute=0, second=0, microsecond=0)
    start = midnight.astimezone(UTC)
    end = (midnight + timedelta(days=1)).astimezone(UTC)
    interval = (end - start) / len(values)
    if interval not in (timedelta(minutes=15), timedelta(minutes=30), timedelta(hours=1)):
        return []
    result = []
    for index, value in enumerate(values):
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        if isfinite(price):
            result.append(PriceSlot(start + index * interval, start + (index + 1) * interval, price))
    return result


def parse_price_slots(attributes: dict[str, Any], now: datetime, state_price: Any = None) -> list[PriceSlot]:
    """Prefer timestamped records over arrays, preserving gaps and explicit ends."""
    zone = now.tzinfo or UTC
    slots = _records(attributes.get("prices"), zone)
    if not slots:
        for raw_key, numeric_key, day in (
            ("raw_today", "today", now),
            ("raw_tomorrow", "tomorrow", now + timedelta(days=1)),
        ):
            slots.extend(_records(attributes.get(raw_key), zone) or _numeric_day(attributes.get(numeric_key), day))
    if not slots:
        # An invalid/empty forecast must not silently become 48 hours of known prices.
        if any(key in attributes for key in ("prices", "raw_today", "raw_tomorrow", "today", "tomorrow")):
            return []
        try:
            current = float(state_price)
        except (TypeError, ValueError):
            return []
        if not isfinite(current):
            return []
        start = now.astimezone(UTC)
        return [PriceSlot(start, start + timedelta(days=2), current)]

    result = []
    for slot in sorted(set(slots), key=lambda item: (item.start, item.end, item.price)):
        start = max(slot.start, result[-1].end) if result else slot.start
        if start < slot.end:
            result.append(PriceSlot(start, slot.end, slot.price))
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
    timezone: tzinfo = UTC,
) -> list[PriceSlot]:
    """Split intervals at local tariff boundaries, including DST transitions."""
    def is_night(value: time) -> bool:
        if night_start < night_end:
            return night_start <= value < night_end
        return value >= night_start or value < night_end

    result = []
    for slot in slots:
        energy_price = fixed_price if fixed_price >= 0 else slot.price
        support = max(0.0, energy_price - support_threshold) * support_rate
        boundaries = {slot.start, slot.end}
        day = slot.start.astimezone(timezone).date() - timedelta(days=1)
        last_day = slot.end.astimezone(timezone).date() + timedelta(days=1)
        while day <= last_day:
            for boundary in (night_start, night_end):
                for fold in (0, 1):
                    local = datetime.combine(day, boundary, timezone).replace(fold=fold)
                    instant = local.astimezone(UTC)
                    if slot.start < instant < slot.end:
                        boundaries.add(instant)
            day += timedelta(days=1)
        # Offset transitions can change a tariff without crossing its wall-clock boundary.
        cursor = slot.start.replace(second=0, microsecond=0) + timedelta(minutes=1)
        previous_offset = slot.start.astimezone(timezone).utcoffset()
        while cursor < slot.end:
            offset = cursor.astimezone(timezone).utcoffset()
            if offset != previous_offset:
                boundaries.add(cursor)
            previous_offset = offset
            cursor += timedelta(minutes=1)
        ordered = sorted(boundaries)
        for start, end in zip(ordered, ordered[1:], strict=False):
            local_time = start.astimezone(timezone).time()
            grid_fee = night_fee if is_night(local_time) else day_fee
            result.append(PriceSlot(start, end, energy_price - support + markup + grid_fee))
    return result
