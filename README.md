# Modbus Bridge

Home Assistant custom integration (HACS) — een **Modbus TCP bridge** die
Modbus-apparatuur en -gateways als entiteiten in Home Assistant brengt.

> **Status:** in ontwikkeling (scaffold). Opgezet door Woon IoT samen met
> René van der Gaag. Nog geen release — de entiteiten/register-mapping worden uitgewerkt.

## Opzet (scaffold aanwezig)
- Config flow: host / poort / unit-ID (Modbus TCP).
- `custom_components/modbus_bridge/` — `__init__.py`, `config_flow.py`,
  `const.py`, `manifest.json`, `strings.json`.
- Afhankelijkheid: `pymodbus>=3.5.0`.

## Nog te doen (samen)
- [ ] Register-map bepalen (welke Modbus-registers → welke functies).
- [ ] Coordinator (polling) + platforms: climate / switch / sensor / cover.
- [ ] Lezen + schrijven getest tegen echte gateway.
- [ ] Beta-release via HACS zodra installeerbaar met echte entiteiten.

## Licentie
Apache-2.0. — Woon IoT BV · https://github.com/wooniot/ha-modbus-bridge
