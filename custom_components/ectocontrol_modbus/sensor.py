"""Sensor platform for Ectocontrol Modbus Adapter v2."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo, CONNECTION_NETWORK_MAC

from .const import DOMAIN


SENSORS = [
    ("CH Temperature", "get_ch_temperature", "°C"),
    ("DHW Temperature", "get_dhw_temperature", "°C"),
    ("Pressure", "get_pressure", "bar"),
    ("Flow Rate", "get_flow_rate", "L/min"),
    ("Modulation", "get_modulation_level", "%"),
    ("Outdoor Temperature", "get_outdoor_temperature", "°C"),
    ("CH Setpoint Active", "get_ch_setpoint_active", "°C"),
    ("Manufacturer Code", "get_manufacturer_code", ""),
    ("Model Code", "get_model_code", ""),
]


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = []
    for name, getter, unit in SENSORS:
        entities.append(BoilerSensor(coordinator, getter, name, unit))

    async_add_entities(entities)


class BoilerSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, getter_name: str, name: str, unit: str):
        super().__init__(coordinator)
        self._getter = getter_name
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.coordinator.gateway.slave_id}_{self._getter}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for entity association."""
        port = self.coordinator.gateway.protocol.port
        slave_id = self.coordinator.gateway.slave_id
        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, f"{port}:{slave_id}")},
            identifiers={(DOMAIN, f"{port}:{slave_id}")},
        )

    @property
    def native_value(self):
        value = getattr(self.coordinator.gateway, self._getter)()
        return value
