"""Constants for Rewards Tracker."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "rewards_tracker"
VERSION: Final = "0.1.7"

CONF_NAME: Final = "name"
CONF_PERSON: Final = "person"
CONF_TIER1_NAME: Final = "tier1_name"
CONF_TIER1_ICON: Final = "tier1_icon"
CONF_TIER1_COUNT: Final = "tier1_count"
CONF_TIER2_NAME: Final = "tier2_name"
CONF_TIER2_ICON: Final = "tier2_icon"
CONF_TIER2_COUNT: Final = "tier2_count"
CONF_UNITS_EARNED: Final = "units_earned"
CONF_TICKS_PER_STAR: Final = "ticks_per_star"
CONF_STARS_PER_POUND: Final = "stars_per_pound"
CONF_DAILY_INTEREST_PERCENT: Final = "daily_interest_percent"
CONF_INTEREST_RATE: Final = "interest_rate_percent"
CONF_INTEREST_EVERY_VALUE: Final = "interest_every_value"
CONF_INTEREST_EVERY_UNIT: Final = "interest_every_unit"
CONF_INTEREST_CALC_VALUE: Final = "interest_calc_value"
CONF_INTEREST_CALC_UNIT: Final = "interest_calc_unit"
CONF_CURRENCY_SYMBOL: Final = "currency_symbol"
CONF_REWARDS: Final = "rewards"

CONF_DESCRIPTION: Final = "description"
CONF_COST: Final = "cost"
CONF_ICON: Final = "icon"
CONF_REWARD_ID: Final = "reward_id"
CONF_DELETE: Final = "delete"

CONF_TICKS: Final = "ticks"
CONF_STARS: Final = "stars"
CONF_BALANCE: Final = "balance"
CONF_SAVINGS: Final = "savings"
CONF_INTEREST_PENCE: Final = "interest_pence"
CONF_INTEREST_NANOS: Final = "interest_nanos"
CONF_INTEREST_REMAINDER: Final = "interest_remainder"
CONF_INTEREST_LAST_PAID: Final = "interest_last_paid"
CONF_INTEREST_LAST_CALCULATED: Final = "interest_last_calculated"

DEFAULT_TIER1_NAME: Final = "Ticks"
DEFAULT_TIER1_ICON: Final = "mdi:check"
DEFAULT_TIER1_COUNT: Final = 5
DEFAULT_TIER2_NAME: Final = "Stars"
DEFAULT_TIER2_ICON: Final = "mdi:star"
DEFAULT_TIER2_COUNT: Final = 3
DEFAULT_UNITS_EARNED: Final = 1
DEFAULT_TICKS_PER_STAR: Final = DEFAULT_TIER1_COUNT
DEFAULT_STARS_PER_POUND: Final = DEFAULT_TIER2_COUNT
DEFAULT_DAILY_INTEREST_PERCENT: Final = 1
DEFAULT_INTEREST_RATE: Final = 1.0
DEFAULT_INTEREST_EVERY_VALUE: Final = 1
DEFAULT_INTEREST_EVERY_UNIT: Final = "days"
DEFAULT_INTEREST_CALC_VALUE: Final = 1
DEFAULT_INTEREST_CALC_UNIT: Final = "days"
DEFAULT_CURRENCY_SYMBOL: Final = "£"
DEFAULT_REWARD_DESCRIPTION: Final = "Buy Book"
DEFAULT_REWARD_COST: Final = 3
DEFAULT_REWARD_ICON: Final = "mdi:book-open-variant"

STORE_VERSION: Final = 1
STORE_KEY: Final = "store"

URL_BASE: Final = "/rewards_tracker"
CARD_FILENAME: Final = "rewards-tracker-card.js"

PLATFORMS: Final[list[str]] = ["sensor"]
