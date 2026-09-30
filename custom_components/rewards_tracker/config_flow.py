"""Config and options flows for Rewards Tracker."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    IconSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
import voluptuous as vol

from .const import (
    CONF_BALANCE,
    CONF_COST,
    CONF_CURRENCY_SYMBOL,
    CONF_DAILY_INTEREST_PERCENT,
    CONF_DELETE,
    CONF_DESCRIPTION,
    CONF_ICON,
    CONF_INTEREST_CALC_UNIT,
    CONF_INTEREST_CALC_VALUE,
    CONF_INTEREST_EVERY_UNIT,
    CONF_INTEREST_EVERY_VALUE,
    CONF_INTEREST_PENCE,
    CONF_INTEREST_RATE,
    CONF_NAME,
    CONF_PERSON,
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
    DEFAULT_REWARD_COST,
    DEFAULT_REWARD_DESCRIPTION,
    DEFAULT_REWARD_ICON,
    DEFAULT_TIER1_COUNT,
    DEFAULT_TIER1_ICON,
    DEFAULT_TIER1_NAME,
    DEFAULT_TIER2_COUNT,
    DEFAULT_TIER2_ICON,
    DEFAULT_TIER2_NAME,
    DEFAULT_UNITS_EARNED,
    DOMAIN,
)
from .tracker import async_get_tracker, linked_person_name, stored_person_id

_ADD = "__add__"
_DONE = "__done__"


def _unit(value: Any) -> str:
    unit = str(value)
    if unit in ("seconds", "minutes", "hours", "days"):
        return unit
    return "days"


def _whole(value: Any) -> int:
    return int(float(value))


def _number(min_value: int, max_value: int) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=min_value,
            max=max_value,
            step=1,
            mode=NumberSelectorMode.BOX,
        )
    )


def _decimal(min_value: float, max_value: float, step: float) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=min_value,
            max=max_value,
            step=step,
            mode=NumberSelectorMode.BOX,
        )
    )


def _time_unit() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                {"value": "seconds", "label": "Seconds"},
                {"value": "minutes", "label": "Minutes"},
                {"value": "hours", "label": "Hours"},
                {"value": "days", "label": "Days"},
            ],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _person_selector() -> EntitySelector:
    return EntitySelector(EntitySelectorConfig(domain="person"))


def _present(defaults: dict[str, Any], key: str, fallback: Any) -> Any:
    if key in defaults:
        return defaults[key]
    return fallback


def _settings_schema(defaults: dict[str, Any]) -> vol.Schema:
    tier1_count = _present(
        defaults,
        CONF_TIER1_COUNT,
        _present(defaults, CONF_TICKS_PER_STAR, DEFAULT_TIER1_COUNT),
    )
    tier2_count = _present(
        defaults,
        CONF_TIER2_COUNT,
        _present(defaults, CONF_STARS_PER_POUND, DEFAULT_TIER2_COUNT),
    )
    rate = _present(defaults, CONF_INTEREST_RATE, None)
    if rate is None:
        rate = _present(defaults, CONF_DAILY_INTEREST_PERCENT, DEFAULT_INTEREST_RATE)
    person_id = str(_present(defaults, CONF_PERSON, "") or "")
    person_field = (
        vol.Optional(CONF_PERSON, default=person_id)
        if person_id
        else vol.Optional(CONF_PERSON)
    )
    return vol.Schema(
        {
            person_field: _person_selector(),
            vol.Optional(
                CONF_NAME, default=_present(defaults, CONF_NAME, "")
            ): TextSelector(),
            vol.Required(
                CONF_TIER1_NAME,
                default=_present(defaults, CONF_TIER1_NAME, DEFAULT_TIER1_NAME),
            ): TextSelector(),
            vol.Required(
                CONF_TIER1_ICON,
                default=_present(defaults, CONF_TIER1_ICON, DEFAULT_TIER1_ICON),
            ): IconSelector(),
            vol.Required(CONF_TIER1_COUNT, default=tier1_count): _number(1, 24),
            vol.Required(
                CONF_TIER2_NAME,
                default=_present(defaults, CONF_TIER2_NAME, DEFAULT_TIER2_NAME),
            ): TextSelector(),
            vol.Required(
                CONF_TIER2_ICON,
                default=_present(defaults, CONF_TIER2_ICON, DEFAULT_TIER2_ICON),
            ): IconSelector(),
            vol.Required(CONF_TIER2_COUNT, default=tier2_count): _number(1, 24),
            vol.Required(
                CONF_UNITS_EARNED,
                default=_present(defaults, CONF_UNITS_EARNED, DEFAULT_UNITS_EARNED),
            ): _number(1, 100),
            vol.Required(
                CONF_CURRENCY_SYMBOL,
                default=_present(defaults, CONF_CURRENCY_SYMBOL, DEFAULT_CURRENCY_SYMBOL),
            ): TextSelector(),
            vol.Required(CONF_INTEREST_RATE, default=rate): _decimal(0, 100, 0.01),
            vol.Required(
                CONF_INTEREST_EVERY_VALUE,
                default=_present(
                    defaults, CONF_INTEREST_EVERY_VALUE, DEFAULT_INTEREST_EVERY_VALUE
                ),
            ): _number(1, 100000),
            vol.Required(
                CONF_INTEREST_EVERY_UNIT,
                default=_present(
                    defaults, CONF_INTEREST_EVERY_UNIT, DEFAULT_INTEREST_EVERY_UNIT
                ),
            ): _time_unit(),
            vol.Required(
                CONF_INTEREST_CALC_VALUE,
                default=_present(
                    defaults, CONF_INTEREST_CALC_VALUE, DEFAULT_INTEREST_CALC_VALUE
                ),
            ): _number(1, 100000),
            vol.Required(
                CONF_INTEREST_CALC_UNIT,
                default=_present(
                    defaults, CONF_INTEREST_CALC_UNIT, DEFAULT_INTEREST_CALC_UNIT
                ),
            ): _time_unit(),
        }
    )


def _reward_schema(defaults: dict[str, Any], *, include_delete: bool) -> vol.Schema:
    fields: dict[Any, Any] = {
        vol.Required(
            CONF_DESCRIPTION, default=defaults.get(CONF_DESCRIPTION, "")
        ): TextSelector(),
        vol.Required(CONF_COST, default=defaults.get(CONF_COST, 1)): _number(1, 10000),
        vol.Required(
            CONF_ICON, default=defaults.get(CONF_ICON, "mdi:gift")
        ): IconSelector(),
    }
    if include_delete:
        fields[vol.Required(CONF_DELETE, default=False)] = bool
    return vol.Schema(fields)


def _clean_settings(user_input: dict[str, Any]) -> dict[str, Any]:
    tier1_count = _whole(user_input[CONF_TIER1_COUNT])
    tier2_count = _whole(user_input[CONF_TIER2_COUNT])
    return {
        CONF_NAME: str(user_input.get(CONF_NAME) or "").strip(),
        CONF_PERSON: stored_person_id(user_input),
        CONF_TIER1_NAME: str(user_input[CONF_TIER1_NAME]).strip(),
        CONF_TIER1_ICON: str(user_input[CONF_TIER1_ICON]).strip(),
        CONF_TIER1_COUNT: tier1_count,
        CONF_TIER2_NAME: str(user_input[CONF_TIER2_NAME]).strip(),
        CONF_TIER2_ICON: str(user_input[CONF_TIER2_ICON]).strip(),
        CONF_TIER2_COUNT: tier2_count,
        CONF_UNITS_EARNED: _whole(user_input[CONF_UNITS_EARNED]),
        CONF_CURRENCY_SYMBOL: str(user_input[CONF_CURRENCY_SYMBOL]).strip(),
        CONF_INTEREST_RATE: round(float(user_input[CONF_INTEREST_RATE]), 2),
        CONF_INTEREST_EVERY_VALUE: _whole(user_input[CONF_INTEREST_EVERY_VALUE]),
        CONF_INTEREST_EVERY_UNIT: _unit(user_input[CONF_INTEREST_EVERY_UNIT]),
        CONF_INTEREST_CALC_VALUE: _whole(user_input[CONF_INTEREST_CALC_VALUE]),
        CONF_INTEREST_CALC_UNIT: _unit(user_input[CONF_INTEREST_CALC_UNIT]),
        CONF_DAILY_INTEREST_PERCENT: int(round(float(user_input[CONF_INTEREST_RATE]))),
        CONF_TICKS_PER_STAR: tier1_count,
        CONF_STARS_PER_POUND: tier2_count,
    }


def _apply_person(hass, settings: dict[str, Any]) -> dict[str, str]:
    """Use the linked person's name. Report an error when that person is missing."""
    person_id = settings.get(CONF_PERSON) or ""
    if not person_id:
        return {}
    name = linked_person_name(hass, person_id)
    if not name:
        return {CONF_PERSON: "person_missing"}
    settings[CONF_NAME] = name
    return {}


