"""Runtime state for one child."""

from __future__ import annotations

import asyncio
from datetime import date
import logging
from typing import Any, Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .calculator import (
    Pot,
    Rules,
    apply_interest,
    award_tick,
    deposit,
    settle,
    spend,
    withdraw,
)
from .const import (
    CONF_BALANCE,
    CONF_CURRENCY_SYMBOL,
    CONF_DAILY_INTEREST_PERCENT,
    CONF_INTEREST_LAST_PAID,
    CONF_INTEREST_PENCE,
    CONF_NAME,
    CONF_REWARDS,
    CONF_SAVINGS,
    CONF_STARS,
    CONF_STARS_PER_POUND,
    CONF_TICKS,
    CONF_TICKS_PER_STAR,
    CONF_TIER1_COUNT,
    CONF_TIER1_ICON,
    CONF_TIER1_NAME,
    CONF_TIER2_COUNT,
    CONF_TIER2_ICON,
    CONF_TIER2_NAME,
    CONF_UNITS_EARNED,
    DEFAULT_CURRENCY_SYMBOL,
    DEFAULT_DAILY_INTEREST_PERCENT,
    DEFAULT_TIER1_COUNT,
    DEFAULT_TIER1_ICON,
    DEFAULT_TIER1_NAME,
    DEFAULT_TIER2_COUNT,
    DEFAULT_TIER2_ICON,
    DEFAULT_TIER2_NAME,
    DEFAULT_UNITS_EARNED,
    DOMAIN,
    INTEREST_HOUR,
    INTEREST_MINUTE,
    STORE_VERSION,
)

_LOGGER = logging.getLogger(__name__)
Listener = Callable[[], None]


def settings_from_entry(entry) -> dict[str, Any]:
    """Return the child's rules, preferring options over the original data."""
    return normalize_settings(dict(entry.options or entry.data))


def normalize_settings(raw: dict[str, Any]) -> dict[str, Any]:
    """Fill tier names and icons, including children saved before those fields existed."""
    tier1_count = _setting_count(
        raw.get(CONF_TIER1_COUNT, raw.get(CONF_TICKS_PER_STAR)),
        DEFAULT_TIER1_COUNT,
        minimum=1,
    )
    tier2_count = _setting_count(
        raw.get(CONF_TIER2_COUNT, raw.get(CONF_STARS_PER_POUND)),
        DEFAULT_TIER2_COUNT,
        minimum=1,
    )
    units_earned = _setting_count(
        raw.get(CONF_UNITS_EARNED), DEFAULT_UNITS_EARNED, minimum=1
    )
    interest = _setting_count(
        raw.get(CONF_DAILY_INTEREST_PERCENT),
        DEFAULT_DAILY_INTEREST_PERCENT,
        minimum=0,
    )
    symbol = str(raw.get(CONF_CURRENCY_SYMBOL) or DEFAULT_CURRENCY_SYMBOL).strip()
    return {
        CONF_NAME: str(raw.get(CONF_NAME) or "").strip(),
        CONF_TIER1_NAME: _setting_label(raw.get(CONF_TIER1_NAME), DEFAULT_TIER1_NAME),
        CONF_TIER1_ICON: _setting_icon(raw.get(CONF_TIER1_ICON), DEFAULT_TIER1_ICON),
        CONF_TIER1_COUNT: tier1_count,
        CONF_TIER2_NAME: _setting_label(raw.get(CONF_TIER2_NAME), DEFAULT_TIER2_NAME),
        CONF_TIER2_ICON: _setting_icon(raw.get(CONF_TIER2_ICON), DEFAULT_TIER2_ICON),
        CONF_TIER2_COUNT: tier2_count,
        CONF_UNITS_EARNED: units_earned,
        CONF_CURRENCY_SYMBOL: symbol or DEFAULT_CURRENCY_SYMBOL,
        CONF_DAILY_INTEREST_PERCENT: interest,
        CONF_REWARDS: list(raw.get(CONF_REWARDS) or []),
        CONF_TICKS_PER_STAR: tier1_count,
        CONF_STARS_PER_POUND: tier2_count,
    }


def _setting_count(value: Any, default: int, minimum: int) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return default
    return number if number >= minimum else default


def _setting_label(value: Any, default: str) -> str:
    text = str(value or "").strip()
    return text or default


def _setting_icon(value: Any, default: str) -> str:
    icon = str(value or "").strip()
    if ":" not in icon or " " in icon:
        return default
    return icon


