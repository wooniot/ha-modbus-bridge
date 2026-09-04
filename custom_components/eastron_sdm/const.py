"""Constants for the Eastron SDM Energy Meters integration."""
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
# Victron Energy meters - these are Carlo Gavazzi devices sold under a
# Victron model name/firmware (ET112 = Carlo Gavazzi EM111, ET340 =
# Carlo Gavazzi EM340, EM540 = Carlo Gavazzi EM530/EM540). Different
# manufacturer/protocol family from the Eastron SDM meters above (see
# registers.py: plain scaled integers instead of IEEE754 floats), but
# supported by the same gateway/coordinator machinery.
MODEL_ET112 = "et112"
MODEL_ET340 = "et340"
MODEL_EM540 = "em540"
# Chint DTSU666 - three phase meter, popular as the grid/CT meter for
# solar inverters/EV chargers (Deye, Growatt, Sofar, Huawei, ...).
# Same IEEE754-float register encoding as the Eastron SDM family, but
# its registers are Modbus *holding* registers (function 03h) rather
# than *input* registers (function 04h) - see HOLDING_REGISTER_MODELS
# below and registers.py.
MODEL_DTSU666 = "dtsu666"
MODELS = [
    MODEL_SDM230,
    MODEL_SDM630,
    MODEL_SDM120,
    MODEL_SDM72V2,
    MODEL_ET112,
    MODEL_ET340,
    MODEL_EM540,
    MODEL_DTSU666,
]

# Manufacturer shown on each meter's Device page, keyed by model - used
# by sensor.py. Every model not listed here defaults to "Eastron".
MANUFACTURERS = {
    MODEL_ET112: "Victron Energy",
    MODEL_ET340: "Victron Energy",
    MODEL_EM540: "Victron Energy",
    MODEL_DTSU666: "Chint",
}

# Models whose registers must be read with Modbus function 03h ("read
# holding registers") instead of the 04h ("read input registers") used
# by every other supported model - see coordinator.py.
HOLDING_REGISTER_MODELS = {MODEL_DTSU666}

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

# Eastron devices (per the official Modbus protocol docs for both the
# SDM230 and SDM630) refuse a single transaction that spans more than
# 40 parameters (=80 16-bit registers). We stay comfortably under that
# so a request never gets rejected with an exception response.
MAX_REGISTERS_PER_READ = 80
# Registers separated by more than this many unused registers are read
# in separate requests, so we don't waste a Modbus transaction reading
# large stretches of unused register space.
MAX_REGISTER_GAP = 8
