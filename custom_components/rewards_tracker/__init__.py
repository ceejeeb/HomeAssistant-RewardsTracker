"""Rewards Tracker integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_NAME, DOMAIN, PLATFORMS
from .frontend import JSModuleRegistration
from .tracker import ChildTracker, settings_from_entry

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Serve the card and prepare storage for child entries."""
    hass.data.setdefault(DOMAIN, {})
    await JSModuleRegistration(hass).async_register()
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one child."""
    hass.data.setdefault(DOMAIN, {})
    settings = settings_from_entry(entry)
    tracker = ChildTracker(hass, entry)
    await tracker.async_load()
    await tracker.async_apply_due_interest()
    tracker.async_schedule_interest()
    hass.data[DOMAIN][entry.entry_id] = tracker

    device_name = str(settings.get(CONF_NAME) or entry.title)
    if entry.title != device_name:
        hass.config_entries.async_update_entry(entry, title=device_name)
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    if device is None:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="Rewards Tracker",
            model="Child",
        )
    elif device.name_by_user is None and device.name != device_name:
        device_registry.async_update_device(device.id, name=device_name)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    _LOGGER.debug("Rewards Tracker ready for %s", tracker.name)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload one child."""
    tracker: ChildTracker | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if tracker is not None:
        await tracker.async_close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after the Configure screen saves."""
    await hass.config_entries.async_reload(entry.entry_id)
