from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from custom_components.smart_ev_charging.models import PriceSlot
from custom_components.smart_ev_charging.pricing import add_tariffs, parse_price_slots


def test_numeric_quarter_hour_prices():
    now = datetime(2026, 9, 4, 12, tzinfo=UTC)
    result = parse_price_slots({"today": list(range(96))}, now)
    assert len(result) == 96
    assert result[0].end - result[0].start == timedelta(minutes=15)


def test_fixed_price_support_and_night_fee():
    start = datetime(2026, 9, 4, 23, tzinfo=UTC)
    result = add_tariffs(
        [PriceSlot(start, start + timedelta(hours=1), 2)],
        markup=0.05,
        day_fee=0.4,
        night_fee=0.2,
        night_start=time(22),
        night_end=time(6),
        fixed_price=1,
        support_threshold=0.5,
        support_rate=0.9,
    )
    assert result[0].price == pytest.approx(0.8)


def test_explicit_ends_preserve_missing_price_gap():
    now = datetime(2026, 9, 10, 18, tzinfo=UTC)
    result = parse_price_slots({"prices": [
        {"start": now, "end": now + timedelta(minutes=15), "price": 1},
        {"start": now + timedelta(hours=2), "end": now + timedelta(hours=2, minutes=15), "price": 2},
    ]}, now)
    assert sum(slot.hours for slot in result) == 0.5


def test_invalid_numeric_price_leaves_a_gap():
    now = datetime(2026, 9, 10, tzinfo=UTC)
    result = parse_price_slots({"today": [1, "unavailable"] + [1] * 22}, now)
    assert len(result) == 23
    assert result[0].end == now + timedelta(hours=1)
    assert result[1].start == now + timedelta(hours=2)


def test_raw_prices_take_precedence_over_duplicate_numeric_arrays():
    now = datetime(2026, 9, 10, tzinfo=UTC)
    result = parse_price_slots({
        "raw_today": [{"start": now, "end": now + timedelta(hours=1), "value": 2}],
        "today": [1] * 24,
    }, now)
    assert result == [PriceSlot(now, now + timedelta(hours=1), 2)]


@pytest.mark.parametrize("attributes", [{"prices": []}, {"today": [float("nan")] * 24}])
def test_invalid_forecast_does_not_fall_back_to_current_price(attributes):
    assert parse_price_slots(attributes, datetime(2026, 9, 10, tzinfo=UTC), 1) == []


@pytest.mark.parametrize(("month", "day", "count"), [(3, 29, 23), (10, 25, 25)])
@pytest.mark.parametrize("per_hour", [1, 2, 4])
def test_numeric_prices_on_dst_days(month, day, count, per_hour):
    now = datetime(2026, month, day, tzinfo=ZoneInfo("Europe/Oslo"))
    result = parse_price_slots({"today": [1] * (count * per_hour)}, now)
    assert len(result) == count * per_hour
    assert sum(slot.hours for slot in result) == count


def test_tariff_splits_a_price_interval_at_local_boundary():
    now = datetime(2026, 9, 10, 19, tzinfo=UTC)  # 21:00 Oslo
    result = add_tariffs(
        [PriceSlot(now, now + timedelta(hours=2), 1)],
        markup=0, day_fee=1, night_fee=0, night_start=time(22), night_end=time(6),
        timezone=ZoneInfo("Europe/Oslo"),
    )
    assert [slot.price for slot in result] == [2, 1]
    assert [slot.hours for slot in result] == [1, 1]


def test_start_only_records_do_not_bridge_long_gaps():
    now = datetime(2026, 9, 10, tzinfo=UTC)
    result = parse_price_slots({"prices": [
        {"start": now, "price": 1}, {"start": now + timedelta(hours=4), "price": 2},
    ]}, now)
    assert sum(slot.hours for slot in result) == 0.5
