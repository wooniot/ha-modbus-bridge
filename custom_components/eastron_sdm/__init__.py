"""The Eastron SDM Energy Meters integration.

One config entry represents one physical gateway/RS485 connection.
Every meter on that bus is a "meter" config subentry underneath it, so
you configure the connection once and then add as many meters as you
like - either right away (looping in the initial setup wizard) or
later via the "+" button on the integration's entry.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import SUBENTRY_TYPE_METER
from .coordinator import EastronCoordinator
from .modbus_client import GatewayHandle, async_get_gateway, async_release_gateway

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass
class EastronRuntimeData:
    """Data attached to the config entry at runtime."""

    gateway: GatewayHandle
    # Keyed by subentry_id.
    coordinators: dict[str, EastronCoordinator] = field(default_factory=dict)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the gateway connection and one coordinator per configured
    meter subentry."""
    gateway = await async_get_gateway(hass, entry.data)

    coordinators: dict[str, EastronCoordinator] = {}
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_METER:
            continue
        coordinator = EastronCoordinator(hass, entry, subentry, gateway)
        await coordinator.async_config_entry_first_refresh()
        coordinators[subentry.subentry_id] = coordinator

    entry.runtime_data = EastronRuntimeData(gateway=gateway, coordinators=coordinators)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Only reachable now that the sensor platform above has created
    # each meter's entities, so they exist in the registry to track.
    for coordinator in coordinators.values():
        entry.async_on_unload(coordinator.setup_registry_listener(hass))

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a gateway entry (and all its meter subentries)."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await async_release_gateway(hass, entry.data)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change.

    Home Assistant already reloads the entry automatically whenever a
    "meter" subentry is added, edited or removed, so this only needs
    to cover entry-level option changes.
    """
    await hass.config_entries.async_reload(entry.entry_id)
