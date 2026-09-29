"""Sensors for one child's reward pots."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import voluptuous as vol

from .const import CONF_REWARD_ID, DOMAIN
from .tracker import ChildTracker

_LOGGER = logging.getLogger(__name__)

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="ticks",
        name="Ticks",
        icon="mdi:check",
    ),
    SensorEntityDescription(
        key="stars",
        name="Stars",
        icon="mdi:star",
    ),
    SensorEntityDescription(
        key="balance",
        name="Money",
        icon="mdi:wallet",
    ),
    SensorEntityDescription(
        key="savings",
        name="Savings",
        icon="mdi:piggy-bank",
    ),
    SensorEntityDescription(
        key="interest_pence",
        name="Interest",
        icon="mdi:chart-line",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the child's sensors and register actions once."""
    tracker: ChildTracker = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(RewardSensor(tracker, description) for description in SENSORS)

    platform = entity_platform.async_get_current_platform()
    if getattr(platform, "_rewards_tracker_services", False):
        return
    platform._rewards_tracker_services = True  # noqa: SLF001
    platform.async_register_entity_service("award_tick", {}, "async_award_tick")
    platform.async_register_entity_service("deposit", {}, "async_deposit")
    platform.async_register_entity_service("withdraw", {}, "async_withdraw")
    platform.async_register_entity_service(
        "spend",
        {vol.Required(CONF_REWARD_ID): str},
        "async_spend",
    )
    _LOGGER.debug("Registered Rewards Tracker services")


class RewardSensor(SensorEntity):
    """One number from a child's pot. Every sensor can run the actions."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(
        self, tracker: ChildTracker, description: SensorEntityDescription
    ) -> None:
        """Bind this sensor to one balance."""
        self.entity_description = description
        self._tracker = tracker
        self._attr_unique_id = f"{tracker.entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, tracker.entry.entry_id)},
            name=tracker.name,
            manufacturer="Rewards Tracker",
            model="Child",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to pot changes."""
        await super().async_added_to_hass()
        self.async_on_remove(self._tracker.add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> int:
        """Return the balance this sensor represents."""
        pot = self._tracker.pot
        return {
            "ticks": pot.ticks,
            "stars": pot.stars,
            "balance": pot.balance,
            "savings": pot.savings,
            "interest_pence": pot.interest_pence,
        }[self.entity_description.key]

    @property
    def extra_state_attributes(self) -> dict:
        """Expose the whole pot so the card can bind to any of the sensors."""
        pot = self._tracker.pot
        rules = self._tracker.rules
        last_paid = (
            pot.interest_last_paid.isoformat() if pot.interest_last_paid else None
        )
        return {
            "role": self.entity_description.key,
            "child_name": self._tracker.name,
            "ticks": pot.ticks,
            "stars": pot.stars,
            "balance": pot.balance,
            "savings": pot.savings,
            "interest_pence": pot.interest_pence,
            "ticks_per_star": rules.ticks_per_star,
            "stars_per_pound": rules.stars_per_pound,
            "daily_interest_percent": rules.daily_interest_percent,
            "currency_symbol": self._tracker.currency,
            "interest_last_paid": last_paid,
            "rewards": self._tracker.rewards,
        }

    async def async_award_tick(self) -> None:
        """Service: award one tick."""
        await self._tracker.async_award_tick()

    async def async_deposit(self) -> None:
        """Service: move one unit into savings."""
        if not await self._tracker.async_deposit():
            raise ServiceValidationError("There isn't enough money to deposit.")

    async def async_withdraw(self) -> None:
        """Service: move one unit back from savings."""
        if not await self._tracker.async_withdraw():
            raise ServiceValidationError("There aren't enough savings to withdraw.")

    async def async_spend(self, reward_id: str) -> None:
        """Service: pay for one configured reward."""
        reward = self._tracker.find_reward(reward_id)
        if reward is None:
            raise ServiceValidationError("That way to spend is no longer on this child.")
        if not await self._tracker.async_spend(int(reward["cost"])):
            raise ServiceValidationError("There isn't enough money for that.")
