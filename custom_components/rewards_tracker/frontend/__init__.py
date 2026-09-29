"""Register the bundled dashboard card."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from ..const import CARD_FILENAME, URL_BASE, VERSION

_LOGGER = logging.getLogger(__name__)
_MAX_ATTEMPTS = 12


class JSModuleRegistration:
    """Serve the card and add it to Lovelace resources in storage mode."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Keep the hass reference."""
        self.hass = hass
        self._attempts = 0

    async def async_register(self) -> None:
        """Register the static path, then the Lovelace resource when ready."""
        await self._async_register_path()
        lovelace = self.hass.data.get("lovelace")
        if lovelace is None:
            _LOGGER.warning(
                "Rewards Tracker could not register its card because Lovelace is not loaded"
            )
            return
        mode = getattr(lovelace, "mode", "storage")
        if mode != "storage":
            _LOGGER.warning(
                "Add %s/%s?v=%s as a Lovelace module resource. "
                "This dashboard is not using storage mode, so it was not added automatically",
                URL_BASE,
                CARD_FILENAME,
                VERSION,
            )
            return
        await self._async_wait_for_resources()

    async def _async_register_path(self) -> None:
        static_dir = Path(__file__).parent / "static"
        try:
            await self.hass.http.async_register_static_paths(
                [StaticPathConfig(URL_BASE, str(static_dir), False)]
            )
        except RuntimeError:
            _LOGGER.debug("Card path %s is already registered", URL_BASE)

    async def _async_wait_for_resources(self) -> None:
        async def _check(_now: Any) -> None:
            self._attempts += 1
            lovelace = self.hass.data.get("lovelace")
            resources = getattr(lovelace, "resources", None)
            if resources is not None and getattr(resources, "loaded", True):
                await self._async_register_module(resources)
                return
            if self._attempts >= _MAX_ATTEMPTS:
                _LOGGER.warning(
                    "Rewards Tracker gave up waiting to register its dashboard card"
                )
                return
            async_call_later(self.hass, 5, _check)

        await _check(None)

    async def _async_register_module(self, resources: Any) -> None:
        url = f"{URL_BASE}/{CARD_FILENAME}"
        versioned = f"{url}?v={VERSION}"
        for resource in resources.async_items():
            current = str(resource.get("url", ""))
            if current.split("?", 1)[0] != url:
                continue
            if current == versioned:
                return
            _LOGGER.info("Updating Rewards Tracker card to %s", VERSION)
            await resources.async_update_item(
                resource["id"],
                {"res_type": "module", "url": versioned},
            )
            return
        _LOGGER.info("Registering Rewards Tracker card %s", VERSION)
        await resources.async_create_item({"res_type": "module", "url": versioned})
