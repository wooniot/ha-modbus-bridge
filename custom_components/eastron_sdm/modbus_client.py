"""Shared Modbus gateway/connection management.

Several Eastron meters can share one RS485 bus (daisy-chained) behind
a single TCP gateway (or a single local serial port). Modbus RTU is
half-duplex, so only one request may be in flight at a time for a
given physical bus - opening a separate TCP connection per meter
would either fail outright (many cheap RS485<->TCP gateways only
accept one client) or silently corrupt traffic.

This module keeps exactly one tmodbus client per physical gateway
(keyed on its connection parameters) and hands out lightweight
per-meter clients via ``AsyncModbusClient.for_unit_id()``, which share
the same underlying transport/connection. A lock serialises all
requests going out over one gateway.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_CONNECTION_TYPE,
    CONF_PARITY,
    CONF_STOPBITS,
    CONF_WAIT_BETWEEN_REQUESTS,
    CONNECTION_RTU_OVER_TCP,
    CONNECTION_SERIAL,
    CONNECTION_TCP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

GATEWAYS_KEY = "gateways"


def gateway_key(data: dict[str, Any]) -> tuple:
    """Build a hashable key identifying the physical gateway a config
    entry talks to, ignoring the per-meter unit_id."""
    conn_type = data[CONF_CONNECTION_TYPE]
    if conn_type == CONNECTION_SERIAL:
        return (
            conn_type,
            data["port"],
            data.get(CONF_BAUDRATE),
            data.get(CONF_PARITY),
            data.get(CONF_STOPBITS),
            data.get(CONF_BYTESIZE),
        )
    return (conn_type, data["host"], data.get("tcp_port"))


@dataclass
class GatewayHandle:
    """One shared connection to a physical Modbus gateway."""

    base_client: Any
    lock: asyncio.Lock
    data: dict[str, Any]
    refcount: int = 0
    _unit_clients: dict[int, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._unit_clients is None:
            self._unit_clients = {}

    def client_for(self, unit_id: int) -> Any:
        client = self._unit_clients.get(unit_id)
        if client is None:
            client = self.base_client.for_unit_id(unit_id)
            self._unit_clients[unit_id] = client
        return client

    async def reconnect(self) -> None:
        """Force-close the underlying gateway connection and build a
        fresh one.

        RS485 gateways (especially cheap RS485<->TCP bridges) can wedge
        after hours of continuous polling: the socket stays "open" but
        no reply ever comes back, so every meter behind it starts
        timing out. Tearing the connection down and rebuilding it fixes
        all meters on the bus at once, without a HA restart.

        Callers MUST hold ``self.lock`` while calling this (it is the
        same lock that serialises every request over this gateway), so
        no request is in flight against the old client while we swap it
        out. The cached per-unit clients are cleared as well: each
        meter fetches its client fresh via ``client_for()`` on its next
        poll and so transparently picks up the new connection.
        """
        _LOGGER.warning(
            "Eastron SDM gateway %s appears wedged - forcing reconnect",
            gateway_key(self.data),
        )
        try:
            await self.base_client.__aexit__(None, None, None)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Error closing wedged gateway connection", exc_info=True)
        # Drop stale per-unit clients before building the new base
        # client so no meter can keep talking to the dead connection.
        self._unit_clients.clear()
        self.base_client = await _create_base_client(self.data)
        await self.base_client.__aenter__()
        _LOGGER.info("Eastron SDM gateway %s reconnected", gateway_key(self.data))


async def _create_base_client(data: dict[str, Any]):
    """Create (but do not yet connect) the tmodbus client for a
    gateway, based on the connection_type stored in the config
    entry."""
    # Imported lazily so this module can be imported (e.g. for tests)
    # even before the tmodbus requirement has been installed.
    from tmodbus import (
        create_async_rtu_client,
        create_async_rtu_over_tcp_client,
        create_async_tcp_client,
    )

    conn_type = data[CONF_CONNECTION_TYPE]
    # unit_id here is only used to bootstrap the connection; every
    # meter gets its own client via for_unit_id() afterwards.
    bootstrap_unit_id = 1

    # Stored in the config entry as whole milliseconds (friendlier to
    # show in the UI); tmodbus wants seconds as a float.
    wait_between_requests = data.get(CONF_WAIT_BETWEEN_REQUESTS, 0) / 1000.0

    if conn_type == CONNECTION_TCP:
        return create_async_tcp_client(
            data["host"],
            data["tcp_port"],
            unit_id=bootstrap_unit_id,
            wait_between_requests=wait_between_requests,
        )
    if conn_type == CONNECTION_RTU_OVER_TCP:
        return create_async_rtu_over_tcp_client(
            data["host"],
            data["tcp_port"],
            unit_id=bootstrap_unit_id,
            wait_between_requests=wait_between_requests,
        )
    if conn_type == CONNECTION_SERIAL:
        return create_async_rtu_client(
            data["port"],
            unit_id=bootstrap_unit_id,
            baudrate=data.get(CONF_BAUDRATE),
            parity=data.get(CONF_PARITY),
            stopbits=data.get(CONF_STOPBITS),
            bytesize=data.get(CONF_BYTESIZE),
            wait_between_requests=wait_between_requests,
        )
    raise ValueError(f"Unknown connection_type: {conn_type}")


async def async_get_gateway(hass: HomeAssistant, data: dict[str, Any]) -> GatewayHandle:
    """Return the (possibly newly created & connected) GatewayHandle
    for the gateway described by ``data``, incrementing its refcount."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    gateways: dict[tuple, GatewayHandle] = domain_data.setdefault(GATEWAYS_KEY, {})

    key = gateway_key(data)
    handle = gateways.get(key)
    if handle is None:
        _LOGGER.debug("Opening new Eastron SDM gateway connection: %s", key)
        base_client = await _create_base_client(data)
        await base_client.__aenter__()
        handle = GatewayHandle(base_client=base_client, lock=asyncio.Lock(), data=data)
        gateways[key] = handle
    handle.refcount += 1
    return handle


async def async_release_gateway(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Release a reference to a gateway, closing the connection once
    the last meter using it is unloaded."""
    domain_data = hass.data.get(DOMAIN, {})
    gateways: dict[tuple, GatewayHandle] = domain_data.get(GATEWAYS_KEY, {})

    key = gateway_key(data)
    handle = gateways.get(key)
    if handle is None:
        return
    handle.refcount -= 1
    if handle.refcount <= 0:
        _LOGGER.debug("Closing Eastron SDM gateway connection: %s", key)
        try:
            await handle.base_client.__aexit__(None, None, None)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Error while closing Eastron SDM gateway connection")
        gateways.pop(key, None)
