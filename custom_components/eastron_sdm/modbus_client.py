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
import time
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
    MIN_SECONDS_BETWEEN_RECREATES,
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
    connection_data: dict[str, Any]
    refcount: int = 0
    _unit_clients: dict[int, Any] = None  # type: ignore[assignment]
    # Monotonic time of the last recreate() on this shared gateway (by
    # any meter on it), or None if it has never been recycled. Used by
    # should_recreate_now() to stop several coordinators thrashing the
    # same connection back-to-back - see MIN_SECONDS_BETWEEN_RECREATES.
    _last_recreate: float | None = None

    def __post_init__(self) -> None:
        if self._unit_clients is None:
            self._unit_clients = {}

    def client_for(self, unit_id: int) -> Any:
        client = self._unit_clients.get(unit_id)
        if client is None:
            client = self.base_client.for_unit_id(unit_id)
            self._unit_clients[unit_id] = client
        return client

    def should_recreate_now(self) -> bool:
        """Whether a (proactive or reactive) recreate is allowed right
        now, or whether another meter on this gateway recycled the
        connection too recently to tear it down again.

        A freshly reopened TCP session needs a moment to prove itself
        before being torn down a second time; without this throttle,
        6 coordinators all seeing the same slowness in the same poll
        cycle would reconnect 6 times in a row. Callers should be
        holding ``lock`` so the check and the recreate() that follows
        are atomic for this bus.
        """
        if self._last_recreate is None:
            return True
        return (time.monotonic() - self._last_recreate) >= MIN_SECONDS_BETWEEN_RECREATES

    async def recreate(self, reason: str | None = None) -> None:
        """Force-close and reopen the underlying connection.

        Call this when a read has stalled well past
        ``MODBUS_READ_TIMEOUT``, or when the proactive watchdog sees a
        meter's successful-poll cadence creep far past its
        scan_interval - a healthy gateway never behaves that way, so
        the shared connection is assumed to be stuck/stale and
        unlikely to recover on its own (this has been observed in
        practice: response times climb gradually over hours of uptime
        with no error ever being raised, until a read effectively
        hangs). Callers must be holding ``lock`` while calling this,
        so no other meter on this bus starts a request against the
        half-replaced connection.

        ``reason`` is logged so the trigger (hard read timeout vs.
        proactive watchdog) is visible. Existing per-unit clients
        (``_unit_clients``) are tied to the old connection's transport,
        so they're dropped here; callers must fetch a fresh one via
        ``client_for()`` afterwards.
        """
        # Stamp first: even if the reopen below throws, we don't want a
        # pile-up of meters all retrying a recreate on the same tick.
        self._last_recreate = time.monotonic()
        _LOGGER.warning(
            "Eastron SDM gateway %s: forcing a reconnect (%s)",
            gateway_key(self.connection_data),
            reason or "read timed out, connection looks stuck",
        )
        try:
            await self.base_client.__aexit__(None, None, None)
        except Exception:  # noqa: BLE001
            _LOGGER.debug(
                "Error while closing stuck Eastron SDM gateway connection (ignored, "
                "reconnecting anyway)",
                exc_info=True,
            )
        self.base_client = await _create_base_client(self.connection_data)
        await self.base_client.__aenter__()
        self._unit_clients.clear()


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
        handle = GatewayHandle(base_client=base_client, lock=asyncio.Lock(), connection_data=data)
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
