"""Pure charging scheduler, independent from Home Assistant."""

from __future__ import annotations

from datetime import datetime, timedelta

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
    required_kwh = max(0.0, target_soc - soc) / 100 * battery_capacity_kwh
    if required_kwh <= 0 or charge_power_kw <= 0 or deadline <= now:
        return ChargePlan(required_kwh=required_kwh)

    candidates = [
        PriceSlot(max(slot.start, now), min(slot.end, deadline), slot.price)
        for slot in prices
        if slot.end > now and slot.start < deadline
    ]
    candidates = [slot for slot in candidates if slot.end > slot.start]
    if not candidates:
        return ChargePlan(required_kwh=required_kwh, complete=False)

    needed_input_kwh = required_kwh / max(0.01, efficiency)
    urgent_battery_kwh = max(0.0, min(minimum_soc, target_soc) - soc) / 100 * battery_capacity_kwh
    urgent_input_kwh = urgent_battery_kwh / max(0.01, efficiency)
    selected: list[PriceSlot] = []
    used: set[int] = set()
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
        used.add(index)
        return amount

    # When SOC is low, reserve the earliest intervals first for resilience.
    for index in sorted(range(len(candidates)), key=lambda i: candidates[i].start):
        delivered_input += take(index, urgent_input_kwh - delivered_input)
        if delivered_input + 1e-9 >= urgent_input_kwh:
            break

    # Up to 80%, cost wins. Above 80%, use the latest possible slots so the
    # battery does not sit full for longer than necessary.
    base_target = min(target_soc, 80.0)
    base_input_kwh = max(0.0, base_target - soc) / 100 * battery_capacity_kwh / max(0.01, efficiency)
    for index in sorted(range(len(candidates)), key=lambda i: (candidates[i].price, candidates[i].start)):
        if index in used:
            continue
        delivered_input += take(index, min(base_input_kwh, needed_input_kwh) - delivered_input)
        if delivered_input + 1e-9 >= min(base_input_kwh, needed_input_kwh):
            break

    if delivered_input < needed_input_kwh:
        for index in sorted(range(len(candidates)), key=lambda i: candidates[i].end, reverse=True):
            if index in used:
                continue
            delivered_input += take(index, needed_input_kwh - delivered_input, from_end=True)
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
