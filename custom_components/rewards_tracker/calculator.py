"""Pure reward rules.

The first tier rolls into the second, the second pays spending money, and
savings earn a percent over a chosen period. That interest can be worked out
on a shorter timer than the period itself.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime

MAX_CATCHUP_DAYS = 31
UNIT = 100_000_000
POINT = UNIT // 100

TIME_UNITS = ("seconds", "minutes", "hours", "days")
_UNIT_SECONDS = {
    "seconds": 1,
    "minutes": 60,
    "hours": 3600,
    "days": 86400,
}


@dataclass(frozen=True)
class Rules:
    """Thresholds and interest for one child."""

    ticks_per_star: int
    stars_per_pound: int
    daily_interest_percent: int
    units_earned: int = 1
    interest_rate_hundredths: int | None = None
    interest_period_seconds: int = 86400


@dataclass(frozen=True)
class Pot:
    """Balances for one child."""

    ticks: int = 0
    stars: int = 0
    balance: int = 0
    savings: int = 0
    interest_pence: int = 0
    interest_last_paid: date | None = None
    interest_nanos: int = 0
    interest_remainder: int = 0
    interest_last_calculated: datetime | None = None


def seconds_for(value: int, unit: str) -> int:
    """Convert a count of seconds, minutes, hours, or days into seconds."""
    return max(1, int(value)) * _UNIT_SECONDS[unit]


def progress_points(nanos: int) -> float:
    """Return progress toward the next whole unit, on a 0 to 100 scale."""
    return round(max(0, nanos) / POINT, 2)


def _whole(value: int) -> int:
    return max(0, int(value))


def _rate_hundredths(rules: Rules) -> int:
    if rules.interest_rate_hundredths is None:
        return max(0, int(rules.daily_interest_percent)) * 100
    return max(0, int(rules.interest_rate_hundredths))


def _stored_nanos(pot: Pot) -> int:
    if pot.interest_nanos:
        return pot.interest_nanos
    return pot.interest_pence * POINT


def settle(pot: Pot, rules: Rules) -> Pot:
    """Fold extra ticks, stars, and interest into the pots that hold them."""
    ticks = _whole(pot.ticks)
    stars = _whole(pot.stars)
    balance = _whole(pot.balance)
    savings = _whole(pot.savings)
    nanos = max(0, _stored_nanos(pot))

    gained, nanos = divmod(nanos, UNIT)
    savings += gained

    while rules.ticks_per_star > 0 and ticks >= rules.ticks_per_star:
        ticks -= rules.ticks_per_star
        stars += 1
    payout = max(1, rules.units_earned)
    while rules.stars_per_pound > 0 and stars >= rules.stars_per_pound:
        stars -= rules.stars_per_pound
        balance += payout

    return Pot(
        ticks=ticks,
        stars=stars,
        balance=balance,
        savings=savings,
        interest_pence=int(nanos // POINT),
        interest_last_paid=pot.interest_last_paid,
        interest_nanos=nanos,
        interest_remainder=max(0, pot.interest_remainder),
        interest_last_calculated=pot.interest_last_calculated,
    )


def award_tick(pot: Pot, rules: Rules) -> Pot:
    """Add one tick and convert anything that crossed a threshold."""
    return settle(replace(pot, ticks=pot.ticks + 1), rules)


def deposit(pot: Pot) -> Pot | None:
    """Move one unit from spending money into savings."""
    if pot.balance < 1:
        return None
    return replace(pot, balance=pot.balance - 1, savings=pot.savings + 1)


def withdraw(pot: Pot) -> Pot | None:
    """Move one unit from savings back into spending money."""
    if pot.savings < 1:
        return None
    return replace(pot, balance=pot.balance + 1, savings=pot.savings - 1)


def spend(pot: Pot, cost: int) -> Pot | None:
    """Subtract a reward cost from spending money."""
    if cost < 1 or pot.balance < cost:
        return None
    return replace(pot, balance=pot.balance - cost)


def accrue(
    savings: int,
    nanos: int,
    remainder: int,
    rate_hundredths: int,
    elapsed_seconds: int,
    period_seconds: int,
) -> tuple[int, int, int]:
    """Add interest for elapsed_seconds. Newly paid units earn after they are paid."""
    remaining = max(0, int(elapsed_seconds))
    period = max(1, int(period_seconds))
    if remaining == 0 or rate_hundredths <= 0 or savings <= 0:
        return savings, nanos, remainder

    steps = 0
    while remaining > 0 and steps < 100000:
        steps += 1
        weight = savings * rate_hundredths * UNIT
        divisor = 10000 * period
        if weight <= 0:
            break
        room = UNIT - nanos
        need = room * divisor - remainder
        seconds_needed = 1 if need <= 0 else (need + weight - 1) // weight
        take = remaining if seconds_needed > remaining else seconds_needed
        total = take * weight + remainder
        nanos += total // divisor
        remainder = total % divisor
        remaining -= take
        if nanos >= UNIT:
            gained, nanos = divmod(nanos, UNIT)
            savings += gained
    return savings, nanos, remainder


def apply_elapsed(pot: Pot, rules: Rules, elapsed_seconds: int) -> Pot:
    """Apply one stretch of interest and keep the fractional progress."""
    savings, nanos, remainder = accrue(
        pot.savings,
        _stored_nanos(pot),
        pot.interest_remainder,
        _rate_hundredths(rules),
        elapsed_seconds,
        rules.interest_period_seconds,
    )
    return replace(
        pot,
        savings=savings,
        interest_nanos=nanos,
        interest_remainder=remainder,
        interest_pence=int(nanos // POINT),
    )


def apply_interest(
    pot: Pot,
    rules: Rules,
    today: date,
    max_days: int = MAX_CATCHUP_DAYS,
) -> Pot:
    """Apply unpaid daily interest, up to max_days, and stamp today as paid.

    A unit created by interest starts earning on the following stretch of time.
    A rate of zero still marks the days as paid.
    """
    if pot.interest_last_paid is None:
        return replace(pot, interest_last_paid=today)

    days = (today - pot.interest_last_paid).days
    if days < 1:
        return pot

    updated = apply_elapsed(pot, rules, min(days, max_days) * 86400)
    return replace(updated, interest_last_paid=today)
