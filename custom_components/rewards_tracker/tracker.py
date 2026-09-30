"""Runtime state for one child."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta
import logging
from typing import Any, Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .calculator import (
    MAX_CATCHUP_DAYS,
    POINT,
    TIME_UNITS,
    Pot,
    Rules,
    apply_elapsed,
    award_tick,
    deposit,
    seconds_for,
    settle,
    spend,
    withdraw,
)
from .const import (
    CONF_BALANCE,
    CONF_CURRENCY_SYMBOL,
    CONF_DAILY_INTEREST_PERCENT,
    CONF_INTEREST_CALC_UNIT,
    CONF_INTEREST_CALC_VALUE,
    CONF_INTEREST_EVERY_UNIT,
    CONF_INTEREST_EVERY_VALUE,
    CONF_INTEREST_LAST_CALCULATED,
    CONF_INTEREST_LAST_PAID,
    CONF_INTEREST_NANOS,
    CONF_INTEREST_PENCE,
    CONF_INTEREST_RATE,
    CONF_INTEREST_REMAINDER,
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
    DEFAULT_INTEREST_CALC_UNIT,
    DEFAULT_INTEREST_CALC_VALUE,
    DEFAULT_INTEREST_EVERY_UNIT,
    DEFAULT_INTEREST_EVERY_VALUE,
    DEFAULT_INTEREST_RATE,
    DEFAULT_TIER1_COUNT,
    DEFAULT_TIER1_ICON,
    DEFAULT_TIER1_NAME,
    DEFAULT_TIER2_COUNT,
    DEFAULT_TIER2_ICON,
    DEFAULT_TIER2_NAME,
    DEFAULT_UNITS_EARNED,
    DOMAIN,
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
    if CONF_INTEREST_RATE in raw and raw.get(CONF_INTEREST_RATE) is not None:
        rate = _setting_rate(raw.get(CONF_INTEREST_RATE), DEFAULT_INTEREST_RATE)
    else:
        rate = _setting_rate(raw.get(CONF_DAILY_INTEREST_PERCENT), DEFAULT_INTEREST_RATE)
    every_unit = _setting_unit(
        raw.get(CONF_INTEREST_EVERY_UNIT), DEFAULT_INTEREST_EVERY_UNIT
    )
    calc_unit = _setting_unit(raw.get(CONF_INTEREST_CALC_UNIT), DEFAULT_INTEREST_CALC_UNIT)
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
        CONF_DAILY_INTEREST_PERCENT: int(round(rate)),
        CONF_INTEREST_RATE: rate,
        CONF_INTEREST_EVERY_VALUE: _setting_count(
            raw.get(CONF_INTEREST_EVERY_VALUE), DEFAULT_INTEREST_EVERY_VALUE, minimum=1
        ),
        CONF_INTEREST_EVERY_UNIT: every_unit,
        CONF_INTEREST_CALC_VALUE: _setting_count(
            raw.get(CONF_INTEREST_CALC_VALUE), DEFAULT_INTEREST_CALC_VALUE, minimum=1
        ),
        CONF_INTEREST_CALC_UNIT: calc_unit,
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


def _setting_rate(value: Any, default: float) -> float:
    try:
        number = round(float(value), 2)
    except (TypeError, ValueError):
        return default
    if number < 0 or number > 100:
        return default
    return number


def _setting_unit(value: Any, default: str) -> str:
    unit = str(value or "").strip()
    return unit if unit in TIME_UNITS else default


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
        self._interest_stopped = False

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
        rate = float(settings[CONF_INTEREST_RATE])
        return Rules(
            ticks_per_star=int(settings[CONF_TIER1_COUNT]),
            stars_per_pound=int(settings[CONF_TIER2_COUNT]),
            daily_interest_percent=int(round(rate)),
            units_earned=int(settings[CONF_UNITS_EARNED]),
            interest_rate_hundredths=int(round(rate * 100)),
            interest_period_seconds=seconds_for(
                int(settings[CONF_INTEREST_EVERY_VALUE]),
                str(settings[CONF_INTEREST_EVERY_UNIT]),
            ),
        )

    @property
    def calc_seconds(self) -> int:
        """Return how often interest is worked out, in seconds."""
        settings = self.settings
        return seconds_for(
            int(settings[CONF_INTEREST_CALC_VALUE]),
            str(settings[CONF_INTEREST_CALC_UNIT]),
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
        loaded = _pot_from_storage(raw, self.hass)
        self.pot = settle(loaded, self.rules)
        if _pot_to_storage(self.pot) != raw:
            await self.store.async_save(_pot_to_storage(self.pot))

    def async_schedule_interest(self) -> None:
        """Work out interest on the child's calculation interval."""
        if self._interest_stopped:
            return
        if self._unsub_interest is not None:
            self._unsub_interest()
            self._unsub_interest = None

        async def _run(_now) -> None:
            await self.async_apply_due_interest()
            self.async_schedule_interest()

        last = self.pot.interest_last_calculated or dt_util.utcnow()
        nxt = last + timedelta(seconds=self.calc_seconds)
        now = dt_util.utcnow()
        if nxt <= now:
            nxt = now + timedelta(seconds=1)
        self._unsub_interest = async_track_point_in_utc_time(self.hass, _run, nxt)

    async def async_close(self) -> None:
        """Stop the interest timer."""
        self._interest_stopped = True
        if self._unsub_interest is not None:
            self._unsub_interest()
            self._unsub_interest = None

    async def async_apply_due_interest(self) -> None:
        """Apply each whole calculation interval that has elapsed, up to 31 days."""
        async with self._lock:
            now = dt_util.utcnow()
            last = self.pot.interest_last_calculated
            if last is None:
                self.pot = Pot(
                    ticks=self.pot.ticks,
                    stars=self.pot.stars,
                    balance=self.pot.balance,
                    savings=self.pot.savings,
                    interest_pence=self.pot.interest_pence,
                    interest_nanos=self.pot.interest_nanos,
                    interest_remainder=self.pot.interest_remainder,
                    interest_last_calculated=now,
                )
                await self._persist_locked()
                return

            elapsed = int((now - last).total_seconds())
            step = self.calc_seconds
            cap = MAX_CATCHUP_DAYS * 86400
            if elapsed < step:
                return
            applied_steps = min(elapsed // step, max(1, cap // step))
            updated = apply_elapsed(self.pot, self.rules, applied_steps * step)
            new_last = now if elapsed > cap else last + timedelta(seconds=applied_steps * step)
            updated = Pot(
                ticks=updated.ticks,
                stars=updated.stars,
                balance=updated.balance,
                savings=updated.savings,
                interest_pence=updated.interest_pence,
                interest_last_paid=updated.interest_last_paid,
                interest_nanos=updated.interest_nanos,
                interest_remainder=updated.interest_remainder,
                interest_last_calculated=new_last,
            )
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
            submitted = max(0, interest_pence)
            if submitted == self.pot.interest_nanos // POINT:
                nanos = self.pot.interest_nanos
                remainder = self.pot.interest_remainder
            else:
                nanos = submitted * POINT
                remainder = 0
            self.pot = settle(
                Pot(
                    ticks=ticks,
                    stars=stars,
                    balance=balance,
                    savings=savings,
                    interest_nanos=nanos,
                    interest_remainder=remainder,
                    interest_last_calculated=self.pot.interest_last_calculated,
                ),
                self.rules,
            )
            await self._persist_locked()

    async def _persist_locked(self) -> None:
        await self.store.async_save(_pot_to_storage(self.pot))
        for listener in list(self._listeners):
            listener()


def _pot_to_storage(pot: Pot) -> dict[str, Any]:
    last = pot.interest_last_calculated
    return {
        CONF_TICKS: pot.ticks,
        CONF_STARS: pot.stars,
        CONF_BALANCE: pot.balance,
        CONF_SAVINGS: pot.savings,
        CONF_INTEREST_PENCE: pot.interest_pence,
        CONF_INTEREST_NANOS: pot.interest_nanos,
        CONF_INTEREST_REMAINDER: pot.interest_remainder,
        CONF_INTEREST_LAST_CALCULATED: last.isoformat() if last else None,
    }


def _pot_from_storage(raw: dict[str, Any] | None, hass: HomeAssistant) -> Pot:
    if not raw:
        return Pot()
    if CONF_INTEREST_NANOS in raw:
        nanos = _stored_int(raw, CONF_INTEREST_NANOS)
    else:
        nanos = _stored_int(raw, CONF_INTEREST_PENCE) * POINT
    return Pot(
        ticks=_stored_int(raw, CONF_TICKS),
        stars=_stored_int(raw, CONF_STARS),
        balance=_stored_int(raw, CONF_BALANCE),
        savings=_stored_int(raw, CONF_SAVINGS),
        interest_pence=nanos // POINT,
        interest_nanos=nanos,
        interest_remainder=_stored_int(raw, CONF_INTEREST_REMAINDER),
        interest_last_calculated=_calculated_from_storage(raw, hass),
    )


def _calculated_from_storage(raw: dict[str, Any], hass: HomeAssistant) -> datetime | None:
    raw_stamp = raw.get(CONF_INTEREST_LAST_CALCULATED)
    if isinstance(raw_stamp, str) and raw_stamp:
        parsed = dt_util.parse_datetime(raw_stamp)
        if parsed is not None:
            return dt_util.as_utc(parsed)
        _LOGGER.warning("Ignoring unreadable interest time %s", raw_stamp)
    raw_date = raw.get(CONF_INTEREST_LAST_PAID)
    if not isinstance(raw_date, str) or not raw_date:
        return None
    try:
        paid = date.fromisoformat(raw_date)
    except ValueError:
        _LOGGER.warning("Ignoring unreadable interest date %s", raw_date)
        return None
    if paid >= dt_util.now().date():
        return dt_util.utcnow()
    zone = dt_util.get_time_zone(hass.config.time_zone) or dt_util.UTC
    next_day = datetime.combine(paid + timedelta(days=1), time.min, tzinfo=zone)
    return dt_util.as_utc(next_day)


def _stored_int(raw: dict[str, Any], key: str) -> int:
    try:
        return int(raw.get(key, 0))
    except (TypeError, ValueError):
        return 0


@callback
def async_get_tracker(hass: HomeAssistant, entry_id: str) -> ChildTracker:
    """Return the running tracker for a config entry."""
    return hass.data[DOMAIN][entry_id]
