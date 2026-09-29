"""Constants for Rewards Tracker."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "rewards_tracker"
VERSION: Final = "0.1.0"

CONF_NAME: Final = "name"
CONF_TICKS_PER_STAR: Final = "ticks_per_star"
CONF_STARS_PER_POUND: Final = "stars_per_pound"
CONF_DAILY_INTEREST_PERCENT: Final = "daily_interest_percent"
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
CONF_INTEREST_LAST_PAID: Final = "interest_last_paid"

DEFAULT_TICKS_PER_STAR: Final = 5
DEFAULT_STARS_PER_POUND: Final = 3
DEFAULT_DAILY_INTEREST_PERCENT: Final = 1
DEFAULT_CURRENCY_SYMBOL: Final = "£"
DEFAULT_REWARD_DESCRIPTION: Final = "Buy Book"
DEFAULT_REWARD_COST: Final = 3
DEFAULT_REWARD_ICON: Final = "mdi:book-open-variant"

INTEREST_HOUR: Final = 7
INTEREST_MINUTE: Final = 0
STORE_VERSION: Final = 1
STORE_KEY: Final = "store"

URL_BASE: Final = "/rewards_tracker"
CARD_FILENAME: Final = "rewards-tracker-card.js"

PLATFORMS: Final[list[str]] = ["sensor"]
