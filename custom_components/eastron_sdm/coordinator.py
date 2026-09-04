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
        self.unit_id: int = subentry.data[CONF_UNIT_ID]
        self.model: str = subentry.data[CONF_MODEL]
        # NB: we deliberately do NOT cache a per-meter client here.
        # After a forced gateway reconnect the cached clients are
        # replaced, so every poll fetches its client fresh via
        # ``self.gateway.client_for()`` - that way a reconnect triggered
        # by one meter is instantly picked up by all others on the bus.
        # Full register map - sensor.py creates one entity per register
        # from this list so a disabled entity can always be re-enabled
        # later. Only the *polled* set (self.blocks, below) is filtered.
        self.registers: list[RegisterDefinition] = REGISTER_MAP[self.model]
        self.blocks: list[ReadBlock] = build_read_blocks(
            self._active_registers(hass), MAX_REGISTERS_PER_READ, MAX_REGISTER_GAP
        )
        self._registry_unsub: Callable[[], None] | None = None

        scan_interval = subentry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

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
            # Fetch the client fresh each poll (see __init__): after a
            # reconnect this returns a client bound to the new
            # connection.
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
                    # tmodbus has its own ~10s per-request timeout; this
                    # outer guard sits above it and catches the case
                    # where a request hangs entirely (wedged gateway).
                    async with asyncio.timeout(MODBUS_READ_TIMEOUT):
                        raw = await read(
                            start_address=block.start_address, quantity=block.quantity
                        )
                except asyncio.TimeoutError as err:
                    # The read hung past tmodbus' own timeout: the gateway
                    # is wedged. Force the shared connection to be rebuilt
                    # for every meter on this bus. We still hold the lock,
                    # so no other request is in flight during the swap.
                    # This poll fails; the next poll of any meter cleanly
                    # picks up the fresh connection.
                    _LOGGER.warning(
                        "Read of registers %s-%s from unit %s timed out "
                        "after %ss - reconnecting gateway",
                        block.start_address,
                        block.start_address + block.quantity,
                        self.unit_id,
                        MODBUS_READ_TIMEOUT,
                    )
                    try:
                        await self.gateway.reconnect()
                    except Exception:  # noqa: BLE001
                        _LOGGER.exception("Gateway reconnect failed")
                    raise UpdateFailed(
                        f"Read of registers {block.start_address}-"
                        f"{block.start_address + block.quantity} from unit "
                        f"{self.unit_id} timed out after {MODBUS_READ_TIMEOUT}s"
                    ) from err
                except Exception as err:  # noqa: BLE001
                    # A protocol/decode-level error (e.g. an Eastron
                    # exception response) - surface it without tearing
                    # down the whole bus, exactly as before.
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
