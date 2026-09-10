"""Pure charging scheduler, independent from Home Assistant."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import isfinite

from .models import ChargePlan, PriceSlot


def merge_adjacent(slots: list[PriceSlot]) -> tuple[PriceSlot, ...]:
    """Merge adjacent selected slots into actual charging windows."""
    if not slots:
        return ()
    ordered = sorted(slots, key=lambda item: item.start)
    merged = [ordered[0]]
    for slot in ordered[1:]:
        previous = merged[-1]
        if previous.end == slot.start:
            total_hours = previous.hours + slot.hours
            average_price = (previous.price * previous.hours + slot.price * slot.hours) / total_hours
            merged[-1] = PriceSlot(previous.start, slot.end, average_price)
        else:
            merged.append(slot)
    return tuple(merged)


def build_plan(
    *,
    now: datetime,
    deadline: datetime,
    soc: float,
    target_soc: float,
    minimum_soc: float,
    battery_capacity_kwh: float,
    charge_power_kw: float,
    efficiency: float,
    prices: list[PriceSlot],
) -> ChargePlan:
    """Choose the cheapest feasible slots, with immediate low-SOC recovery."""
    now, deadline = now.astimezone(UTC), deadline.astimezone(UTC)
    if not all(isfinite(value) for value in (
        soc, target_soc, minimum_soc, battery_capacity_kwh, charge_power_kw, efficiency
    )) or not (0 <= soc <= 100 and battery_capacity_kwh > 0 and charge_power_kw > 0 and 0 < efficiency <= 1):
        return ChargePlan(complete=False)
    required_kwh = max(0.0, target_soc - soc) / 100 * battery_capacity_kwh
    if required_kwh <= 0:
        return ChargePlan(required_kwh=required_kwh)
    if deadline <= now:
        return ChargePlan(required_kwh=required_kwh, complete=False)

    candidates = [
        PriceSlot(max(slot.start, now), min(slot.end, deadline), slot.price)
        for slot in prices
        if slot.end > now and slot.start < deadline and isfinite(slot.price)
    ]
    candidates = [slot for slot in candidates if slot.end > slot.start]
    # Never count overlapping input intervals as simultaneous charging capacity.
    non_overlapping = []
    for slot in sorted(candidates, key=lambda item: (item.start, item.end)):
        start = max(slot.start, non_overlapping[-1].end) if non_overlapping else slot.start
        if start < slot.end:
            non_overlapping.append(PriceSlot(start, slot.end, slot.price))
    candidates = non_overlapping
    if not candidates:
        return ChargePlan(required_kwh=required_kwh, complete=False)

    needed_input_kwh = required_kwh / max(0.01, efficiency)
    urgent_battery_kwh = max(0.0, min(minimum_soc, target_soc) - soc) / 100 * battery_capacity_kwh
    urgent_input_kwh = urgent_battery_kwh / max(0.01, efficiency)
    selected: list[PriceSlot] = []
    delivered_input = 0.0

    def take(index: int, wanted_kwh: float, *, from_end: bool = False) -> float:
        """Reserve all or part of a candidate and return input energy."""
        slot = candidates[index]
        available = slot.hours * charge_power_kw
        amount = min(available, max(0.0, wanted_kwh))
        if amount <= 1e-9:
            return 0.0
        duration = timedelta(hours=amount / charge_power_kw)
        chosen = (
            PriceSlot(slot.end - duration, slot.end, slot.price)
            if from_end
            else PriceSlot(slot.start, slot.start + duration, slot.price)
        )
        selected.append(chosen)
        candidates[index] = (
            PriceSlot(slot.start, chosen.start, slot.price)
            if from_end else PriceSlot(chosen.end, slot.end, slot.price)
        )
        return amount

    # When SOC is low, reserve the earliest intervals first for resilience.
    for index in sorted(range(len(candidates)), key=lambda i: candidates[i].start):
        delivered_input += take(index, urgent_input_kwh - delivered_input)
        if delivered_input + 1e-9 >= urgent_input_kwh:
            break

    # Reserve the top-up last in time, then buy the remaining base energy cheaply.
    # A partial reservation leaves the rest of its interval available.
    base_target = min(target_soc, 80.0)
    base_input_kwh = max(0.0, base_target - soc) / 100 * battery_capacity_kwh / max(0.01, efficiency)
    top_up_kwh = max(0.0, needed_input_kwh - max(base_input_kwh, delivered_input))
    top_up_delivered = 0.0
    for index in sorted(range(len(candidates)), key=lambda i: candidates[i].end, reverse=True):
        top_up_delivered += take(index, top_up_kwh - top_up_delivered, from_end=True)
        if top_up_delivered + 1e-9 >= top_up_kwh:
            break
    delivered_input += top_up_delivered
    for index in sorted(range(len(candidates)), key=lambda i: (candidates[i].price, candidates[i].start)):
        delivered_input += take(index, needed_input_kwh - delivered_input)
        if delivered_input + 1e-9 >= needed_input_kwh:
            break

    selected = sorted(selected, key=lambda item: item.start)

    input_kwh = sum(slot.hours * charge_power_kw for slot in selected)
    battery_kwh = input_kwh * efficiency
    cost = sum(slot.hours * charge_power_kw * slot.price for slot in selected)
    return ChargePlan(
        slots=merge_adjacent(selected),
        required_kwh=required_kwh,
        deliverable_kwh=battery_kwh,
        estimated_cost=cost,
        complete=battery_kwh + 0.02 >= required_kwh,
    )
