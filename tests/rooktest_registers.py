"""Rooktest zonder Home Assistant: laadt de pure modules en toetst de kern.

- registers.py: alle modellen hebben een kaart, blokken worden netjes gebouwd
- decode_register: een bekende IEEE754-waarde en een te korte lezing
- const: holding-register-modellen bestaan ook echt in de modellijst
"""
import importlib.util, pathlib, struct, sys, types


# --- nagebootste Home Assistant-onderdelen die registers.py nodig heeft ---
import enum
def _nep_enum(naam, waarden):
    return enum.Enum(naam, {w: w.lower() for w in waarden})

ha = types.ModuleType("homeassistant")
comp = types.ModuleType("homeassistant.components")
sensor = types.ModuleType("homeassistant.components.sensor")
class _Klasse(str):
    def __getattr__(self, naam): return naam.lower()
sensor.SensorDeviceClass = type("SensorDeviceClass", (), {k: k.lower() for k in
    ["VOLTAGE","CURRENT","POWER","APPARENT_POWER","REACTIVE_POWER","POWER_FACTOR",
     "FREQUENCY","ENERGY","REACTIVE_ENERGY","APPARENT_ENERGY","TEMPERATURE"]})
sensor.SensorStateClass = type("SensorStateClass", (), {k: k.lower() for k in
    ["MEASUREMENT","TOTAL","TOTAL_INCREASING"]})
const_mod = types.ModuleType("homeassistant.const")
for naam in ["UnitOfElectricPotential","UnitOfElectricCurrent","UnitOfPower",
             "UnitOfApparentPower","UnitOfReactivePower","UnitOfEnergy",
             "UnitOfFrequency","PERCENTAGE","DEGREE","UnitOfTime",
             "UnitOfReactiveEnergy","UnitOfApparentEnergy"]:
    setattr(const_mod, naam, type(naam, (), {k: k for k in
        ["VOLT","AMPERE","WATT","KILO_WATT","VOLT_AMPERE","VOLT_AMPERE_REACTIVE",
         "KILO_WATT_HOUR","WATT_HOUR","HERTZ","KILO_VOLT_AMPERE_REACTIVE_HOUR",
         "KILO_VOLT_AMPERE_HOUR","SECONDS","MINUTES","HOURS"]}))
const_mod.PERCENTAGE = "%"
const_mod.DEGREE = "deg"
ha.components = comp; comp.sensor = sensor
sys.modules["homeassistant"] = ha
sys.modules["homeassistant.components"] = comp
sys.modules["homeassistant.components.sensor"] = sensor
sys.modules["homeassistant.const"] = const_mod

BASIS = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "eastron_sdm"

# const.py en registers.py importeren geen homeassistant -> direct laadbaar
def laad(naam):
    spec = importlib.util.spec_from_file_location(naam, BASIS / f"{naam}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[naam] = mod
    spec.loader.exec_module(mod)
    return mod

const = laad("const")
sys.modules["custom_components"] = types.ModuleType("custom_components")
registers = None
try:
    registers = laad("registers")
except ImportError as e:
    # registers.py doet 'from .const import ...' -> pakket-context nabootsen
    pakket = types.ModuleType("eastron_pkg"); pakket.__path__ = [str(BASIS)]
    sys.modules["eastron_pkg"] = pakket
    spec = importlib.util.spec_from_file_location("eastron_pkg.registers", BASIS / "registers.py")
    registers = importlib.util.module_from_spec(spec)
    sys.modules["eastron_pkg.const"] = const
    sys.modules["eastron_pkg.registers"] = registers
    spec.loader.exec_module(registers)

fouten = []
modellen = sorted(registers.REGISTER_MAP)
print("modellen met een registerkaart:", len(modellen))
for m in modellen:
    regs = registers.REGISTER_MAP[m]
    blokken = registers.build_read_blocks(regs, const.MAX_REGISTERS_PER_READ, const.MAX_REGISTER_GAP)
    totaal = sum(len(b.registers) for b in blokken)
    print(f"  {m:<28} {len(regs):>3} registers -> {len(blokken):>2} blokken ({totaal} erin)")
    if not regs:
        fouten.append(f"{m} heeft een lege kaart")
    if totaal != len(regs):
        fouten.append(f"{m}: {len(regs)} registers maar {totaal} in blokken")
    for b in blokken:
        if b.quantity > const.MAX_REGISTERS_PER_READ:
            fouten.append(f"{m}: blok van {b.quantity} registers > max {const.MAX_REGISTERS_PER_READ}")

holding = getattr(const, "HOLDING_REGISTER_MODELS", set())
print("holding-register-modellen:", sorted(holding))
for m in holding:
    if m not in registers.REGISTER_MAP:
        fouten.append(f"HOLDING_REGISTER_MODELS noemt '{m}', maar die staat niet in REGISTER_MAP")

# decode van een bekende float (230.5 V) in twee registers
reg = [r for r in registers.REGISTER_MAP[modellen[0]] if r.value_type == "float32"][:1]
if reg:
    r = reg[0]
    rauw = list(struct.unpack(">HH", struct.pack(">f", 230.5)))
    uit = registers.decode_register(rauw, 0, r)
    print("decode float32 230.5 ->", uit)
    if abs(uit - 230.5) > 0.01:
        fouten.append(f"float-decode gaf {uit}")
    try:
        registers.decode_register(rauw[:1], 0, r)
        fouten.append("te korte lezing gaf GEEN fout")
    except Exception as e:
        print("te korte lezing geeft netjes:", type(e).__name__)

print()
print("FOUTEN:" if fouten else "geen fouten", *fouten, sep="\n  " if fouten else "")
sys.exit(1 if fouten else 0)
