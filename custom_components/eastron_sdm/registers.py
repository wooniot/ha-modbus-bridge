"""Eastron SDM230 / SDM630 / SDM120 / SDM72Modbus-V2 Modbus register maps.

Register addresses below are 0-based Modbus "input register" offsets,
i.e. the manufacturer's documented address (e.g. "30073") minus the
30001 base used in the Eastron Modbus protocol documents. Every
parameter occupies two consecutive 16-bit registers and is encoded as
a big-endian (most-significant-register-first) IEEE754 32-bit float,
exactly like the meter's own default "Register Order" setting.

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

from .const import MODEL_SDM120, MODEL_SDM230, MODEL_SDM630, MODEL_SDM72V2

MEASUREMENT = SensorStateClass.MEASUREMENT
TOTAL_INCREASING = SensorStateClass.TOTAL_INCREASING
TOTAL = SensorStateClass.TOTAL


@dataclass(frozen=True)
class RegisterDefinition:
    """A single Eastron input-register parameter."""

    key: str
    address: int
    name: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    icon: str | None = None
    entity_registry_enabled_default: bool = True
    # Number of 16-bit registers this parameter occupies. Every Eastron
    # parameter is a 32-bit float, so this is always 2.
    count: int = field(default=2, init=False)


def _v(key: str, address: int, name: str) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=MEASUREMENT,
    )


def _a(key: str, address: int, name: str, enabled: bool = True) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=MEASUREMENT,
        entity_registry_enabled_default=enabled,
    )


def _w(key: str, address: int, name: str, enabled: bool = True) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=MEASUREMENT,
        entity_registry_enabled_default=enabled,
    )


def _va(key: str, address: int, name: str, enabled: bool = True) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit="VA",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=MEASUREMENT,
        entity_registry_enabled_default=enabled,
    )


def _var(key: str, address: int, name: str, enabled: bool = True) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit="var",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=MEASUREMENT,
        entity_registry_enabled_default=enabled,
    )


def _pf(key: str, address: int, name: str, enabled: bool = True) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit=None,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=MEASUREMENT,
        entity_registry_enabled_default=enabled,
    )


def _deg(key: str, address: int, name: str) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit="°",
        state_class=MEASUREMENT,
        icon="mdi:angle-acute",
        entity_registry_enabled_default=False,
    )


def _hz(key: str, address: int, name: str) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=MEASUREMENT,
    )


def _kwh(key: str, address: int, name: str, resettable: bool = False, enabled: bool = True) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=TOTAL if resettable else TOTAL_INCREASING,
        entity_registry_enabled_default=enabled,
    )


def _kvarh(key: str, address: int, name: str, resettable: bool = False, enabled: bool = True) -> RegisterDefinition:
    return RegisterDefinition(
        key, address, name,
        unit="kvarh",
        state_class=TOTAL if resettable else TOTAL_INCREASING,
        icon="mdi:lightning-bolt",
        entity_registry_enabled_default=enabled,
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

REGISTER_MAP: dict[str, list[RegisterDefinition]] = {
    MODEL_SDM230: SDM230_REGISTERS,
    MODEL_SDM630: SDM630_REGISTERS,
    MODEL_SDM120: SDM120_REGISTERS,
    MODEL_SDM72V2: SDM72V2_REGISTERS,
}


def decode_float32(registers: list[int], offset: int) -> float:
    """Decode a big-endian (hi-register-first) IEEE754 float from a
    list of 16-bit register values, starting at ``offset``."""
    hi, lo = registers[offset], registers[offset + 1]
    raw = (hi << 16) | lo
    return struct.unpack(">f", raw.to_bytes(4, "big"))[0]


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
