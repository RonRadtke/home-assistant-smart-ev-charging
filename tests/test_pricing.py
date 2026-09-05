from datetime import UTC, datetime, time, timedelta

import pytest
from smart_ev_charging.models import PriceSlot
from smart_ev_charging.pricing import add_tariffs, parse_price_slots


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
