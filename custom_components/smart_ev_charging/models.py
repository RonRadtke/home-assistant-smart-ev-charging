"""Runtime models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coordinator import SmartEVChargingCoordinator


@dataclass(frozen=True, slots=True)
class PriceSlot:
    """One price interval."""

    start: datetime
    end: datetime
    price: float

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
        return any(slot.start <= now < slot.end for slot in self.slots)


@dataclass(slots=True)
class RuntimeData:
    """Config entry runtime data."""

    coordinator: SmartEVChargingCoordinator
    unload_callbacks: list = field(default_factory=list)
