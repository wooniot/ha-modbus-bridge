"""Constants for the Eastron Modbus meters integration."""
from __future__ import annotations

DOMAIN = "eastron_sdm"

# --- Config entry keys -----------------------------------------------------
CONF_CONNECTION_TYPE = "connection_type"
CONF_UNIT_ID = "unit_id"
CONF_MODEL = "model"
CONF_SCAN_INTERVAL = "scan_interval"

# Serial-only config keys (connection_type == CONNECTION_SERIAL)
CONF_BAUDRATE = "baudrate"
CONF_PARITY = "parity"
CONF_STOPBITS = "stopbits"
CONF_BYTESIZE = "bytesize"

# Gateway-wide: minimum silence between two Modbus requests on the same
# bus, in milliseconds. tmodbus itself defaults this to 0 (no delay),
# but many cheap RS485 gateways/adapters need a short pause after a
# response before they're ready for the next request - HA's own
# built-in modbus integration defaults this to 30ms for serial links
# for the same reason (its "message_wait_milliseconds" option).
CONF_WAIT_BETWEEN_REQUESTS = "wait_between_requests_ms"

# --- Connection types --------------------------------------------------
# TCP: the gateway is a "real" Modbus TCP device (adds an MBAP header,
#      no CRC on the wire between HA and the gateway). Used by e.g.
#      Waveshare RS485-to-ETH(B) in "Modbus TCP" mode.
CONNECTION_TCP = "tcp"
# RTU-over-TCP: the gateway is a transparent serial-to-TCP bridge that
#      just forwards the raw RTU bytes (incl. CRC) over a TCP socket.
#      This is the mode used by most cheap RS485<->WiFi/LAN adapters,
#      e.g. Elfin EW11, USR-W610/TCP232, in their default "transparent"
#      mode. If you're not sure which one you have, start here.
CONNECTION_RTU_OVER_TCP = "rtu_over_tcp"
# Serial: a USB-RS485 adapter (or similar) plugged directly into the
#      machine running Home Assistant, e.g. /dev/ttyUSB0.
CONNECTION_SERIAL = "serial"

CONNECTION_TYPES = [CONNECTION_TCP, CONNECTION_RTU_OVER_TCP, CONNECTION_SERIAL]

DEFAULT_TCP_PORT = 502
DEFAULT_BAUDRATE = 9600
DEFAULT_PARITY = "N"  # N(one) / E(ven) / O(dd)
DEFAULT_STOPBITS = 1
DEFAULT_BYTESIZE = 8

PARITY_OPTIONS = ["N", "E", "O"]

# Defaults for CONF_WAIT_BETWEEN_REQUESTS, split by connection family:
# serial buses (and transparent RTU-over-TCP bridges, which are really
# a serial bus underneath) tend to need a bit more slack than a native
# Modbus TCP gateway that queues requests itself.
DEFAULT_WAIT_BETWEEN_REQUESTS_NETWORK = 20
DEFAULT_WAIT_BETWEEN_REQUESTS_SERIAL = 30

# --- Meter models ------------------------------------------------------
MODEL_SDM230 = "sdm230"
MODEL_SDM630 = "sdm630"
MODEL_SDM120 = "sdm120"
MODEL_SDM72V2 = "sdm72v2"
MODELS = [
    MODEL_SDM230,
    MODEL_SDM630,
    MODEL_SDM120,
    MODEL_SDM72V2,
]

# Manufacturer shown on each meter's Device page, keyed by model - used
# by sensor.py. Every model not listed here defaults to "Eastron".
MANUFACTURERS: dict[str, str] = {}

# Models whose registers must be read with Modbus function 03h ("read
# holding registers") instead of the 04h ("read input registers") used
# by every other supported model - see coordinator.py.
HOLDING_REGISTER_MODELS: set[str] = set()

# --- Subentries ------------------------------------------------------
# Each physical meter on the bus is a subentry of type "meter" under
# one parent config entry (the gateway/connection).
SUBENTRY_TYPE_METER = "meter"

# --- Polling -------------------------------------------------------------
DEFAULT_SCAN_INTERVAL = 30  # seconds

# Watchdog timeout for a single Modbus read (register block), in
# seconds. tmodbus applies its own ~10s per-transaction timeout
# internally, so this is set comfortably above that - it exists to
# catch a *stuck* shared connection (the TCP socket to the gateway
# going quietly stale after hours of uptime, with no error, just ever
# slower responses) rather than a normal single slow/lost response.
# When a read blows through this, the gateway connection is assumed
# unrecoverable and is force-closed and reopened - see
# GatewayHandle.recreate() in modbus_client.py.
MODBUS_READ_TIMEOUT = 15  # seconds

# --- Proactive reconnect watchdog (option 2 from the 2026-09-09 gateway
# degradation analysis) ----------------------------------------------------
# MODBUS_READ_TIMEOUT above only catches a read that is *itself* stuck for
# 15s. In practice the observed degradation is often milder than that: every
# individual read still completes (no error, no `unavailable`), but the
# gateway responds slower and slower, so the actual time between successful
# polls for a given meter creeps from ~5s up to 60-120s while nothing ever
# trips the hard per-read timeout - this was confirmed on 2026-10-06, where
# the gateway sat at a chronic ~55-90s cadence (vs. a configured 5s
# scan_interval) for at least several days without a single reconnect/
# timeout log line.
#
# To catch that case, each coordinator tracks when *it* last completed a
# poll successfully. If that is significantly longer ago than its own
# scan_interval, the shared gateway connection is proactively recycled
# before this read is even attempted, instead of waiting for a read to
# actually hang.
WATCHDOG_SCAN_INTERVAL_MULTIPLIER = 3
WATCHDOG_MIN_SECONDS = 30  # floor, so a very short scan_interval doesn't make this hair-triggered
# Shared across all meters on one gateway: once any coordinator forces a
# proactive or reactive recreate(), don't let another one force a second
# one within this many seconds - a fresh TCP session needs a moment to
# prove itself before being torn down again, and this avoids 6 coordinators
# thrashing the same connection back-to-back if the underlying slowness
# isn't fixed by reconnecting alone.
MIN_SECONDS_BETWEEN_RECREATES = 60

# Openen en sluiten van de gatewayverbinding gebeurt terwijl de gedeelde lock
# vastgehouden wordt: hangt dat, dan ligt de hele bus stil zonder dat
# MODBUS_READ_TIMEOUT daar iets tegen doet (een half bereikbare gateway laat
# een TCP-connect minutenlang hangen). Daarom een eigen, korte grens.
GATEWAY_CONNECT_TIMEOUT = 10  # seconden

# Eastron devices (per the official Modbus protocol docs for both the
# SDM230 and SDM630) refuse a single transaction that spans more than
# 40 parameters (=80 16-bit registers). We stay comfortably under that
# so a request never gets rejected with an exception response.
MAX_REGISTERS_PER_READ = 80
# Registers separated by more than this many unused registers are read
# in separate requests, so we don't waste a Modbus transaction reading
# large stretches of unused register space.
MAX_REGISTER_GAP = 8
