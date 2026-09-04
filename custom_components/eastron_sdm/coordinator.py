"""DataUpdateCoordinator for a single Eastron SDM meter (config subentry)."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Callable

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_entity_registry_updated_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_MODEL,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    HOLDING_REGISTER_MODELS,
    MAX_REGISTER_GAP,
    MAX_REGISTERS_PER_READ,
    MODBUS_READ_TIMEOUT,
)
from .modbus_client import GatewayHandle
from .registers import REGISTER_MAP, ReadBlock, RegisterDefinition, build_read_blocks, decode_register

_LOGGER = logging.getLogger(__name__)


class EastronCoordinator(DataUpdateCoordinator[dict[str, float]]):
    """Polls one Eastron meter (one unit_id on a shared gateway) and
    makes its decoded register values available to sensor entities.

    One instance per "meter" config subentry; several instances share
    the same underlying gateway connection (and its lock) via the
    ``gateway`` handle they're given.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        gateway: GatewayHandle,
    ) -> None:
        self.entry = entry
        self.subentry = subentry
        self.gateway = gateway
        # HA's NumberSelector always hands back a float (e.g. 1.0), even
        # with step=1, so a unit_id coming from the config flow is stored
        # as a float. tmodbus packs the unit id straight into the Modbus
        # frame with struct.pack(">...B", ...), which rejects a float with
        # "required argument is not an integer" - so coerce to int here.
        # Doing it in the coordinator (not only in the config flow) also
        # repairs meters that were already stored with a float unit_id,
        # without the user having to remove and re-add them.
        self.unit_id: int = int(subentry.data[CONF_UNIT_ID])
        self.model: str = subentry.data[CONF_MODEL]
        # Not cached on self: fetched fresh from the gateway on every
        # poll (see _async_update_data) so that a reconnect triggered
        # by *any* meter on this bus - not just this one - is picked
        # up immediately, instead of this coordinator being left
        # holding a client bound to a connection that's already been
        # replaced.
        # Full register map - sensor.py creates one entity per register
        # from this list so a disabled entity can always be re-enabled
        # later. Only the *polled* set (self.blocks, below) is filtered.
        self.registers: list[RegisterDefinition] = REGISTER_MAP[self.model]
        self.blocks: list[ReadBlock] = build_read_blocks(
            self._active_registers(hass), MAX_REGISTERS_PER_READ, MAX_REGISTER_GAP
        )
        self._registry_unsub: Callable[[], None] | None = None

        # Also float-from-NumberSelector; timedelta tolerates a float, but
        # keep it an int for tidy logs and consistency with unit_id above.
        scan_interval = int(subentry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

        super().__init__(
            hass,
            _LOGGER,
            name=f"Eastron {self.model.upper()} ({subentry.title})",
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )

    def _unique_id(self, register: RegisterDefinition) -> str:
        return f"{self.subentry.subentry_id}_{register.key}"

    def _active_registers(self, hass: HomeAssistant) -> list[RegisterDefinition]:
        """Registers whose sensor entity is (or will be) enabled.

        RS485 is a shared, half-duplex bus: every register this
        coordinator reads is traffic every *other* meter on the same
        gateway has to wait behind. Skipping a register whose entity
        the user disabled keeps that traffic off the bus instead of
        just hiding the resulting entity.

        For a register whose entity doesn't exist in the registry yet
        (first setup, before sensor.py has run), this falls back to
        the same ``entity_registry_enabled_default`` that entity will
        be created with a moment later - so a fresh install still
        polls exactly what it's about to expose.
        """
        registry = er.async_get(hass)
        active: list[RegisterDefinition] = []
        for register in self.registers:
            entity_id = registry.async_get_entity_id("sensor", DOMAIN, self._unique_id(register))
            if entity_id is None:
                enabled = register.entity_registry_enabled_default
            else:
                entry = registry.async_get(entity_id)
                enabled = entry is None or entry.disabled_by is None
            if enabled:
                active.append(register)
        return active

    def setup_registry_listener(self, hass: HomeAssistant) -> Callable[[], None]:
        """Start watching this meter's entities for enable/disable
        changes, so toggling one in the UI takes effect on the next
        poll without requiring a reload or restart.

        Must be called after the sensor platform has been set up (the
        entities need to already exist in the registry to be
        trackable). Returns an unsub callable.
        """
        registry = er.async_get(hass)
        entity_ids = [
            entity_id
            for register in self.registers
            if (entity_id := registry.async_get_entity_id("sensor", DOMAIN, self._unique_id(register)))
        ]

        @callback
        def _handle_registry_update(event: Event) -> None:
            hass.async_create_task(self._async_refresh_blocks(hass))

        self._registry_unsub = async_track_entity_registry_updated_event(
            hass, entity_ids, _handle_registry_update
        )
        return self._registry_unsub

    async def _async_refresh_blocks(self, hass: HomeAssistant) -> None:
        new_blocks = build_read_blocks(
            self._active_registers(hass), MAX_REGISTERS_PER_READ, MAX_REGISTER_GAP
        )
        if new_blocks == self.blocks:
            return
        _LOGGER.debug(
            "Eastron SDM %s: register selection changed, now polling %d block(s)",
            self.subentry.title, len(new_blocks),
        )
        self.blocks = new_blocks
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, float]:
        data: dict[str, float] = {}
        # Serialise all traffic for this gateway: RS485 is half-duplex,
        # and other meters on the same bus share this lock too.
        async with self.gateway.lock:
            # Fetched fresh (not cached on self) so a reconnect done by
            # another meter's coordinator earlier in this poll cycle -
            # or by this one, below - is always picked up.
            client = self.gateway.client_for(self.unit_id)
            # Almost every supported model exposes its measurements as
            # Modbus *input* registers (function 04h); a few (e.g. the
            # Chint DTSU666) use *holding* registers (03h) instead -
            # see HOLDING_REGISTER_MODELS.
            read = (
                client.read_holding_registers
                if self.model in HOLDING_REGISTER_MODELS
                else client.read_input_registers
            )
            for block in self.blocks:
                try:
                    raw = await asyncio.wait_for(
                        read(start_address=block.start_address, quantity=block.quantity),
                        timeout=MODBUS_READ_TIMEOUT,
                    )
                except TimeoutError as err:
                    # A single read has no business taking this long -
                    # the shared connection is presumed stuck. Force a
                    # reconnect (while still holding the lock, so no
                    # other meter on this bus races us) and fail *this*
                    # poll cleanly; the next scheduled poll - for this
                    # meter or any other on the same gateway - gets a
                    # fresh connection to try again.
                    await self.gateway.recreate()
                    raise UpdateFailed(
                        f"Timed out after {MODBUS_READ_TIMEOUT}s reading registers "
                        f"{block.start_address}-{block.start_address + block.quantity} from "
                        f"unit {self.unit_id}; the gateway connection was reset and will be "
                        "retried on the next poll"
                    ) from err
                except Exception as err:  # noqa: BLE001
                    raise UpdateFailed(
                        f"Failed reading registers {block.start_address}-"
                        f"{block.start_address + block.quantity} from unit "
                        f"{self.unit_id}: {err}"
                    ) from err

                for reg in block.registers:
                    offset = reg.address - block.start_address
                    try:
                        data[reg.key] = decode_register(raw, offset, reg)
                    except (IndexError, ValueError, OverflowError):
                        _LOGGER.debug(
                            "Could not decode register %s (offset %s) for unit %s",
                            reg.key, offset, self.unit_id,
                        )
        return data
