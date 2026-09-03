# Digital Strom Modbus

Home Assistant custom integration (HACS) voor Digital Strom / gerelateerde
apparatuur via **Modbus TCP**. Zusterproject van
[ha-digitalstrom-smart](https://github.com/wooniot/ha-digitalstrom-smart)
(die de dSS-JSON-API gebruikt); deze variant richt zich op de Modbus-kant.

> **Status:** in ontwikkeling (scaffold). Opgezet door Woon IoT samen met
> René van der Gaag. Nog geen release — de entiteiten/mapping worden uitgewerkt.

## Opzet (scaffold aanwezig)
- Config flow: host / poort / unit-ID (Modbus TCP).
- `custom_components/digitalstrom_modbus/` — `__init__.py`, `config_flow.py`,
  `const.py`, `manifest.json`, `strings.json`.
- Afhankelijkheid: `pymodbus>=3.5.0`.

## Nog te doen (samen)
- [ ] Register-map bepalen (welke Modbus-registers → welke DS/HVAC-functies).
- [ ] Coordinator (polling) + platforms: climate / switch / sensor / cover.
- [ ] Lezen + schrijven getest tegen echte gateway.
- [ ] Beta-release via HACS zodra installeerbaar met echte entiteiten.

## Licentie
Apache-2.0. — Woon IoT BV · https://github.com/wooniot/ha-digitalstrom-modbus
