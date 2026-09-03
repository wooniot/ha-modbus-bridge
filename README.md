# Eastron SDM Energy Meters

**English** | [Nederlands](README.nl.md) | [Deutsch](README.de.md)

> Home Assistant custom integration for Eastron SDM230/SDM630 energy meters over Modbus (TCP, RTU-over-TCP, or local serial), with per-meter polling intervals for dashboards or fast zero-export/load-balancing use.

## What it does

This is a custom Home Assistant integration for Eastron SDM230 (single-phase) and SDM630 (three-phase) Modbus energy meters. It talks to your meter(s) over the Modbus protocol and exposes every reading as a native Home Assistant sensor - voltage, current, active/apparent/reactive power, power factor, frequency, import/export energy, THD%, demand values, and more - with the right device class, unit and long-term statistics support out of the box.

## What it offers

- Three connection types, chosen in the setup wizard: a transparent RS485-to-TCP gateway (e.g. Elfin EW11, USR-W610/TCP232), a native Modbus TCP gateway (e.g. Waveshare RS485-to-ETH in Modbus TCP mode), or a local USB-RS485 adapter plugged directly into the Home Assistant host.
- Multiple meters on one RS485 bus, one integration. One config entry represents the physical gateway/connection; every meter on that bus is added as a lightweight sub-device, either in a loop during initial setup or later via "+ Add device" - no need to re-enter the gateway settings each time.
- One shared, serialized connection per gateway. RS485 is half-duplex, so all meters on the same bus share a single persistent Modbus connection with a lock that guarantees only one request is ever in flight - safe by design even with several meters daisy-chained together.
- Efficient register reads. The full Eastron register map is grouped into as few Modbus transactions as possible per poll, respecting the manufacturer's 40-parameter/80-register limit per request.
- Per-meter polling interval, fully configurable (1-3600s, default 30s). Leave it at the default for normal monitoring and dashboards, or speed up an individual meter to as fast as a few seconds when you're feeding a zero-export or load-balancing controller that needs near-real-time data - with an in-UI note explaining the trade-off (faster polling on one meter adds traffic for every meter sharing that bus).
- Tunable timing for flaky hardware. A configurable pause between Modbus requests helps with cheap RS485 gateways/adapters that need a moment to recover between transactions.
- Reconfigurable without losing history. Both the gateway connection and individual meter settings (name, model, address, polling interval) can be changed after the fact from the Home Assistant UI, without removing and re-adding entities.
- Built for Home Assistant's modern config subentries architecture and requires Python 3.12+ (via the tmodbus library).

---

