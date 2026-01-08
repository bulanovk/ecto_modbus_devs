"""Binary sensor platform for Ectocontrol Modbus Adapter v2."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from ..const import DOMAIN


BINARY_SENSORS = [
    ("Burner On", "get_burner_on"),
    ("Heating Enabled", "get_heating_enabled"),
    ("DHW Enabled", "get_dhw_enabled"),
]


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = []
    for name, getter in BINARY_SENSORS:
        entities.append(BoilerBinarySensor(coordinator, getter, name))

    async_add_entities(entities)


class BoilerBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, getter_name: str, name: str):
        super().__init__(coordinator)
        self._getter = getter_name
        self._attr_name = name

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.coordinator.gateway.slave_id}_{self._getter}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for entity association."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.gateway.protocol.port}:{self.coordinator.gateway.slave_id}")}
        )

    @property
    def is_on(self) -> bool | None:
        return getattr(self.coordinator.gateway, self._getter)()
