"""Runtime models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coordinator import SmartEVChargingCoordinator


@dataclass(frozen=True, slots=True)
class PriceSlot:
    """One price interval."""

    start: datetime
    end: datetime
    price: float

    def __post_init__(self) -> None:
        """Keep elapsed-time arithmetic correct across daylight-saving changes."""
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("Price intervals must have timezone-aware timestamps")
        object.__setattr__(self, "start", self.start.astimezone(UTC))
        object.__setattr__(self, "end", self.end.astimezone(UTC))

    @property
    def hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600


@dataclass(frozen=True, slots=True)
class ChargePlan:
    """Calculated charging plan."""

    slots: tuple[PriceSlot, ...] = ()
    required_kwh: float = 0
    deliverable_kwh: float = 0
    estimated_cost: float = 0
    complete: bool = True

    @property
    def next_start(self) -> datetime | None:
        return self.slots[0].start if self.slots else None

    @property
    def next_end(self) -> datetime | None:
        return self.slots[0].end if self.slots else None

    def active(self, now: datetime) -> bool:
        now = now.astimezone(UTC)
        return any(slot.start <= now < slot.end for slot in self.slots)


@dataclass(slots=True)
class RuntimeData:
    """Config entry runtime data."""

    coordinator: SmartEVChargingCoordinator
    unload_callbacks: list = field(default_factory=list)
