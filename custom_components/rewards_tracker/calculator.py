"""Pure reward rules.

Ticks roll into stars, stars roll into spending money, and savings earn a
whole-percent daily rate that is paid one unit at a time.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

MAX_CATCHUP_DAYS = 31


@dataclass(frozen=True)
class Rules:
    """Thresholds and the daily interest percent for one child."""

    ticks_per_star: int
    stars_per_pound: int
    daily_interest_percent: int


@dataclass(frozen=True)
class Pot:
    """Balances for one child."""

    ticks: int = 0
    stars: int = 0
    balance: int = 0
    savings: int = 0
    interest_pence: int = 0
    interest_last_paid: date | None = None


def _whole(value: int) -> int:
    return max(0, int(value))


def settle(pot: Pot, rules: Rules) -> Pot:
    """Fold extra ticks, stars, and interest into the pots that hold them."""
    ticks = _whole(pot.ticks)
    stars = _whole(pot.stars)
    balance = _whole(pot.balance)
    savings = _whole(pot.savings)
    pence = _whole(pot.interest_pence)

    gained, pence = divmod(pence, 100)
    savings += gained

    while rules.ticks_per_star > 0 and ticks >= rules.ticks_per_star:
        ticks -= rules.ticks_per_star
        stars += 1
    while rules.stars_per_pound > 0 and stars >= rules.stars_per_pound:
        stars -= rules.stars_per_pound
        balance += 1

    return Pot(
        ticks=ticks,
        stars=stars,
        balance=balance,
        savings=savings,
        interest_pence=pence,
        interest_last_paid=pot.interest_last_paid,
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


def apply_interest(
    pot: Pot,
    rules: Rules,
    today: date,
    max_days: int = MAX_CATCHUP_DAYS,
) -> Pot:
    """Apply unpaid daily interest, up to max_days, and stamp today as paid.

    The first call, when no payday has been stored, stamps today and pays
    nothing. Later calls pay one percent-point of the whole-unit savings
    balance per day. A unit created by interest starts earning on the next day.
    A rate of zero still marks the days as paid.
    """
    if pot.interest_last_paid is None:
        return replace(pot, interest_last_paid=today)

    days = (today - pot.interest_last_paid).days
    if days < 1:
        return pot

    savings = pot.savings
    pence = pot.interest_pence
    rate = max(0, rules.daily_interest_percent)
    for _ in range(min(days, max_days)):
        pence += savings * rate
        gained, pence = divmod(pence, 100)
        savings += gained

    return Pot(
        ticks=pot.ticks,
        stars=pot.stars,
        balance=pot.balance,
        savings=savings,
        interest_pence=pence,
        interest_last_paid=today,
    )
