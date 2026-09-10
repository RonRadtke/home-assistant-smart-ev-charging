from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.smart_ev_charging.models import PriceSlot
from custom_components.smart_ev_charging.planner import build_plan, merge_adjacent

UTC = UTC
NOW = datetime(2026, 9, 4, 18, tzinfo=UTC)


def slots(prices):
    return [PriceSlot(NOW + timedelta(hours=i), NOW + timedelta(hours=i + 1), price) for i, price in enumerate(prices)]


def plan(*, soc=70, target=80, minimum=30, prices=(5, 1, 2, 4), deadline_hours=4, power=10, efficiency=1):
    return build_plan(
        now=NOW,
        deadline=NOW + timedelta(hours=deadline_hours),
        soc=soc,
        target_soc=target,
        minimum_soc=minimum,
        battery_capacity_kwh=100,
        charge_power_kw=power,
        efficiency=efficiency,
        prices=slots(prices),
    )


def test_chooses_cheapest_slots():
    result = plan(soc=70)
    assert result.complete
    assert result.required_kwh == 10
    assert result.slots[0].start == NOW + timedelta(hours=1)
    assert result.estimated_cost == 10


def test_low_soc_charges_immediately_to_minimum():
    result = plan(soc=20, target=40, minimum=30, prices=(10, 1, 2, 3))
    assert result.slots[0].start == NOW
    assert result.slots[0].end == NOW + timedelta(hours=2)


def test_deadline_wins_when_all_slots_needed():
    result = plan(soc=60, target=100, prices=(100, 1, 2, 3))
    assert result.complete
    assert sum(slot.hours for slot in result.slots) == 4


def test_unreachable_deadline_is_reported():
    result = plan(soc=20, target=80, prices=(1, 2), deadline_hours=2)
    assert not result.complete
    assert result.deliverable_kwh == 20


def test_trip_top_up_is_at_end():
    result = plan(soc=80, target=100, minimum=30, prices=(1, 1, 100, 100), power=10)
    assert result.slots[0].start == NOW + timedelta(hours=2)
    assert result.slots[-1].end == NOW + timedelta(hours=4)


def test_efficiency_increases_grid_energy_and_cost():
    result = plan(soc=90, target=100, minimum=30, prices=(2, 2), power=10, efficiency=0.5, deadline_hours=2)
    assert result.required_kwh == 10
    assert result.deliverable_kwh == 10
    assert result.estimated_cost == 40


def test_no_charge_when_target_reached():
    result = plan(soc=80, target=80)
    assert result.complete
    assert not result.slots


def test_no_known_prices_is_incomplete():
    result = build_plan(
        now=NOW,
        deadline=NOW + timedelta(hours=4),
        soc=20,
        target_soc=80,
        minimum_soc=30,
        battery_capacity_kwh=100,
        charge_power_kw=10,
        efficiency=1,
        prices=[],
    )
    assert not result.complete
    assert not result.slots


def test_merge_empty_schedule():
    assert merge_adjacent([]) == ()


def test_partial_urgent_interval_is_reused():
    result = plan(soc=29, target=31, minimum=30, prices=(5,), deadline_hours=1)
    assert result.complete
    assert result.deliverable_kwh == pytest.approx(2)
    assert result.slots[0].hours == pytest.approx(0.2)


def test_partial_base_and_trip_share_an_interval():
    result = plan(soc=79, target=81, prices=(5,), deadline_hours=1)
    assert result.complete
    assert result.deliverable_kwh == pytest.approx(2)
    assert result.slots[-1].end == NOW + timedelta(hours=1)


def test_trip_reserves_latest_energy_before_cheap_base():
    result = plan(soc=75, target=95, prices=(5, 1), deadline_hours=2)
    assert result.complete
    assert sum(slot.hours for slot in result.slots) == pytest.approx(2)


@pytest.mark.parametrize(("month", "day", "hours"), [(3, 29, 3), (10, 25, 5)])
def test_dst_uses_elapsed_hours(month, day, hours):
    zone = ZoneInfo("Europe/Oslo")
    start = datetime(2026, month, day, 0, tzinfo=zone)
    end = datetime(2026, month, day, 4, tzinfo=zone)
    slot = PriceSlot(start, end, 1)
    assert slot.hours == hours
    result = build_plan(
        now=start, deadline=end, soc=0, target_soc=hours * 10, minimum_soc=0,
        battery_capacity_kwh=100, charge_power_kw=10, efficiency=1, prices=[slot],
    )
    assert result.complete
    assert result.deliverable_kwh == pytest.approx(hours * 10)


def test_overlapping_intervals_do_not_double_count_capacity():
    result = build_plan(
        now=NOW, deadline=NOW + timedelta(hours=1), soc=0, target_soc=20, minimum_soc=0,
        battery_capacity_kwh=100, charge_power_kw=10, efficiency=1,
        prices=[PriceSlot(NOW, NOW + timedelta(hours=1), 1)] * 2,
    )
    assert not result.complete
    assert result.deliverable_kwh == 10


@pytest.mark.parametrize("soc", [float("nan"), float("inf"), -1, 101])
def test_invalid_soc_is_incomplete(soc):
    result = plan(soc=soc)
    assert not result.complete
    assert not result.slots
