"""Modbus register maps for every supported meter model.

Two unrelated encoding families are supported, distinguished by each
``RegisterDefinition``'s ``value_type``:

- **Eastron SDM230 / SDM630 / SDM120 / SDM72Modbus-V2** (default,
  ``value_type="float32"``). Register addresses are 0-based Modbus
  "input register" offsets, i.e. the manufacturer's documented address
  (e.g. "30073") minus the 30001 base used in the Eastron Modbus
  protocol documents. Every parameter occupies two consecutive 16-bit
  registers and is encoded as a big-endian (most-significant-register-
  first) IEEE754 32-bit float, exactly like the meter's own default
  "Register Order" setting.
- **Victron Energy ET112 / ET340 / EM540** (``value_type="int16"`` or
  ``"int32"``). These are Carlo Gavazzi devices sold under a Victron
  model name (ET112 = Carlo Gavazzi EM111, ET340 = Carlo Gavazzi
  EM340, EM540 = Carlo Gavazzi EM530/EM540) with a completely
  different, older Modbus convention: every parameter is a plain
  big-endian signed integer (1 register for INT16, 2 for INT32) that
  must be divided by that register's ``scale`` to get the physical
  value - e.g. a raw current reading of 1234 with scale=1000 is
  1.234 A. Register addresses below use the same 0-based-offset
  convention as above (documented "3xxxx" input-register address minus
  300001), which matches consistently across all three Carlo
  Gavazzi/Victron protocol docs.

Sources:
- Eastron SDM230Modbus Protocol Implementation V1.4 (input registers
  table, section 1.2.1)
- Eastron SDM630Modbus Protocol Implementation V1.8 (input registers
  table, section 1.2.1)
- Eastron SDM120-Modbus protocol/register map (single-phase; the
  addresses it documents are a strict subset of, and share identical
  offsets with, the SDM230 map above - both are from the same
  single-phase meter family).
- Eastron SDM72DM-V2 user manual V1.1 (2021) - "SDM72Modbus V2" line.
  Its addresses are a subset of, and share identical offsets with, the
  SDM630 map above (same three-phase family), minus THD/demand/
  per-phase-energy registers that the plain SDM630 has but the
  SDM72-V2 line does not document, plus two SDM72-specific registers
  (31281/31283, "total import/export active power") that aren't part
  of the SDM630 map.
- Carlo Gavazzi EM111 (MV5 model) Modbus serial protocol rev. 2.12 -
  underlying protocol for the Victron ET112.
- Carlo Gavazzi EM330/EM340/ET330/ET340 communication protocol V2
  rev. 17 - underlying protocol for the Victron ET340.
- Carlo Gavazzi EM530/EM540 Modbus communication protocol V1.3
  (13/02/2024) - underlying protocol for the Victron EM540.
  NOTE: these three ET112/ET340/EM540 register maps have not been
  tested against real hardware (2026-09-04) - only cross-checked for
  internal consistency (sequential register offsets, matching layouts
  between the three closely-related Carlo Gavazzi docs).
- Chint DTSU666/DSSU666 User Manual (official chintglobal.com PDF).
  Like the Eastron SDM family, its registers are plain IEEE754 float32
  values in physical units (no integer scale factor needed) - but
  they are Modbus *holding* registers (function 03h), not *input*
  registers (function 04h) like every other model here; see
  HOLDING_REGISTER_MODELS in const.py and coordinator.py. Also not
  tested against real hardware (2026-09-04).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)

from .const import (
    MODEL_DTSU666,
    MODEL_EM540,
    MODEL_ET112,
    MODEL_ET340,
    MODEL_SDM120,
    MODEL_SDM230,
    MODEL_SDM630,
    MODEL_SDM72V2,
)

MEASUREMENT = SensorStateClass.MEASUREMENT
TOTAL_INCREASING = SensorStateClass.TOTAL_INCREASING
TOTAL = SensorStateClass.TOTAL


@dataclass(frozen=True)
class RegisterDefinition:
    """A single input-register parameter, from either supported
    encoding family - see the module docstring for ``value_type``."""

    key: str
    address: int
    name: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    icon: str | None = None
    entity_registry_enabled_default: bool = True
    # "float32" (Eastron SDM family) or "int16"/"int32" (Carlo Gavazzi /
    # Victron family, see module docstring) - decode_register() below
    # dispatches on this.
    value_type: str = "float32"
    # Only meaningful for value_type "int16"/"int32": divide the raw
    # signed integer by this to get the physical value.
    scale: float = 1.0
    # Number of 16-bit registers this parameter occupies, derived from
    # value_type in __post_init__ (float32/int32 = 2, int16 = 1).
    count: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        counts = {"float32": 2, "int16": 1, "int32": 2}
        object.__setattr__(self, "count", counts[self.value_type])


def _v(
    key: str, address: int, name: str, enabled: bool = True,
    *, value_type: str = "float32", scale: float = 1.0,
) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=MEASUREMENT,
        entity_registry_enabled_default=enabled,
        value_type=value_type,
        scale=scale,
    )


def _a(
    key: str, address: int, name: str, enabled: bool = True,
    *, value_type: str = "float32", scale: float = 1.0,
) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=MEASUREMENT,
        entity_registry_enabled_default=enabled,
        value_type=value_type,
        scale=scale,
    )


def _w(
    key: str, address: int, name: str, enabled: bool = True,
    *, value_type: str = "float32", scale: float = 1.0,
) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=MEASUREMENT,
        entity_registry_enabled_default=enabled,
        value_type=value_type,
        scale=scale,
    )


def _va(
    key: str, address: int, name: str, enabled: bool = True,
    *, value_type: str = "float32", scale: float = 1.0,
) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit="VA",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=MEASUREMENT,
        entity_registry_enabled_default=enabled,
        value_type=value_type,
        scale=scale,
    )


def _var(
    key: str, address: int, name: str, enabled: bool = True,
    *, value_type: str = "float32", scale: float = 1.0,
) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit="var",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=MEASUREMENT,
        entity_registry_enabled_default=enabled,
        value_type=value_type,
        scale=scale,
    )


def _pf(
    key: str, address: int, name: str, enabled: bool = True,
    *, value_type: str = "float32", scale: float = 1.0,
) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit=None,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=MEASUREMENT,
        entity_registry_enabled_default=enabled,
        value_type=value_type,
        scale=scale,
    )


def _deg(key: str, address: int, name: str) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit="°",
        state_class=MEASUREMENT,
        icon="mdi:angle-acute",
        entity_registry_enabled_default=False,
    )


def _hz(
    key: str, address: int, name: str, *, value_type: str = "float32", scale: float = 1.0
) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=MEASUREMENT,
        value_type=value_type,
        scale=scale,
    )


def _kwh(
    key: str, address: int, name: str, resettable: bool = False, enabled: bool = True,
    *, value_type: str = "float32", scale: float = 1.0,
) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=TOTAL if resettable else TOTAL_INCREASING,
        entity_registry_enabled_default=enabled,
        value_type=value_type,
        scale=scale,
    )


def _kvarh(
    key: str, address: int, name: str, resettable: bool = False, enabled: bool = True,
    *, value_type: str = "float32", scale: float = 1.0,
) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit="kvarh",
        state_class=TOTAL if resettable else TOTAL_INCREASING,
        icon="mdi:lightning-bolt",
        entity_registry_enabled_default=enabled,
        value_type=value_type,
        scale=scale,
    )


def _pct(key: str, address: int, name: str, enabled: bool = False) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit=PERCENTAGE,
        state_class=MEASUREMENT,
        icon="mdi:sine-wave",
        entity_registry_enabled_default=enabled,
    )


# --------------------------------------------------------------------------
# SDM230 - single phase meter
# --------------------------------------------------------------------------
SDM230_REGISTERS: list[RegisterDefinition] = [
    _v("voltage", 0, "Voltage"),
    _a("current", 6, "Current"),
    _w("active_power", 12, "Active power"),
    _va("apparent_power", 18, "Apparent power", enabled=False),
    _var("reactive_power", 24, "Reactive power", enabled=False),
    _pf("power_factor", 30, "Power factor", enabled=False),
    _deg("phase_angle", 36, "Phase angle"),
    _hz("frequency", 70, "Frequency"),
    _kwh("import_active_energy", 72, "Import active energy"),
    _kwh("export_active_energy", 74, "Export active energy"),
    _kvarh("import_reactive_energy", 76, "Import reactive energy", enabled=False),
    _kvarh("export_reactive_energy", 78, "Export reactive energy", enabled=False),
    _w("total_power_demand", 84, "Power demand", enabled=False),
    _w("max_total_power_demand", 86, "Max power demand", enabled=False),
    _a("current_demand", 258, "Current demand", enabled=False),
    _a("max_current_demand", 264, "Max current demand", enabled=False),
    _kwh("total_active_energy", 342, "Total active energy"),
    _kvarh("total_reactive_energy", 344, "Total reactive energy", enabled=False),
    _kwh("resettable_total_active_energy", 384, "Resettable total active energy", resettable=True, enabled=False),
    _kvarh("resettable_total_reactive_energy", 386, "Resettable total reactive energy", resettable=True, enabled=False),
]

# --------------------------------------------------------------------------
# SDM630 - three phase meter
# --------------------------------------------------------------------------
SDM630_REGISTERS: list[RegisterDefinition] = [
    _v("l1_voltage", 0, "L1 voltage"),
    _v("l2_voltage", 2, "L2 voltage"),
    _v("l3_voltage", 4, "L3 voltage"),
    _a("l1_current", 6, "L1 current"),
    _a("l2_current", 8, "L2 current"),
    _a("l3_current", 10, "L3 current"),
    _w("l1_power", 12, "L1 power"),
    _w("l2_power", 14, "L2 power"),
    _w("l3_power", 16, "L3 power"),
    _va("l1_apparent_power", 18, "L1 apparent power", enabled=False),
    _va("l2_apparent_power", 20, "L2 apparent power", enabled=False),
    _va("l3_apparent_power", 22, "L3 apparent power", enabled=False),
    _var("l1_reactive_power", 24, "L1 reactive power", enabled=False),
    _var("l2_reactive_power", 26, "L2 reactive power", enabled=False),
    _var("l3_reactive_power", 28, "L3 reactive power", enabled=False),
    _pf("l1_power_factor", 30, "L1 power factor", enabled=False),
    _pf("l2_power_factor", 32, "L2 power factor", enabled=False),
    _pf("l3_power_factor", 34, "L3 power factor", enabled=False),
    _deg("l1_phase_angle", 36, "L1 phase angle"),
    _deg("l2_phase_angle", 38, "L2 phase angle"),
    _deg("l3_phase_angle", 40, "L3 phase angle"),
    _v("avg_ln_voltage", 42, "Average L-N voltage", ),
    _a("avg_line_current", 46, "Average line current", enabled=False),
    _a("sum_line_current", 48, "Sum of line currents", enabled=False),
    _w("total_power", 52, "Total power"),
    _va("total_apparent_power", 56, "Total apparent power", enabled=False),
    _var("total_reactive_power", 60, "Total reactive power", enabled=False),
    _pf("total_power_factor", 62, "Total power factor", enabled=False),
    _deg("total_phase_angle", 66, "Total phase angle"),
    _hz("frequency", 70, "Frequency"),
    _kwh("total_import_energy", 72, "Total import energy"),
    _kwh("total_export_energy", 74, "Total export energy"),
    _kvarh("total_import_reactive_energy", 76, "Total import reactive energy", enabled=False),
    _kvarh("total_export_reactive_energy", 78, "Total export reactive energy", enabled=False),
    RegisterDefinition("total_va_hours", 80, "Total apparent energy", unit="kVAh", state_class=TOTAL_INCREASING, entity_registry_enabled_default=False),
    RegisterDefinition("ampere_hours", 82, "Ampere hours", unit="Ah", state_class=TOTAL_INCREASING, icon="mdi:current-ac", entity_registry_enabled_default=False),
    _w("total_power_demand", 84, "Power demand", enabled=False),
    _va("max_total_power_demand", 86, "Max power demand", enabled=False),
    _va("total_va_demand", 100, "Total VA demand", enabled=False),
    _va("max_total_va_demand", 102, "Max total VA demand", enabled=False),
    _a("neutral_current_demand", 104, "Neutral current demand", enabled=False),
    _a("max_neutral_current_demand", 106, "Max neutral current demand", enabled=False),
    _v("l1l2_voltage", 200, "L1-L2 voltage", ),
    _v("l2l3_voltage", 202, "L2-L3 voltage"),
    _v("l3l1_voltage", 204, "L3-L1 voltage"),
    _v("avg_ll_voltage", 206, "Average L-L voltage"),
    _a("neutral_current", 224, "Neutral current", enabled=False),
    _pct("l1_ln_volts_thd", 234, "L1 voltage THD"),
    _pct("l2_ln_volts_thd", 236, "L2 voltage THD"),
    _pct("l3_ln_volts_thd", 238, "L3 voltage THD"),
    _pct("l1_current_thd", 240, "L1 current THD"),
    _pct("l2_current_thd", 242, "L2 current THD"),
    _pct("l3_current_thd", 244, "L3 current THD"),
    _pct("avg_ln_volts_thd", 248, "Average voltage THD"),
    _pct("avg_current_thd", 250, "Average current THD"),
    _a("l1_current_demand", 258, "L1 current demand", enabled=False),
    _a("l2_current_demand", 260, "L2 current demand", enabled=False),
    _a("l3_current_demand", 262, "L3 current demand", enabled=False),
    _a("max_l1_current_demand", 264, "Max L1 current demand", enabled=False),
    _a("max_l2_current_demand", 266, "Max L2 current demand", enabled=False),
    _a("max_l3_current_demand", 268, "Max L3 current demand", enabled=False),
    _pct("l1l2_volts_thd", 334, "L1-L2 voltage THD"),
    _pct("l2l3_volts_thd", 336, "L2-L3 voltage THD"),
    _pct("l3l1_volts_thd", 338, "L3-L1 voltage THD"),
    _pct("avg_ll_volts_thd", 340, "Average L-L voltage THD"),
    _kwh("total_energy", 342, "Total energy (import+export)"),
    _kvarh("total_reactive_energy", 344, "Total reactive energy", enabled=False),
    _kwh("l1_import_energy", 346, "L1 import energy", enabled=False),
    _kwh("l2_import_energy", 348, "L2 import energy", enabled=False),
    _kwh("l3_import_energy", 350, "L3 import energy", enabled=False),
    _kwh("l1_export_energy", 352, "L1 export energy", enabled=False),
    _kwh("l2_export_energy", 354, "L2 export energy", enabled=False),
    _kwh("l3_export_energy", 356, "L3 export energy", enabled=False),
    _kwh("l1_total_energy", 358, "L1 total energy", enabled=False),
    _kwh("l2_total_energy", 360, "L2 total energy", enabled=False),
    _kwh("l3_total_energy", 362, "L3 total energy", enabled=False),
    _kvarh("l1_import_reactive_energy", 364, "L1 import reactive energy", enabled=False),
    _kvarh("l2_import_reactive_energy", 366, "L2 import reactive energy", enabled=False),
    _kvarh("l3_import_reactive_energy", 368, "L3 import reactive energy", enabled=False),
    _kvarh("l1_export_reactive_energy", 370, "L1 export reactive energy", enabled=False),
    _kvarh("l2_export_reactive_energy", 372, "L2 export reactive energy", enabled=False),
    _kvarh("l3_export_reactive_energy", 374, "L3 export reactive energy", enabled=False),
    _kvarh("l1_total_reactive_energy", 376, "L1 total reactive energy", enabled=False),
    _kvarh("l2_total_reactive_energy", 378, "L2 total reactive energy", enabled=False),
    _kvarh("l3_total_reactive_energy", 380, "L3 total reactive energy", enabled=False),
]

# --------------------------------------------------------------------------
# SDM120 - single phase meter (cost-reduced SDM230 sibling: same
# family/offsets, but no phase-angle or demand registers, and no
# resettable-energy registers).
# --------------------------------------------------------------------------
SDM120_REGISTERS: list[RegisterDefinition] = [
    _v("voltage", 0, "Voltage"),
    _a("current", 6, "Current"),
    _w("active_power", 12, "Active power"),
    _va("apparent_power", 18, "Apparent power", enabled=False),
    _var("reactive_power", 24, "Reactive power", enabled=False),
    _pf("power_factor", 30, "Power factor", enabled=False),
    _hz("frequency", 70, "Frequency"),
    _kwh("import_active_energy", 72, "Import active energy"),
    _kwh("export_active_energy", 74, "Export active energy"),
    _kvarh("import_reactive_energy", 76, "Import reactive energy", enabled=False),
    _kvarh("export_reactive_energy", 78, "Export reactive energy", enabled=False),
    _kwh("total_active_energy", 342, "Total active energy"),
    _kvarh("total_reactive_energy", 344, "Total reactive energy", enabled=False),
]

# --------------------------------------------------------------------------
# SDM72Modbus V2 (SDM72DM-V2) - three phase meter, SDM630 sibling: same
# family/offsets for everything it documents, but no THD, no demand
# registers, and no per-phase energy breakdown. Adds two SDM72-specific
# registers (total import/export active power at 31281/31283) that the
# plain SDM630 map doesn't have.
# --------------------------------------------------------------------------
SDM72V2_REGISTERS: list[RegisterDefinition] = [
    _v("l1_voltage", 0, "L1 voltage"),
    _v("l2_voltage", 2, "L2 voltage"),
    _v("l3_voltage", 4, "L3 voltage"),
    _a("l1_current", 6, "L1 current"),
    _a("l2_current", 8, "L2 current"),
    _a("l3_current", 10, "L3 current"),
    _w("l1_power", 12, "L1 power"),
    _w("l2_power", 14, "L2 power"),
    _w("l3_power", 16, "L3 power"),
    _va("l1_apparent_power", 18, "L1 apparent power", enabled=False),
    _va("l2_apparent_power", 20, "L2 apparent power", enabled=False),
    _va("l3_apparent_power", 22, "L3 apparent power", enabled=False),
    _var("l1_reactive_power", 24, "L1 reactive power", enabled=False),
    _var("l2_reactive_power", 26, "L2 reactive power", enabled=False),
    _var("l3_reactive_power", 28, "L3 reactive power", enabled=False),
    _pf("l1_power_factor", 30, "L1 power factor", enabled=False),
    _pf("l2_power_factor", 32, "L2 power factor", enabled=False),
    _pf("l3_power_factor", 34, "L3 power factor", enabled=False),
    _v("avg_ln_voltage", 42, "Average L-N voltage"),
    _a("avg_line_current", 46, "Average line current", enabled=False),
    _a("sum_line_current", 48, "Sum of line currents", enabled=False),
    _w("total_power", 52, "Total power"),
    _va("total_apparent_power", 56, "Total apparent power", enabled=False),
    _var("total_reactive_power", 60, "Total reactive power", enabled=False),
    _pf("total_power_factor", 62, "Total power factor", enabled=False),
    _hz("frequency", 70, "Frequency"),
    _kwh("total_import_energy", 72, "Total import energy"),
    _kwh("total_export_energy", 74, "Total export energy"),
    _v("l1l2_voltage", 200, "L1-L2 voltage"),
    _v("l2l3_voltage", 202, "L2-L3 voltage"),
    _v("l3l1_voltage", 204, "L3-L1 voltage"),
    _v("avg_ll_voltage", 206, "Average L-L voltage"),
    _a("neutral_current", 224, "Neutral current", enabled=False),
    _kwh("total_energy", 342, "Total energy (import+export)"),
    _kvarh("total_reactive_energy", 344, "Total reactive energy", enabled=False),
    _kwh("resettable_total_active_energy", 384, "Resettable total active energy", resettable=True, enabled=False),
    _kwh("resettable_import_active_energy", 388, "Resettable import active energy", resettable=True, enabled=False),
    _kwh("resettable_export_active_energy", 390, "Resettable export active energy", resettable=True, enabled=False),
    RegisterDefinition("net_active_energy", 396, "Net active energy (import - export)", unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=TOTAL, entity_registry_enabled_default=False),
    _w("total_import_power", 1280, "Total import power"),
    _w("total_export_power", 1282, "Total export power"),
]

# --------------------------------------------------------------------------
# Victron ET112 - single phase (Carlo Gavazzi EM111 protocol). Every
# parameter below is a plain signed integer, not a float - see the
# module docstring. Demand/peak-demand and partial/tariff energy
# registers are intentionally left out (not useful for HA polling).
# --------------------------------------------------------------------------
ET112_REGISTERS: list[RegisterDefinition] = [
    _v("voltage", 0, "Voltage", value_type="int32", scale=10),
    _a("current", 2, "Current", value_type="int32", scale=1000),
    _w("active_power", 4, "Active power", value_type="int32", scale=10),
    _va("apparent_power", 6, "Apparent power", enabled=False, value_type="int32", scale=10),
    _var("reactive_power", 8, "Reactive power", enabled=False, value_type="int32", scale=10),
    _pf("power_factor", 14, "Power factor", enabled=False, value_type="int16", scale=1000),
    _hz("frequency", 15, "Frequency", value_type="int16", scale=10),
    _kwh("import_active_energy", 16, "Import active energy", value_type="int32", scale=10),
    _kvarh("import_reactive_energy", 18, "Import reactive energy", enabled=False, value_type="int32", scale=10),
    _kwh("export_active_energy", 32, "Export active energy", value_type="int32", scale=10),
    _kvarh("export_reactive_energy", 34, "Export reactive energy", enabled=False, value_type="int32", scale=10),
]

# --------------------------------------------------------------------------
# Victron ET340 - three phase (Carlo Gavazzi EM340 protocol).
# --------------------------------------------------------------------------
ET340_REGISTERS: list[RegisterDefinition] = [
    _v("l1_voltage", 0, "L1 voltage", value_type="int32", scale=10),
    _v("l2_voltage", 2, "L2 voltage", value_type="int32", scale=10),
    _v("l3_voltage", 4, "L3 voltage", value_type="int32", scale=10),
    _a("l1_current", 12, "L1 current", value_type="int32", scale=1000),
    _a("l2_current", 14, "L2 current", value_type="int32", scale=1000),
    _a("l3_current", 16, "L3 current", value_type="int32", scale=1000),
    _w("l1_power", 18, "L1 power", value_type="int32", scale=10),
    _w("l2_power", 20, "L2 power", value_type="int32", scale=10),
    _w("l3_power", 22, "L3 power", value_type="int32", scale=10),
    _va("l1_apparent_power", 24, "L1 apparent power", enabled=False, value_type="int32", scale=10),
    _va("l2_apparent_power", 26, "L2 apparent power", enabled=False, value_type="int32", scale=10),
    _va("l3_apparent_power", 28, "L3 apparent power", enabled=False, value_type="int32", scale=10),
    _var("l1_reactive_power", 30, "L1 reactive power", enabled=False, value_type="int32", scale=10),
    _var("l2_reactive_power", 32, "L2 reactive power", enabled=False, value_type="int32", scale=10),
    _var("l3_reactive_power", 34, "L3 reactive power", enabled=False, value_type="int32", scale=10),
    _w("total_power", 40, "Total power", value_type="int32", scale=10),
    _va("total_apparent_power", 42, "Total apparent power", enabled=False, value_type="int32", scale=10),
    _var("total_reactive_power", 44, "Total reactive power", enabled=False, value_type="int32", scale=10),
    _pf("l1_power_factor", 46, "L1 power factor", enabled=False, value_type="int16", scale=1000),
    _pf("l2_power_factor", 47, "L2 power factor", enabled=False, value_type="int16", scale=1000),
    _pf("l3_power_factor", 48, "L3 power factor", enabled=False, value_type="int16", scale=1000),
    _pf("power_factor", 49, "Power factor", enabled=False, value_type="int16", scale=1000),
    _hz("frequency", 51, "Frequency", value_type="int16", scale=10),
    _kwh("import_active_energy", 52, "Import active energy", value_type="int32", scale=10),
    _kvarh("import_reactive_energy", 54, "Import reactive energy", enabled=False, value_type="int32", scale=10),
    _kwh("export_active_energy", 78, "Export active energy", value_type="int32", scale=10),
    _kvarh("export_reactive_energy", 80, "Export reactive energy", enabled=False, value_type="int32", scale=10),
]

# --------------------------------------------------------------------------
# Victron EM540 - three phase (Carlo Gavazzi EM530/EM540 protocol).
# ET340 sibling, plus L-L voltages and an L-N/L-L system average.
# --------------------------------------------------------------------------
EM540_REGISTERS: list[RegisterDefinition] = [
    _v("l1_voltage", 0, "L1 voltage", value_type="int32", scale=10),
    _v("l2_voltage", 2, "L2 voltage", value_type="int32", scale=10),
    _v("l3_voltage", 4, "L3 voltage", value_type="int32", scale=10),
    _v("l1l2_voltage", 6, "L1-L2 voltage", enabled=False, value_type="int32", scale=10),
    _v("l2l3_voltage", 8, "L2-L3 voltage", enabled=False, value_type="int32", scale=10),
    _v("l3l1_voltage", 10, "L3-L1 voltage", enabled=False, value_type="int32", scale=10),
    _a("l1_current", 12, "L1 current", value_type="int32", scale=1000),
    _a("l2_current", 14, "L2 current", value_type="int32", scale=1000),
    _a("l3_current", 16, "L3 current", value_type="int32", scale=1000),
    _w("l1_power", 18, "L1 power", value_type="int32", scale=10),
    _w("l2_power", 20, "L2 power", value_type="int32", scale=10),
    _w("l3_power", 22, "L3 power", value_type="int32", scale=10),
    _va("l1_apparent_power", 24, "L1 apparent power", enabled=False, value_type="int32", scale=10),
    _va("l2_apparent_power", 26, "L2 apparent power", enabled=False, value_type="int32", scale=10),
    _va("l3_apparent_power", 28, "L3 apparent power", enabled=False, value_type="int32", scale=10),
    _var("l1_reactive_power", 30, "L1 reactive power", enabled=False, value_type="int32", scale=10),
    _var("l2_reactive_power", 32, "L2 reactive power", enabled=False, value_type="int32", scale=10),
    _var("l3_reactive_power", 34, "L3 reactive power", enabled=False, value_type="int32", scale=10),
    _v("avg_ln_voltage", 36, "Average L-N voltage", value_type="int32", scale=10),
    _v("avg_ll_voltage", 38, "Average L-L voltage", enabled=False, value_type="int32", scale=10),
    _w("total_power", 40, "Total power", value_type="int32", scale=10),
    _va("total_apparent_power", 42, "Total apparent power", enabled=False, value_type="int32", scale=10),
    _var("total_reactive_power", 44, "Total reactive power", enabled=False, value_type="int32", scale=10),
    _pf("l1_power_factor", 46, "L1 power factor", enabled=False, value_type="int16", scale=1000),
    _pf("l2_power_factor", 47, "L2 power factor", enabled=False, value_type="int16", scale=1000),
    _pf("l3_power_factor", 48, "L3 power factor", enabled=False, value_type="int16", scale=1000),
    _pf("power_factor", 49, "Power factor", enabled=False, value_type="int16", scale=1000),
    _hz("frequency", 51, "Frequency", value_type="int16", scale=10),
    _kwh("import_active_energy", 52, "Import active energy", value_type="int32", scale=10),
    _kvarh("import_reactive_energy", 54, "Import reactive energy", enabled=False, value_type="int32", scale=10),
    _kwh("export_active_energy", 78, "Export active energy", value_type="int32", scale=10),
    _kvarh("export_reactive_energy", 80, "Export reactive energy", enabled=False, value_type="int32", scale=10),
    RegisterDefinition(
        "total_apparent_energy", 86, "Total apparent energy", unit="kVAh",
        state_class=TOTAL_INCREASING, entity_registry_enabled_default=False,
        value_type="int32", scale=10,
    ),
]

# --------------------------------------------------------------------------
# Chint DTSU666 - three phase, holding registers (function 03h), plain
# IEEE754 floats like the Eastron family (no scale factor needed).
# Addresses below are the manual's documented hex register addresses,
# used directly (no 30001-style base to subtract, unlike the Eastron/
# Carlo Gavazzi "3xxxx" input-register convention).
# --------------------------------------------------------------------------
DTSU666_REGISTERS: list[RegisterDefinition] = [
    _v("l1l2_voltage", 0x2000, "L1-L2 voltage", enabled=False),
    _v("l2l3_voltage", 0x2002, "L2-L3 voltage", enabled=False),
    _v("l3l1_voltage", 0x2004, "L3-L1 voltage", enabled=False),
    _v("l1_voltage", 0x2006, "L1 voltage"),
    _v("l2_voltage", 0x2008, "L2 voltage"),
    _v("l3_voltage", 0x200A, "L3 voltage"),
    _a("l1_current", 0x200C, "L1 current"),
    _a("l2_current", 0x200E, "L2 current"),
    _a("l3_current", 0x2010, "L3 current"),
    _w("total_power", 0x2012, "Total power"),
    _w("l1_power", 0x2014, "L1 power"),
    _w("l2_power", 0x2016, "L2 power"),
    _w("l3_power", 0x2018, "L3 power"),
    _var("total_reactive_power", 0x201A, "Total reactive power", enabled=False),
    _var("l1_reactive_power", 0x201C, "L1 reactive power", enabled=False),
    _var("l2_reactive_power", 0x201E, "L2 reactive power", enabled=False),
    _var("l3_reactive_power", 0x2020, "L3 reactive power", enabled=False),
    _pf("power_factor", 0x202A, "Power factor", enabled=False),
    _pf("l1_power_factor", 0x202C, "L1 power factor", enabled=False),
    _pf("l2_power_factor", 0x202E, "L2 power factor", enabled=False),
    _pf("l3_power_factor", 0x2030, "L3 power factor", enabled=False),
    _hz("frequency", 0x2044, "Frequency"),
    _kwh("import_active_energy", 0x101E, "Import active energy"),
    _kwh("l1_import_active_energy", 0x1020, "L1 import active energy", enabled=False),
    _kwh("l2_import_active_energy", 0x1022, "L2 import active energy", enabled=False),
    _kwh("l3_import_active_energy", 0x1024, "L3 import active energy", enabled=False),
    _kwh("net_import_active_energy", 0x1026, "Net import active energy", enabled=False),
    _kwh("export_active_energy", 0x1028, "Export active energy"),
    _kwh("l1_export_active_energy", 0x102A, "L1 export active energy", enabled=False),
    _kwh("l2_export_active_energy", 0x102C, "L2 export active energy", enabled=False),
    _kwh("l3_export_active_energy", 0x102E, "L3 export active energy", enabled=False),
    _kwh("net_export_active_energy", 0x1030, "Net export active energy", enabled=False),
]

REGISTER_MAP: dict[str, list[RegisterDefinition]] = {
    MODEL_SDM230: SDM230_REGISTERS,
    MODEL_SDM630: SDM630_REGISTERS,
    MODEL_SDM120: SDM120_REGISTERS,
    MODEL_SDM72V2: SDM72V2_REGISTERS,
    MODEL_ET112: ET112_REGISTERS,
    MODEL_ET340: ET340_REGISTERS,
    MODEL_EM540: EM540_REGISTERS,
    MODEL_DTSU666: DTSU666_REGISTERS,
}


def decode_float32(registers: list[int], offset: int) -> float:
    """Decode a big-endian (hi-register-first) IEEE754 float from a
    list of 16-bit register values, starting at ``offset``."""
    hi, lo = registers[offset], registers[offset + 1]
    raw = (hi << 16) | lo
    return struct.unpack(">f", raw.to_bytes(4, "big"))[0]


def decode_int(registers: list[int], offset: int, count: int, scale: float) -> float:
    """Decode a big-endian signed integer (1 register = int16, 2 =
    int32) from a list of 16-bit register values, starting at
    ``offset``, and divide it by ``scale`` to get the physical value -
    the Carlo Gavazzi/Victron encoding (see module docstring)."""
    raw = 0
    for reg in registers[offset : offset + count]:
        raw = (raw << 16) | reg
    bits = count * 16
    if raw >= 1 << (bits - 1):
        raw -= 1 << bits
    return raw / scale


def decode_register(registers: list[int], offset: int, register: RegisterDefinition) -> float:
    """Decode one parameter's raw register(s) into its physical value,
    dispatching on ``register.value_type`` (see ``RegisterDefinition``
    in this module for what each value_type means)."""
    if register.value_type == "float32":
        return decode_float32(registers, offset)
    if register.value_type in ("int16", "int32"):
        return decode_int(registers, offset, register.count, register.scale)
    raise ValueError(f"Unknown value_type {register.value_type!r} for register {register.key!r}")


@dataclass(frozen=True)
class ReadBlock:
    """One Modbus 'read input registers' request covering one or more
    parameters."""

    start_address: int
    quantity: int
    registers: list[RegisterDefinition]


def build_read_blocks(
    registers: list[RegisterDefinition],
    max_block_size: int,
    max_gap: int,
) -> list[ReadBlock]:
    """Group a register map into as few Modbus read requests as
    possible, without ever asking for more than ``max_block_size``
    registers in one go, and without leaving more than ``max_gap``
    unused registers inside a single request."""
    ordered = sorted(registers, key=lambda r: r.address)
    blocks: list[ReadBlock] = []
    current: list[RegisterDefinition] = []

    def flush() -> None:
        if not current:
            return
        start = current[0].address
        end = current[-1].address + current[-1].count
        blocks.append(ReadBlock(start, end - start, list(current)))

    for reg in ordered:
        if current:
            block_start = current[0].address
            prospective_end = reg.address + reg.count
            gap = reg.address - (current[-1].address + current[-1].count)
            if gap > max_gap or (prospective_end - block_start) > max_block_size:
                flush()
                current = []
        current.append(reg)
    flush()
    return blocks
