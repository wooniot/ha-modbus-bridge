"""Sensor platform for the Eastron SDM Energy Meters integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURERS, SUBENTRY_TYPE_METER
from .coordinator import EastronCoordinator
from .registers import RegisterDefinition


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_METER:
            continue
        coordinator = entry.runtime_data.coordinators[subentry.subentry_id]
        async_add_entities(
            (
                EastronSdmSensor(coordinator, register, subentry)
                for register in coordinator.registers
            ),
            config_subentry_id=subentry.subentry_id,
        )


class EastronSdmSensor(CoordinatorEntity[EastronCoordinator], SensorEntity):
    """One decoded register of one Eastron meter."""

    _attr_has_entity_name = True
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        coordinator: EastronCoordinator,
        register: RegisterDefinition,
        subentry: ConfigSubentry,
    ) -> None:
        super().__init__(coordinator)
        self._register = register

        self._attr_unique_id = f"{subentry.subentry_id}_{register.key}"
        self._attr_name = register.name
        self._attr_native_unit_of_measurement = register.unit
        self._attr_device_class = register.device_class
        self._attr_state_class = register.state_class
        self._attr_icon = register.icon
        self._attr_entity_registry_enabled_default = register.entity_registry_enabled_default

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer=MANUFACTURERS.get(coordinator.model, "Eastron"),
            model=coordinator.model.upper(),
        )

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._register.key)