def _entry_label(hass, entry) -> str:
    data = entry.options or entry.data
    linked = linked_person_name(hass, stored_person_id(data))
    return linked or str(data.get(CONF_NAME) or entry.title)


def _person_taken(hass, person_id: str, ignore_entry_id: str | None = None) -> bool:
    if not person_id:
        return False
    for entry in hass.config_entries.async_entries(DOMAIN):
        if ignore_entry_id and entry.entry_id == ignore_entry_id:
            continue
        if stored_person_id(entry.options or entry.data) == person_id:
            return True
    return False


def _icon_ok(icon: str) -> bool:
    return ":" in icon and " " not in icon


def _validate_settings(settings: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not settings[CONF_NAME]:
        errors[CONF_NAME] = "name_required"
    if not settings[CONF_TIER1_NAME]:
        errors[CONF_TIER1_NAME] = "tier_name_required"
    elif len(settings[CONF_TIER1_NAME]) > 24:
        errors[CONF_TIER1_NAME] = "tier_name_too_long"
    if not settings[CONF_TIER2_NAME]:
        errors[CONF_TIER2_NAME] = "tier_name_required"
    elif len(settings[CONF_TIER2_NAME]) > 24:
        errors[CONF_TIER2_NAME] = "tier_name_too_long"
    if not _icon_ok(settings[CONF_TIER1_ICON]):
        errors[CONF_TIER1_ICON] = "icon_invalid"
    if not _icon_ok(settings[CONF_TIER2_ICON]):
        errors[CONF_TIER2_ICON] = "icon_invalid"
    symbol = settings[CONF_CURRENCY_SYMBOL]
    if not symbol or len(symbol) > 4:
        errors[CONF_CURRENCY_SYMBOL] = "currency_too_long"
    return errors


def _clean_reward(
    user_input: dict[str, Any], reward_id: str | None = None
) -> dict[str, Any]:
    return {
        "id": reward_id or uuid4().hex[:8],
        CONF_DESCRIPTION: str(user_input[CONF_DESCRIPTION]).strip(),
        CONF_COST: _whole(user_input[CONF_COST]),
        CONF_ICON: str(user_input[CONF_ICON]).strip(),
    }


def _validate_reward(reward: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not reward[CONF_DESCRIPTION]:
        errors[CONF_DESCRIPTION] = "description_required"
    if ":" not in reward[CONF_ICON] or " " in reward[CONF_ICON]:
        errors[CONF_ICON] = "icon_invalid"
    return errors


def _reward_summary(rewards: list[dict[str, Any]]) -> str:
    if not rewards:
        return "None yet"
    return ", ".join(
        f"{reward[CONF_DESCRIPTION]} ({reward[CONF_COST]})" for reward in rewards
    )


class RewardsTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add one child."""

    VERSION = 1

    def __init__(self) -> None:
        """Start with no rewards."""
        self._settings: dict[str, Any] = {}
        self._rewards: list[dict[str, Any]] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> RewardsTrackerOptionsFlow:
        """Return the configure flow."""
        return RewardsTrackerOptionsFlow()

    def _name_taken(self, name: str, ignore_entry_id: str | None = None) -> bool:
        needle = name.casefold()
        for entry in self._async_current_entries():
            if ignore_entry_id and entry.entry_id == ignore_entry_id:
                continue
            existing = _entry_label(self.hass, entry)
            if str(existing).casefold() == needle:
                return True
        return False

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Collect the child's name and rules."""
        errors: dict[str, str] = {}
        defaults = dict(user_input or {})
        if user_input is not None:
            self._settings = _clean_settings(user_input)
            defaults = self._settings
            errors = _apply_person(self.hass, self._settings)
            errors.update(_validate_settings(self._settings))
            if not errors and self._name_taken(self._settings[CONF_NAME]):
                errors[CONF_NAME] = "name_used"
            if not errors and _person_taken(self.hass, self._settings[CONF_PERSON]):
                errors[CONF_PERSON] = "person_used"
            if not errors:
                return await self.async_step_rewards_menu()

        return self.async_show_form(
            step_id="user",
            data_schema=_settings_schema(defaults),
            errors=errors,
        )

    async def async_step_rewards_menu(self, user_input: dict[str, Any] | None = None):
        """Add spend options, then create the child."""
        return self.async_show_menu(
            step_id="rewards_menu",
            menu_options=["add_reward", "finish"],
            description_placeholders={"rewards": _reward_summary(self._rewards)},
        )

    async def async_step_add_reward(self, user_input: dict[str, Any] | None = None):
        """Append one spend option."""
        errors: dict[str, str] = {}
        first = not self._rewards
        defaults = {
            CONF_DESCRIPTION: DEFAULT_REWARD_DESCRIPTION if first else "",
            CONF_COST: DEFAULT_REWARD_COST if first else 1,
            CONF_ICON: DEFAULT_REWARD_ICON if first else "mdi:gift",
        }
        if user_input is not None:
            reward = _clean_reward(user_input)
            errors = _validate_reward(reward)
            defaults = reward
            if not errors:
                self._rewards.append(reward)
                return await self.async_step_rewards_menu()

        return self.async_show_form(
            step_id="add_reward",
            data_schema=_reward_schema(defaults, include_delete=False),
            errors=errors,
        )

    async def async_step_finish(self, user_input: dict[str, Any] | None = None):
        """Create the config entry."""
        await self.async_set_unique_id(uuid4().hex)
        self._settings[CONF_REWARDS] = self._rewards
        return self.async_create_entry(title=self._settings[CONF_NAME], data=self._settings)


class RewardsTrackerOptionsFlow(OptionsFlow):
    """Change rules, spend options, or correct balances."""

    def __init__(self) -> None:
        """Keep edited rewards on the flow until they are saved."""
        super().__init__()
        self._rewards: list[dict[str, Any]] | None = None
        self._edit_id: str | None = None

    def _stored_options(self) -> dict[str, Any]:
        entry = self.config_entry
        return dict(entry.options or entry.data)

    def _reward_list(self) -> list[dict[str, Any]]:
        if self._rewards is None:
            self._rewards = [dict(reward) for reward in self._stored_options().get(CONF_REWARDS, [])]
        return self._rewards

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Choose what to change."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["settings", "rewards", "balances"],
        )

    async def async_step_settings(self, user_input: dict[str, Any] | None = None):
        """Update rules and the currency symbol."""
        errors: dict[str, str] = {}
        current = self._stored_options()
        defaults = dict(user_input or current)
        if user_input is not None:
            settings = _clean_settings(user_input)
            defaults = settings
            errors = _apply_person(self.hass, settings)
            errors.update(_validate_settings(settings))
            if not errors and self._name_taken(settings[CONF_NAME]):
                errors[CONF_NAME] = "name_used"
            if not errors and _person_taken(
                self.hass, settings[CONF_PERSON], self.config_entry.entry_id
            ):
                errors[CONF_PERSON] = "person_used"
            if not errors:
                updated = dict(current)
                updated.update(settings)
                return self.async_create_entry(title=settings[CONF_NAME], data=updated)

        return self.async_show_form(
            step_id="settings",
            data_schema=_settings_schema(defaults),
            errors=errors,
        )

    def _name_taken(self, name: str) -> bool:
        needle = name.casefold()
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.entry_id == self.config_entry.entry_id:
                continue
            existing = _entry_label(self.hass, entry)
            if str(existing).casefold() == needle:
                return True
        return False

    async def async_step_rewards(self, user_input: dict[str, Any] | None = None):
        """Pick a spend option to edit, add one, or save."""
        rewards = self._reward_list()
        if user_input is not None:
            choice = user_input["choice"]
            if choice == _ADD:
                return await self.async_step_add_reward()
            if choice == _DONE:
                updated = self._stored_options()
                updated[CONF_REWARDS] = rewards
                return self.async_create_entry(title=self.config_entry.title, data=updated)
            self._edit_id = choice
            return await self.async_step_edit_reward()

        options = [
            {
                "label": f"{reward[CONF_DESCRIPTION]} ({reward[CONF_COST]})",
                "value": reward["id"],
            }
            for reward in rewards
        ]
        options.append({"label": "Add a way to spend", "value": _ADD})
        options.append({"label": "Done", "value": _DONE})
        return self.async_show_form(
            step_id="rewards",
            data_schema=vol.Schema(
                {
                    vol.Required("choice", default=_DONE): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
            description_placeholders={"rewards": _reward_summary(rewards)},
        )

    async def async_step_add_reward(self, user_input: dict[str, Any] | None = None):
        """Add a spend option during configure."""
        errors: dict[str, str] = {}
        defaults = {
            CONF_DESCRIPTION: "",
            CONF_COST: 1,
            CONF_ICON: "mdi:gift",
        }
        if user_input is not None:
            reward = _clean_reward(user_input)
            errors = _validate_reward(reward)
            defaults = reward
            if not errors:
                self._reward_list().append(reward)
                return await self.async_step_rewards()

        return self.async_show_form(
            step_id="add_reward",
            data_schema=_reward_schema(defaults, include_delete=False),
            errors=errors,
        )

    async def async_step_edit_reward(self, user_input: dict[str, Any] | None = None):
        """Change or remove one spend option."""
        rewards = self._reward_list()
        current = next(
            (reward for reward in rewards if reward["id"] == self._edit_id), None
        )
        if current is None:
            return await self.async_step_rewards()

        errors: dict[str, str] = {}
        defaults: dict[str, Any] = dict(current)
        if user_input is not None:
            if user_input.get(CONF_DELETE):
                self._rewards = [reward for reward in rewards if reward["id"] != current["id"]]
                return await self.async_step_rewards()
            reward = _clean_reward(user_input, current["id"])
            errors = _validate_reward(reward)
            defaults = {**reward, CONF_DELETE: False}
            if not errors:
                self._rewards = [
                    reward if item["id"] == current["id"] else item for item in rewards
                ]
                return await self.async_step_rewards()

        return self.async_show_form(
            step_id="edit_reward",
            data_schema=_reward_schema(defaults, include_delete=True),
            errors=errors,
        )

    async def async_step_balances(self, user_input: dict[str, Any] | None = None):
        """Correct the five balances. Thresholds are applied on save."""
        tracker = async_get_tracker(self.hass, self.config_entry.entry_id)
        pot = tracker.pot
        errors: dict[str, str] = {}
        defaults = {
            CONF_TICKS: pot.ticks,
            CONF_STARS: pot.stars,
            CONF_BALANCE: pot.balance,
            CONF_SAVINGS: pot.savings,
            CONF_INTEREST_PENCE: pot.interest_pence,
        }
        if user_input is not None:
            defaults = user_input
            try:
                await tracker.async_set_balances(
                    _whole(user_input[CONF_TICKS]),
                    _whole(user_input[CONF_STARS]),
                    _whole(user_input[CONF_BALANCE]),
                    _whole(user_input[CONF_SAVINGS]),
                    _whole(user_input[CONF_INTEREST_PENCE]),
                )
            except (TypeError, ValueError, KeyError):
                errors["base"] = "balances_invalid"
            else:
                return self.async_create_entry(
                    title=self.config_entry.title, data=self._stored_options()
                )

        return self.async_show_form(
            step_id="balances",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TICKS, default=defaults[CONF_TICKS]): _number(0, 10000),
                    vol.Required(CONF_STARS, default=defaults[CONF_STARS]): _number(0, 10000),
                    vol.Required(CONF_BALANCE, default=defaults[CONF_BALANCE]): _number(0, 100000),
                    vol.Required(CONF_SAVINGS, default=defaults[CONF_SAVINGS]): _number(0, 100000),
                    vol.Required(
                        CONF_INTEREST_PENCE, default=defaults[CONF_INTEREST_PENCE]
                    ): _number(0, 99),
                }
            ),
            errors=errors,
        )
