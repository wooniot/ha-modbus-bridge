"""DataUpdateCoordinator for a single Eastron SDM meter (config subentry)."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_MODEL,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DEFAULT_SCAN_INTERVAL,
    MAX_REGISTER_GAP,
    MAX_REGISTERS_PER_READ,
)
from .modbus_client import GatewayHandle
from .registers import REGISTER_MAP, ReadBlock, RegisterDefinition, build_read_blocks, decode_float32

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
        self.client = gateway.client_for(self.unit_id)
        self.registers: list[RegisterDefinition] = REGISTER_MAP[self.model]
        self.blocks: list[ReadBlock] = build_read_blocks(
            self.registers, MAX_REGISTERS_PER_READ, MAX_REGISTER_GAP
        )

        scan_interval = subentry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=f"Eastron {self.model.upper()} ({subentry.title})",
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[str, float]:
        data: dict[str, float] = {}
        # Serialise all traffic for this gateway: RS485 is half-duplex,
        # and other meters on the same bus share this lock too.
        async with self.gateway.lock:
            for block in self.blocks:
                try:
                    raw = await self.client.read_input_registers(
                        start_address=block.start_address, quantity=block.quantity
                    )
                except Exception as err:  # noqa: BLE001
                    raise UpdateFailed(
                        f"Failed reading registers {block.start_address}-"
                        f"{block.start_address + block.quantity} from unit "
                        f"{self.unit_id}: {err}"
                    ) from err

                for reg in block.registers:
                    offset = reg.address - block.start_address
                    try:
                        data[reg.key] = decode_float32(raw, offset)
                    except (IndexError, ValueError, OverflowError):
                        _LOGGER.debug(
                            "Could not decode register %s (offset %s) for unit %s",
                            reg.key, offset, self.unit_id,
                        )
        return data
