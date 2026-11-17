"""Norgespris night-window scheduling regression tests."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.smart_ev_charging.models import PriceSlot
from custom_components.smart_ev_charging.planner import build_norgespris_plan


ZONE = ZoneInfo("Europe/Oslo")


def plan(*, soc=50, fill=False, target=80, power=10, now=None, deadline=None):
    now = now or datetime(2026, 11, 17, 20, tzinfo=ZONE)
    deadline = deadline or datetime(2026, 11, 18, 8, tzinfo=ZONE)
    prices = [
        PriceSlot(now + timedelta(hours=i), now + timedelta(hours=i + 1), 0.9 if i < 2 or i >= 10 else 0.6)
        for i in range(12)
    ]
    return build_norgespris_plan(
        now=now, deadline=deadline, soc=soc, target_soc=target,
        battery_capacity_kwh=100, charge_power_kw=power, efficiency=1,
        prices=prices, night_start=time(22), night_end=time(6),
        timezone=ZONE, fill_outside_window=fill,
    )


def test_strict_only_charges_at_night():
    result = plan(soc=50, target=80)
    assert result.complete
    assert result.required_kwh == 30
    assert all(22 <= slot.start.astimezone(ZONE).hour or slot.start.astimezone(ZONE).hour < 6 for slot in result.slots)
    assert result.slots[0].start.astimezone(ZONE).hour == 22


def test_strict_mode_incomplete_when_night_insufficient():
    result = plan(soc=0, target=100, power=10)
    assert not result.complete
    assert result.deliverable_kwh == pytest.approx(80)


def test_extension_fills_outside_night_to_100_percent():
    result = plan(soc=0, fill=True)
    assert result.complete
    assert result.required_kwh == pytest.approx(100)
    assert result.deliverable_kwh == pytest.approx(100)
    assert any(slot.start.astimezone(ZONE).hour < 22 and slot.start.astimezone(ZONE).hour >= 6 for slot in result.slots)


def test_extension_does_not_charge_daytime_if_night_suffices():
    result = plan(soc=80, fill=True)
    assert result.complete
    assert result.required_kwh == pytest.approx(20)
    assert result.slots[0].start.astimezone(ZONE).hour == 22


def test_full_charge_unreachable_if_total_time_insufficient():
    result = plan(soc=0, fill=True, power=5)
    assert not result.complete
    assert result.deliverable_kwh == pytest.approx(60)


def test_no_price_intervals_never_fabricates_charge():
    result = build_norgespris_plan(
        now=datetime(2026, 11, 17, 20, tzinfo=ZONE),
        deadline=datetime(2026, 11, 18, 8, tzinfo=ZONE),
        soc=20, target_soc=80, battery_capacity_kwh=100,
        charge_power_kw=10, efficiency=1, prices=[],
        night_start=time(22), night_end=time(6), timezone=ZONE,
    )
    assert not result.complete
    assert not result.slots
