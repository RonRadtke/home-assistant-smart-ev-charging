from datetime import UTC, datetime, timedelta

from smart_ev_charging.models import PriceSlot
from smart_ev_charging.planner import build_plan, merge_adjacent

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