class ChildTracker:
    """Persisted balances and actions for one config entry."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        """Load nothing yet. Call async_load before use."""
        self.hass = hass
        self.entry = entry
        self.pot = Pot()
        self.store: Store[dict[str, Any]] = Store(
            hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._lock = asyncio.Lock()
        self._listeners: list[Listener] = []
        self._unsub_interest: Callable[[], None] | None = None

    @property
    def settings(self) -> dict[str, Any]:
        """Return the current options for this child."""
        return settings_from_entry(self.entry)

    @property
    def name(self) -> str:
        """Return the child's name."""
        return str(self.settings.get(CONF_NAME) or self.entry.title)

    @property
    def currency(self) -> str:
        """Return the currency symbol."""
        return str(self.settings.get(CONF_CURRENCY_SYMBOL) or "£")

    @property
    def rewards(self) -> list[dict[str, Any]]:
        """Return the spend list."""
        return [dict(reward) for reward in self.settings.get(CONF_REWARDS, [])]

    @property
    def tier1_name(self) -> str:
        """Return the name of the first tier."""
        return str(self.settings[CONF_TIER1_NAME])

    @property
    def tier1_icon(self) -> str:
        """Return the icon of the first tier."""
        return str(self.settings[CONF_TIER1_ICON])

    @property
    def tier2_name(self) -> str:
        """Return the name of the second tier."""
        return str(self.settings[CONF_TIER2_NAME])

    @property
    def tier2_icon(self) -> str:
        """Return the icon of the second tier."""
        return str(self.settings[CONF_TIER2_ICON])

    @property
    def rules(self) -> Rules:
        """Return the conversion and interest rules."""
        settings = self.settings
        return Rules(
            ticks_per_star=int(settings[CONF_TIER1_COUNT]),
            stars_per_pound=int(settings[CONF_TIER2_COUNT]),
            daily_interest_percent=int(settings[CONF_DAILY_INTEREST_PERCENT]),
            units_earned=int(settings[CONF_UNITS_EARNED]),
        )

    def find_reward(self, reward_id: str) -> dict[str, Any] | None:
        """Return one spend option by its id."""
        for reward in self.rewards:
            if reward.get("id") == reward_id:
                return reward
        return None

    def add_listener(self, listener: Listener) -> Callable[[], None]:
        """Subscribe to balance changes. Returns an unsubscribe callback."""
        self._listeners.append(listener)

        def _remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _remove

    async def async_load(self) -> None:
        """Load balances from disk, or start an empty pot."""
        raw = await self.store.async_load()
        self.pot = settle(_pot_from_storage(raw), self.rules)
        if raw is None or _pot_from_storage(raw) != self.pot:
            await self.store.async_save(_pot_to_storage(self.pot))

    def async_schedule_interest(self) -> None:
        """Pay interest every morning at 07:00 local time."""

        async def _run(_now) -> None:
            await self.async_apply_due_interest()

        self._unsub_interest = async_track_time_change(
            self.hass,
            _run,
            hour=INTEREST_HOUR,
            minute=INTEREST_MINUTE,
            second=0,
        )

    async def async_close(self) -> None:
        """Stop the morning interest job."""
        if self._unsub_interest is not None:
            self._unsub_interest()
            self._unsub_interest = None

    async def async_apply_due_interest(self) -> None:
        """Pay any days that have not been paid yet."""
        async with self._lock:
            today = dt_util.now().date()
            updated = apply_interest(self.pot, self.rules, today)
            if updated == self.pot:
                return
            if updated.savings != self.pot.savings:
                _LOGGER.info(
                    "%s savings interest paid. Savings are now %s",
                    self.name,
                    updated.savings,
                )
            self.pot = updated
            await self._persist_locked()

    async def async_award_tick(self) -> None:
        """Award one tick."""
        async with self._lock:
            self.pot = award_tick(self.pot, self.rules)
            await self._persist_locked()

    async def async_deposit(self) -> bool:
        """Move one unit into savings. False when spending money is empty."""
        async with self._lock:
            updated = deposit(self.pot)
            if updated is None:
                return False
            self.pot = updated
            await self._persist_locked()
            return True

    async def async_withdraw(self) -> bool:
        """Move one unit back to spending money. False when savings are empty."""
        async with self._lock:
            updated = withdraw(self.pot)
            if updated is None:
                return False
            self.pot = updated
            await self._persist_locked()
            return True

    async def async_spend(self, cost: int) -> bool:
        """Subtract a cost from spending money. False when it does not cover it."""
        async with self._lock:
            updated = spend(self.pot, cost)
            if updated is None:
                return False
            self.pot = updated
            await self._persist_locked()
            return True

    async def async_set_balances(
        self,
        ticks: int,
        stars: int,
        balance: int,
        savings: int,
        interest_pence: int,
    ) -> None:
        """Replace the balances from the Configure screen and fold thresholds."""
        async with self._lock:
            self.pot = settle(
                Pot(
                    ticks=ticks,
                    stars=stars,
                    balance=balance,
                    savings=savings,
                    interest_pence=interest_pence,
                    interest_last_paid=self.pot.interest_last_paid,
                ),
                self.rules,
            )
            await self._persist_locked()

    async def _persist_locked(self) -> None:
        await self.store.async_save(_pot_to_storage(self.pot))
        for listener in list(self._listeners):
            listener()


def _pot_to_storage(pot: Pot) -> dict[str, Any]:
    last_paid = pot.interest_last_paid.isoformat() if pot.interest_last_paid else None
    return {
        CONF_TICKS: pot.ticks,
        CONF_STARS: pot.stars,
        CONF_BALANCE: pot.balance,
        CONF_SAVINGS: pot.savings,
        CONF_INTEREST_PENCE: pot.interest_pence,
        CONF_INTEREST_LAST_PAID: last_paid,
    }


def _pot_from_storage(raw: dict[str, Any] | None) -> Pot:
    if not raw:
        return Pot()
    last_paid: date | None = None
    raw_date = raw.get(CONF_INTEREST_LAST_PAID)
    if isinstance(raw_date, str) and raw_date:
        try:
            last_paid = date.fromisoformat(raw_date)
        except ValueError:
            _LOGGER.warning("Ignoring unreadable interest date %s", raw_date)
    return Pot(
        ticks=_stored_int(raw, CONF_TICKS),
        stars=_stored_int(raw, CONF_STARS),
        balance=_stored_int(raw, CONF_BALANCE),
        savings=_stored_int(raw, CONF_SAVINGS),
        interest_pence=_stored_int(raw, CONF_INTEREST_PENCE),
        interest_last_paid=last_paid,
    )


def _stored_int(raw: dict[str, Any], key: str) -> int:
    try:
        return int(raw.get(key, 0))
    except (TypeError, ValueError):
        return 0


@callback
def async_get_tracker(hass: HomeAssistant, entry_id: str) -> ChildTracker:
    """Return the running tracker for a config entry."""
    return hass.data[DOMAIN][entry_id]