A custom Home Assistant integration to read multiple Eastron SDM230 (single-phase) and/or SDM630 (three-phase) Modbus energy meters directly over RS485, with no cloud dependency. Built on [tmodbus](https://github.com/wlcrs/tmodbus), the same modern, async Modbus library used by Home Assistant's own "Modernizing Modbus" architecture (release 2026.9). Register addresses and data types come directly from the official Eastron Modbus protocol documents (SDM230Modbus V1.4, SDM630Modbus V1.8).

## What this does and does not do

- Reading (read-only): voltage, current, power (W/VA/VAr), power factor, frequency, energy (import/export/total, per phase on the SDM630), THD%, and so on - as sensors, with the correct `device_class` and `state_class` for the Energy Dashboard.
- No write functions: the configuration holding registers (network settings, pulse output, reset) are deliberately not exposed - this reduces the risk of a faulty automation accidentally reconfiguring the meter. This is easy to extend using the existing `registers.py` should you want it later.
- One shared connection per gateway: multiple meters on the same RS485 daisy chain/gateway automatically share a single underlying Modbus connection - important because RS485 is half-duplex and many cheap RS485-to-TCP gateways only accept one TCP session at a time anyway.

## Installation

1. Copy the folder `custom_components/eastron_sdm` to `<your HA config>/custom_components/eastron_sdm` (via Samba, SSH, or the Studio Code Server add-on). Alternatively: add the repo as a "Custom repository" in HACS (category Integration).
2. Restart Home Assistant.
3. Settings -> Devices & Services -> Add Integration -> search for "Eastron SDM".
4. Work through the flow below - you configure the gateway/RS485 bus once, and then add as many meters as you have on that bus within the same wizard.

## Working through the config flow

**Step 1 - connection type.** Choose what matches your hardware:

- *RS485-to-TCP gateway, transparent* - the most common situation with a cheap RS485<->WiFi/LAN adapter (Elfin EW11, USR-W610/TCP232, etc.) in "transparent"/"serial bridge" mode: the gateway forwards the raw RTU bytes (including CRC) one-to-one over a TCP socket. Start here if you're not sure which type of gateway you have.
- *Modbus TCP gateway, native* - for gateways that perform a real Modbus TCP translation (MBAP header, no CRC on the wire between HA and the gateway), e.g. a Waveshare RS485-to-ETH in Modbus TCP mode.
- *Local serial port* - a USB-RS485 adapter plugged directly into the machine Home Assistant runs on (e.g. `/dev/ttyUSB0`).

**Step 2 - gateway address.** Host/IP + port (network) or the serial device + baud rate/parity/stop bits/byte size (serial, the Eastron default is usually 9600-N-1, but check this on the meter itself). You enter this only once, for the entire bus.

In both variants you'll also find **"Pause between requests (ms)"** here - a minimum period of silence inserted after each Modbus response before the next request is sent. Default 30ms for serial/RTU-over-TCP connections and 20ms for a native Modbus TCP gateway. `tmodbus` itself defaults to 0ms; some cheap RS485 gateways need a moment after a response and, without a pause, react with timeouts or corrupt readings. If you see that behaviour, raise this value (e.g. 50-100ms); on a stable bus you can instead lower it for faster polling. It can be changed afterwards via **Reconfigure** without losing the meters.

**Step 3 - first meter.** Name, model (SDM230 or SDM630), and the Modbus address (unit ID / slave ID, 1-247 - every meter on the bus must have a unique address).

**Step 4 - another meter, or finish.** After each meter you get the choice "Add another meter" or "Finish setup".

**Want to add another meter later?** Open the Eastron gateway under Settings -> Devices & Services and click "+ Add device" on that integration card - this opens the same meter questions, without re-entering the gateway settings. Removing or reconfiguring a meter is done via the "..." menu on that device.

## How this works

One config entry = one gateway/RS485 connection. Each meter on that bus is a separate "meter" subentry underneath it (with its own Device in Home Assistant), not a separate integration. `modbus_client.py` keeps exactly one `tmodbus` connection open per physical gateway, regardless of how many meters are on that bus. For each meter a lightweight client object is created via `AsyncModbusClient.for_unit_id()` that reuses the same underlying connection but talks to its own Modbus address. An `asyncio.Lock` per gateway ensures that two requests never go onto the wire at the same time. `registers.py` contains the full register map from the Eastron manuals and automatically groups contiguous registers into as few Modbus requests as possible (with a margin under the limit of 40 parameters/80 registers per transaction).

## Known limitations / things to verify yourself

- This integration has been built and syntax-checked, but not tested against a real meter or a live Home Assistant installation - so test with a single meter first before adding the rest, and check Settings -> System -> Logs if something doesn't work right away.
- `tmodbus` requires Python 3.12+; recent Home Assistant Core versions meet this.
- Some entities (phase angles, THD%, per-phase demand/energy on the SDM630) are disabled by default to keep the entity list manageable - enable them via Settings -> Entities if you need them.
- The polling interval is configurable per meter (1-3600s). Recommended: leave this at the default (30s) for normal monitoring. Only lower it for a zero-export or load-balancing application; keep in mind that all requests run serially through a single lock, so a faster meter means more traffic for everyone on that bus. Don't go much below 3 seconds.
- This uses Home Assistant's "config subentries" system. Adding meters is the best-verified path; reconfiguring an existing meter or gateway relies on the same API but is slightly less certain - should a button not work, removing and re-adding is a perfectly fine workaround.

## Integration icon

Home Assistant always fetches the integration icon from [brands.home-assistant.io](https://brands.home-assistant.io/), including for custom_components, via `custom_integrations/eastron_sdm/icon.png` in the public [home-assistant/brands](https://github.com/home-assistant/brands) GitHub repo. There is no manifest.json field or local file with which a custom_component can override this itself. If you want to see the official Eastron logo in that overview, a PR to that brands repo is needed (`icon.png` 256x256, transparent background). Until then the sensors show regular Material Design icons per measurement type.

## License

Apache-2.0 - Woon IoT BV, together with René van der Gaag. https://github.com/wooniot/ha-modbus-bridge
